from __future__ import annotations

import time
from datetime import datetime
import os
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, NonNegativeFloat, NonNegativeInt, PositiveInt
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from emergency_agents.config import AppConfig
from emergency_agents.llm.client import get_openai_client
from emergency_agents.llm.prompts.rescue_assessment import build_rescue_assessment_prompt
from emergency_agents.llm.prompts.post_rescue_assessment import build_post_rescue_assessment_prompt

logger = structlog.get_logger(__name__)

# 默认模型可通过环境覆盖，主模型+超时降级模型。
DEFAULT_REPORT_MODEL = "glm-4-flash"
DEFAULT_REPORT_FALLBACK_MODEL = "glm-4-flash"

# 依赖在 main.py 中注入
_pg_pool_async: Optional[AsyncConnectionPool] = None


class DisasterType(str, Enum):
    FLOOD = "洪涝灾害"
    DROUGHT = "干旱灾害"
    TYPHOON = "台风灾害"
    WIND_HAIL = "风雹灾害"
    COLD_SNAP = "低温冷冻灾害"
    SNOW = "雪灾"
    SANDSTORM = "沙尘暴灾害"
    EARTHQUAKE = "地震灾害"
    GEOLOGICAL = "地质灾害"
    MARINE = "海洋灾害"
    FOREST_FIRE = "森林草原火灾"
    BIOLOGICAL = "生物灾害"


class BasicInfo(BaseModel):
    disaster_type: DisasterType = Field(..., description="灾种分类，应符合国家灾情统计体系。")
    occurrence_time: datetime = Field(..., description="灾害发生时间，需精确到分钟。")
    report_time: datetime = Field(..., description="本次汇报生成时间。")
    location: str = Field(..., description="灾害主要影响行政区。")
    command_unit: str = Field(..., description="执行前突任务的指挥单位名称。")
    frontline_overview: Optional[str] = Field(
        None,
        description="现场总体态势概述，例如地形、天气、交通可达性等。",
    )
    communication_status: Optional[str] = Field(None, description="现场通信状况补充说明。")
    weather_trend: Optional[str] = Field(None, description="未来 24-48 小时天气趋势。")


class CasualtyStats(BaseModel):
    affected_population: Optional[NonNegativeInt] = Field(None, description="受灾人口数量。")
    deaths: Optional[NonNegativeInt] = Field(None, description="因灾死亡人数。")
    missing: Optional[NonNegativeInt] = Field(None, description="因灾失踪人数。")
    injured: Optional[NonNegativeInt] = Field(None, description="受伤人数。")
    emergency_evacuation: Optional[NonNegativeInt] = Field(None, description="紧急避险转移人口。")
    emergency_resettlement: Optional[NonNegativeInt] = Field(None, description="紧急安置人口。")
    urgent_life_support: Optional[NonNegativeInt] = Field(None, description="需紧急生活救助人口。")
    requiring_support: Optional[NonNegativeInt] = Field(None, description="仍需持续救助人口。")
    casualty_notes: Optional[str] = Field(None, description="其他与人员相关的说明。")


class DisruptionStatus(BaseModel):
    road_blocked_villages: Optional[NonNegativeInt] = Field(None, description="道路中断的行政村/社区数量。")
    power_outage_villages: Optional[NonNegativeInt] = Field(None, description="供电中断的行政村/社区数量。")
    water_outage_villages: Optional[NonNegativeInt] = Field(None, description="供水中断的行政村/社区数量。")
    telecom_outage_villages: Optional[NonNegativeInt] = Field(None, description="通信中断的行政村/社区数量。")
    infrastructure_notes: Optional[str] = Field(None, description="其他基础设施或生命线受损情况补充。")


class InfrastructureDamage(BaseModel):
    collapsed_buildings: Optional[NonNegativeInt] = Field(None, description="倒塌房屋间数。")
    severely_damaged_buildings: Optional[NonNegativeInt] = Field(None, description="严重损坏房屋间数。")
    mildly_damaged_buildings: Optional[NonNegativeInt] = Field(None, description="一般损坏房屋间数。")
    transport_damage: Optional[str] = Field(None, description="交通设施受损情况。")
    communication_damage: Optional[str] = Field(None, description="通信设施受损情况。")
    energy_damage: Optional[str] = Field(None, description="电力、燃气等能源设施受损情况。")
    water_facility_damage: Optional[str] = Field(None, description="水利及供水设施受损情况。")
    public_service_damage: Optional[str] = Field(None, description="医院、学校等公共服务设施情况。")
    direct_economic_loss: Optional[NonNegativeFloat] = Field(
        None,
        description="直接经济损失（万元），如无法统计可为空。",
    )
    other_critical_damage: Optional[str] = Field(None, description="其它重点损毁信息。")


class AgricultureDamage(BaseModel):
    affected_area_ha: Optional[NonNegativeFloat] = Field(
        None, description="农作物受灾面积（公顷）。"
    )
    ruined_area_ha: Optional[NonNegativeFloat] = Field(
        None, description="农作物成灾面积（公顷）。"
    )
    destroyed_area_ha: Optional[NonNegativeFloat] = Field(
        None, description="农作物绝收面积（公顷）。"
    )
    livestock_loss: Optional[str] = Field(None, description="畜牧、水产等损失情况。")
    other_agri_loss: Optional[str] = Field(None, description="其他涉农损失说明。")


class ForceUnit(BaseModel):
    name: str = Field(..., description="力量名称，例如“消防救援总队一支队”。")
    personnel: Optional[PositiveInt] = Field(None, description="投入该力量的人数。")
    equipment: Optional[str] = Field(None, description="携带的主要装备。")
    tasks: Optional[str] = Field(None, description="承担的作战任务。")


class ResourceDeployment(BaseModel):
    deployed_forces: List[ForceUnit] = Field(
        default_factory=list,
        description="已投入的救援力量清单。",
    )
    air_support: Optional[str] = Field(None, description="航空或无人机支援情况。")
    waterborne_support: Optional[str] = Field(None, description="水面或水下救援力量情况。")
    medical_support: Optional[str] = Field(None, description="医疗救护与防疫力量部署。")
    engineering_support: Optional[str] = Field(None, description="工程抢险力量部署。")
    public_security_support: Optional[str] = Field(None, description="公安、武警等维稳力量部署。")
    logistics_support: Optional[str] = Field(None, description="后勤、物资发放、油料补给等情况。")


class SupportNeeds(BaseModel):
    reinforcement_forces: Optional[str] = Field(None, description="需追加的救援力量种类与规模。")
    material_shortages: Optional[str] = Field(None, description="亟需调拨的物资种类与数量。")
    infrastructure_requests: Optional[str] = Field(None, description="需上级协调的交通、通信、能源保障。")
    coordination_matters: Optional[str] = Field(None, description="需指挥部决策的重点事项。")


class RiskOutlook(BaseModel):
    aftershock_risk: Optional[str] = Field(None, description="余震、滑坡等地质次生风险评估。")
    meteorological_risk: Optional[str] = Field(None, description="降雨、降温、大风等气象风险。")
    hydrological_risk: Optional[str] = Field(None, description="堰塞湖、洪水、溃坝等水文风险。")
    hazardous_sources: Optional[str] = Field(None, description="危化品、油气管线等重大风险源。")
    safety_measures: Optional[str] = Field(None, description="拟采取的防范与安全措施。")


class OperationsProgress(BaseModel):
    completed_actions: Optional[str] = Field(None, description="已完成的救援行动。")
    ongoing_actions: Optional[str] = Field(None, description="正在推进的重点任务。")
    pending_actions: Optional[str] = Field(None, description="待指挥部批示的事项或下一步计划。")


class RescueAssessmentInput(BaseModel):
    basic: BasicInfo
    casualties: CasualtyStats
    disruptions: DisruptionStatus
    infrastructure: InfrastructureDamage
    agriculture: AgricultureDamage
    resources: ResourceDeployment
    support_needs: SupportNeeds
    risk_outlook: RiskOutlook
    operations: OperationsProgress


class EquipmentRecommendation(BaseModel):
    """装备推荐项"""
    name: str = Field(..., description="装备名称")
    score: float = Field(..., description="推荐得分")
    source: str = Field(default="知识图谱", description="推荐来源")


class RescueAssessmentResponse(BaseModel):
    report_text: str = Field(..., description="面向指挥大厅的完整灾情汇报，Markdown 格式。")
    key_points: List[str] = Field(
        default_factory=list,
        description="便于前端展示的要点摘要，可用于快速检索关键结论。",
    )
    data_sources: List[str] = Field(
        default_factory=list,
        description="报告生成使用的数据来源列表（如：知识图谱、RAG规范库等）。",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="报告置信度评分（0-1），基于输入完整性和外部数据支撑度计算。",
    )
    referenced_specs: List[str] = Field(
        default_factory=list,
        description="报告引用的应急预案规范文档标题列表。",
    )
    referenced_cases: List[str] = Field(
        default_factory=list,
        description="报告引用的历史救援案例标题列表。",
    )
    equipment_recommendations: List[EquipmentRecommendation] = Field(
        default_factory=list,
        description="基于知识图谱推荐的救援装备配置清单。",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="数据获取过程中遇到的错误或警告信息（透明展示）。",
    )


router = APIRouter(prefix="/reports", tags=["reports"])

_kg_service: Any | None = None
_rag_pipeline: Any | None = None


async def _fetch_available_devices(pool: AsyncConnectionPool) -> List[Dict[str, Any]]:
    """查询所有可用设备及其能力信息。
    
    同时考虑 car_device_select 表，优先标记被选中的设备。
    """
    sql = """
        SELECT 
            d.id, 
            d.name, 
            d.device_type, 
            d.env_type, 
            d.is_recon,
            d.weather_capability,
            COALESCE(cds.is_selected, 0) as is_selected
        FROM operational.device d
        LEFT JOIN operational.car_device_select cds ON d.id = cds.device_id AND cds.is_selected = 1
        WHERE d.deleted_at IS NULL
    """
    
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@router.post("/rescue-assessment", response_model=RescueAssessmentResponse)
async def generate_rescue_assessment(payload: RescueAssessmentInput) -> RescueAssessmentResponse:
    """生成救援评估汇报（集成KG+RAG+实有装备库）。

    流程：
    1. 调用KG获取装备推荐
    2. 查询数据库获取实有装备列表
    3. 调用RAG检索规范文档
    4. 调用KG检索历史案例
    5. 构造增强prompt（包含权威参考资料和实有装备）
    6. 调用LLM生成报告
    7. 计算置信度评分
    8. 返回完整报告信息
    """
    total_start = time.perf_counter()
    cfg = AppConfig.load_from_env()
    disaster_type = payload.basic.disaster_type.value
    fallback_location = "四川茂县"
    location = payload.basic.location.strip() if payload.basic.location else ""
    if not location or location == "未知区域":
        location = fallback_location

    logger.info(
        "rescue_assessment_start",
        disaster_type=disaster_type,
        location=location,
    )

    data_sources: List[str] = []
    errors: List[str] = []
    equipment_list: List[EquipmentRecommendation] = []
    spec_titles: List[str] = []
    case_titles: List[str] = []
    reference_materials: List[str] = []

    # ============ 1. KG装备推荐 ============
    kg_start = time.perf_counter()
    try:
        if _kg_service is None:
            raise RuntimeError("KG Service 未初始化")

        logger.info(
            "kg_recommend_equipment_start",
            hazard=disaster_type,
            environment=payload.basic.frontline_overview,
        )

        kg_equipment = _kg_service.recommend_equipment(
            hazard=disaster_type,
            environment=payload.basic.frontline_overview,
            top_k=5
        )

        kg_elapsed_ms = int((time.perf_counter() - kg_start) * 1000)
        logger.info(
            "kg_recommend_equipment_success",
            result_count=len(kg_equipment),
            latency_ms=kg_elapsed_ms,
        )

        equipment_list = [
            EquipmentRecommendation(
                name=item.get("name", "未知装备"),
                score=float(item.get("score", 0.0)),
                source="知识图谱"
            )
            for item in kg_equipment
        ]

        if equipment_list:
            data_sources.append("知识图谱装备库")
            reference_materials.append(
                "**推荐装备配置（基于知识图谱）：**\n" +
                "\n".join([f"- {eq.name}（推荐指数：{eq.score:.2f}）" for eq in equipment_list])
            )

    except Exception as e:
        kg_elapsed_ms = int((time.perf_counter() - kg_start) * 1000)
        error_msg = f"知识图谱装备推荐失败: {str(e)}"
        logger.error(
            "kg_recommend_equipment_failed",
            error=str(e),
            latency_ms=kg_elapsed_ms,
        )
        errors.append(error_msg)

    # ============ 2. 实有装备查询 ============
    db_start = time.perf_counter()
    try:
        if _pg_pool_async:
            real_devices = await _fetch_available_devices(_pg_pool_async)
            
            # 分类整理实有装备
            selected_devices = [d for d in real_devices if d['is_selected'] == 1]
            other_devices = [d for d in real_devices if d['is_selected'] == 0]
            
            device_summary = []
            if selected_devices:
                device_summary.append("【当前选中/携带装备】（优先使用）：")
                for d in selected_devices:
                    desc = f"- {d['name']} ({d['device_type']}/{d['env_type']})"
                    if d['weather_capability']:
                        desc += f" [能力: {d['weather_capability']}]"
                    device_summary.append(desc)
            
            if other_devices:
                device_summary.append("\n【库内其他可用装备】（可供调派）：")
                # 仅列出前10个避免prompt过长，优先展示侦察设备
                sorted_others = sorted(other_devices, key=lambda x: x['is_recon'], reverse=True)[:10]
                for d in sorted_others:
                     device_summary.append(f"- {d['name']} ({d['device_type']})")
                if len(other_devices) > 10:
                    device_summary.append(f"...等共{len(other_devices)}台设备")

            if device_summary:
                data_sources.append("实有装备库")
                reference_materials.append(
                    "**现有可用装备清单（基于数据库）：**\n" +
                    "\n".join(device_summary)
                )
                logger.info(
                    "db_fetch_devices_success",
                    selected_count=len(selected_devices),
                    total_count=len(real_devices)
                )
        else:
            logger.warning("db_pool_not_initialized_skipping_devices")

    except Exception as e:
        db_elapsed_ms = int((time.perf_counter() - db_start) * 1000)
        error_msg = f"实有装备查询失败: {str(e)}"
        logger.error(
            "db_fetch_devices_failed",
            error=str(e),
            latency_ms=db_elapsed_ms,
        )
        errors.append(error_msg)

    # ============ 3. RAG规范检索 ============
    rag_spec_start = time.perf_counter()
    try:
        if _rag_pipeline is None:
            raise RuntimeError("RAG Pipeline 未初始化")

        spec_query = f"{disaster_type}应急预案规范"
        logger.info(
            "rag_query_specs_start",
            query=spec_query,
            domain="规范",
        )

        spec_chunks = _rag_pipeline.query(
            question=spec_query,
            domain="规范",
            top_k=3
        )

        rag_spec_elapsed_ms = int((time.perf_counter() - rag_spec_start) * 1000)
        logger.info(
            "rag_query_specs_success",
            result_count=len(spec_chunks),
            latency_ms=rag_spec_elapsed_ms,
        )

        if spec_chunks:
            data_sources.append("RAG规范文档库")
            spec_titles = [chunk.source for chunk in spec_chunks]
            reference_materials.append(
                "**应急预案规范（RAG检索）：**\n" +
                "\n".join([
                    f"- [{chunk.source}@{chunk.loc}] {chunk.text[:100]}..."
                    for chunk in spec_chunks
                ])
            )

    except Exception as e:
        rag_spec_elapsed_ms = int((time.perf_counter() - rag_spec_start) * 1000)
        error_msg = f"RAG规范检索失败: {str(e)}"
        logger.error(
            "rag_query_specs_failed",
            error=str(e),
            latency_ms=rag_spec_elapsed_ms,
        )
        errors.append(error_msg)

    kg_case_start = time.perf_counter()
    try:
        if _kg_service is None:
            raise RuntimeError("KG Service 未初始化")

        case_keywords = f"{disaster_type} {location}"
        logger.info(
            "kg_search_cases_start",
            keywords=case_keywords,
        )

        kg_cases = _kg_service.search_cases(
            keywords=case_keywords,
            top_k=3
        )

        kg_case_elapsed_ms = int((time.perf_counter() - kg_case_start) * 1000)
        logger.info(
            "kg_search_cases_success",
            result_count=len(kg_cases),
            latency_ms=kg_case_elapsed_ms,
        )

        if kg_cases:
            data_sources.append("知识图谱案例库")
            case_titles = [case.get("title", "未知案例") for case in kg_cases]
            reference_materials.append(
                "**历史救援案例（知识图谱）：**\n" +
                "\n".join([
                    f"- {case.get('title', '未知')}: {case.get('summary', '无摘要')[:80]}..."
                    for case in kg_cases
                ])
            )

    except Exception as e:
        kg_case_elapsed_ms = int((time.perf_counter() - kg_case_start) * 1000)
        error_msg = f"知识图谱案例检索失败: {str(e)}"
        logger.error(
            "kg_search_cases_failed",
            error=str(e),
            latency_ms=kg_case_elapsed_ms,
        )
        errors.append(error_msg)

    prompt_payload = _build_prompt_payload(payload)

    if not reference_materials:
        reference_materials.append("**注意：未检索到外部参考资料，报告仅基于输入数据生成**")

    prompt = build_rescue_assessment_prompt(prompt_payload, reference_materials)

    logger.info(
        "prompt_built",
        prompt_length=len(prompt),
        data_sources_count=len(data_sources),
    )

    llm_client = get_openai_client(cfg)
    primary_model = os.getenv("RESCUE_REPORT_MODEL", DEFAULT_REPORT_MODEL)
    fallback_model = os.getenv("RESCUE_REPORT_FALLBACK_MODEL", DEFAULT_REPORT_FALLBACK_MODEL)
    llm_start = time.perf_counter()

    def _call_llm(model: str, max_tokens: int):
        return llm_client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_tokens=max_tokens,
            presence_penalty=0,
            frequency_penalty=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名国家级应急救援指挥专家，擅长将复杂灾情转化为结构化的正式汇报。"
                        "务必严格遵循用户提供的数据和权威参考资料，严禁虚构。"
                        "在汇报中引用外部资料时，需标注来源。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

    try:
        completion = _call_llm(primary_model, 8000)
        used_model = primary_model
    except Exception as exc:
        errmsg = str(exc).lower()
        if fallback_model and fallback_model != primary_model and ("timeout" in errmsg or "timed out" in errmsg):
            logger.warning(
                "rescue_assessment_llm_retry_fallback",
                primary=primary_model,
                fallback=fallback_model,
            )
            completion = _call_llm(fallback_model, 6000)
            used_model = fallback_model
        else:
            llm_elapsed_ms = int((time.perf_counter() - llm_start) * 1000)
            logger.exception(
                "rescue_assessment_llm_failed",
                latency_ms=llm_elapsed_ms,
                disaster_type=disaster_type,
            )
            raise HTTPException(status_code=502, detail="模型生成失败，请稍后重试") from exc

    llm_elapsed_ms = int((time.perf_counter() - llm_start) * 1000)
    content = completion.choices[0].message.content if completion.choices else None
    if not content:
        logger.error(
            "rescue_assessment_empty_response",
            latency_ms=llm_elapsed_ms,
            disaster_type=disaster_type,
        )
        raise HTTPException(status_code=502, detail="模型未返回有效内容")

    logger.info(
        "rescue_assessment_llm_success",
        latency_ms=llm_elapsed_ms,
        model=used_model,
        output_length=len(content),
    )

    input_completeness = _calculate_input_completeness(payload)
    confidence_score = _calculate_confidence_score(
        input_completeness=input_completeness,
        spec_count=len(spec_titles),
        case_count=len(case_titles),
        equipment_count=len(equipment_list),
    )

    logger.info(
        "confidence_score_calculated",
        input_completeness=input_completeness,
        spec_count=len(spec_titles),
        case_count=len(case_titles),
        equipment_count=len(equipment_list),
        confidence_score=confidence_score,
    )

    key_points = _extract_key_points(payload)
    total_elapsed_ms = int((time.perf_counter() - total_start) * 1000)

    logger.info(
        "rescue_assessment_completed",
        total_latency_ms=total_elapsed_ms,
        disaster_type=disaster_type,
        confidence_score=confidence_score,
        data_sources_count=len(data_sources),
        errors_count=len(errors),
    )

    return RescueAssessmentResponse(
        report_text=content,
        key_points=key_points,
        data_sources=data_sources,
        confidence_score=confidence_score,
        referenced_specs=spec_titles,
        referenced_cases=case_titles,
        equipment_recommendations=equipment_list,
        errors=errors,
    )


def _fmt_datetime(dt: datetime) -> str:
    return dt.strftime("%Y年%m月%d日%H时%M分")


def _compact_dict(entries: Dict[str, Any]) -> Dict[str, Any]:
    def _valid(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set)):
            return bool(value)
        return True

    return {key: value for key, value in entries.items() if _valid(value)}


def _build_prompt_payload(payload: RescueAssessmentInput) -> Dict[str, Any]:
    deployed_forces = [
        _compact_dict(
            {
                "名称": unit.name,
                "人员": unit.personnel,
                "装备": unit.equipment,
                "任务": unit.tasks,
            }
        )
        for unit in payload.resources.deployed_forces
    ]

    return _compact_dict(
        {
            "基础信息": _compact_dict(
                {
                    "灾种": payload.basic.disaster_type.value,
                    "发生时间": _fmt_datetime(payload.basic.occurrence_time),
                    "报告时间": _fmt_datetime(payload.basic.report_time),
                    "所在地区": payload.basic.location,
                    "前突指挥单位": payload.basic.command_unit,
                    "现场概况": payload.basic.frontline_overview,
                    "通讯态势": payload.basic.communication_status,
                    "天气趋势": payload.basic.weather_trend,
                }
            ),
            "人员与群众": _compact_dict(
                {
                    "受灾人口": payload.casualties.affected_population,
                    "死亡": payload.casualties.deaths,
                    "失踪": payload.casualties.missing,
                    "受伤": payload.casualties.injured,
                    "紧急避险转移": payload.casualties.emergency_evacuation,
                    "紧急安置": payload.casualties.emergency_resettlement,
                    "需紧急生活救助": payload.casualties.urgent_life_support,
                    "需持续救助": payload.casualties.requiring_support,
                    "补充说明": payload.casualties.casualty_notes,
                }
            ),
            "生命线受损": _compact_dict(
                {
                    "道路中断行政村数": payload.disruptions.road_blocked_villages,
                    "供电中断行政村数": payload.disruptions.power_outage_villages,
                    "供水中断行政村数": payload.disruptions.water_outage_villages,
                    "通信中断行政村数": payload.disruptions.telecom_outage_villages,
                    "补充说明": payload.disruptions.infrastructure_notes,
                }
            ),
            "基础设施与房屋损毁": _compact_dict(
                {
                    "倒塌房屋": payload.infrastructure.collapsed_buildings,
                    "严重损坏房屋": payload.infrastructure.severely_damaged_buildings,
                    "一般损坏房屋": payload.infrastructure.mildly_damaged_buildings,
                    "交通设施": payload.infrastructure.transport_damage,
                    "通信设施": payload.infrastructure.communication_damage,
                    "能源设施": payload.infrastructure.energy_damage,
                    "水利设施": payload.infrastructure.water_facility_damage,
                    "公共服务设施": payload.infrastructure.public_service_damage,
                    "直接经济损失(万元)": payload.infrastructure.direct_economic_loss,
                    "其它关键信息": payload.infrastructure.other_critical_damage,
                }
            ),
            "农业与产业损失": _compact_dict(
                {
                    "农作物受灾面积(公顷)": payload.agriculture.affected_area_ha,
                    "农作物成灾面积(公顷)": payload.agriculture.ruined_area_ha,
                    "农作物绝收面积(公顷)": payload.agriculture.destroyed_area_ha,
                    "牲畜及水产损失": payload.agriculture.livestock_loss,
                    "其他产业损失": payload.agriculture.other_agri_loss,
                }
            ),
            "救援力量部署": _compact_dict(
                {
                    "现场力量": deployed_forces,
                    "航空支援": payload.resources.air_support,
                    "水面/水下支援": payload.resources.waterborne_support,
                    "医疗防疫支援": payload.resources.medical_support,
                    "工程抢险支援": payload.resources.engineering_support,
                    "公安武警支援": payload.resources.public_security_support,
                    "后勤保障": payload.resources.logistics_support,
                }
            ),
            "后续支援需求": _compact_dict(
                {
                    "需要增援的力量": payload.support_needs.reinforcement_forces,
                    "物资缺口": payload.support_needs.material_shortages,
                    "基础设施保障诉求": payload.support_needs.infrastructure_requests,
                    "需协调事项": payload.support_needs.coordination_matters,
                }
            ),
            "风险研判": _compact_dict(
                {
                    "地质灾害风险": payload.risk_outlook.aftershock_risk,
                    "气象风险": payload.risk_outlook.meteorological_risk,
                    "水文风险": payload.risk_outlook.hydrological_risk,
                    "重大风险源": payload.risk_outlook.hazardous_sources,
                    "防范举措": payload.risk_outlook.safety_measures,
                }
            ),
            "行动进展": _compact_dict(
                {
                    "已完成行动": payload.operations.completed_actions,
                    "进行中行动": payload.operations.ongoing_actions,
                    "待批示事项": payload.operations.pending_actions,
                }
            ),
        }
    )


def _extract_key_points(payload: RescueAssessmentInput) -> List[str]:
    points: List[str] = []

    casualties = payload.casualties
    if casualties.deaths:
        points.append(f"死亡 {casualties.deaths} 人")
    if casualties.missing:
        points.append(f"失踪 {casualties.missing} 人")
    if casualties.emergency_resettlement:
        points.append(f"紧急安置 {casualties.emergency_resettlement} 人")

    infra = payload.infrastructure
    if infra.direct_economic_loss is not None:
        points.append(f"直接经济损失 {infra.direct_economic_loss} 万元")
    if infra.collapsed_buildings:
        points.append(f"倒塌房屋 {infra.collapsed_buildings} 间")

    disruptions = payload.disruptions
    if disruptions.road_blocked_villages:
        points.append(f"道路中断村(社区) {disruptions.road_blocked_villages} 个")

    support = payload.support_needs
    if support.reinforcement_forces:
        points.append(f"增援诉求：{support.reinforcement_forces}")
    if support.material_shortages:
        points.append(f"物资缺口：{support.material_shortages}")

    risk = payload.risk_outlook
    if risk.aftershock_risk:
        points.append(f"地质风险：{risk.aftershock_risk}")
    if risk.meteorological_risk:
        points.append(f"气象风险：{risk.meteorological_risk}")

    return points[:8]


def _calculate_input_completeness(payload: RescueAssessmentInput) -> float:
    """计算输入数据的完整性得分

    遍历输入payload的所有字段，统计非空字段占比
    """
    total_fields = 0
    filled_fields = 0

    for field_name, field_value in payload.model_dump().items():
        if isinstance(field_value, dict):
            for sub_key, sub_value in field_value.items():
                total_fields += 1
                if sub_value is not None and sub_value != "" and sub_value != []:
                    filled_fields += 1
        elif isinstance(field_value, list):
            total_fields += 1
            if field_value:
                filled_fields += 1
        else:
            total_fields += 1
            if field_value is not None and field_value != "":
                filled_fields += 1

    return filled_fields / total_fields if total_fields > 0 else 0.0


def _calculate_confidence_score(
    input_completeness: float,
    spec_count: int,
    case_count: int,
    equipment_count: int,
    expected_specs: int = 3,
    expected_cases: int = 2,
    expected_equipment: int = 5,
) -> float:
    """计算报告置信度评分

    Args:
        input_completeness: 输入完整性（0-1）
        spec_count: 检索到的规范数量
        case_count: 检索到的案例数量
        equipment_count: 推荐到的装备数量
        expected_specs: 期望的规范数量
        expected_cases: 期望的案例数量
        expected_equipment: 期望的装备数量

    Returns:
        综合置信度评分（0-1）
    """
    external_support = (
        min(spec_count / expected_specs, 1.0) * 0.4
        + min(case_count / expected_cases, 1.0) * 0.3
        + min(equipment_count / expected_equipment, 1.0) * 0.3
    )

    source_count = sum([
        1 if spec_count > 0 else 0,
        1 if case_count > 0 else 0,
        1 if equipment_count > 0 else 0,
    ])
    source_diversity = source_count / 3.0

    confidence = (
        input_completeness * 0.4
        + external_support * 0.4
        + source_diversity * 0.2
    )

    return round(confidence, 3)


# ============================================================================
# 救援评估报告（Post-Rescue Assessment）数据模型
# 用于救灾结束后的总结性评估报告生成
# ============================================================================


class ResponseLevel(str, Enum):
    """应急响应级别"""
    LEVEL_I = "一级响应"  # 特别重大
    LEVEL_II = "二级响应"  # 重大
    LEVEL_III = "三级响应"  # 较大
    LEVEL_IV = "四级响应"  # 一般


class DisasterOverview(BaseModel):
    """灾害基本概况"""
    disaster_type: DisasterType = Field(..., description="灾害类型")
    disaster_name: str = Field(..., description="灾害事件名称，如'汶川8.0级地震'")
    occurrence_time: datetime = Field(..., description="灾害发生时间")
    end_time: datetime = Field(..., description="救援结束时间")
    location: str = Field(..., description="主要影响区域")
    disaster_scale: str = Field(..., description="灾害规模描述（如震级、洪峰流量等）")
    affected_area_km2: Optional[NonNegativeFloat] = Field(None, description="受灾面积（平方公里）")

    # 灾情统计（最终统计）
    final_deaths: NonNegativeInt = Field(..., description="最终死亡人数（含失踪）")
    final_injured: NonNegativeInt = Field(..., description="最终受伤人数")
    affected_population: NonNegativeInt = Field(..., description="受灾人口")
    economic_loss_billion: Optional[NonNegativeFloat] = Field(None, description="直接经济损失（亿元）")


class ResponseActivation(BaseModel):
    """应急响应启动信息"""
    response_level: ResponseLevel = Field(..., description="启动的应急响应级别")
    activation_time: datetime = Field(..., description="响应启动时间")
    command_center: str = Field(..., description="指挥机构名称")
    leading_unit: str = Field(..., description="牵头单位")
    participating_departments: List[str] = Field(
        default_factory=list,
        description="参与部门列表"
    )
    legal_basis: Optional[str] = Field(None, description="启动依据（预案名称）")


class TimelineEvent(BaseModel):
    """关键时间节点"""
    time: datetime = Field(..., description="事件发生时间")
    event_type: str = Field(..., description="事件类型（如'灾害发生'、'响应启动'、'首支队伍到达'）")
    description: str = Field(..., description="事件描述")
    significance: Optional[str] = Field(None, description="该节点的重要意义")


class DeployedForce(BaseModel):
    """投入救援力量详情"""
    force_type: str = Field(..., description="力量类型（如'消防救援'、'武警部队'、'医疗队伍'）")
    force_name: str = Field(..., description="具体单位名称")
    personnel: PositiveInt = Field(..., description="投入人数")
    arrival_time: Optional[datetime] = Field(None, description="到位时间")
    main_equipment: Optional[str] = Field(None, description="主要装备")
    assigned_tasks: str = Field(..., description="承担的主要任务")

    # 成效统计
    rescued_people: Optional[NonNegativeInt] = Field(None, description="搜救人数")
    completed_tasks: Optional[str] = Field(None, description="完成任务情况")


class RescueStatistics(BaseModel):
    """救援成效统计"""
    # 人员搜救
    total_rescued: NonNegativeInt = Field(..., description="累计搜救人数")
    rescued_alive: NonNegativeInt = Field(..., description="成功救出生还者人数")

    # 转移安置
    evacuated_people: NonNegativeInt = Field(..., description="紧急转移人数")
    resettled_people: NonNegativeInt = Field(..., description="安置人数")

    # 医疗救治
    treated_patients: NonNegativeInt = Field(..., description="累计救治伤员人数")
    transferred_critical: Optional[NonNegativeInt] = Field(None, description="转运重伤员人数")

    # 物资发放
    relief_materials_distributed: Optional[str] = Field(None, description="发放救灾物资情况")

    # 基础设施抢通
    roads_reopened_km: Optional[NonNegativeFloat] = Field(None, description="抢通道路里程（公里）")
    power_restored_households: Optional[NonNegativeInt] = Field(None, description="恢复供电户数")
    water_restored_households: Optional[NonNegativeInt] = Field(None, description="恢复供水户数")


class CoordinationInfo(BaseModel):
    """协同配合情况"""
    government_agencies: Optional[str] = Field(None, description="政府部门协同情况")
    military_cooperation: Optional[str] = Field(None, description="军地协同情况")
    social_forces: Optional[str] = Field(None, description="社会力量参与情况")
    inter_regional: Optional[str] = Field(None, description="跨区域协作情况")
    information_sharing: Optional[str] = Field(None, description="信息共享机制运行情况")
    coordination_effectiveness: Optional[str] = Field(
        None,
        description="协同配合效果总体评价"
    )


class ChallengesEncountered(BaseModel):
    """遇到的困难和问题"""
    access_difficulties: Optional[str] = Field(None, description="交通受阻、通达困难")
    communication_issues: Optional[str] = Field(None, description="通信中断、信息不畅")
    equipment_shortages: Optional[str] = Field(None, description="装备不足或不适用")
    personnel_issues: Optional[str] = Field(None, description="人员配置、专业能力不足")
    weather_impact: Optional[str] = Field(None, description="恶劣天气影响")
    secondary_disasters: Optional[str] = Field(None, description="次生灾害威胁")
    coordination_problems: Optional[str] = Field(None, description="协调配合方面的问题")
    other_challenges: Optional[str] = Field(None, description="其他困难和挑战")


class ResourceUtilization(BaseModel):
    """资源投入与消耗统计"""
    total_personnel: PositiveInt = Field(..., description="累计投入救援人员总数")
    total_vehicles: Optional[NonNegativeInt] = Field(None, description="投入车辆总数")
    aircraft_sorties: Optional[NonNegativeInt] = Field(None, description="航空器出动架次")

    # 物资消耗
    relief_tents: Optional[NonNegativeInt] = Field(None, description="发放帐篷（顶）")
    relief_quilts: Optional[NonNegativeInt] = Field(None, description="发放棉被（床）")
    food_tons: Optional[NonNegativeFloat] = Field(None, description="发放食品（吨）")
    water_tons: Optional[NonNegativeFloat] = Field(None, description="发放饮用水（吨）")

    # 资金投入
    total_funds_million: Optional[NonNegativeFloat] = Field(
        None,
        description="累计投入资金（百万元）"
    )
    central_funds_million: Optional[NonNegativeFloat] = Field(
        None,
        description="中央财政资金（百万元）"
    )
    local_funds_million: Optional[NonNegativeFloat] = Field(
        None,
        description="地方财政资金（百万元）"
    )


class PostRescueAssessmentInput(BaseModel):
    """救援评估报告输入数据（救灾结束后）"""
    disaster_overview: DisasterOverview = Field(..., description="灾害基本概况")
    response_activation: ResponseActivation = Field(..., description="应急响应启动信息")
    timeline: List[TimelineEvent] = Field(
        default_factory=list,
        description="关键时间节点（按时间顺序）"
    )
    forces_deployed: List[DeployedForce] = Field(
        default_factory=list,
        description="投入救援力量详情"
    )
    rescue_statistics: RescueStatistics = Field(..., description="救援成效统计")
    coordination: CoordinationInfo = Field(..., description="协同配合情况")
    challenges: ChallengesEncountered = Field(..., description="遇到的困难和问题")
    resource_utilization: ResourceUtilization = Field(..., description="资源投入与消耗")

    # 可选字段：经验教训和改进建议可由LLM基于数据生成
    lessons_learned: Optional[str] = Field(
        None,
        description="（可选）已识别的经验教训总结"
    )
    improvement_suggestions: Optional[str] = Field(
        None,
        description="（可选）已识别的改进建议"
    )


class PostRescueAssessmentResponse(BaseModel):
    """救援评估报告响应（事后总结）"""
    report_text: str = Field(..., description="完整的救援评估报告，Markdown格式")
    key_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="关键量化指标（响应及时性、救援成功率、资源利用效率等）"
    )
    data_sources: List[str] = Field(
        default_factory=list,
        description="报告生成使用的数据来源"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="报告置信度评分（0-1），基于数据完整性评估"
    )
    referenced_specs: List[str] = Field(
        default_factory=list,
        description="引用的评估标准和规范文档"
    )
    referenced_cases: List[str] = Field(
        default_factory=list,
        description="引用的历史案例用于对比分析"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="数据获取过程中的错误或警告"
    )


@router.post("/post-rescue-assessment", response_model=PostRescueAssessmentResponse)
async def generate_post_rescue_assessment(
    payload: PostRescueAssessmentInput
) -> PostRescueAssessmentResponse:
    """生成救援评估报告（事后总结）。

    本接口用于救灾结束后的总结性评估，重点在于：
    1. 客观评估救援成效
    2. 量化关键指标（响应及时性、救援成功率、资源利用效率）
    3. 对比分析（与预案要求、历史案例对比）
    4. 问题总结与改进建议

    流程：
    1. 计算关键量化指标
    2. 调用KG检索历史案例用于对比
    3. 调用RAG检索评估标准和规范
    4. 构造评估报告prompt（包含对比分析要求）
    5. 调用LLM生成报告
    6. 计算置信度评分
    """
    total_start = time.perf_counter()
    cfg = AppConfig.load_from_env()

    disaster_name = payload.disaster_overview.disaster_name
    disaster_type = payload.disaster_overview.disaster_type.value

    logger.info(
        "post_rescue_assessment_start",
        disaster_name=disaster_name,
        disaster_type=disaster_type,
        response_level=payload.response_activation.response_level.value,
    )

    data_sources: List[str] = []
    errors: List[str] = []
    spec_titles: List[str] = []
    case_titles: List[str] = []
    reference_materials: List[str] = []

    # ============ 计算关键量化指标 ============
    key_metrics = {}

    try:
        # 响应及时性（秒）
        response_time_delta = (
            payload.response_activation.activation_time
            - payload.disaster_overview.occurrence_time
        )
        key_metrics["response_time_seconds"] = response_time_delta.total_seconds()
        key_metrics["response_time_hours"] = round(response_time_delta.total_seconds() / 3600, 2)

        # 救援持续时间（天）
        rescue_duration = (
            payload.disaster_overview.end_time
            - payload.disaster_overview.occurrence_time
        )
        key_metrics["rescue_duration_days"] = round(rescue_duration.total_seconds() / 86400, 2)

        # 救援成功率
        if payload.rescue_statistics.total_rescued > 0:
            success_rate = (
                payload.rescue_statistics.rescued_alive
                / payload.rescue_statistics.total_rescued
            )
            key_metrics["rescue_success_rate"] = round(success_rate, 4)

        # 人均救援人数
        if payload.resource_utilization.total_personnel > 0:
            per_capita = (
                payload.rescue_statistics.total_rescued
                / payload.resource_utilization.total_personnel
            )
            key_metrics["per_capita_rescued"] = round(per_capita, 2)

        logger.info(
            "key_metrics_calculated",
            **key_metrics
        )

    except Exception as e:
        logger.warning(
            "key_metrics_calculation_failed",
            error=str(e)
        )
        errors.append(f"关键指标计算失败: {str(e)}")

    # ============ KG：检索历史案例 ============
    kg_start = time.perf_counter()
    try:
        if _kg_service is None:
            raise RuntimeError("KG Service 未初始化")

        logger.info(
            "kg_search_cases_start",
            disaster_type=disaster_type,
        )

        # KGService.search_cases的参数是keywords(str)和top_k
        # 拼接灾害类型和地点作为关键词
        _loc = (payload.disaster_overview.location or "").strip()
        if not _loc or _loc == "未知区域":
            _loc = "四川茂县"
        search_keywords = f"{disaster_type} {_loc}"
        kg_cases = _kg_service.search_cases(
            keywords=search_keywords,
            top_k=3
        )

        kg_elapsed_ms = int((time.perf_counter() - kg_start) * 1000)
        logger.info(
            "kg_search_cases_success",
            result_count=len(kg_cases),
            latency_ms=kg_elapsed_ms,
        )

        if kg_cases:
            data_sources.append("知识图谱-历史案例")
            case_titles.extend([case["title"] for case in kg_cases])

            case_summaries = []
            for case in kg_cases:
                summary = (
                    f"【案例】{case['title']}\n"
                    f"- 时间：{case.get('date', '未知')}\n"
                    f"- 伤亡：{case.get('casualties', '未知')}\n"
                    f"- 救援成效：{case.get('rescue_outcome', '未知')}\n"
                    f"- 经验教训：{case.get('lessons', '未知')}"
                )
                case_summaries.append(summary)

            if case_summaries:
                reference_materials.append(
                    "## 历史案例对比\n" + "\n\n".join(case_summaries)
                )

    except Exception as exc:
        kg_elapsed_ms = int((time.perf_counter() - kg_start) * 1000)
        logger.warning(
            "kg_search_cases_failed",
            error=str(exc),
            latency_ms=kg_elapsed_ms,
        )
        errors.append(f"历史案例检索失败: {str(exc)}")

    # ============ RAG：检索评估标准规范 ============
    rag_start = time.perf_counter()
    try:
        if _rag_pipeline is None:
            raise RuntimeError("RAG Pipeline 未初始化")

        query_text = (
            f"{disaster_type}救援评估标准 应急响应效果评估 "
            f"救援成效评估指标 地震灾害调查评估规范"
        )

        logger.info(
            "rag_query_start",
            query=query_text,
        )

        # RagPipeline.query的参数是question(str)、domain和top_k
        rag_results = _rag_pipeline.query(
            question=query_text,
            domain="规范",
            top_k=3
        )

        rag_elapsed_ms = int((time.perf_counter() - rag_start) * 1000)
        logger.info(
            "rag_query_success",
            result_count=len(rag_results),
            latency_ms=rag_elapsed_ms,
        )

        if rag_results:
            data_sources.append("RAG规范库")
            for doc in rag_results:
                spec_titles.append(doc.get("title", "未知文档"))
                ref_text = (
                    f"【规范】{doc['title']}\n{doc.get('snippet', '')}"
                )
                reference_materials.append(ref_text)

    except Exception as exc:
        rag_elapsed_ms = int((time.perf_counter() - rag_start) * 1000)
        logger.warning(
            "rag_query_failed",
            error=str(exc),
            latency_ms=rag_elapsed_ms,
        )
        errors.append(f"评估标准检索失败: {str(exc)}")

    # ============ 构造提示词 ============
    payload_dict = payload.model_dump(mode="json")
    prompt = build_post_rescue_assessment_prompt(
        payload=payload_dict,
        reference_materials=reference_materials if reference_materials else None
    )

    logger.info(
        "prompt_built",
        prompt_length=len(prompt),
        reference_count=len(reference_materials),
    )

    # ============ LLM生成报告 ============
    llm_client = get_openai_client(cfg)
    primary_model = os.getenv("RESCUE_REPORT_MODEL", DEFAULT_REPORT_MODEL)
    fallback_model = os.getenv("RESCUE_REPORT_FALLBACK_MODEL", DEFAULT_REPORT_FALLBACK_MODEL)
    llm_start = time.perf_counter()

    def _call_llm(model: str, max_tokens: int):
        return llm_client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_tokens=max_tokens,
            presence_penalty=0,
            frequency_penalty=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名应急管理评估专家，擅长撰写客观、专业的救援评估报告。"
                        "你必须严格基于提供的数据进行分析，不得虚构或夸大。"
                        "你的报告将用于总结经验、查找不足、改进应急响应能力。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

    try:
        completion = _call_llm(primary_model, 10000)
        used_model = primary_model
    except Exception as exc:
        errmsg = str(exc).lower()
        if fallback_model and fallback_model != primary_model and ("timeout" in errmsg or "timed out" in errmsg):
            logger.warning(
                "post_rescue_assessment_llm_retry_fallback",
                primary=primary_model,
                fallback=fallback_model,
            )
            completion = _call_llm(fallback_model, 7000)
            used_model = fallback_model
        else:
            llm_elapsed_ms = int((time.perf_counter() - llm_start) * 1000)
            logger.exception(
                "post_rescue_assessment_llm_failed",
                latency_ms=llm_elapsed_ms,
                disaster_name=disaster_name,
            )
            raise HTTPException(status_code=502, detail="模型生成失败，请稍后重试") from exc

    llm_elapsed_ms = int((time.perf_counter() - llm_start) * 1000)
    content = completion.choices[0].message.content if completion.choices else None

    if not content:
        logger.error(
            "post_rescue_assessment_empty_response",
            latency_ms=llm_elapsed_ms,
            disaster_name=disaster_name,
        )
        raise HTTPException(status_code=502, detail="模型未返回有效内容")

    logger.info(
        "post_rescue_assessment_llm_success",
        latency_ms=llm_elapsed_ms,
        model=used_model,
        output_length=len(content),
    )

    # ============ 计算置信度评分 ============
    input_completeness = _calculate_post_rescue_input_completeness(payload)
    confidence_score = _calculate_confidence_score(
        input_completeness=input_completeness,
        spec_count=len(spec_titles),
        case_count=len(case_titles),
        equipment_count=0,  # 评估报告不涉及装备推荐
    )

    logger.info(
        "confidence_score_calculated",
        input_completeness=input_completeness,
        spec_count=len(spec_titles),
        case_count=len(case_titles),
        confidence_score=confidence_score,
    )

    total_elapsed_ms = int((time.perf_counter() - total_start) * 1000)

    logger.info(
        "post_rescue_assessment_completed",
        total_latency_ms=total_elapsed_ms,
        disaster_name=disaster_name,
        confidence_score=confidence_score,
        data_sources_count=len(data_sources),
        errors_count=len(errors),
    )

    return PostRescueAssessmentResponse(
        report_text=content,
        key_metrics=key_metrics,
        data_sources=data_sources,
        confidence_score=confidence_score,
        referenced_specs=spec_titles,
        referenced_cases=case_titles,
        errors=errors,
    )


def _calculate_post_rescue_input_completeness(payload: PostRescueAssessmentInput) -> float:
    """计算救援评估报告输入数据的完整性（0-1）。

    评估维度：
    1. 必填字段完整性（40%）
    2. 时间轴数据（20%）
    3. 救援力量详情（20%）
    4. 资源消耗统计（20%）
    """
    scores = []

    # 1. 必填字段（disaster_overview, response_activation, rescue_statistics, resource_utilization）
    required_fields_score = 1.0  # 这些是必填的，Pydantic已验证
    scores.append(required_fields_score * 0.4)

    # 2. 时间轴完整性
    timeline_score = min(len(payload.timeline) / 5.0, 1.0)  # 预期至少5个关键节点
    scores.append(timeline_score * 0.2)

    # 3. 救援力量详情
    forces_score = min(len(payload.forces_deployed) / 5.0, 1.0)  # 预期至少5支队伍
    scores.append(forces_score * 0.2)

    # 4. 资源消耗统计
    resource_fields = [
        payload.resource_utilization.total_vehicles,
        payload.resource_utilization.aircraft_sorties,
        payload.resource_utilization.relief_tents,
        payload.resource_utilization.total_funds_million,
    ]
    filled_count = sum(1 for field in resource_fields if field is not None)
    resource_score = filled_count / len(resource_fields)
    scores.append(resource_score * 0.2)

    return round(sum(scores), 3)
