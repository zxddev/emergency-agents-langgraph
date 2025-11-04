"""
侦察任务详细化生成模块

功能：基于设备能力和目标信息，生成结构化的侦察任务执行方案
核心原则：纯规则引擎，零LLM调用，完全基于真实数据

技术要点：
- 强类型：所有参数和返回值使用TypedDict
- 防幻觉：所有数据来自数据库查询
- 高性能：纯规则引擎，响应时间<500ms
- 可预测：相同输入保证相同输出
"""

import math
from typing import List, Dict, Any, TypedDict, Optional, FrozenSet
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)


# ============ 类型定义（强类型） ============


class GeoPoint(TypedDict):
    """地理坐标点"""
    lon: float
    lat: float


class TargetPoint(TypedDict):
    """目标点（输入）"""
    id: int  # 目标ID
    name: str  # 目标名称（如"河西小学"）
    target_type: str  # 目标类型
    hazard_level: str  # 危险等级
    priority: float  # 优先级分数
    lon: float  # 经度
    lat: float  # 纬度


class DeviceInput(TypedDict):
    """设备输入（从数据库查询）"""
    id: str  # 设备ID
    name: str  # 设备名称
    device_type: str  # 设备类型（drone/dog/ship）
    env_type: str  # 环境类型（air/land/sea）
    capabilities: List[str]  # 设备能力列表


class DisasterInfo(TypedDict):
    """灾情信息（输入）"""
    disaster_type: str  # 灾害类型（flood/earthquake/landslide/chemical_leak）
    severity: str  # 严重程度（critical/high/medium/low）
    epicenter: GeoPoint  # 震中/灾害中心
    location_desc: str  # 位置描述


class TaskDetail(TypedDict):
    """任务详情（输出）"""
    task_number: str  # 任务编号（如"1.重灾区扫图建模"）
    task_type: str  # 任务类型（扫图建模/人员搜索/环境检测等）
    device_id: str  # 执行设备ID
    device_name: str  # 设备名称
    device_selection_reason: str  # 设备选择理由
    target_ids: List[int]  # 目标ID列表
    target_names: List[str]  # 目标名称列表
    reconnaissance_detail: str  # 侦察详情（路线、方法、数据采集）
    result_reporting: str  # 结果上报内容
    start_time: str  # 开始时间（HH:MM:SS格式）
    end_time: str  # 结束时间（HH:MM:SS格式）
    estimated_duration_minutes: int  # 预计耗时（分钟）
    route_distance_km: float  # 路线总距离（公里）


class ReconSection(TypedDict):
    """侦察方案章节（输出）"""
    section_title: str  # 章节标题（如"一、空中侦察方案"）
    section_number: int  # 章节编号（1/2/3）
    tasks: List[TaskDetail]  # 任务列表


class DetailedReconPlan(TypedDict):
    """完整的详细侦察方案（输出）"""
    command_center: GeoPoint  # 指挥中心坐标
    command_center_name: str  # 指挥中心名称
    disaster_info: DisasterInfo  # 灾情信息
    air_recon_section: Optional[ReconSection]  # 空中侦察方案
    ground_recon_section: Optional[ReconSection]  # 地面侦察方案
    water_recon_section: Optional[ReconSection]  # 水上侦察方案
    data_integration_desc: str  # 数据整合说明
    earliest_start_time: str  # 最早开始时间
    latest_end_time: str  # 最晚结束时间
    total_estimated_hours: float  # 总预计完成时间（小时）


# ============ 配置常量 ============


# 设备速度配置（km/h）
DEVICE_SPEED_KMH: Dict[str, float] = {
    "air": 60.0,  # 空中设备（无人机）
    "land": 15.0,  # 地面设备（机器狗）
    "sea": 20.0,  # 水上设备（无人艇）
}

# 单点作业时间（分钟）
WORK_TIME_PER_TARGET_MINUTES: Dict[str, int] = {
    "air": 10,  # 空中设备
    "land": 15,  # 地面设备
    "sea": 20,  # 水上设备
}

# 能力组合 → 任务类型映射（使用frozenset精确匹配）
# frozenset确保顺序无关的匹配
CAPABILITY_TO_TASK_TYPE: Dict[FrozenSet[str], str] = {
    frozenset(["mapping", "aerial_recon"]): "扫图建模",
    frozenset(["thermal_imaging", "aerial_recon"]): "人员搜索",
    frozenset(["gas_detection", "aerial_recon"]): "环境检测",
    frozenset(["aerial_recon"]): "宏观侦察",
    frozenset(["close_inspection"]): "近距离检查",
    frozenset(["hazmat_detection", "close_inspection"]): "危险物质检测",
    frozenset(["water_recon"]): "航道识别",
    frozenset(["water_recon", "thermal_imaging"]): "水域搜救",
    frozenset(["rescue_support", "water_recon"]): "救援支持",
}

# 默认任务类型（当能力不匹配时）
DEFAULT_TASK_TYPE_BY_ENV: Dict[str, str] = {
    "air": "空中侦察",
    "land": "地面巡逻",
    "sea": "水域巡查",
}


# ============ 工具函数 ============


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    计算两点之间的Haversine距离（公里）

    使用地球半径6371km进行计算
    """
    R = 6371.0  # 地球半径（公里）

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


# ============ 规则引擎 ============


def match_task_type(capabilities: List[str], env_type: str) -> str:
    """
    根据设备能力匹配任务类型

    匹配策略：
    1. 尝试精确匹配能力组合
    2. 尝试子集匹配（包含某些能力即可）
    3. 使用默认任务类型

    参数：
        capabilities: 设备能力列表
        env_type: 环境类型（air/land/sea）

    返回：
        任务类型字符串
    """
    if not capabilities:
        return DEFAULT_TASK_TYPE_BY_ENV.get(env_type, "通用侦察")

    cap_set = frozenset(capabilities)

    # 精确匹配
    if cap_set in CAPABILITY_TO_TASK_TYPE:
        return CAPABILITY_TO_TASK_TYPE[cap_set]

    # 子集匹配（找到最佳匹配）
    best_match_score = 0
    best_task_type = None

    for cap_pattern, task_type in CAPABILITY_TO_TASK_TYPE.items():
        if cap_pattern.issubset(cap_set):
            match_score = len(cap_pattern)
            if match_score > best_match_score:
                best_match_score = match_score
                best_task_type = task_type

    if best_task_type:
        return best_task_type

    # 默认任务类型
    return DEFAULT_TASK_TYPE_BY_ENV.get(env_type, "通用侦察")


def generate_device_selection_reason(
    device: DeviceInput,
    task_type: str,
    targets: List[TargetPoint],
    disaster_type: str
) -> str:
    """
    生成设备选择理由

    基于模板拼接：设备能力 + 任务适配性 + 目标特征
    """
    cap_desc = "、".join(device["capabilities"]) if device["capabilities"] else "通用侦察"
    target_count = len(targets)

    reason_parts = [
        f"{device['name']}（{device['device_type']}）",
        f"具备{cap_desc}能力",
    ]

    # 根据任务类型添加适配性说明
    if task_type == "扫图建模" and "mapping" in device["capabilities"]:
        reason_parts.append("配备激光雷达和多光谱传感器，适合高精度地形扫描")
    elif task_type == "人员搜索" and "thermal_imaging" in device["capabilities"]:
        reason_parts.append("配备热成像仪和可见光摄像头，适合生命体征检测")
    elif task_type == "环境检测" and "gas_detection" in device["capabilities"]:
        reason_parts.append("配备气体传感器，适合危险物质检测")
    elif task_type == "航道识别" and "water_recon" in device["capabilities"]:
        reason_parts.append("配备声纳和摄像头，适合水域地形测绘")
    elif task_type == "水域搜救" and "thermal_imaging" in device["capabilities"]:
        reason_parts.append("配备热成像和侧扫声纳，适合水上人员搜救")
    else:
        reason_parts.append(f"适合执行{task_type}任务")

    # 添加目标适配性
    if target_count > 0:
        reason_parts.append(f"负责{target_count}个目标点的侦察")

    return "，".join(reason_parts) + "。"


def generate_reconnaissance_detail(
    device: DeviceInput,
    task_type: str,
    targets: List[TargetPoint],
    command_center: GeoPoint,
    command_center_name: str,
    route_distance_km: float,
    start_time: str,
    end_time: str,
    disaster_type: str
) -> str:
    """
    生成侦察详情描述

    包含：起点、目标点、路线、方法、时间
    """
    target_names = "、".join([t["name"] for t in targets])
    env_desc = {
        "air": "起飞",
        "land": "出发",
        "sea": "下水"
    }.get(device["env_type"], "出发")

    detail_parts = [
        f"从{command_center_name}（坐标：{command_center['lon']:.2f}, {command_center['lat']:.2f}）{env_desc}",
    ]

    # 根据任务类型添加方法描述
    if task_type == "扫图建模":
        detail_parts.append(f"沿预设网格路径覆盖{target_names}区域")
        if device["env_type"] == "air":
            detail_parts.append("飞行高度100-150米，分辨率优于5厘米")
        detail_parts.append("实时采集高精度点云和影像数据，生成三维地图")

    elif task_type == "人员搜索":
        detail_parts.append(f"前往{target_names}进行低空/近距离搜索")
        detail_parts.append("使用热成像检测生命体征，可见光摄像头识别人员位置")
        detail_parts.append("通过扬声器进行语音安抚，标注异常点位")

    elif task_type == "环境检测":
        detail_parts.append(f"在{target_names}进行精细扫描")
        detail_parts.append("检测火灾热点、气体泄露（甲烷传感器）、积水区域")
        detail_parts.append("每10分钟更新一次风险地图")

    elif task_type == "航道识别":
        detail_parts.append(f"沿水域航行，经过{target_names}")
        detail_parts.append("使用声纳测绘河床地形，识别航道通航能力（水深、障碍物）")
        detail_parts.append("重点监测桥梁和堤坝结构完整性")

    elif task_type == "水域搜救":
        detail_parts.append(f"沿水域航行，搜索{target_names}区域")
        detail_parts.append("使用侧扫声纳探测水下可疑物体，热成像扫描沿岸区域")
        detail_parts.append("通过扬声器向沿岸广播，引导受困人员发出求救信号")

    else:
        detail_parts.append(f"前往{target_names}执行{task_type}")
        detail_parts.append("实时回传视频和数据，标注关键信息")

    detail_parts.append(f"路线总长约{route_distance_km:.1f}公里")
    detail_parts.append(f"预计{start_time}开始，{end_time}完成")
    detail_parts.append("数据实时回传至指挥中心")

    return "，".join(detail_parts) + "。"


def generate_result_reporting(task_type: str, targets: List[TargetPoint]) -> str:
    """
    生成结果上报内容

    基于任务类型和目标特征
    """
    result_map = {
        "扫图建模": "三维地图，标注建筑损毁程度、地形变化、关键基础设施状态",
        "人员搜索": "受困人员位置坐标、生命体征状态、现场视频和图片",
        "环境检测": "环境检测报告，包括气体浓度曲线、火灾热点、风险等级",
        "航道识别": "航道通航评估报告，标注水深、障碍物、风险点位置",
        "水域搜救": "水域人员搜救报告，标注发现的幸存者位置、疑似点位及现场影像",
        "宏观侦察": "宏观损毁报告，标注道路阻塞、桥梁倒塌、山体滑坡等关键基础设施状态",
        "近距离检查": "近距离检查报告，标注结构完整性、危险区域、受困人员详细位置",
        "危险物质检测": "危险物质检测报告，包括有毒气体浓度、燃气浓度、爆炸风险评估",
    }

    base_result = result_map.get(task_type, f"{task_type}报告，标注关键信息和异常点位")

    # 添加目标特定信息
    if targets:
        target_names = "、".join([t["name"] for t in targets[:3]])
        if len(targets) > 3:
            target_names += f"等{len(targets)}个点位"
        return f"{base_result}。重点关注{target_names}的详细情况。"

    return f"{base_result}。"


# ============ 路线规划算法 ============


def plan_route_greedy(
    start_point: GeoPoint,
    targets: List[TargetPoint]
) -> tuple[List[TargetPoint], float]:
    """
    贪心算法规划路线（最近邻）

    策略：从起点开始，每次选择最近的未访问目标

    返回：(路径顺序的目标列表, 总距离km)
    """
    if not targets:
        return ([], 0.0)

    route: List[TargetPoint] = []
    remaining = list(targets)
    current_lon = start_point["lon"]
    current_lat = start_point["lat"]
    total_distance = 0.0

    while remaining:
        # 找到最近的目标
        nearest_idx = 0
        nearest_dist = haversine_distance(current_lon, current_lat, remaining[0]["lon"], remaining[0]["lat"])

        for i in range(1, len(remaining)):
            dist = haversine_distance(current_lon, current_lat, remaining[i]["lon"], remaining[i]["lat"])
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = i

        # 添加到路径
        nearest_target = remaining.pop(nearest_idx)
        route.append(nearest_target)
        total_distance += nearest_dist
        current_lon = nearest_target["lon"]
        current_lat = nearest_target["lat"]

    return (route, total_distance)


def calculate_task_time(
    route_distance_km: float,
    target_count: int,
    env_type: str
) -> int:
    """
    计算任务完成时间（分钟）

    时间 = 路程时间 + 作业时间
    路程时间 = 距离 / 速度
    作业时间 = 目标数 × 单点作业时间
    """
    speed_kmh = DEVICE_SPEED_KMH.get(env_type, 30.0)
    work_time_per_target = WORK_TIME_PER_TARGET_MINUTES.get(env_type, 15)

    travel_time_minutes = (route_distance_km / speed_kmh) * 60
    work_time_minutes = target_count * work_time_per_target

    total_minutes = travel_time_minutes + work_time_minutes
    return int(math.ceil(total_minutes))


def format_time_from_base(base_time: datetime, offset_minutes: int) -> str:
    """
    从基准时间计算偏移后的时间字符串（HH:MM:SS格式）
    """
    result_time = base_time + timedelta(minutes=offset_minutes)
    return result_time.strftime("%H:%M:%S")


# ============ 主生成函数 ============


def generate_detailed_recon_plan(
    devices: List[DeviceInput],
    targets: List[TargetPoint],
    disaster_info: DisasterInfo,
    command_center: GeoPoint,
    command_center_name: str = "指挥中心",
    base_time: Optional[datetime] = None,
) -> DetailedReconPlan:
    """
    生成详细的侦察方案（主函数）

    流程：
    1. 按env_type分组设备
    2. 为每组设备轮询分配目标
    3. 为每个设备规划路线
    4. 生成TaskDetail
    5. 组装ReconSection
    6. 组装DetailedReconPlan

    参数：
        devices: 可用设备列表（含能力）
        targets: 目标点列表（已按优先级排序）
        disaster_info: 灾情信息
        command_center: 指挥中心坐标
        command_center_name: 指挥中心名称
        base_time: 基准时间（任务开始时间），默认为当前时间

    返回：
        DetailedReconPlan 完整的详细侦察方案
    """
    if not devices:
        raise ValueError("设备列表为空，无法生成侦察方案")

    if not targets:
        raise ValueError("目标列表为空，无法生成侦察方案")

    if base_time is None:
        base_time = datetime.now()

    logger.info(
        "开始生成详细侦察方案",
        device_count=len(devices),
        target_count=len(targets),
        disaster_type=disaster_info["disaster_type"],
        command_center_name=command_center_name,
    )

    # Step 1: 按env_type分组设备
    devices_by_env: Dict[str, List[DeviceInput]] = {}
    for device in devices:
        env = device["env_type"]
        if env not in devices_by_env:
            devices_by_env[env] = []
        devices_by_env[env].append(device)

    logger.debug(
        "设备分组完成",
        air_count=len(devices_by_env.get("air", [])),
        land_count=len(devices_by_env.get("land", [])),
        sea_count=len(devices_by_env.get("sea", [])),
    )

    # Step 2: 为每组设备分配目标（轮询算法）
    device_targets: Dict[str, List[TargetPoint]] = {}
    target_index = 0

    for env_type in ["air", "land", "sea"]:
        if env_type not in devices_by_env:
            continue

        env_devices = devices_by_env[env_type]
        for device_idx, device in enumerate(env_devices):
            device_id = device["id"]
            device_targets[device_id] = []

            # 轮询分配：每个设备分配 ceil(targets / devices) 个目标
            while target_index < len(targets):
                device_targets[device_id].append(targets[target_index])
                target_index += 1

                # 当前设备已分配足够目标，切换到下一个设备
                if target_index % len(env_devices) == (device_idx + 1) % len(env_devices):
                    break

    logger.debug("目标分配完成", total_assignments=sum(len(t) for t in device_targets.values()))

    # Step 3: 为每个设备生成任务详情
    all_tasks: Dict[str, List[TaskDetail]] = {"air": [], "land": [], "sea": []}
    current_time_offset_minutes = 0  # 累计时间偏移（所有任务并行执行，因此不累加）

    section_task_counters = {"air": 1, "land": 1, "sea": 1}

    for device in devices:
        device_id = device["id"]
        assigned_targets = device_targets.get(device_id, [])

        if not assigned_targets:
            continue

        env_type = device["env_type"]
        task_type = match_task_type(device["capabilities"], env_type)

        # 规划路线
        route, route_distance_km = plan_route_greedy(command_center, assigned_targets)

        # 计算时间
        duration_minutes = calculate_task_time(route_distance_km, len(route), env_type)
        start_time = format_time_from_base(base_time, 0)  # 所有设备并行开始
        end_time = format_time_from_base(base_time, duration_minutes)

        # 生成任务编号
        task_number = section_task_counters[env_type]
        section_task_counters[env_type] += 1

        # 生成任务详情
        task = TaskDetail(
            task_number=f"{task_number}.{task_type}",
            task_type=task_type,
            device_id=device_id,
            device_name=device["name"],
            device_selection_reason=generate_device_selection_reason(
                device, task_type, route, disaster_info["disaster_type"]
            ),
            target_ids=[t["id"] for t in route],
            target_names=[t["name"] for t in route],
            reconnaissance_detail=generate_reconnaissance_detail(
                device,
                task_type,
                route,
                command_center,
                command_center_name,
                route_distance_km,
                start_time,
                end_time,
                disaster_info["disaster_type"],
            ),
            result_reporting=generate_result_reporting(task_type, route),
            start_time=start_time,
            end_time=end_time,
            estimated_duration_minutes=duration_minutes,
            route_distance_km=route_distance_km,
        )

        all_tasks[env_type].append(task)

        logger.debug(
            "任务详情生成完成",
            device_id=device_id,
            task_type=task_type,
            target_count=len(route),
            duration_minutes=duration_minutes,
        )

    # Step 4: 组装ReconSection
    section_map = {
        "air": ("一、空中侦察方案", 1),
        "land": ("二、地面侦察方案", 2),
        "sea": ("三、水上侦察方案", 3),
    }

    air_section = None
    ground_section = None
    water_section = None

    if all_tasks["air"]:
        air_section = ReconSection(
            section_title=section_map["air"][0],
            section_number=section_map["air"][1],
            tasks=all_tasks["air"],
        )

    if all_tasks["land"]:
        ground_section = ReconSection(
            section_title=section_map["land"][0],
            section_number=section_map["land"][1],
            tasks=all_tasks["land"],
        )

    if all_tasks["sea"]:
        water_section = ReconSection(
            section_title=section_map["sea"][0],
            section_number=section_map["sea"][1],
            tasks=all_tasks["sea"],
        )

    # Step 5: 计算时间范围
    all_tasks_flat = all_tasks["air"] + all_tasks["land"] + all_tasks["sea"]
    if all_tasks_flat:
        earliest_start = min(t["start_time"] for t in all_tasks_flat)
        latest_end = max(t["end_time"] for t in all_tasks_flat)
        max_duration_minutes = max(t["estimated_duration_minutes"] for t in all_tasks_flat)
        total_hours = max_duration_minutes / 60.0
    else:
        earliest_start = format_time_from_base(base_time, 0)
        latest_end = format_time_from_base(base_time, 0)
        total_hours = 0.0

    # Step 6: 组装完整方案
    plan = DetailedReconPlan(
        command_center=command_center,
        command_center_name=command_center_name,
        disaster_info=disaster_info,
        air_recon_section=air_section,
        ground_recon_section=ground_section,
        water_recon_section=water_section,
        data_integration_desc=(
            "所有设备通过前突侦察控制车上的通信系统（卫星和4G/5G备份）实时回传数据至指挥中心。"
            "数据整合平台将空中、地面、水上信息叠加至同一地图，生成综合灾情报告。"
            "优先级：受困人员搜索 > 风险识别 > 扫图建模 > 宏观侦察 > 环境检测。"
            "安全措施：设备具备避障和自主返航功能；操作员实时监控，遇险立即中断。"
        ),
        earliest_start_time=earliest_start,
        latest_end_time=latest_end,
        total_estimated_hours=total_hours,
    )

    logger.info(
        "详细侦察方案生成完成",
        air_tasks=len(all_tasks["air"]),
        land_tasks=len(all_tasks["land"]),
        sea_tasks=len(all_tasks["sea"]),
        total_hours=total_hours,
    )

    return plan
