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
    timeout_seconds: float = 300.0


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
            "所有值需替换为实际内容，禁止返回示例文字或多余字段；"
            "mission_phase 只能取 \"recon\"、\"alert\"、\"rescue\"、\"logistics\" 之一；"
            "priority 只能取 \"critical\"、\"high\"、\"medium\"、\"low\" 之一；"
            "objectives 数量不超过 3 条，若有更多请合并；"
            "target_points 每个任务最多保留 3 个关键坐标。"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是应急指挥领域的侦察任务规划官。"
                    "请基于提供的事件态势、可用装备和坐标，生成专业的侦察方案。"
                    "必须使用提供的设备ID，任务数量限制在1到4之间。"
                    "输出严格遵循指定的JSON结构，不得添加多余字段。"
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
