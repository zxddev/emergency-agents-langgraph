# Copyright 2025 msq
from __future__ import annotations

import logging
from typing import Dict, Any, Protocol

from emergency_agents.container import container

logger = logging.getLogger(__name__)

class ActionExecutor(Protocol):
    async def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        ...

class RealActionExecutor(ActionExecutor):
    """真实执行器：调用 AdapterHub 接口。"""
    
    async def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("type")
        params = action.get("params") or {}
        
        logger.info(f"Executing real action: {action_type} {params}")
        
        # 这里调用 AdapterHubClient (需要先注册到 container)
        # 假设我们已经注册了 adapter_client
        # adapter = container.get("adapter_client")
        # return await adapter.send_command(action_type, params)
        
        # 暂时 Mock，等待 AdapterHubClient 完整对接
        return {"status": "executed", "result": "mock_success"}

class MockActionExecutor(ActionExecutor):
    """测试用执行器。"""
    async def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[MOCK] Executing: {action.get('type')}")
        return {"status": "mock_success"}

# ... (Can be expanded)
