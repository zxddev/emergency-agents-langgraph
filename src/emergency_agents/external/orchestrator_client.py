from __future__ import annotations

import json  # 引入 json 便于调试时输出
import os  # 读取环境变量
from dataclasses import dataclass  # dataclass 提供强类型数据容器
from typing import Any, Dict, List, Optional  # 类型提示

import httpx  # HTTP 客户端
import structlog  # 结构化日志


logger = structlog.get_logger(__name__)  # 初始化日志器用于排障


class OrchestratorClientError(RuntimeError):
    """Java 协同编排接口错误。"""


@dataclass(slots=True)
class IncidentCreatePayload:
    """事件创建请求体。"""

    title: str
    event_type: str
    priority: int
    description: str
    location: Dict[str, Any]
    impact_area: Optional[Dict[str, Any]] = None
    event_code: Optional[str] = None
    reporter: Optional[str] = None
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为 JSON 字典，自动剔除空值。"""
        data: Dict[str, Any] = {
            "title": self.title,
            "eventType": self.event_type,
            "priority": self.priority,
            "description": self.description,
            "location": self.location,
            "impactArea": self.impact_area,
            "eventCode": self.event_code,
            "reporter": self.reporter,
            "source": self.source,
            "metadata": self.metadata,
        }
        return {key: value for key, value in data.items() if value is not None}


class OrchestratorClient:
    """AI 大脑 → Java Orchestrator API 封装。"""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 8.0) -> None:
        # 读取 Java 服务地址，默认指向 web-api
        root = base_url or os.getenv("WEB_API_BASE_URL", "http://localhost:28080/web-api")
        self._base_url: str = root.rstrip("/")
        source: str = "explicit" if base_url else ("env" if os.getenv("WEB_API_BASE_URL") else "default")
        logger.info("orchestrator_client_initialized", base_url=self._base_url, source=source)
        # 配置 HTTP 客户端，禁用代理，设置超时
        self._client = httpx.Client(
            timeout=httpx.Timeout(connect=3.0, read=timeout, write=timeout, pool=timeout),
            trust_env=False,
            base_url=self._base_url,
        )

    def close(self) -> None:
        """释放 HTTP 客户端资源。"""
        self._client.close()

    def create_incident(self, payload: IncidentCreatePayload) -> Dict[str, Any]:
        """创建事件，返回 Java 侧事件详情。"""
        body = payload.to_dict()
        response = self._post("/api/incidents", body)
        logger.info("orchestrator_incident_created", response=response)
        return response

    def publish_rescue_scenario(self, payload: "RescueScenarioPayload") -> Dict[str, Any]:
        """推送救援场景消息，驱动前端动画。"""
        body = payload.to_dict()
        response = self._post("/api/v1/rescue/scenario", body)
        logger.info("rescue_scenario_published", response=response)
        return response

    def publish_scout_scenario(self, payload: "ScoutScenarioPayload") -> Dict[str, Any]:
        """推送侦察场景消息，通知前端侦察任务生成（用于notify_backend_task）"""
        body = payload.to_dict()
        response = self._post("/api/v1/scout/scenario", body)
        logger.info("scout_scenario_published", response=response)
        return response

    def _post(self, path: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
        """发送 POST 请求并做统一错误处理。"""
        url = path if path.startswith("/") else f"/{path}"
        full_url = f"{self._base_url}{url}"
        logger.info("orchestrator_http_post", url=full_url, payload=json_body)
        try:
            response = self._client.post(url, json=json_body)
        except httpx.HTTPError as exc:
            logger.error("orchestrator_http_failed", url=full_url, error=str(exc))
            raise OrchestratorClientError(f"调用 {url} 网络失败: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "orchestrator_http_error_status",
                url=full_url,
                status_code=response.status_code,
                body=response.text,
            )
            raise OrchestratorClientError(
                f"调用 {url} 失败: {response.status_code} {response.text}"
            )

        try:
            data: Dict[str, Any] = response.json()
        except ValueError as exc:
            logger.error("orchestrator_http_invalid_json", url=full_url, body=response.text)
            raise OrchestratorClientError(f"解析 {url} 响应失败: {exc}") from exc

        # API 统一为 ApiResponse 包装，抽取 data 字段
        if "data" in data:
            result = data["data"]
            if isinstance(result, dict):
                logger.info("orchestrator_http_success", url=full_url)
                return result
            logger.error("orchestrator_http_invalid_data_shape", url=full_url, data=data)
            raise OrchestratorClientError(f"{url} 返回 data 结构异常: {data}")
        logger.info("orchestrator_http_success", url=full_url)
        return data


@dataclass(slots=True)
class RescueScenarioLocation:
    """救援场景的经纬度信息。"""

    longitude: float
    latitude: float
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "longitude": self.longitude,
            "latitude": self.latitude,
        }
        if self.name:
            data["name"] = self.name
        return data


@dataclass(slots=True)
class RescueScenarioPayload:
    """救援场景推送请求。"""

    event_id: str
    location: RescueScenarioLocation
    title: str
    content: str
    origin: Optional[str] = None
    victims_estimate: Optional[int] = None
    hazards: Optional[List[str]] = None
    attachments: Optional[List[str]] = None
    scope: Optional[List[str]] = None
    prompt_level: Optional[int] = None
    required_capabilities: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "eventId": self.event_id,
            "location": self.location.to_dict(),
            "title": self.title,
            "content": self.content,
        }
        if self.origin:
            data["origin"] = self.origin
        if self.victims_estimate is not None:
            data["victimsEstimate"] = self.victims_estimate
        if self.hazards:
            data["hazards"] = self.hazards
        if self.attachments:
            data["attachments"] = self.attachments
        if self.scope:
            data["scope"] = self.scope
        if self.prompt_level is not None:
            data["promptLevel"] = self.prompt_level
        if self.required_capabilities:
            data["requiredCapabilities"] = self.required_capabilities
        return data


@dataclass(slots=True)
class ScoutScenarioPayload:
    """侦察场景推送请求（用于notify_backend_task通知前端）"""

    event_id: str
    task_id: str
    location: RescueScenarioLocation
    title: Optional[str] = None
    content: Optional[str] = None
    targets: Optional[List[Dict[str, Any]]] = None
    sensors: Optional[List[str]] = None
    route: Optional[List[Dict[str, Any]]] = None
    estimated_duration_minutes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为 JSON 字典（camelCase），自动剔除空值"""
        data: Dict[str, Any] = {
            "eventId": self.event_id,
            "taskId": self.task_id,
            "location": self.location.to_dict(),
        }
        if self.title:
            data["title"] = self.title
        if self.content:
            data["content"] = self.content
        if self.targets:
            data["targets"] = self.targets
        if self.sensors:
            data["sensors"] = self.sensors
        if self.route:
            data["route"] = self.route
        if self.estimated_duration_minutes is not None:
            data["estimatedDurationMinutes"] = self.estimated_duration_minutes
        return data
