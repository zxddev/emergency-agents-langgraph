"""系统数据统一查询Handler

基于ToolNode模式，处理所有系统内部数据查询请求。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict

import structlog

from emergency_agents.db.dao import (
    DeviceDAO,
    EventDAO,
    PoiDAO,
    RescuerDAO,
    TaskDAO,
)
from emergency_agents.graph.system_data_query_node import SystemDataQueryNode
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import SystemDataQuerySlots

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class SystemDataQueryHandler(IntentHandler[SystemDataQuerySlots]):
    """系统数据查询Handler

    统一处理所有系统内部数据查询请求：
    - 设备查询（携带设备、按名称查询等）
    - 任务查询（进度、日志、路线等）
    - 位置查询（事件、队伍、POI等）

    使用ToolNode模式，避免ReAct Agent的多轮LLM调用，
    确保强类型和高性能。
    """

    device_dao: DeviceDAO
    task_dao: TaskDAO
    event_dao: EventDAO
    poi_dao: PoiDAO
    rescuer_dao: RescuerDAO

    async def handle(
        self,
        slots: SystemDataQuerySlots,
        state: Dict[str, object]
    ) -> Dict[str, object]:
        """处理系统数据查询请求

        Args:
            slots: 查询槽位（query_type和query_params）
            state: 会话状态

        Returns:
            包含查询结果的字典
        """
        start_time = time.perf_counter()

        # 提取查询参数
        query_type = slots.query_type
        query_params = slots.query_params or {}

        # 记录查询请求
        logger.info(
            "system_data_query_handler_start",
            query_type=query_type,
            has_params=bool(query_params),
            thread_id=state.get("thread_id"),
            user_id=state.get("user_id")
        )

        # 创建查询节点
        query_node = SystemDataQueryNode(
            device_dao=self.device_dao,
            task_dao=self.task_dao,
            event_dao=self.event_dao,
            poi_dao=self.poi_dao,
            rescuer_dao=self.rescuer_dao
        )

        # 执行查询
        result = await query_node.execute(query_type, query_params)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # 记录查询完成
        logger.info(
            "system_data_query_handler_completed",
            query_type=query_type,
            success=result["success"],
            elapsed_ms=elapsed_ms,
            thread_id=state.get("thread_id")
        )

        # 构建响应
        if result["success"]:
            return {
                "response_text": result["message"],
                "query_result": result["data"],
                "query_type": query_type,
                "elapsed_ms": elapsed_ms
            }
        else:
            return {
                "response_text": result["message"],
                "query_result": None,
                "query_type": query_type,
                "error": True,
                "elapsed_ms": elapsed_ms
            }