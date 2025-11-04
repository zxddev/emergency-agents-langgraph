"""
LLM智能侦察方案生成模块

功能：使用LLM根据设备能力和目标信息，智能生成详细的侦察任务方案
"""

import json
from typing import List, Dict, Any, TypedDict, Optional, Union
from uuid import UUID
from datetime import datetime, timedelta
from openai import OpenAI
import structlog
import math

logger = structlog.get_logger(__name__)


# 类型定义占位 - 完整代码太长，先创建基础框架
class GeoPoint(TypedDict):
    lon: float
    lat: float


class DeviceInput(TypedDict):
    id: str
    name: str
    device_type: str
    env_type: str
    capabilities: List[str]


class TargetPoint(TypedDict):
    id: Union[int, str, UUID]  # 支持int/string/UUID（数据库实际为UUID）
    name: str
    target_type: str
    hazard_level: str
    priority: float
    lon: float
    lat: float


class DisasterInfo(TypedDict):
    disaster_type: str
    severity: str
    epicenter: GeoPoint
    location_desc: str


class TaskDetail(TypedDict):
    """任务详情（最终输出）"""
    task_number: str
    task_type: str
    device_id: str
    device_name: str
    device_selection_reason: str
    target_ids: List[Union[int, str, UUID]]  # 支持int/string/UUID
    target_names: List[str]
    reconnaissance_detail: str
    result_reporting: str
    start_time: str
    end_time: str
    estimated_duration_minutes: int
    route_distance_km: float


class ReconSection(TypedDict):
    """侦察分段（输出）"""
    section_name: str
    tasks: List[TaskDetail]


class DetailedReconPlan(TypedDict):
    """完整的详细侦察方案（输出）"""
    command_center: GeoPoint
    command_center_name: str
    disaster_info: DisasterInfo
    air_recon_section: Optional[ReconSection]
    ground_recon_section: Optional[ReconSection]
    water_recon_section: Optional[ReconSection]
    data_integration_desc: str
    earliest_start_time: str
    latest_end_time: str
    total_estimated_hours: float


# ============ 系统提示词 ============

RECON_PLAN_SYSTEM_PROMPT = """你是应急救援侦察规划专家，负责根据设备能力和目标信息生成侦察任务方案。

**核心原则**：
1. **设备-目标匹配**：根据设备的env_type（air/land/sea）和capabilities优先匹配合适的目标
2. **优先级优先**：高优先级目标应分配最适合的设备
3. **能力互补**：不同设备协同覆盖（如空中扫图 + 地面搜索 + 水域侦察）
4. **时间估算**：考虑设备速度、目标距离、作业时间

**输出要求**：
- air_tasks: 空中设备任务列表（env_type=air）
- ground_tasks: 地面设备任务列表（env_type=land）
- water_tasks: 水上设备任务列表（env_type=sea）
- data_integration_desc: 数据整合说明（如何汇总三类数据）

**每个任务必须包含**：
- task_number: 任务编号（如"1.扫图建模"）
- device_id: 执行设备ID
- device_selection_reason: 设备选择理由（为什么选这个设备？）
- target_ids: 目标ID列表（该设备负责的目标）
- reconnaissance_detail: 侦察详情（路线、方法、数据采集）
- result_reporting: 结果上报内容（回传什么数据）
- estimated_duration_minutes: 预计耗时（分钟，整数）

**严格返回JSON格式，不要包含markdown标记。**
"""


# ============ 辅助函数 ============

def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """计算两点间的Haversine距离（公里）"""
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _build_llm_user_prompt(
    devices: List[DeviceInput],
    targets: List[TargetPoint],
    disaster_info: DisasterInfo,
    command_center: GeoPoint,
) -> str:
    """构造LLM用户提示词（紧凑格式）"""
    prompt_parts = []

    # 灾情信息
    prompt_parts.append("**灾情信息**：")
    prompt_parts.append(f"- 类型: {disaster_info['disaster_type']}")
    prompt_parts.append(f"- 严重程度: {disaster_info['severity']}")
    prompt_parts.append(f"- 震中: ({disaster_info['epicenter']['lon']}, {disaster_info['epicenter']['lat']})")
    prompt_parts.append("")

    # 指挥中心坐标
    prompt_parts.append(f"**指挥中心坐标**：({command_center['lon']}, {command_center['lat']})")
    prompt_parts.append("")

    # 可用设备
    prompt_parts.append(f"**可用设备**（共{len(devices)}台）：")
    for idx, device in enumerate(devices, start=1):
        caps = ", ".join(device["capabilities"]) if device["capabilities"] else "无"
        prompt_parts.append(
            f"{idx}. [ID: {device['id']}] {device['name']} | 类型: {device['device_type']} | 环境: {device['env_type']} | 能力: {caps}"
        )
    prompt_parts.append("")

    # 侦察目标
    prompt_parts.append(f"**侦察目标**（共{len(targets)}个，已按优先级排序）：")
    for idx, target in enumerate(targets, start=1):
        prompt_parts.append(
            f"{idx}. [ID: {target['id']}] {target['name']} | 坐标: ({target['lon']}, {target['lat']}) | 优先级: {target['priority']} | 危险等级: {target['hazard_level']}"
        )
    prompt_parts.append("")

    # 任务指令
    prompt_parts.append("**请生成侦察方案（JSON格式）**：")
    prompt_parts.append("- 智能分配设备到目标（考虑设备能力、目标特征、环境匹配）")
    prompt_parts.append("- 为每个任务生成：设备选择理由、侦察方法、结果上报内容")
    prompt_parts.append("- 估算每个任务的完成时间（分钟）")

    return "\n".join(prompt_parts)


def _calculate_route_distance(command_center: GeoPoint, target_points: List[TargetPoint]) -> float:
    """计算路线总距离"""
    if not target_points:
        return 0.0
    total_distance = 0.0
    current_lon, current_lat = command_center["lon"], command_center["lat"]
    first_target = target_points[0]
    total_distance += haversine_distance(current_lon, current_lat, first_target["lon"], first_target["lat"])
    for i in range(len(target_points) - 1):
        curr = target_points[i]
        next_t = target_points[i + 1]
        total_distance += haversine_distance(curr["lon"], curr["lat"], next_t["lon"], next_t["lat"])
    return total_distance


def _parse_section(
    section_name: str,
    raw_tasks: List[Dict[str, Any]],
    devices: List[DeviceInput],
    targets: List[TargetPoint],
    command_center: GeoPoint,
    base_time: datetime,
) -> ReconSection:
    """
    解析单个侦察分段（空中/地面/水域）

    功能：
    1. 从LLM返回的原始任务列表中提取该分段的任务
    2. 计算路线距离（基于target_ids）
    3. 计算开始/结束时间（基于estimated_duration_minutes）
    4. 补充设备名称（从device_id反查）

    参数：
        section_name: 分段名称（如"空中侦察"）
        raw_tasks: LLM返回的原始任务列表
        devices: 设备列表（用于反查设备名称）
        targets: 目标列表（用于反查目标名称和坐标）
        command_center: 指挥中心坐标（用于计算路线）
        base_time: 基准开始时间

    返回：
        ReconSection 包含完整的任务详情列表
    """
    tasks: List[TaskDetail] = []
    current_time = base_time

    # 构建设备ID到设备对象的映射（统一转为字符串key）
    device_map = {str(d["id"]): d for d in devices}
    # 构建目标ID到目标对象的映射（统一转为字符串key，兼容UUID/int/str）
    target_map = {str(t["id"]): t for t in targets}

    for raw_task in raw_tasks:
        device_id = str(raw_task.get("device_id", ""))
        device = device_map.get(device_id)

        # 获取目标ID列表（LLM可能返回UUID字符串、int或其他格式）
        target_ids = raw_task.get("target_ids", [])
        # 反查目标名称（统一转为字符串进行查找）
        target_names = [target_map[str(tid)]["name"] for tid in target_ids if str(tid) in target_map]

        # 计算路线距离（指挥中心 → 目标点序列）
        target_objs = [target_map[str(tid)] for tid in target_ids if str(tid) in target_map]
        route_distance = _calculate_route_distance(command_center, target_objs)

        # 解析时长（默认60分钟）
        duration_minutes = int(raw_task.get("estimated_duration_minutes", 60))

        # 计算开始和结束时间
        start_time = current_time
        end_time = start_time + timedelta(minutes=duration_minutes)

        # 构造任务详情
        task_detail = TaskDetail(
            task_number=raw_task.get("task_number", "未编号"),
            task_type=raw_task.get("task_type", "侦察"),
            device_id=device_id,
            device_name=device["name"] if device else "未知设备",
            device_selection_reason=raw_task.get("device_selection_reason", "AI智能匹配"),
            target_ids=target_ids,
            target_names=target_names,
            reconnaissance_detail=raw_task.get("reconnaissance_detail", "详细侦察方案待补充"),
            result_reporting=raw_task.get("result_reporting", "实时回传数据"),
            start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
            estimated_duration_minutes=duration_minutes,
            route_distance_km=round(route_distance, 2),
        )
        tasks.append(task_detail)

        # 更新当前时间（串行执行假设）
        current_time = end_time

    return ReconSection(section_name=section_name, tasks=tasks)


def _parse_llm_response(
    llm_output: Dict[str, Any],
    devices: List[DeviceInput],
    targets: List[TargetPoint],
    command_center: GeoPoint,
    base_time: datetime,
) -> DetailedReconPlan:
    """
    解析并后处理LLM的JSON输出

    功能：
    1. 提取air_tasks/ground_tasks/water_tasks
    2. 为每个分段调用_parse_section进行后处理
    3. 计算全局统计信息（最早/最晚时间、总时长）
    4. 组装完整的DetailedReconPlan

    参数：
        llm_output: LLM返回的JSON对象
        devices: 设备列表
        targets: 目标列表
        command_center: 指挥中心坐标
        base_time: 基准开始时间

    返回：
        DetailedReconPlan 完整的详细侦察方案
    """
    # 提取三类任务
    air_tasks = llm_output.get("air_tasks", [])
    ground_tasks = llm_output.get("ground_tasks", [])
    water_tasks = llm_output.get("water_tasks", [])

    # 解析三个分段
    air_section = None
    if air_tasks:
        air_section = _parse_section("空中侦察", air_tasks, devices, targets, command_center, base_time)

    ground_section = None
    if ground_tasks:
        # 地面任务在空中任务结束后开始
        ground_base_time = base_time
        if air_section and air_section["tasks"]:
            last_air_end = datetime.strptime(air_section["tasks"][-1]["end_time"], "%Y-%m-%d %H:%M:%S")
            ground_base_time = last_air_end
        ground_section = _parse_section("地面侦察", ground_tasks, devices, targets, command_center, ground_base_time)

    water_section = None
    if water_tasks:
        # 水域任务在地面任务结束后开始
        water_base_time = base_time
        if ground_section and ground_section["tasks"]:
            last_ground_end = datetime.strptime(ground_section["tasks"][-1]["end_time"], "%Y-%m-%d %H:%M:%S")
            water_base_time = last_ground_end
        elif air_section and air_section["tasks"]:
            last_air_end = datetime.strptime(air_section["tasks"][-1]["end_time"], "%Y-%m-%d %H:%M:%S")
            water_base_time = last_air_end
        water_section = _parse_section("水域侦察", water_tasks, devices, targets, command_center, water_base_time)

    # 计算全局时间统计
    all_tasks: List[TaskDetail] = []
    if air_section:
        all_tasks.extend(air_section["tasks"])
    if ground_section:
        all_tasks.extend(ground_section["tasks"])
    if water_section:
        all_tasks.extend(water_section["tasks"])

    if all_tasks:
        earliest_start = min(datetime.strptime(t["start_time"], "%Y-%m-%d %H:%M:%S") for t in all_tasks)
        latest_end = max(datetime.strptime(t["end_time"], "%Y-%m-%d %H:%M:%S") for t in all_tasks)
        total_hours = (latest_end - earliest_start).total_seconds() / 3600
    else:
        earliest_start = base_time
        latest_end = base_time
        total_hours = 0.0

    # 提取数据整合说明
    data_integration_desc = llm_output.get(
        "data_integration_desc", "将空中、地面、水域侦察数据整合，形成立体态势图"
    )

    # 构造完整方案（需要从外部传入command_center_name和disaster_info）
    # 注意：这里暂时留空，由generate_recon_plan_with_llm补充
    return {
        "air_recon_section": air_section,
        "ground_recon_section": ground_section,
        "water_recon_section": water_section,
        "data_integration_desc": data_integration_desc,
        "earliest_start_time": earliest_start.strftime("%Y-%m-%d %H:%M:%S"),
        "latest_end_time": latest_end.strftime("%Y-%m-%d %H:%M:%S"),
        "total_estimated_hours": round(total_hours, 2),
    }


def _fallback_to_simple_allocation(
    devices: List[DeviceInput],
    targets: List[TargetPoint],
    disaster_info: DisasterInfo,
    command_center: GeoPoint,
) -> DetailedReconPlan:
    """
    降级策略：当LLM失败时，使用简单规则分配任务

    策略：
    1. 按env_type分组设备（air/land/sea）
    2. 每个设备分配1-2个目标（按优先级）
    3. 生成最基本的任务描述

    参数：
        devices: 设备列表
        targets: 目标列表
        disaster_info: 灾情信息
        command_center: 指挥中心坐标

    返回：
        DetailedReconPlan 简单分配方案
    """
    logger.warning("LLM生成失败，使用简单规则降级分配")

    # 按env_type分组设备
    air_devices = [d for d in devices if d["env_type"] == "air"]
    land_devices = [d for d in devices if d["env_type"] == "land"]
    sea_devices = [d for d in devices if d["env_type"] == "sea"]

    # 目标按优先级排序
    sorted_targets = sorted(targets, key=lambda t: t["priority"], reverse=True)

    base_time = datetime.now()

    # 简单分配：每个设备分配1-2个目标
    def allocate_targets_to_devices(
        device_list: List[DeviceInput], remaining_targets: List[TargetPoint]
    ) -> List[Dict[str, Any]]:
        tasks = []
        targets_per_device = max(1, len(remaining_targets) // max(len(device_list), 1))

        for idx, device in enumerate(device_list):
            start_idx = idx * targets_per_device
            end_idx = start_idx + targets_per_device
            assigned = remaining_targets[start_idx:end_idx]

            if not assigned:
                continue

            task = {
                "task_number": f"{idx + 1}",
                "task_type": "侦察",
                "device_id": str(device["id"]),
                "device_selection_reason": f"设备{device['name']}可执行该环境侦察任务",
                "target_ids": [str(t["id"]) for t in assigned],  # 统一转为字符串
                "reconnaissance_detail": f"对{len(assigned)}个目标进行侦察",
                "result_reporting": "回传实时数据",
                "estimated_duration_minutes": 60 * len(assigned),
            }
            tasks.append(task)

        return tasks

    # 分配任务
    air_tasks = allocate_targets_to_devices(air_devices, sorted_targets[: len(air_devices) * 2])
    ground_tasks = allocate_targets_to_devices(land_devices, sorted_targets[len(air_devices) * 2 :])
    water_tasks = allocate_targets_to_devices(sea_devices, sorted_targets[len(air_devices) * 2 :])

    # 构造伪LLM输出
    llm_output = {
        "air_tasks": air_tasks,
        "ground_tasks": ground_tasks,
        "water_tasks": water_tasks,
        "data_integration_desc": "简单规则分配，LLM失败降级方案",
    }

    # 解析为标准格式
    parsed = _parse_llm_response(llm_output, devices, targets, command_center, base_time)

    # 补充完整字段
    return DetailedReconPlan(
        command_center=command_center,
        command_center_name="指挥中心",
        disaster_info=disaster_info,
        air_recon_section=parsed["air_recon_section"],
        ground_recon_section=parsed["ground_recon_section"],
        water_recon_section=parsed["water_recon_section"],
        data_integration_desc=parsed["data_integration_desc"],
        earliest_start_time=parsed["earliest_start_time"],
        latest_end_time=parsed["latest_end_time"],
        total_estimated_hours=parsed["total_estimated_hours"],
    )


def generate_recon_plan_with_llm(
    devices: List[DeviceInput],
    targets: List[TargetPoint],
    disaster_info: DisasterInfo,
    command_center: GeoPoint,
    llm_client: OpenAI,
    llm_model: str,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    使用LLM智能生成详细侦察方案

    核心流程：
    1. 构造紧凑的LLM提示词（设备、目标、灾情）
    2. 调用LLM生成JSON格式任务分配
    3. 后处理：计算时间、距离、补充设备名称
    4. 降级策略：LLM失败时使用简单规则分配

    参数：
        devices: 可用设备列表（已通过天气评估）
        targets: 侦察目标列表（已按优先级排序）
        disaster_info: 灾情信息
        command_center: 指挥中心坐标
        llm_client: OpenAI客户端
        llm_model: LLM模型名称（如glm-4.6）
        trace_id: 追踪ID（用于日志）

    返回：
        DetailedReconPlan 完整的详细侦察方案

    异常：
        - 如果LLM失败，返回降级方案（不抛异常）
    """
    logger.info(
        "开始LLM智能侦察方案生成",
        device_count=len(devices),
        target_count=len(targets),
        disaster_type=disaster_info["disaster_type"],
        model=llm_model,
        trace_id=trace_id,
    )

    # 输入验证
    if not devices:
        logger.error("设备列表为空，无法生成侦察方案", trace_id=trace_id)
        raise ValueError("设备列表为空")

    if not targets:
        logger.error("目标列表为空，无法生成侦察方案", trace_id=trace_id)
        raise ValueError("目标列表为空")

    # 构造用户提示词
    user_prompt = _build_llm_user_prompt(devices, targets, disaster_info, command_center)

    try:
        # 调用LLM（JSON模式）
        logger.debug("调用LLM生成侦察方案", prompt_length=len(user_prompt), trace_id=trace_id)

        completion = llm_client.chat.completions.create(
            model=llm_model,
            temperature=0.2,  # 低温度保证稳定性
            response_format={"type": "json_object"},  # 强制JSON输出
            messages=[
                {"role": "system", "content": RECON_PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        response_text = completion.choices[0].message.content
        logger.debug("LLM响应原始内容", response_length=len(response_text), trace_id=trace_id)

        # 解析JSON
        llm_output = json.loads(response_text)

        # 后处理：解析并补充计算字段
        base_time = datetime.now()
        parsed_plan = _parse_llm_response(llm_output, devices, targets, command_center, base_time)

        # 补充完整字段
        detailed_plan = DetailedReconPlan(
            command_center=command_center,
            command_center_name="指挥中心",
            disaster_info=disaster_info,
            air_recon_section=parsed_plan["air_recon_section"],
            ground_recon_section=parsed_plan["ground_recon_section"],
            water_recon_section=parsed_plan["water_recon_section"],
            data_integration_desc=parsed_plan["data_integration_desc"],
            earliest_start_time=parsed_plan["earliest_start_time"],
            latest_end_time=parsed_plan["latest_end_time"],
            total_estimated_hours=parsed_plan["total_estimated_hours"],
        )

        logger.info(
            "LLM侦察方案生成成功",
            air_tasks=len(parsed_plan["air_recon_section"]["tasks"]) if parsed_plan["air_recon_section"] else 0,
            ground_tasks=len(parsed_plan["ground_recon_section"]["tasks"])
            if parsed_plan["ground_recon_section"]
            else 0,
            water_tasks=len(parsed_plan["water_recon_section"]["tasks"]) if parsed_plan["water_recon_section"] else 0,
            total_hours=parsed_plan["total_estimated_hours"],
            trace_id=trace_id,
        )

        return detailed_plan

    except json.JSONDecodeError as e:
        logger.error("LLM返回内容无法解析为JSON，使用降级方案", error=str(e), response=response_text[:500], trace_id=trace_id)
        return _fallback_to_simple_allocation(devices, targets, disaster_info, command_center)

    except Exception as e:
        logger.error(
            "LLM调用失败，使用降级方案", error=str(e), error_type=type(e).__name__, model=llm_model, trace_id=trace_id
        )
        return _fallback_to_simple_allocation(devices, targets, disaster_info, command_center)
