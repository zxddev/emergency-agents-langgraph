"""侦察方案 LLM 生成服务。"""

from __future__ import annotations

import json
from dataclasses import dataclass
import time
from typing import List, Optional, Protocol, runtime_checkable

import httpx
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
import structlog

from emergency_agents.planner.recon_models import (
    GeoPoint,
    ReconContext,
    ReconIntent,
)


@runtime_checkable
class ReconLLMEngine(Protocol):
    """侦察方案生成接口。"""

    def generate_plan(self, *, intent: ReconIntent, context: ReconContext) -> "LLMPlanBlueprint":
        ...


@dataclass(frozen=True)
class ReconLLMConfig:
    """侦察 LLM 配置。"""

    model: str
    base_url: str
    api_key: str
    temperature: float = 0.2
    timeout_seconds: float = 600.0  # 10分钟超时


class LLMTaskBlueprint(BaseModel):
    """LLM 输出的任务蓝图。"""

    title: str = Field(..., min_length=1, description="任务标题")
    objective: str = Field(..., min_length=1, description="任务目标")
    mission_phase: str = Field("recon", description="任务阶段")
    priority: str = Field("high", description="任务优先级")
    recommended_device: str = Field(..., min_length=1, description="建议设备ID")
    target_points: List[GeoPoint] = Field(default_factory=list, description="目标坐标点")
    required_capabilities: List[str] = Field(default_factory=list, description="能力要求")
    duration_minutes: Optional[int] = Field(None, description="预计持续时长")
    safety_notes: Optional[str] = Field(None, description="安全提示")
    dependencies: List[str] = Field(default_factory=list, description="依赖任务")


class LLMJustification(BaseModel):
    """LLM 输出的解释结构。"""

    summary: str = Field(..., min_length=1, description="摘要")
    reasoning_chain: List[str] = Field(default_factory=list, description="推理步骤")
    risk_warnings: List[str] = Field(default_factory=list, description="风险提示")


class LLMPlanBlueprint(BaseModel):
    """LLM 输出的整体方案蓝图。"""

    objectives: List[str] = Field(default_factory=list, description="方案目标")
    tasks: List[LLMTaskBlueprint] = Field(default_factory=list, description="任务蓝图")
    justification: LLMJustification = Field(..., description="解释信息")


class OpenAIReconLLMEngine(ReconLLMEngine):
    """基于 OpenAI 兼容接口的侦察 LLM 实现。"""

    def __init__(self, *, config: ReconLLMConfig, client: Optional[OpenAI] = None) -> None:
        if not config.model or not config.base_url or not config.api_key:
            raise ValueError("侦察 LLM 配置缺失")
        self._config = config
        if client is not None:
            self._client = client
        else:
            timeout = httpx.Timeout(
                connect=5.0,
                read=config.timeout_seconds,
                write=config.timeout_seconds,
                pool=None,
            )
            http_client = httpx.Client(trust_env=False, timeout=timeout)
            self._client = OpenAI(
                base_url=config.base_url,
                api_key=config.api_key,
                http_client=http_client,
                timeout=config.timeout_seconds,
            )
        self._logger = structlog.get_logger(__name__).bind(model=config.model)

    def generate_plan(self, *, intent: ReconIntent, context: ReconContext) -> LLMPlanBlueprint:
        start = time.time()
        payload = self._build_payload(intent=intent, context=context)
        schema_hint = (
            "输出 JSON 对象，字段结构必须为："
            '{"objectives":["..."],'
            '"tasks":[{"title":"","objective":"","mission_phase":"","priority":"","recommended_device":"","target_points":[{"lon":0.0,"lat":0.0}],"required_capabilities":[],"duration_minutes":0,"safety_notes":"","dependencies":[]}],'
            '"justification":{"summary":"","reasoning_chain":[],"risk_warnings":[]}}。'
            "严格要求：仅使用上下文提供的数据（设备ID/坐标/队伍/受阻道路/已有任务/设备capabilities），禁止臆造；"
            "mission_phase ∈ {recon, alert, rescue, logistics}；priority ∈ {critical, high, medium, low}；"
            "objectives ≤ 3；每个任务 target_points ≤ 3（WGS84，经度lon、纬度lat，度单位）；"
            "所有 recommended_device 必须来自 available_devices.device_id，且其 capabilities 能满足任务；"
            "灾情→设备能力匹配示例：洪水/水域→water_recon/usv/sonar；化工泄漏→hazmat_detection/gas_detection/robot_dog；火灾/高温→thermal_imaging；近距观察→robot_dog；空域巡检→uav；"
            "若无任何设备满足本次灾情能力需求：tasks 数组须为空，并在 justification.summary 写明 no_suitable_equipment，risk_warnings 给出原因；不得编造替代设备。"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是基于 ICS/IAP 的侦察作战规划官（面向作战与计划岗位）。"
                    "根据灾情类型与可用装备capabilities进行设备-任务匹配：水域/洪水优先USV，化工泄漏优先具备hazmat/gas检测的robot_dog，空域巡检优先UAV。"
                    "如确无合适装备，必须返回空任务并明确 no_suitable_equipment 理由（不得臆造设备或坐标）。"
                    "任务数量限制在1到4之间；输出严格为 JSON 结构，不得添加未定义字段或自然语言说明。"
                ),
            },
            {
                "role": "user",
                "content": f"{schema_hint}\n上下文：{json.dumps(payload, ensure_ascii=False)}",
            },
        ]
        response = self._client.chat.completions.create(
            model=self._config.model,
            temperature=self._config.temperature,
            response_format={"type": "json_object"},
            messages=messages,
        )
        content = response.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            self._logger.error(
                "recon_llm_invalid_json",
                event_id=intent.event_id,
                command=intent.raw_text,
                elapsed_ms=int((time.time() - start) * 1000),
            )
            raise ValueError("LLM 返回内容无法解析为 JSON") from exc
        try:
            blueprint = LLMPlanBlueprint.model_validate(data)
            self._logger.info(
                "recon_llm_success",
                event_id=intent.event_id,
                command=intent.raw_text,
                task_count=len(blueprint.tasks),
                elapsed_ms=int((time.time() - start) * 1000),
            )
            return blueprint
        except ValidationError as exc:
            self._logger.error(
                "recon_llm_validation_error",
                event_id=intent.event_id,
                command=intent.raw_text,
                errors=exc.errors(),
                raw_payload=data,
                elapsed_ms=int((time.time() - start) * 1000),
            )
            raise ValueError(f"LLM 输出结构不合法: {exc}") from exc

    def _build_payload(self, *, intent: ReconIntent, context: ReconContext) -> dict:
        """构造提示上下文。"""

        devices = [
            {
                "device_id": device.device_id,
                "name": device.name,
                "category": device.category,
                "environment": device.environment,
                "capabilities": device.capabilities,
                "endurance_minutes": device.endurance_minutes,
                "available": device.available,
            }
            for device in context.available_devices
        ]
        agents = [
            {
                "unit_id": agent.unit_id,
                "name": agent.name,
                "kind": agent.kind,
                "capabilities": agent.capabilities,
                "available": agent.available,
            }
            for agent in context.available_agents
        ]
        targets = [point.model_dump(mode="json") for point in intent.target_spots]
        return {
            "event_id": context.event_id,
            "hazard": context.hazard.model_dump(mode="json"),
            "intent": {
                "raw_text": intent.raw_text,
                "keywords": intent.risk_keywords,
                "deadline_minutes": intent.deadline_minutes,
                "target_spots": targets,
            },
            "available_devices": devices,
            "available_agents": agents,
            "blocked_routes": context.blocked_routes,
            "existing_tasks": context.existing_tasks,
        }
