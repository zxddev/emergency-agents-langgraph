"""
批次分配模块

功能：将侦察目标分配给可用设备，生成批次执行计划
算法：Round-robin（轮询）分配，确保负载均衡

技术要点：
- 纯函数：无副作用，可测试性强
- 强类型：所有参数和返回值使用TypedDict
- 确定性：相同输入保证相同输出
- 优先级保证：目标列表必须已排序（高优先级优先）
"""

from typing import List, TypedDict, Union
from uuid import UUID
import structlog

logger = structlog.get_logger(__name__)


# ============ 类型定义（强类型） ============


class Target(TypedDict):
    """侦察目标（输入）"""

    id: Union[int, str, UUID]  # 目标ID（支持int/string/UUID）
    name: str  # 目标名称
    priority_score: float  # 优先级分数（越高越重要）
    lon: float  # 经度
    lat: float  # 纬度


class Device(TypedDict):
    """设备信息（输入）"""

    id: Union[int, str]  # 设备ID（支持int/string，数据库实际为string如'dog-dv-1'）
    name: str  # 设备名称
    device_type: str  # 设备类型（drone/ship/dog）


class Batch(TypedDict):
    """批次（输出）"""

    device_id: Union[int, str]  # 执行该批次的设备ID（支持int/string）
    device_name: str  # 设备名称
    target_ids: List[Union[int, str, UUID]]  # 该批次包含的目标ID列表（支持int/string/UUID）
    estimated_completion_minutes: int  # 预计完成时间（分钟）


class AllocationResult(TypedDict):
    """分配结果（输出）"""

    batches: List[Batch]  # 批次列表
    total_targets: int  # 总目标数
    total_devices: int  # 总设备数
    max_batch_size: int  # 最大批次大小（设备任务最不均衡时的差值）


# ============ 核心函数 ============


def allocate_batches(
    targets: List[Target],
    devices: List[Device],
    avg_time_per_target_minutes: int = 15,
) -> AllocationResult:
    """
    使用Round-robin算法分配侦察批次

    算法逻辑：
    1. 前提：targets已按priority_score降序排序（外部保证）
    2. 初始化：为每个设备创建空批次
    3. 轮询分配：遍历目标，轮流分配给设备（idx % len(devices)）
    4. 计算时间：批次时间 = 目标数 × 单个目标平均时间

    优点：
    - 简单明确，没有复杂优化
    - 优先级高的目标优先执行（因为targets已排序）
    - 负载均衡（每台设备任务数相差不超过1）
    - 完全确定性，可测试

    参数：
        targets: 侦察目标列表（必须已按priority_score降序排序）
        devices: 可用设备列表（非空）
        avg_time_per_target_minutes: 单个目标平均侦察时间（分钟），默认15分钟

    返回：
        AllocationResult 包含批次列表和统计信息

    异常：
        - ValueError: devices为空或targets为空
    """
    # 参数验证：不做任何fallback，直接暴露问题
    if not devices:
        raise ValueError("设备列表为空，无法分配批次。请检查设备筛选逻辑或请求装备增援。")

    if not targets:
        raise ValueError("目标列表为空，无法分配批次。请检查目标范围查询逻辑。")

    if avg_time_per_target_minutes <= 0:
        raise ValueError(f"单个目标平均时间必须>0，当前值: {avg_time_per_target_minutes}")

    logger.info(
        "开始批次分配",
        target_count=len(targets),
        device_count=len(devices),
        avg_time_minutes=avg_time_per_target_minutes,
    )

    # 初始化每个设备的批次（使用字典映射 device_id -> target_ids）
    device_batches: dict[int, List[int]] = {device["id"]: [] for device in devices}

    # Round-robin分配：遍历目标，轮流分配给设备
    for idx, target in enumerate(targets):
        device_index = idx % len(devices)  # 轮询索引
        device_id = devices[device_index]["id"]
        device_batches[device_id].append(target["id"])

    # 构造返回结果（只包含有任务的批次）
    batches: List[Batch] = []
    batch_sizes: List[int] = []

    for device in devices:
        target_ids = device_batches[device["id"]]
        if target_ids:  # 只添加有任务的批次
            batch_size = len(target_ids)
            estimated_minutes = batch_size * avg_time_per_target_minutes

            batches.append(
                Batch(
                    device_id=device["id"],
                    device_name=device["name"],
                    target_ids=target_ids,
                    estimated_completion_minutes=estimated_minutes,
                )
            )
            batch_sizes.append(batch_size)

    # 计算最大批次大小差（衡量负载均衡性）
    max_batch_size = max(batch_sizes) - min(batch_sizes) if batch_sizes else 0

    logger.info(
        "批次分配完成",
        batch_count=len(batches),
        max_batch_size_diff=max_batch_size,
        total_estimated_minutes=sum(b["estimated_completion_minutes"] for b in batches),
    )

    return AllocationResult(
        batches=batches,
        total_targets=len(targets),
        total_devices=len(devices),
        max_batch_size=max_batch_size,
    )


def validate_targets_sorted(targets: List[Target]) -> None:
    """
    验证目标列表是否已按priority_score降序排序

    该函数用于调试和验证，确保调用方正确排序了目标列表。
    如果未排序，抛出ValueError（不做自动排序，强制调用方修正）。

    参数：
        targets: 目标列表

    异常：
        - ValueError: 目标列表未按priority_score降序排序
    """
    if len(targets) < 2:
        return  # 少于2个目标无需验证

    for i in range(len(targets) - 1):
        if targets[i]["priority_score"] < targets[i + 1]["priority_score"]:
            raise ValueError(
                f"目标列表未按priority_score降序排序。"
                f"索引{i}的优先级({targets[i]['priority_score']}) "
                f"< 索引{i+1}的优先级({targets[i + 1]['priority_score']})。"
                f"请在调用allocate_batches前先排序。"
            )

    logger.debug("目标列表排序验证通过", target_count=len(targets))
