"""
设备-目标智能匹配规则引擎

功能：
- 根据设备能力和目标特征进行智能匹配
- 基于规则的确定性分配（无需LLM，50ms内完成）
- 确保每个设备至少分配1个目标，每个目标至少被1个设备覆盖

核心算法：
1. 计算设备-目标匹配分数（环境匹配 + 能力匹配 + 优先级加权）
2. 贪心分配：高优先级目标优先，选择最佳设备
3. 负载均衡：确保设备任务量均衡，避免某些设备过载
"""

from __future__ import annotations

import math
from enum import Enum
from typing import List, Dict, Any, Union
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


# ============ 枚举定义 ============


class DeviceCapabilityLevel(Enum):
    """设备能力等级（根据capabilities推断）"""
    ADVANCED = 3  # 高级（如：激光雷达、热成像、夜视、多光谱）
    STANDARD = 2  # 标准（如：高清摄像、GPS定位、数据传输）
    BASIC = 1     # 基础（如：普通摄像头）


# ============ 类型定义 ============


class DeviceInput:
    """设备输入（使用TypedDict定义在recon_llm_planner.py）"""
    id: str
    name: str
    device_type: str
    env_type: str  # 'air' / 'land' / 'sea'
    capabilities: List[str]


class TargetPoint:
    """目标点（使用TypedDict定义在recon_llm_planner.py）"""
    id: Union[int, str, UUID]
    name: str
    target_type: str
    hazard_level: str  # 'critical' / 'high' / 'medium' / 'low'
    priority: float  # 0-100分制
    lon: float
    lat: float


# ============ 辅助函数 ============


def infer_capability_level(capabilities: List[str]) -> DeviceCapabilityLevel:
    """
    根据capabilities列表推断设备能力等级

    评分规则：
    - 包含高级关键词 → ADVANCED (3分)
    - 包含标准关键词 → STANDARD (2分)
    - 其他 → BASIC (1分)
    """
    advanced_keywords = [
        "激光雷达", "热成像", "夜视", "多光谱", "红外",
        "LiDAR", "thermal", "infrared", "hyperspectral"
    ]
    standard_keywords = [
        "高清摄像", "GPS", "定位", "数据传输", "云台",
        "HD", "4K", "positioning", "gimbal"
    ]

    capability_str = " ".join(capabilities).lower()

    # 检查是否包含高级关键词
    if any(kw.lower() in capability_str for kw in advanced_keywords):
        return DeviceCapabilityLevel.ADVANCED

    # 检查是否包含标准关键词
    if any(kw.lower() in capability_str for kw in standard_keywords):
        return DeviceCapabilityLevel.STANDARD

    # 默认基础等级
    return DeviceCapabilityLevel.BASIC


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


# ============ 匹配规则 ============


class MatchingRule:
    """设备-目标匹配规则"""

    @staticmethod
    def calculate_match_score(
        device: Dict[str, Any],
        target: Dict[str, Any],
        disaster_type: str,
        command_center: Dict[str, float] = None
    ) -> float:
        """
        计算设备-目标匹配分数（0-100分）

        评分维度：
        1. 环境匹配 (40分)：env_type与目标环境的匹配度
        2. 能力匹配 (30分)：capabilities与hazard_level的匹配度
        3. 优先级加权 (20分)：高优先级目标给能力强的设备
        4. 距离因素 (10分)：设备与目标的距离（可选）
        """
        score = 0.0

        # 1. 环境匹配 (40分)
        env_type = device.get("env_type", "").lower()
        target_type = target.get("target_type", "").lower()
        target_name = target.get("name", "").lower()

        if env_type == "air":
            # 空中设备适合：广域监控、快速侦察、全局扫描
            if any(keyword in target_type or keyword in target_name for keyword in
                   ["广域", "监控", "重灾区", "搜索", "扫图", "建模", "aerial", "overview"]):
                score += 40
            else:
                score += 30  # 空中设备可以覆盖任何目标，但不是最优

        elif env_type == "land":
            # 地面设备适合：近距离侦察、复杂地形、建筑物内部
            if any(keyword in target_type or keyword in target_name for keyword in
                   ["建筑", "道路", "地质", "滑坡", "裂缝", "桥梁", "社区", "building", "road", "bridge"]):
                score += 40
            else:
                score += 25

        elif env_type == "sea" or env_type == "water":
            # 水域设备适合：水域侦察、洪水区域、水质检测
            if disaster_type.lower() in ["flood", "洪水", "水灾"]:
                score += 40
            elif any(keyword in target_type or keyword in target_name for keyword in
                     ["水", "河", "湖", "江", "水库", "water", "river", "flood"]):
                score += 40
            else:
                score += 10  # 水域设备不适合陆地任务

        else:
            # 混合或其他环境类型，给予中等分数
            score += 25

        # 2. 能力匹配 (30分)
        device_capability_level = infer_capability_level(device.get("capabilities", []))
        hazard_level = target.get("hazard_level", "medium").lower()

        if hazard_level == "critical":
            # 极高危目标需要高级设备
            if device_capability_level == DeviceCapabilityLevel.ADVANCED:
                score += 30
            elif device_capability_level == DeviceCapabilityLevel.STANDARD:
                score += 20
            else:
                score += 10

        elif hazard_level == "high":
            # 高危目标需要标准或高级设备
            if device_capability_level.value >= DeviceCapabilityLevel.STANDARD.value:
                score += 30
            else:
                score += 20

        else:
            # 中低危目标，基础设备即可
            score += 25

        # 3. 优先级加权 (20分)
        priority = target.get("priority", 50.0)  # 默认50分
        priority_bonus = min(20, priority / 5.0)  # priority是0-100，映射到0-20
        score += priority_bonus

        # 4. 距离因素 (10分) - 优先分配距离近的设备
        if command_center:
            device_lon = device.get("lon", command_center.get("lon", 0))
            device_lat = device.get("lat", command_center.get("lat", 0))
            target_lon = target.get("lon", 0)
            target_lat = target.get("lat", 0)

            distance_km = haversine_distance(device_lon, device_lat, target_lon, target_lat)

            # 距离越近分数越高（10km内满分，50km外0分）
            if distance_km < 10:
                distance_score = 10
            elif distance_km < 50:
                distance_score = 10 * (1 - (distance_km - 10) / 40)
            else:
                distance_score = 0

            score += distance_score
        else:
            # 如果没有位置信息，给予中等距离分数
            score += 5

        return score


# ============ 核心分配算法 ============


def smart_allocate(
    devices: List[Dict[str, Any]],
    targets: List[Dict[str, Any]],
    disaster_type: str,
    command_center: Dict[str, float] = None,
    trace_id: str = None
) -> Dict[str, List[str]]:
    """
    智能分配设备到目标

    算法流程：
    1. 计算所有设备-目标的匹配分数矩阵 (M x N)
    2. 贪心分配：
       - 优先分配高优先级目标
       - 为每个目标选择得分最高的设备
    3. 负载均衡：
       - 确保每个设备至少分配1个目标
       - 避免某个设备任务过载（不超过平均任务数+2）

    参数：
        devices: 设备列表（每个设备包含id, name, env_type, capabilities等）
        targets: 目标列表（每个目标包含id, name, priority, hazard_level等）
        disaster_type: 灾害类型（用于环境匹配判断）
        command_center: 指挥中心坐标（可选，用于距离计算）
        trace_id: 追踪ID（用于日志）

    返回：
        {
            "device_id_1": ["target_id_1", "target_id_3"],
            "device_id_2": ["target_id_2"],
            ...
        }
    """
    logger.info(
        "开始智能设备-目标分配",
        device_count=len(devices),
        target_count=len(targets),
        disaster_type=disaster_type,
        trace_id=trace_id
    )

    # 边界检查
    if not devices:
        logger.error("设备列表为空，无法分配", trace_id=trace_id)
        return {}

    if not targets:
        logger.warning("目标列表为空，返回空分配", trace_id=trace_id)
        return {str(d["id"]): [] for d in devices}

    # 初始化分配结果
    allocation: Dict[str, List[str]] = {str(d["id"]): [] for d in devices}
    target_assigned: Dict[str, bool] = {str(t["id"]): False for t in targets}

    # 1. 计算匹配矩阵
    match_matrix = []
    for device in devices:
        for target in targets:
            score = MatchingRule.calculate_match_score(
                device, target, disaster_type, command_center
            )
            match_matrix.append({
                "device_id": str(device["id"]),
                "target_id": str(target["id"]),
                "score": score,
                "target_priority": target.get("priority", 50.0)
            })

    logger.debug(
        "匹配矩阵计算完成",
        matrix_size=len(match_matrix),
        trace_id=trace_id
    )

    # 2. 按目标优先级和匹配分数排序
    match_matrix.sort(
        key=lambda x: (x["target_priority"], x["score"]),
        reverse=True
    )

    # 3. 贪心分配（优先处理高优先级目标）
    avg_load = len(targets) / len(devices)
    max_load = avg_load + 2  # 单个设备最多分配平均值+2个任务

    for match in match_matrix:
        device_id = match["device_id"]
        target_id = match["target_id"]

        # 检查目标是否已分配
        if target_assigned[target_id]:
            continue

        # 检查设备负载（避免过载）
        if len(allocation[device_id]) >= max_load:
            continue

        # 分配
        allocation[device_id].append(target_id)
        target_assigned[target_id] = True

    logger.info(
        "贪心分配完成",
        assigned_targets=sum(target_assigned.values()),
        total_targets=len(targets),
        trace_id=trace_id
    )

    # 4. 确保每个设备至少有1个任务（负载均衡兜底）
    unassigned_targets = [tid for tid, assigned in target_assigned.items() if not assigned]
    idle_devices = [did for did, targets_list in allocation.items() if not targets_list]

    for device_id in idle_devices:
        if unassigned_targets:
            target_id = unassigned_targets.pop(0)
            allocation[device_id].append(target_id)
            target_assigned[target_id] = True
            logger.debug(
                "为空闲设备分配任务",
                device_id=device_id,
                target_id=target_id,
                trace_id=trace_id
            )

    # 5. 如果还有未分配目标，分配给任务最少的设备
    while unassigned_targets:
        # 找到任务最少的设备
        min_device = min(allocation.keys(), key=lambda d: len(allocation[d]))
        target_id = unassigned_targets.pop(0)
        allocation[min_device].append(target_id)
        target_assigned[target_id] = True
        logger.debug(
            "剩余目标分配给任务最少设备",
            device_id=min_device,
            target_id=target_id,
            trace_id=trace_id
        )

    # 6. 统计分配结果
    task_counts = [len(v) for v in allocation.values()]
    logger.info(
        "智能分配完成",
        total_devices=len(devices),
        total_targets=len(targets),
        min_tasks_per_device=min(task_counts) if task_counts else 0,
        max_tasks_per_device=max(task_counts) if task_counts else 0,
        avg_tasks_per_device=sum(task_counts) / len(task_counts) if task_counts else 0,
        coverage_rate=sum(target_assigned.values()) / len(targets) if targets else 0,
        trace_id=trace_id
    )

    return allocation


# ============ 分组辅助函数 ============


def group_allocation_by_env_type(
    allocation: Dict[str, List[str]],
    devices: List[Dict[str, Any]]
) -> Dict[str, Dict[str, List[str]]]:
    """
    按设备环境类型分组分配结果

    参数：
        allocation: 原始分配结果 {device_id: [target_ids]}
        devices: 设备列表

    返回：
        {
            "air": {device_id: [target_ids]},
            "land": {device_id: [target_ids]},
            "sea": {device_id: [target_ids]}
        }
    """
    grouped = {
        "air": {},
        "land": {},
        "sea": {}
    }

    # 创建设备ID到设备对象的映射
    device_map = {str(d["id"]): d for d in devices}

    for device_id, target_ids in allocation.items():
        device = device_map.get(device_id)
        if not device:
            continue

        env_type = device.get("env_type", "").lower()

        if env_type == "air":
            grouped["air"][device_id] = target_ids
        elif env_type == "land":
            grouped["land"][device_id] = target_ids
        elif env_type in ["sea", "water"]:
            grouped["sea"][device_id] = target_ids
        else:
            # 默认归为地面
            grouped["land"][device_id] = target_ids

    return grouped
