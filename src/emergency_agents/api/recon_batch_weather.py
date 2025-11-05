"""
批次侦察天气评估API

功能：
- 根据灾情场景计算侦察范围
- 查询范围内的优先目标
- 评估设备天气适应性
- 分配批次或生成增援请求

关键流程：
1. 计算灾害侦察半径 → 查询范围内目标（PostGIS）
2. 查询可用侦察设备 → 天气适应性评估（LLM）
3. 如果设备足够 → 批次分配（round-robin）
4. 如果设备不足 → 增援需求分析（LLM + 真实来源）

技术栈：
- FastAPI: RESTful API
- AsyncConnectionPool[DictRow]: PostgreSQL异步查询
- OpenAI: LLM调用（glm-4-flash）
- structlog: 结构化日志
- Pydantic: 强类型请求/响应模型
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Response, Query
from pydantic import BaseModel, Field
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import DictRow, dict_row
from openai import OpenAI
import httpx
import structlog
import uuid
import os
import json

from emergency_agents.config import AppConfig
from emergency_agents.logging import get_trace_id
from emergency_agents.api.recon_priority import GeoPoint
from emergency_agents.db.dao import IncidentSnapshotRepository
from emergency_agents.db.models import IncidentSnapshotCreateInput

# 导入我们刚实现的模块
from emergency_agents.planner.weather_assessor import (
    assess_weather_suitability,
    DeviceInfo,
    WeatherCondition,
    WeatherAssessmentResult,
)
from emergency_agents.planner.batch_allocator import (
    allocate_batches,
    validate_targets_sorted,
    Target,
    Device,
    Batch,
)
from emergency_agents.planner.reinforcement_analyzer import (
    analyze_reinforcement_need,
    DisasterScenario,
    ReinforcementSource,
    DeviceSummary,
    ReinforcementRequest,
)
from emergency_agents.planner.recon_llm_planner import (
    generate_recon_plan_with_llm,
    DeviceInput,
    TargetPoint,
    DisasterInfo as TaskDisasterInfo,
    DetailedReconPlan,
)

# 导入新的规则引擎和分组生成器
from emergency_agents.planner.device_target_matcher import (
    smart_allocate,
    group_allocation_by_env_type,
)
from emergency_agents.planner.grouped_markdown_generator import GroupedMarkdownGenerator

# 导入Markdown结构化提取工具
from emergency_agents.utils.md_extractor import ReconPlanExtractor, TaskExtract

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ai/recon", tags=["ai-recon"])

# 由 main.py 在应用启动时注入（同 recon_priority 的做法）
_pg_pool_async: Optional[AsyncConnectionPool[DictRow]] = None


# ============ 灾害侦察半径配置（公里） ============

HAZARD_RECON_RADIUS: Dict[str, float] = {
    "flood": 30.0,  # 洪水：30km
    "landslide": 10.0,  # 山体滑坡：10km
    "chemical_leak": 5.0,  # 化工泄露：5km
    "earthquake": 50.0,  # 地震：50km
}


# ============ 请求/响应模型（强类型） ============


class WeatherInput(BaseModel):
    """天气条件输入（可选，前端可传入实时天气数据）

    所有字段都有默认值，代表正常天气条件：
    - phenomena: [] (无特殊天气现象，晴天或多云)
    - wind_speed_mps: 3.0 (微风，2级风)
    - visibility_km: 10.0 (能见度良好)
    - precip_mm_h: 0.0 (无降水)
    """

    phenomena: List[str] = Field(
        default=[],
        description="天气现象列表，如 ['heavy_rain', 'strong_wind']。默认[]表示晴天"
    )
    wind_speed_mps: float = Field(
        default=3.0,
        ge=0,
        description="风速（米/秒）。默认3.0表示微风（2级风）"
    )
    visibility_km: float = Field(
        default=10.0,
        ge=0,
        description="能见度（公里）。默认10.0表示能见度良好"
    )
    precip_mm_h: float = Field(
        default=0.0,
        ge=0,
        description="降水量（毫米/小时）。默认0.0表示无降水"
    )


class BatchWeatherPlanRequest(BaseModel):
    """批次天气计划请求"""

    disaster_type: str = Field(..., description="灾害类型（flood/landslide/earthquake/chemical_leak）")
    epicenter: GeoPoint = Field(..., description="灾害中心点坐标")
    severity: str = Field(..., description="严重程度（critical/high/medium/low）")

    # 方式1：前端传入实时天气数据（推荐）
    weather: Optional[WeatherInput] = Field(
        None,
        description="实时天气条件（前端传入）。如果不传，则使用 weather_scenario 兜底"
    )

    # 方式2：使用预设天气场景（向后兼容，废弃中）
    weather_scenario: Optional[str] = Field(
        default="clear",
        description="天气场景（已废弃，请使用 weather 字段）。支持：heavy_rain/clear。默认clear（晴天）"
    )


class BatchWeatherPlanResponse(BaseModel):
    """批次天气计划响应（JSON格式 - 保留用于向后兼容）"""

    success: bool = Field(..., description="是否成功生成计划")
    batches: Optional[List[Batch]] = Field(None, description="批次列表（设备足够时）")
    detailed_plan: Optional[DetailedReconPlan] = Field(None, description="详细侦察方案（设备足够时生成）")
    reinforcement_request: Optional[ReinforcementRequest] = Field(None, description="增援请求（设备不足时）")
    total_targets: int = Field(..., description="总目标数")
    suitable_devices_count: int = Field(..., description="通过天气评估的设备数")
    estimated_total_hours: Optional[float] = Field(None, description="预计总完成时间（小时）")


class BatchWeatherPlanMarkdownResponse(BaseModel):
    """批次天气计划响应（Markdown格式 - 用于人类审阅）"""

    markdown: str = Field(..., description="人类可读的Markdown格式报告")
    raw_json: Dict[str, Any] = Field(..., description="原始JSON数据（审核通过后用于保存到数据库）")
    summary: Dict[str, Any] = Field(..., description="方案摘要统计")


# ============ API端点 ============


@router.post("/batch-weather-plan")
async def create_batch_weather_plan(
    format: str = Query("json", description="返回格式：json(默认，纯文本)|md(Markdown格式)")
) -> Response:
    """
    生成侦察方案（支持JSON纯文本或Markdown格式）

    ⚠️ 演示接口：参数已写死为四川茂县7.5级地震场景
    - 灾害类型：earthquake（地震）
    - 严重等级：critical（最高级）
    - 震中坐标：四川省阿坝藏族羌族自治州茂县 (103.85°E, 31.68°N)

    **参数说明：**
    - format: 返回格式选择
      - "json" (默认): 返回纯文本格式（已移除Markdown格式符号）
      - "md": 返回原始Markdown格式（供结构化提取使用）

    工作流程：
    1. 计算灾害侦察半径（基于disaster_type）
    2. 查询范围内的优先目标（PostGIS距离查询）
    3. 查询可用侦察设备（is_recon=TRUE, in_task_use=0）
    4. 调用LLM评估设备天气适应性
    5. 调用round-robin算法分配批次
    6. 调用LLM生成人类可读的Markdown报告

    返回：纯Markdown文本（text/markdown）

    使用说明：
    1. 前端调用此接口获得Markdown文档
    2. 展示给人类审阅，可能需要修改内容
    3. 修改完成后调用 /ai/recon/markdown-to-json 接口转换为JSON
    4. 最后调用 /ai/recon/save-plan 保存到数据库

    每个步骤都有详细日志记录，支持完整的决策追踪。
    """
    # 获取或生成 trace_id（用于日志追踪）
    trace_id = get_trace_id() or str(uuid.uuid4())

    # 写死参数：四川茂县7.5级地震场景
    req = BatchWeatherPlanRequest(
        disaster_type="earthquake",
        epicenter=GeoPoint(lon=103.85, lat=31.68),  # 四川省茂县坐标
        severity="critical",  # 最高等级
        weather=None,  # 使用默认天气
        weather_scenario="normal"  # 正常天气场景
    )

    if _pg_pool_async is None:
        raise HTTPException(
            status_code=503,
            detail="数据库连接池未初始化，请检查服务启动配置",
        )

    logger.info(
        "收到批次天气计划请求",
        disaster_type=req.disaster_type,
        epicenter=req.epicenter.model_dump(),
        severity=req.severity,
        has_custom_weather=req.weather is not None,
        weather_scenario_fallback=req.weather_scenario,
        trace_id=trace_id,
    )

    # Step 1: 计算侦察半径
    radius_km = HAZARD_RECON_RADIUS.get(req.disaster_type)
    if radius_km is None:
        raise HTTPException(
            status_code=400,
            detail=f"未知的灾害类型: {req.disaster_type}。支持的类型: {list(HAZARD_RECON_RADIUS.keys())}",
        )

    radius_meters = radius_km * 1000.0
    logger.info("计算侦察半径", disaster_type=req.disaster_type, radius_km=radius_km, trace_id=trace_id)

    # Step 2: 查询范围内的优先目标（PostGIS）
    targets = await _fetch_targets_in_radius(_pg_pool_async, req.epicenter.lon, req.epicenter.lat, radius_meters)
    if not targets:
        logger.warning("范围内无侦察目标", radius_km=radius_km, trace_id=trace_id)
        raise HTTPException(
            status_code=404,
            detail=f"在{radius_km}km范围内未找到侦察目标",
        )

    logger.info("查询到侦察目标", count=len(targets), trace_id=trace_id)

    # Step 3: 查询可用侦察设备
    devices = await _fetch_available_recon_devices(_pg_pool_async)
    if not devices:
        logger.warning("无可用侦察设备", trace_id=trace_id)
        raise HTTPException(
            status_code=503,
            detail="当前无可用侦察设备（所有设备均被占用或无侦察能力设备）",
        )

    logger.info("查询到可用设备", count=len(devices), trace_id=trace_id)

    # Step 4: 获取天气条件（优先使用前端传入的数据）
    if req.weather is not None:
        # 方式1：前端传入实时天气数据（推荐）
        weather = WeatherCondition(
            phenomena=req.weather.phenomena,
            wind_speed_mps=req.weather.wind_speed_mps,
            visibility_km=req.weather.visibility_km,
            precip_mm_h=req.weather.precip_mm_h,
        )
        logger.info(
            "使用前端传入的天气数据",
            phenomena=weather["phenomena"],
            wind_speed_mps=weather["wind_speed_mps"],
            visibility_km=weather["visibility_km"],
            precip_mm_h=weather["precip_mm_h"],
            trace_id=trace_id,
        )
    else:
        # 方式2：使用预设天气场景兜底（默认晴天）
        scenario = req.weather_scenario or "clear"
        weather = _get_weather_condition(scenario)
        logger.info(
            "前端未传入天气数据，使用默认晴天场景",
            scenario=scenario,
            phenomena=weather["phenomena"],
            wind_speed_mps=weather["wind_speed_mps"],
            visibility_km=weather["visibility_km"],
            trace_id=trace_id,
        )

    # Step 5: 调用LLM评估设备天气适应性（永不抛出异常，确保指挥员能看到结果）
    cfg = AppConfig.load_from_env()

    device_infos: List[DeviceInfo] = [
        DeviceInfo(
            id=d["id"],
            name=d["name"],
            device_type=d["device_type"],
            weather_capability=d.get("weather_capability") or "未提供天气能力描述",
        )
        for d in devices
    ]

    # ============ 天气评估（已注释）============
    # 用户需求：跳过天气评估，所有设备直接可用
    # try:
    #     llm_client = _get_llm_client(cfg)
    #     weather_result: WeatherAssessmentResult = assess_weather_suitability(
    #         devices=device_infos, weather=weather, llm_client=llm_client, llm_model="glm-4.6", trace_id=trace_id
    #     )
    # except Exception as e:
    #     logger.error("天气评估出现意外异常", error=str(e), trace_id=trace_id)
    #     weather_result = WeatherAssessmentResult(
    #         suitable_device_ids=[d["id"] for d in devices],
    #         unsuitable_devices=[],
    #         reasoning=f"⚠️ AI天气评估服务异常（{type(e).__name__}）",
    #     )
    # suitable_device_ids = set(weather_result["suitable_device_ids"])
    # suitable_devices = [d for d in devices if d["id"] in suitable_device_ids]

    # 直接使用所有设备（跳过天气评估）
    suitable_devices = devices
    llm_client = _get_llm_client(cfg)

    logger.info(
        "跳过天气评估，所有设备直接可用",
        device_count=len(suitable_devices),
        trace_id=trace_id,
    )

    # Step 6: 直接生成侦察方案（跳过增援判断）
    # 原逻辑：if len(suitable_devices) >= len(targets) - 现已移除增援分支
    if True:  # 始终执行LLM方案生成
        # 设备足够：分配批次 + 生成详细侦察方案
        logger.info("设备足够，开始批次分配和详细方案生成")

        target_list: List[Target] = [
            Target(id=t["id"], name=t["name"], priority_score=float(t["priority"]), lon=t["lon"], lat=t["lat"])
            for t in targets
        ]

        device_list: List[Device] = [
            Device(id=d["id"], name=d["name"], device_type=d["device_type"]) for d in suitable_devices
        ]

        # 验证目标已排序
        validate_targets_sorted(target_list)

        # 分配批次（简单的round-robin）
        allocation = allocate_batches(targets=target_list, devices=device_list, avg_time_per_target_minutes=15)

        total_hours = sum(b["estimated_completion_minutes"] for b in allocation["batches"]) / 60.0

        # 生成详细侦察方案（LLM智能生成）
        logger.info("开始生成详细侦察方案（使用LLM）", trace_id=trace_id)

        # 转换设备为DeviceInput格式
        device_inputs: List[DeviceInput] = [
            DeviceInput(
                id=str(d["id"]),  # 确保ID是字符串
                name=d["name"],
                device_type=d["device_type"],
                env_type=d["env_type"],
                capabilities=d.get("capabilities", [])
            )
            for d in suitable_devices
        ]

        # 转换目标为TargetPoint格式
        target_points: List[TargetPoint] = [
            TargetPoint(
                id=t["id"],
                name=t["name"],
                target_type=t.get("target_type", "未知"),
                hazard_level=t.get("hazard_level", "medium"),
                priority=float(t["priority"]),
                lon=t["lon"],
                lat=t["lat"]
            )
            for t in targets
        ]

        # 构造灾情信息（包含epicenter字段）
        disaster_info = TaskDisasterInfo(
            disaster_type=req.disaster_type,
            severity=req.severity,
            epicenter={"lon": req.epicenter.lon, "lat": req.epicenter.lat},
            location_desc=f"({req.epicenter.lon}, {req.epicenter.lat})"
        )

        # 使用规则引擎进行智能设备-目标分配（替代LLM调用）
        logger.info("开始规则引擎智能分配",
                   device_count=len(device_inputs),
                   target_count=len(target_points),
                   trace_id=trace_id)

        # 转换设备和目标为规则引擎所需格式（Dict）
        devices_dict = [
            {
                "id": d["id"],
                "name": d["name"],
                "device_type": d["device_type"],
                "env_type": d["env_type"],
                "capabilities": d["capabilities"],
                "lon": req.epicenter.lon,  # 默认使用指挥中心位置
                "lat": req.epicenter.lat,
            }
            for d in device_inputs
        ]

        targets_dict = [
            {
                "id": t["id"],
                "name": t["name"],
                "target_type": t["target_type"],
                "hazard_level": t["hazard_level"],
                "priority": t["priority"],
                "lon": t["lon"],
                "lat": t["lat"],
            }
            for t in target_points
        ]

        # 调用规则引擎进行智能分配
        allocation_result = smart_allocate(
            devices=devices_dict,
            targets=targets_dict,
            disaster_type=req.disaster_type,
            command_center={"lon": req.epicenter.lon, "lat": req.epicenter.lat},
            trace_id=trace_id
        )

        logger.info("规则引擎分配完成",
                   allocated_devices=len(allocation_result),
                   trace_id=trace_id)

        # 使用分组Markdown生成器并行生成报告（替代LLM顺序调用）
        logger.info("开始分组并行生成Markdown报告",
                   device_count=len(devices_dict),
                   target_count=len(targets_dict),
                   trace_id=trace_id)

        # 创建分组Markdown生成器
        markdown_generator = GroupedMarkdownGenerator(llm_client, "glm-4.6")

        # 调用并行生成（内部会自动分组为air/land/sea，并行调用LLM）
        markdown_text = markdown_generator.generate(
            allocation=allocation_result,
            devices=devices_dict,
            targets=targets_dict,
            disaster_info=disaster_info,
            command_center={"lon": req.epicenter.lon, "lat": req.epicenter.lat},
            trace_id=trace_id
        )

        logger.info("分组Markdown报告生成完成",
                   total_length=len(markdown_text),
                   trace_id=trace_id)

        # 生成方案ID
        plan_id = str(uuid.uuid4())

        # 如果请求Markdown格式，直接返回
        if format == "md":
            logger.info("返回Markdown格式数据", plan_id=plan_id, trace_id=trace_id)
            # 保存到数据库（使用Markdown原文）
            try:
                async with _pg_pool_async.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            """
                            INSERT INTO recon_plans (
                                plan_id, incident_id, plan_type, plan_subtype,
                                plan_title, plan_content, plan_data,
                                disaster_type, disaster_location, severity,
                                device_count, target_count,
                                llm_model, status, created_by
                            ) VALUES (
                                %s, %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s,
                                %s, %s, %s
                            )
                            """,
                            (
                                plan_id,
                                None,
                                "recon",
                                "batch_weather",
                                f"{req.disaster_type}侦察方案(MD)",
                                markdown_text,
                                json.dumps({"format": "markdown"}, ensure_ascii=False),
                                req.disaster_type,
                                json.dumps({"lon": req.epicenter.lon, "lat": req.epicenter.lat}),
                                req.severity,
                                len(devices_dict),
                                len(targets_dict),
                                os.getenv("RECON_LLM_MODEL", "glm-4.6"),
                                "draft",
                                "system"
                            )
                        )
                        await conn.commit()
                logger.info("Markdown方案已保存到数据库", plan_id=plan_id, trace_id=trace_id)
            except Exception as e:
                logger.warning("数据库保存失败（不影响业务）", error=str(e), trace_id=trace_id)

            return {
                "code": 200,
                "data": markdown_text,
                "plan_id": plan_id
            }

        # 否则转换Markdown为纯文本（移除格式符号）
        import re
        plain_text = markdown_text

        # 移除标题符号 (##, ###)
        plain_text = re.sub(r'^#{1,6}\s+', '', plain_text, flags=re.MULTILINE)

        # 移除加粗符号 (**)
        plain_text = re.sub(r'\*\*(.*?)\*\*', r'\1', plain_text)

        # 移除斜体符号 (*)
        plain_text = re.sub(r'\*(.*?)\*', r'\1', plain_text)

        # 移除代码块标记 (```)
        plain_text = re.sub(r'```.*?\n', '', plain_text)
        plain_text = re.sub(r'```', '', plain_text)

        # 移除行内代码标记 (`)
        plain_text = re.sub(r'`(.*?)`', r'\1', plain_text)

        # 移除链接格式 [text](url) -> text
        plain_text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', plain_text)

        logger.info("Markdown转纯文本完成",
                   original_length=len(markdown_text),
                   plain_length=len(plain_text),
                   trace_id=trace_id)

        # 准备完整响应数据（plan_id已在前面生成）
        response_data = {
            "plan_id": plan_id,
            "plan_content": plain_text,
            "plan_type": "recon",
            "plan_subtype": "batch_weather",
            "disaster_type": req.disaster_type,
            "epicenter": {"lon": req.epicenter.lon, "lat": req.epicenter.lat},
            "severity": req.severity,
            "device_count": len(devices_dict),
            "target_count": len(targets_dict),
            "llm_model": os.getenv("RECON_LLM_MODEL", "glm-4.6"),
            "generated_at": datetime.utcnow().isoformat(),
            "trace_id": trace_id
        }

        # 保存到PostgreSQL数据库（失败不阻塞）
        try:
            async with _pg_pool_async.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO recon_plans (
                            plan_id, incident_id, plan_type, plan_subtype,
                            plan_title, plan_content, plan_data,
                            disaster_type, disaster_location, severity,
                            device_count, target_count,
                            llm_model, status, created_by
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s
                        )
                        """,
                        (
                            plan_id,
                            None,  # incident_id（可选，后续关联）
                            "recon",
                            "batch_weather",
                            f"{req.disaster_type}侦察方案",
                            plain_text,
                            json.dumps(response_data, ensure_ascii=False),
                            req.disaster_type,
                            json.dumps({"lon": req.epicenter.lon, "lat": req.epicenter.lat}),
                            req.severity,
                            len(devices_dict),
                            len(targets_dict),
                            os.getenv("RECON_LLM_MODEL", "glm-4.6"),
                            "draft",
                            "system"
                        )
                    )
                    await conn.commit()

            logger.info("侦察方案已保存到数据库",
                       plan_id=plan_id,
                       trace_id=trace_id)

        except Exception as e:
            logger.warning("数据库保存失败（不影响业务）",
                          error=str(e),
                          trace_id=trace_id)

        # 返回标准JSON格式
        return {
            "code": 200,
            "data": plain_text,
            "plan_id": plan_id
        }

    # ============ 增援分析（已注释）============
    # 用户需求：跳过增援分析，即使设备不足也直接用现有设备生成方案
    # else:
    #     # 设备不足：生成增援请求
    #     logger.info("设备不足，开始增援需求分析", suitable=len(suitable_devices), required=len(targets), trace_id=trace_id)
    #     reinforcement_sources = await _fetch_reinforcement_sources(_pg_pool_async)
    #     if not reinforcement_sources:
    #         raise HTTPException(status_code=503, detail="当前无可用侦察设备，且数据库中无增援来源配置")
    #     device_summaries: List[DeviceSummary] = [...]
    #     disaster_scenario = DisasterScenario(...)
    #     reinforcement_req = analyze_reinforcement_need(...)
    #     return BatchWeatherPlanResponse(reinforcement_request=reinforcement_req)


# ============ 数据库查询函数 ============


async def _fetch_targets_in_radius(
    pool: AsyncConnectionPool[DictRow], lon: float, lat: float, radius_meters: float
) -> List[Dict[str, Any]]:
    """
    查询范围内的侦察优先目标（PostGIS距离查询）

    返回按priority降序排序的目标列表
    """
    sql = (
        "SELECT id, name, target_type, hazard_level, priority, "
        "ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat "
        "FROM operational.recon_priority_targets "
        "WHERE ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s) "
        "ORDER BY priority DESC"
    )

    logger.debug("PostGIS查询SQL", sql=sql, params=(lon, lat, radius_meters))
    print(f"DEBUG: SQL before execute: {repr(sql)}")  # 临时调试
    print(f"DEBUG: Params: {(lon, lat, radius_meters)}")  # 临时调试

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (lon, lat, radius_meters))
            rows = await cur.fetchall()

    logger.debug("PostGIS查询完成", row_count=len(rows), radius_meters=radius_meters)
    return [dict(row) for row in rows]


async def _fetch_available_recon_devices(pool: AsyncConnectionPool[DictRow]) -> List[Dict[str, Any]]:
    """
    查询可用的侦察设备（is_recon=TRUE, in_task_use=0）及其能力列表

    返回结构：
    {
        "id": int/str,
        "name": str,
        "device_type": str,
        "env_type": str,
        "weather_capability": str,
        "capabilities": List[str]  # 设备能力列表（从device_capability表聚合）
    }
    """
    sql = """
    SELECT
        d.id,
        d.name,
        d.device_type,
        d.env_type,
        d.weather_capability,
        COALESCE(
            array_agg(dc.capability) FILTER (WHERE dc.capability IS NOT NULL),
            ARRAY[]::varchar[]
        ) as capabilities
    FROM operational.device d
    LEFT JOIN operational.device_capability dc ON d.id = dc.device_id
    WHERE d.is_recon IS TRUE
      AND COALESCE(d.in_task_use, 0) = 0
      AND d.deleted_at IS NULL
    GROUP BY d.id, d.name, d.device_type, d.env_type, d.weather_capability
    ORDER BY d.id
    """

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql)
            rows = await cur.fetchall()

    logger.debug("查询可用侦察设备（含能力）", row_count=len(rows))

    result = []
    for row in rows:
        device = dict(row)

        # 如果env_type为空，从device_type推断
        if not device.get("env_type"):
            device_type = device.get("device_type", "").lower()
            if "drone" in device_type:
                device["env_type"] = "air"
            elif "dog" in device_type:
                device["env_type"] = "land"
            elif "ship" in device_type:
                device["env_type"] = "sea"
            else:
                device["env_type"] = "unknown"

            if device["env_type"] != "unknown":
                logger.debug(
                    "从device_type推断env_type",
                    device_id=device["id"],
                    device_type=device["device_type"],
                    inferred_env_type=device["env_type"]
                )

        # 确保capabilities是列表
        if not isinstance(device.get("capabilities"), list):
            device["capabilities"] = []

        # 如果id是字符串且看起来像数字ID，尝试转换
        if isinstance(device["id"], str):
            # 保持原始字符串ID，不做转换（避免数据丢失）
            pass

        result.append(device)

    return result


async def _fetch_reinforcement_sources(pool: AsyncConnectionPool[DictRow]) -> List[ReinforcementSource]:
    """查询真实的增援来源（operational.reinforcement_sources表）"""
    sql = """
    SELECT
        id, name, available_devices, response_time_hours, location
    FROM operational.reinforcement_sources
    WHERE available_devices IS NOT NULL
    ORDER BY response_time_hours ASC
    """

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql)
            rows = await cur.fetchall()

    logger.debug("查询增援来源", row_count=len(rows))
    return [
        ReinforcementSource(
            id=row["id"],
            name=row["name"],
            available_devices=row["available_devices"],
            response_time_hours=float(row["response_time_hours"]),
            location=row["location"],
        )
        for row in rows
    ]


# ============ 辅助函数 ============


def _get_weather_condition(scenario: str) -> WeatherCondition:
    """
    获取预设天气条件（硬编码，后续从数据库读取）

    默认场景：晴天（clear）
    """
    scenarios = {
        "heavy_rain": WeatherCondition(
            phenomena=["heavy_rain", "strong_wind"],
            wind_speed_mps=15.0,
            visibility_km=2.0,
            precip_mm_h=6.0,
        ),
        "clear": WeatherCondition(
            phenomena=[],  # 晴天无特殊天气现象
            wind_speed_mps=3.0,  # 微风（2级）
            visibility_km=10.0,  # 能见度良好
            precip_mm_h=0.0,  # 无降水
        ),
    }

    if scenario not in scenarios:
        logger.warning("未知天气场景，使用默认晴天", scenario=scenario, default="clear")
        return scenarios["clear"]

    return scenarios[scenario]


def _get_llm_client(cfg: AppConfig) -> OpenAI:
    """获取LLM客户端（glm-4.6）- 同步版本"""
    if not cfg.recon_llm_base_url or not cfg.recon_llm_api_key:
        raise HTTPException(
            status_code=503,
            detail="RECON_LLM_BASE_URL或RECON_LLM_API_KEY未配置，无法调用glm-4.6",
        )

    # 使用同步的 httpx.Client（而非 AsyncClient）
    http_client = httpx.Client(
        timeout=httpx.Timeout(cfg.llm_request_timeout_seconds),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )

    return OpenAI(
        base_url=cfg.recon_llm_base_url,
        api_key=cfg.recon_llm_api_key,
        http_client=http_client,
        timeout=cfg.llm_request_timeout_seconds,
    )


# ============ 侦察方案保存API ============


class SaveReconPlanRequest(BaseModel):
    """保存侦察方案请求"""

    incident_id: str = Field(..., description="事件ID（UUID格式）")
    plan_data: Dict[str, Any] = Field(..., description="侦察方案完整数据（BatchWeatherPlanResponse的JSON）")
    created_by: Optional[str] = Field(None, description="创建者（用户ID或用户名）")


class SaveReconPlanResponse(BaseModel):
    """保存侦察方案响应"""

    success: bool = Field(..., description="是否保存成功")
    snapshot_id: str = Field(..., description="快照ID")
    incident_id: str = Field(..., description="事件ID")
    message: str = Field(..., description="保存结果描述")


@router.post("/save-plan", response_model=SaveReconPlanResponse)
async def save_recon_plan(
    req: SaveReconPlanRequest,
) -> SaveReconPlanResponse:
    """
    保存侦察方案到 incident_snapshots 草稿表

    功能：
    1. 将 /ai/recon/batch-weather-plan 返回的侦察方案数据保存到数据库
    2. 存储为类型 "reconnaissance_plan" 的快照
    3. 关联到指定的 incident_id（事件ID）
    4. 支持后续查询、修改、审批流程

    使用场景：
    - 前端生成侦察方案后，需要保存为草稿
    - 方案需要经过人工审核后才执行
    - 需要追踪方案的历史版本

    数据存储：
    - 表: operational.incident_snapshots
    - snapshot_type: "reconnaissance_plan"
    - payload: 完整的侦察方案JSON（包含batches、detailed_plan等）
    """
    trace_id = get_trace_id() or str(uuid.uuid4())

    if _pg_pool_async is None:
        raise HTTPException(
            status_code=503,
            detail="数据库连接池未初始化，请检查服务启动配置",
        )

    logger.info(
        "收到保存侦察方案请求",
        incident_id=req.incident_id,
        has_batches="batches" in req.plan_data,
        has_detailed_plan="detailed_plan" in req.plan_data,
        created_by=req.created_by,
        trace_id=trace_id,
    )

    # 验证 incident_id 格式
    try:
        uuid.UUID(req.incident_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的incident_id格式: {req.incident_id}，必须是UUID格式",
        )

    # 验证 plan_data 必填字段
    if "success" not in req.plan_data:
        raise HTTPException(
            status_code=400,
            detail="plan_data缺少必填字段: success",
        )

    # 创建快照仓库
    snapshot_repo = IncidentSnapshotRepository.create(_pg_pool_async)

    # 构造快照输入
    snapshot_input = IncidentSnapshotCreateInput(
        incident_id=req.incident_id,
        snapshot_type="reconnaissance_plan",  # 侦察方案快照类型
        payload=req.plan_data,  # 完整的侦察方案数据
        generated_at=datetime.now(),  # 方案生成时间
        created_by=req.created_by,  # 创建者（可选）
    )

    try:
        # 保存到数据库
        snapshot_record = await snapshot_repo.create_snapshot(snapshot_input)

        logger.info(
            "侦察方案保存成功",
            snapshot_id=snapshot_record.snapshot_id,
            incident_id=snapshot_record.incident_id,
            snapshot_type=snapshot_record.snapshot_type,
            trace_id=trace_id,
        )

        return SaveReconPlanResponse(
            success=True,
            snapshot_id=snapshot_record.snapshot_id,
            incident_id=snapshot_record.incident_id,
            message="侦察方案已成功保存到草稿表",
        )

    except Exception as e:
        logger.error(
            "保存侦察方案失败",
            error=str(e),
            incident_id=req.incident_id,
            trace_id=trace_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"保存侦察方案失败: {str(e)}",
        )


@router.get("/list-plans/{incident_id}", response_model=List[Dict[str, Any]])
async def list_recon_plans(
    incident_id: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    查询指定事件的所有侦察方案快照

    功能：
    - 获取某个事件的所有已保存的侦察方案（按时间倒序）
    - 支持查看历史方案版本
    - 用于方案对比、审核、回溯

    返回：
    - 快照列表，每个快照包含完整的方案数据
    """
    trace_id = get_trace_id() or str(uuid.uuid4())

    if _pg_pool_async is None:
        raise HTTPException(
            status_code=503,
            detail="数据库连接池未初始化",
        )

    # 验证 incident_id 格式
    try:
        uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的incident_id格式: {incident_id}",
        )

    logger.info(
        "查询侦察方案列表",
        incident_id=incident_id,
        limit=limit,
        trace_id=trace_id,
    )

    # 创建快照仓库
    snapshot_repo = IncidentSnapshotRepository.create(_pg_pool_async)

    try:
        # 查询快照列表
        snapshots = await snapshot_repo.list_snapshots(
            incident_id=incident_id,
            snapshot_type="reconnaissance_plan",
            limit=limit,
        )

        logger.info(
            "侦察方案列表查询成功",
            incident_id=incident_id,
            count=len(snapshots),
            trace_id=trace_id,
        )

        # 转换为API响应格式
        result = [
            {
                "snapshot_id": s.snapshot_id,
                "incident_id": s.incident_id,
                "snapshot_type": s.snapshot_type,
                "payload": s.payload,  # 完整的方案数据
                "generated_at": s.generated_at.isoformat(),
                "created_by": s.created_by,
                "created_at": s.created_at.isoformat(),
            }
            for s in snapshots
        ]

        return result

    except Exception as e:
        logger.error(
            "查询侦察方案列表失败",
            error=str(e),
            incident_id=incident_id,
            trace_id=trace_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"查询侦察方案失败: {str(e)}",
        )


@router.get("/get-plan/{snapshot_id}", response_model=Dict[str, Any])
async def get_recon_plan(
    snapshot_id: str,
) -> Dict[str, Any]:
    """
    获取单个侦察方案快照详情

    功能：
    - 根据快照ID获取完整的侦察方案数据
    - 用于查看、编辑、审核特定版本的方案
    """
    trace_id = get_trace_id() or str(uuid.uuid4())

    if _pg_pool_async is None:
        raise HTTPException(
            status_code=503,
            detail="数据库连接池未初始化",
        )

    # 验证 snapshot_id 格式
    try:
        uuid.UUID(snapshot_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的snapshot_id格式: {snapshot_id}",
        )

    logger.info(
        "查询侦察方案详情",
        snapshot_id=snapshot_id,
        trace_id=trace_id,
    )

    # 创建快照仓库
    snapshot_repo = IncidentSnapshotRepository.create(_pg_pool_async)

    try:
        # 查询快照
        snapshot = await snapshot_repo.get_snapshot(snapshot_id)

        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail=f"未找到快照: {snapshot_id}",
            )

        logger.info(
            "侦察方案详情查询成功",
            snapshot_id=snapshot.snapshot_id,
            incident_id=snapshot.incident_id,
            trace_id=trace_id,
        )

        # 返回完整快照数据
        return {
            "snapshot_id": snapshot.snapshot_id,
            "incident_id": snapshot.incident_id,
            "snapshot_type": snapshot.snapshot_type,
            "payload": snapshot.payload,  # 完整的方案数据
            "generated_at": snapshot.generated_at.isoformat(),
            "created_by": snapshot.created_by,
            "created_at": snapshot.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "查询侦察方案详情失败",
            error=str(e),
            snapshot_id=snapshot_id,
            trace_id=trace_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"查询侦察方案失败: {str(e)}",
        )


# ============================================================================
# 侦察方案Markdown格式化 - 将结构化JSON转换为人类可读的报告
# ============================================================================


class FormatPlanMarkdownRequest(BaseModel):
    """格式化侦察方案为Markdown请求"""

    plan_data: Dict[str, Any] = Field(
        ..., description="侦察方案完整数据（BatchWeatherPlanResponse的JSON）"
    )
    include_raw_data: bool = Field(
        default=False, description="是否在末尾附加原始JSON数据（用于调试）"
    )


class FormatPlanMarkdownResponse(BaseModel):
    """格式化后的Markdown响应"""

    success: bool = Field(..., description="是否生成成功")
    markdown: str = Field(..., description="格式化后的Markdown文本")
    summary: Dict[str, Any] = Field(..., description="方案摘要统计")


@router.post("/format-plan-markdown", response_model=FormatPlanMarkdownResponse)
async def format_plan_markdown(
    req: FormatPlanMarkdownRequest,
) -> FormatPlanMarkdownResponse:
    """
    将侦察方案JSON数据转换为人类可读的Markdown格式报告

    功能：
    - 智能生成流畅的中文描述
    - 按照空中/地面/水上分类展示任务
    - 合理处理一个设备执行多个任务的情况
    - 生成包含时间线、设备配置、任务详情的完整报告

    使用场景：
    - 前端展示侦察方案详情
    - 生成PDF报告
    - 人工审核方案
    """
    trace_id = get_trace_id() or str(uuid.uuid4())

    # 验证必填字段
    if "detailed_plan" not in req.plan_data:
        raise HTTPException(
            status_code=400, detail="plan_data缺少必填字段: detailed_plan"
        )

    detailed_plan = req.plan_data.get("detailed_plan", {})
    disaster_info = detailed_plan.get("disaster_info", {})
    command_center = detailed_plan.get("command_center", {})

    # 构建LLM的Prompt
    import json
    plan_json = json.dumps(req.plan_data, ensure_ascii=False, indent=2)
    
    prompt = f"""你是一名应急救援指挥专家，需要将结构化的侦察方案数据转换为人类可读的Markdown格式报告。

**侦察方案数据（JSON格式）：**
```json
{plan_json}
```

**报告要求：**

1. **标题和概述**：
   - 灾害类型、等级、地点（从disaster_info提取）
   - 指挥中心位置和到达时间（从command_center提取）
   - 配备的设备和车辆（从batches中的device_name汇总）
   - 整体任务目标（从各section的tasks中提取关键信息）

2. **空中侦察方案**（如果有air_recon_section）：
   - 以指挥中心为出发点
   - 列出所有空中侦察任务（从air_recon_section.tasks中提取）
   - 每个任务包含：
     * 任务名称（task_name或task_type）
     * 设备选择（device_names和key_capabilities）
     * 侦察详情（from_location, to_location, route_waypoints, actions, start_time, end_time）
     * 结果上报（expected_outputs）

3. **地面侦察方案**（如果有ground_recon_section）：
   - 列出所有地面侦察任务
   - 格式同空中侦察

4. **水上侦察方案**（如果有water_recon_section）：
   - 列出所有水上侦察任务
   - 格式同空中侦察

5. **数据整合与通信**：
   - 数据整合说明（从data_integration_desc提取）
   - 任务时间线（earliest_start_time, latest_end_time, total_estimated_hours）
   - 安全措施和优先级

**关键规则：**
- 如果一个设备执行多个任务，每个任务单独成段，使用数字编号（1. 2. 3.）
- 时间格式统一为 HH:MM:SS 或 YYYY-MM-DD HH:MM:SS
- 坐标格式统一为 (经度, 纬度)
- 设备能力要详细描述（从key_capabilities提取）
- 语言流畅自然，符合专业报告风格
- 使用Markdown标题层级：一级标题（灾害名称），二级标题（空中/地面/水上），三级标题（具体任务编号）

**输出格式：**
直接输出Markdown文本，不要包含```markdown标记。

**示例格式参考：**
# 针对四川茂县7.5级地震智能侦察方案

（概述段落）

## 一、空中侦察方案

（空中侦察总体说明）

### 1. 重灾区扫图建模
**设备选择**：扫图建模无人机（具备激光雷达和多光谱传感器）。
**侦察详情**：
从水西村起飞...（详细描述）
**结果上报**：重灾区三维地图...

### 2. 受困人员搜索
...

## 二、地面侦察方案
...

**开始生成报告：**
"""

    try:
        # 获取LLM配置
        cfg = AppConfig.load_from_env()
        client = OpenAI(api_key=cfg.openai_api_key, base_url=cfg.openai_base_url)

        logger.info(
            "开始生成Markdown格式报告",
            disaster_type=disaster_info.get("disaster_type"),
            total_targets=req.plan_data.get("total_targets"),
            trace_id=trace_id,
        )

        # 调用LLM生成Markdown
        response = client.chat.completions.create(
            model="glm-4.6",  # 使用glm-4.6模型
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # 保持一致性，但允许适当的语言变化
            max_tokens=8000,  # GLM-4系列最大输出限制为8192
        )

        markdown_text = response.choices[0].message.content.strip()

        # 如果需要，附加原始JSON数据
        if req.include_raw_data:
            markdown_text += "\n\n---\n\n## 原始数据（调试用）\n\n```json\n"
            markdown_text += plan_json
            markdown_text += "\n```\n"

        # 生成摘要统计
        summary = {
            "disaster_type": disaster_info.get("disaster_type", "未知"),
            "severity": disaster_info.get("severity", "未知"),
            "total_targets": req.plan_data.get("total_targets", 0),
            "suitable_devices": req.plan_data.get("suitable_devices_count", 0),
            "air_tasks": len(
                detailed_plan.get("air_recon_section", {}).get("tasks", [])
            ),
            "ground_tasks": len(
                detailed_plan.get("ground_recon_section", {}).get("tasks", [])
            ),
            "water_tasks": len(
                detailed_plan.get("water_recon_section", {}).get("tasks", [])
            ),
            "earliest_start": detailed_plan.get("earliest_start_time", "未知"),
            "latest_end": detailed_plan.get("latest_end_time", "未知"),
            "total_hours": detailed_plan.get("total_estimated_hours", 0),
        }

        logger.info(
            "Markdown报告生成成功",
            markdown_length=len(markdown_text),
            summary=summary,
            trace_id=trace_id,
        )

        return FormatPlanMarkdownResponse(
            success=True,
            markdown=markdown_text,
            summary=summary,
        )

    except Exception as e:
        logger.error(
            "生成Markdown报告失败",
            error=str(e),
            trace_id=trace_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"生成Markdown报告失败: {str(e)}",
        )


# ============================================================================
# 侦察方案结构化提取API - 将用户修改后的文本转换为结构化JSON
# ============================================================================


class ExtractTasksRequest(BaseModel):
    """提取任务请求"""

    text: str = Field(..., description="侦察方案文本（支持Markdown或纯文本格式）")
    format_hint: Optional[str] = Field(
        default="auto",
        description="格式提示：auto(自动识别)|md(Markdown)|plain(纯文本)，默认auto"
    )


class ExtractTasksResponse(BaseModel):
    """提取任务响应"""

    code: int = Field(default=200, description="响应状态码")
    data: List[Dict[str, Any]] = Field(description="提取的任务列表")
    total_tasks: int = Field(description="任务总数")
    summary: Dict[str, Any] = Field(description="统计摘要（按类型分组）")
    message: str = Field(default="提取成功", description="响应消息")


@router.post("/extract-tasks", response_model=ExtractTasksResponse)
async def extract_recon_tasks(
    req: ExtractTasksRequest,
) -> ExtractTasksResponse:
    """
    从侦察方案文本中提取结构化任务数据

    **使用场景：**
    1. 前端调用 `/ai/recon/batch-weather-plan?format=md` 获得Markdown文本
    2. 展示给用户审阅，用户可能修改内容（删除任务、调整时长、修改设备等）
    3. 前端调用本接口，传入用户修改后的文本
    4. 后端使用Instructor库提取结构化JSON数据
    5. 返回标准化的任务列表，供后续接口使用（如保存、执行）

    **技术特点：**
    - 使用Instructor库（11.7k⭐）进行LLM结构化输出
    - 自动识别Markdown或纯文本格式
    - 批量提取，减少LLM调用次数
    - 容错处理，部分提取失败不影响整体

    **输入示例：**
    ```json
    {
        "text": "# 地震侦察方案\\n\\n## 一、空中侦察方案\\n\\n### 任务一\\n设备配置：无人机(ID: drone-10)\\n预计时长：90分钟\\n..."
    }
    ```

    **输出示例：**
    ```json
    {
        "code": 200,
        "data": [
            {
                "task_id": "任务一",
                "task_type": "air",
                "device_name": "10号态势侦察无人机",
                "device_id": "drone-10",
                "duration_min": 90,
                "targets": [...],
                "details": "...",
                "safety_tips": "..."
            }
        ],
        "total_tasks": 15,
        "summary": {
            "air_tasks": 5,
            "land_tasks": 7,
            "sea_tasks": 3
        },
        "message": "成功提取15个任务"
    }
    ```

    **错误处理：**
    - 文本为空：返回400错误
    - 提取失败：返回500错误，附带详细错误信息
    - 部分提取：返回成功，summary中标注失败的章节
    """
    trace_id = get_trace_id() or str(uuid.uuid4())

    # 验证输入
    if not req.text or not req.text.strip():
        raise HTTPException(
            status_code=400,
            detail="文本内容不能为空",
        )

    logger.info(
        "收到任务提取请求",
        text_length=len(req.text),
        format_hint=req.format_hint,
        trace_id=trace_id,
    )

    try:
        # 初始化提取器
        config = AppConfig.load_from_env()
        extractor = ReconPlanExtractor(config)

        # 提取所有任务
        tasks: List[TaskExtract] = extractor.extract_all_tasks(
            markdown=req.text,
            trace_id=trace_id
        )

        # 转换为字典（用于JSON序列化）
        task_dicts = [task.model_dump() for task in tasks]

        # 生成详细的任务-设备分配摘要
        tasks_by_type = {"air": [], "land": [], "sea": [], "unknown": []}
        devices_allocation = {}

        for task in tasks:
            # 按类型分组任务
            task_summary = {
                "task_id": task.task_id,
                "device_id": task.device_id,
                "device_name": task.device_name,
                "duration_min": task.duration_min,
            }
            task_type = task.task_type if task.task_type in ["air", "land", "sea"] else "unknown"
            tasks_by_type[task_type].append(task_summary)

            # 构建设备分配映射（一个设备可能执行多个任务）
            if task.device_id not in devices_allocation:
                devices_allocation[task.device_id] = {
                    "device_name": task.device_name,
                    "tasks": [],
                }
            devices_allocation[task.device_id]["tasks"].append(task.task_id)

        # 生成统计信息
        air_count = len(tasks_by_type["air"])
        land_count = len(tasks_by_type["land"])
        sea_count = len(tasks_by_type["sea"])
        unknown_count = len(tasks_by_type["unknown"])

        summary = {
            "tasks_by_type": tasks_by_type,
            "devices_allocation": devices_allocation,
            "statistics": {
                "total_tasks": len(tasks),
                "total_devices": len(devices_allocation),
                "total_duration_min": sum(t.duration_min for t in tasks),
                "air_task_count": air_count,
                "land_task_count": land_count,
                "sea_task_count": sea_count,
                "unknown_task_count": unknown_count,
            },
        }

        logger.info(
            "任务提取成功",
            total_tasks=len(tasks),
            air=air_count,
            land=land_count,
            sea=sea_count,
            trace_id=trace_id,
        )

        return ExtractTasksResponse(
            code=200,
            data=task_dicts,
            total_tasks=len(tasks),
            summary=summary,
            message=f"成功提取{len(tasks)}个任务",
        )

    except ValueError as e:
        # 提取逻辑错误（如格式不正确）
        logger.warning(
            "任务提取失败（格式错误）",
            error=str(e),
            trace_id=trace_id,
        )
        raise HTTPException(
            status_code=400,
            detail=f"文本格式错误，无法提取任务: {str(e)}",
        )

    except Exception as e:
        # 其他未预期错误
        logger.error(
            "任务提取失败（系统错误）",
            error=str(e),
            error_type=type(e).__name__,
            trace_id=trace_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"任务提取失败: {str(e)}",
        )
