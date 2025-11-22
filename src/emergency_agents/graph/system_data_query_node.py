"""系统数据统一查询节点

使用ToolNode模式实现高性能数据查询，避免ReAct Agent的多轮LLM调用。
所有系统内部数据查询都通过这个节点处理，确保类型安全和性能优化。
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, TypedDict

import structlog

from emergency_agents.db.dao import (
    DeviceDAO,
    EventDAO,
    PoiDAO,
    RescuerDAO,
    TaskDAO,
)
from emergency_agents.db.models import (
    CarriedDevice,
    DeviceSummary,
    EntityLocation,
    EventLocation,
    PoiLocation,
    TaskLogEntry,
    TaskRoutePlan,
    TaskSummary,
)

logger = structlog.get_logger(__name__)


class QueryResult(TypedDict):
    """查询结果的统一格式"""

    success: bool
    data: Optional[Any]  # 查询结果数据
    message: str  # 用户友好的消息
    query_type: str  # 执行的查询类型
    elapsed_ms: int  # 查询耗时（毫秒）


class SystemDataQueryNode:
    """系统数据查询节点（基于ToolNode模式）

    优势：
    1. 强类型：所有工具都有明确的输入输出类型
    2. 高性能：直接调用DAO，无需LLM推理
    3. 确定性：根据query_type精确路由
    4. 可维护：新增查询只需添加工具映射

    支持的查询类型：
    - carried_devices: 查询所有携带设备
    - device_by_name: 根据名称查询设备
    - task_progress: 查询任务进度
    - task_by_code: 根据代码查询任务
    - event_location: 查询事件位置
    - team_location: 查询队伍位置
    - poi_location: 查询POI位置
    """

    def __init__(
        self,
        device_dao: DeviceDAO,
        task_dao: TaskDAO,
        event_dao: EventDAO,
        poi_dao: PoiDAO,
        rescuer_dao: RescuerDAO,
    ):
        """初始化查询节点

        Args:
            device_dao: 设备数据访问对象
            task_dao: 任务数据访问对象
            event_dao: 事件数据访问对象
            poi_dao: POI数据访问对象
            rescuer_dao: 救援人员数据访问对象
        """
        self.device_dao = device_dao
        self.task_dao = task_dao
        self.event_dao = event_dao
        self.poi_dao = poi_dao
        self.rescuer_dao = rescuer_dao

        # 工具映射表（query_type -> 处理函数）
        self.tools: Dict[str, Any] = {
            # 设备查询
            "carried_devices": self._query_carried_devices,
            "device_by_name": self._query_device_by_name,
            "device_by_id": self._query_device_by_id,
            "vehicle_location": self._query_vehicle_location,

            # 任务查询
            "task_progress": self._query_task_progress,
            "task_by_code": self._query_task_by_code,
            "task_latest_log": self._query_task_latest_log,
            "task_route_plan": self._query_task_route_plan,
            "task_count": self._query_task_count,
            "task_status_by_name": self._query_task_status_by_name,
            "task_assignees": self._query_task_assignees,

            # 位置查询
            "event_location": self._query_event_location,
            "team_location": self._query_team_location,
            "poi_location": self._query_poi_location,
        }

    async def execute(
        self,
        query_type: str,
        query_params: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """执行查询（主入口）

        Args:
            query_type: 查询类型
            query_params: 查询参数

        Returns:
            QueryResult: 统一格式的查询结果
        """
        start_time = time.perf_counter()

        # 参数验证
        if not query_type:
            return QueryResult(
                success=False,
                data=None,
                message="查询类型不能为空",
                query_type="",
                elapsed_ms=0
            )

        # 查找对应的工具
        if query_type not in self.tools:
            logger.warning(
                "unsupported_query_type",
                query_type=query_type,
                available_types=list(self.tools.keys())
            )
            return QueryResult(
                success=False,
                data=None,
                message=f"不支持的查询类型: {query_type}",
                query_type=query_type,
                elapsed_ms=0
            )

        try:
            # 执行查询工具
            tool_func = self.tools[query_type]
            result = await tool_func(query_params or {})

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            logger.info(
                "system_data_query_success",
                query_type=query_type,
                elapsed_ms=elapsed_ms,
                has_result=result.get("data") is not None
            )

            return QueryResult(
                success=True,
                data=result.get("data"),
                message=result.get("message", "查询成功"),
                query_type=query_type,
                elapsed_ms=elapsed_ms
            )

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(
                "system_data_query_error",
                query_type=query_type,
                error=str(e),
                elapsed_ms=elapsed_ms
            )
            return QueryResult(
                success=False,
                data=None,
                message=f"查询失败: {str(e)}",
                query_type=query_type,
                elapsed_ms=elapsed_ms
            )

    # ==================== 设备查询工具 ====================

    async def _query_carried_devices(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询所有携带设备"""
        devices: list[CarriedDevice] = await self.device_dao.fetch_carried_devices()

        if not devices:
            return {
                "data": [],
                "message": "当前没有车载携带的设备"
            }

        # 格式化输出 - 只显示设备名称
        device_lines = []
        device_names = []  # 用于去重

        for device in devices:
            name = device.name or "未命名设备"
            if name not in device_names:
                device_names.append(name)

        # 按设备类型分组显示
        for idx, name in enumerate(device_names, start=1):
            device_lines.append(f"{idx}. {name}")

        return {
            "data": [
                {"name": d.name, "capability": d.weather_capability}  # 改字段名为capability
                for d in devices
            ],
            "message": f"车载携带设备清单（共{len(devices)}台，{len(device_names)}种）：\n" + "\n".join(device_lines)
        }

    async def _query_device_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """根据名称查询设备"""
        device_name = params.get("device_name", "").strip()

        if not device_name:
            return {
                "data": None,
                "message": "设备名称不能为空"
            }

        device: DeviceSummary | None = await self.device_dao.fetch_device_by_name(device_name)

        if device is None:
            return {
                "data": None,
                "message": f"未找到名称为 {device_name} 的设备"
            }

        return {
            "data": {
                "id": device.id,
                "name": device.name,
                "device_type": device.device_type
            },
            "message": f"设备 {device.name}（编号 {device.id}）记录在案"
        }

    async def _query_device_by_id(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """根据ID查询设备"""
        device_id = params.get("device_id", "").strip()

        if not device_id:
            return {
                "data": None,
                "message": "设备ID不能为空"
            }

        device: DeviceSummary | None = await self.device_dao.fetch_device_by_id(device_id)

        if device is None:
            return {
                "data": None,
                "message": f"未找到ID为 {device_id} 的设备"
            }

        return {
            "data": {
                "id": device.id,
                "name": device.name,
                "device_type": device.device_type
            },
            "message": f"设备 {device.name}（编号 {device.id}）查询成功"
        }

    async def _query_vehicle_location(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询车辆位置（指挥/作战车辆）。"""
        vehicle_id = str(params.get("vehicle_id") or "").strip()
        vehicle_name = str(params.get("vehicle_name") or params.get("name") or "").strip()

        location = await self.rescuer_dao.fetch_vehicle_location(
            vehicle_id=vehicle_id or None,
            vehicle_name=vehicle_name or None,
        )

        if location is None:
            identifier = vehicle_name or vehicle_id or "车辆"
            return {
                "data": None,
                "message": f"未找到 {identifier} 的位置信息"
            }

        return {
            "data": {
                "name": location.name,
                "lng": location.lng,
                "lat": location.lat
            },
            "message": f"{location.name} 位置: ({location.lat}, {location.lng})"
        }

    # ==================== 任务数量与状态 ====================

    async def _query_task_count(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """统计当前任务数量（未删除）。"""
        total = await self.task_dao.count_tasks()
        return {
            "data": {"total": total},
            "message": f"当前共有 {total} 个任务"
        }

    async def _query_task_status_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """按任务名称/编号模糊匹配，并返回状态与参与设备数。"""
        task_name = str(params.get("task_name") or params.get("name") or "").strip()
        if not task_name:
            return {
                "data": None,
                "message": "任务名称不能为空"
            }

        record = await self.task_dao.fetch_task_by_name(task_name)
        if record is None:
            return {
                "data": None,
                "message": f"未找到名称包含 {task_name} 的任务"
            }

        # 查询指派实体列表
        assignees = await self.task_dao.fetch_task_assignees(record.id)
        assignee_brief = ", ".join([a.name or a.entity_id for a in assignees][:5])

        return {
            "data": {
                "id": record.id,
                "code": record.code,
                "description": record.description,
                "status": record.status,
                "progress": record.progress,
                "device_count": record.device_count,
                "assignees": [
                    {"entity_id": a.entity_id, "entity_type": a.entity_type, "name": a.name}
                    for a in assignees
                ],
            },
            "message": (
                f"任务 {record.code or record.id} 状态 {record.status}，"
                f"进度 {record.progress or 0}% ，参与设备 {record.device_count} 台"
                + (f"：{assignee_brief}" if assignee_brief else "")
            ),
        }

    async def _query_task_assignees(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询任务指派实体列表，支持 task_id 或 task_name 模糊匹配。"""
        task_id = str(params.get("task_id") or "").strip()
        task_name = str(params.get("task_name") or params.get("name") or "").strip()

        # 若未提供 task_id，用名称先查一次
        if not task_id and task_name:
            record = await self.task_dao.fetch_task_by_name(task_name)
            task_id = record.id if record else ""
        if not task_id:
            record = await self.task_dao.fetch_latest_task_with_assignees()
            task_id = record.id if record else ""
            fallback_used = True
        else:
            fallback_used = False

        assignees = await self.task_dao.fetch_task_assignees(task_id) if task_id else []
        if not assignees:
            return {
                "data": [],
                "message": "该任务当前没有指派设备/实体" if task_id else "未找到可用的指派设备/实体"
            }

        names = ", ".join([a.name or a.entity_id for a in assignees])
        return {
            "data": [
                {"entity_id": a.entity_id, "entity_type": a.entity_type, "name": a.name}
                for a in assignees
            ],
            "message": (
                ("使用最近任务" if fallback_used else "任务指派列表")
                + f"（{len(assignees)}）：{names}"
            )
        }

    # ==================== 任务查询工具 ====================

    async def _query_task_progress(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询任务进度"""
        task_id = params.get("task_id", "").strip()

        if not task_id:
            return {
                "data": None,
                "message": "任务ID不能为空"
            }

        task: TaskSummary | None = await self.task_dao.fetch_task_summary(task_id=task_id)

        if task is None:
            return {
                "data": None,
                "message": f"未找到ID为 {task_id} 的任务"
            }

        return {
            "data": {
                "id": task.id,
                "code": task.code,
                "description": task.description,
                "status": task.status,
                "progress": task.progress,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            },
            "message": f"任务 {task.code or task.id} 进度: {task.progress or 0}%"
        }

    async def _query_task_by_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """根据代码查询任务"""
        task_code = params.get("task_code", "").strip()

        if not task_code:
            return {
                "data": None,
                "message": "任务代码不能为空"
            }

        task: TaskSummary | None = await self.task_dao.fetch_task_summary(task_code=task_code)

        if task is None:
            return {
                "data": None,
                "message": f"未找到代码为 {task_code} 的任务"
            }

        return {
            "data": {
                "id": task.id,
                "code": task.code,
                "description": task.description,
                "status": task.status,
                "progress": task.progress,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            },
            "message": f"任务 {task.code} 状态: {task.status}"
        }

    async def _query_task_latest_log(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询任务最新日志"""
        task_id = params.get("task_id", "").strip()

        if not task_id:
            return {
                "data": None,
                "message": "任务ID不能为空"
            }

        log: TaskLogEntry | None = await self.task_dao.fetch_task_latest_log(task_id)

        if log is None:
            return {
                "data": None,
                "message": f"任务 {task_id} 暂无日志记录"
            }

        return {
            "data": {
                "description": log.description,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "recorder_name": log.recorder_name
            },
            "message": f"最新日志: {log.description or '无描述'}"
        }

    async def _query_task_route_plan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询任务路线规划"""
        task_id = params.get("task_id", "").strip()

        if not task_id:
            return {
                "data": None,
                "message": "任务ID不能为空"
            }

        route: TaskRoutePlan | None = await self.task_dao.fetch_task_route_plan(task_id)

        if route is None:
            return {
                "data": None,
                "message": f"任务 {task_id} 暂无路线规划"
            }

        return {
            "data": {
                "strategy": route.strategy,
                "distance_meters": route.distance_meters,
                "duration_seconds": route.duration_seconds
            },
            "message": f"路线策略: {route.strategy or '默认'}, 距离: {route.distance_meters or 0}米"
        }

    # ==================== 位置查询工具 ====================

    async def _query_event_location(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询事件位置"""
        # 支持多种参数
        event_id = params.get("event_id", "").strip()
        event_code = params.get("event_code", "").strip()

        if not event_id and not event_code:
            return {
                "data": None,
                "message": "需要提供事件ID或事件代码"
            }

        location: EventLocation | None = await self.event_dao.fetch_event_location(
            event_id=event_id or None,
            event_code=event_code or None
        )

        if location is None:
            identifier = event_code if event_code else event_id
            return {
                "data": None,
                "message": f"未找到事件 {identifier} 的位置信息"
            }

        return {
            "data": {
                "name": location.name,
                "lng": location.lng,
                "lat": location.lat
            },
            "message": f"事件 {location.name} 位置: ({location.lat}, {location.lng})"
        }

    async def _query_team_location(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询队伍位置"""
        team_id = params.get("team_id", "").strip()
        team_name = params.get("team_name", "").strip()

        if not team_id and not team_name:
            return {
                "data": None,
                "message": "需要提供队伍ID或队伍名称"
            }

        location: EntityLocation | None = await self.rescuer_dao.fetch_team_location(
            team_id=team_id or None,
            team_name=team_name or None
        )

        if location is None:
            identifier = team_name if team_name else team_id
            return {
                "data": None,
                "message": f"未找到队伍 {identifier} 的位置信息"
            }

        return {
            "data": {
                "name": location.name,
                "lng": location.lng,
                "lat": location.lat
            },
            "message": f"队伍 {location.name} 位置: ({location.lat}, {location.lng})"
        }

    async def _query_poi_location(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询POI位置"""
        poi_name = params.get("poi_name", "").strip()

        if not poi_name:
            return {
                "data": None,
                "message": "POI名称不能为空"
            }

        location: PoiLocation | None = await self.poi_dao.fetch_poi_location(poi_name)

        if location is None:
            return {
                "data": None,
                "message": f"未找到POI {poi_name} 的位置信息"
            }

        return {
            "data": {
                "name": location.name,
                "lng": location.lng,
                "lat": location.lat
            },
            "message": f"POI {location.name} 位置: ({location.lat}, {location.lng})"
        }


async def system_data_query_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph节点函数（用于集成到图中）

    从state中提取查询参数，执行查询，返回结果。

    Args:
        state: LangGraph状态，应包含：
            - intent: 意图信息（含slots）
            - db_pool: 数据库连接池

    Returns:
        更新后的state，包含查询结果
    """
    start_time = time.perf_counter()

    # 提取意图和槽位
    intent = state.get("intent", {})
    slots = intent.get("slots", {})

    # 提取查询参数
    query_type = slots.get("query_type", "")
    query_params = slots.get("query_params", {})

    # 获取数据库连接池
    db_pool = state.get("db_pool")
    if not db_pool:
        logger.error("system_data_query_no_db_pool")
        return state | {
            "query_result": QueryResult(
                success=False,
                data=None,
                message="系统错误：数据库连接池未初始化",
                query_type=query_type,
                elapsed_ms=0
            )
        }

    try:
        # 创建DAO对象
        device_dao = DeviceDAO(db_pool)
        task_dao = TaskDAO(db_pool)
        event_dao = EventDAO(db_pool)
        poi_dao = PoiDAO(db_pool)
        rescuer_dao = RescuerDAO(db_pool)

        # 创建查询节点
        query_node = SystemDataQueryNode(
            device_dao=device_dao,
            task_dao=task_dao,
            event_dao=event_dao,
            poi_dao=poi_dao,
            rescuer_dao=rescuer_dao
        )

        # 执行查询
        result = await query_node.execute(query_type, query_params)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            "system_data_query_node_completed",
            query_type=query_type,
            success=result["success"],
            elapsed_ms=elapsed_ms,
            thread_id=state.get("thread_id")
        )

        return state | {"query_result": result}

    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(
            "system_data_query_node_error",
            error=str(e),
            query_type=query_type,
            elapsed_ms=elapsed_ms
        )

        return state | {
            "query_result": QueryResult(
                success=False,
                data=None,
                message=f"查询节点错误: {str(e)}",
                query_type=query_type,
                elapsed_ms=elapsed_ms
            )
        }
