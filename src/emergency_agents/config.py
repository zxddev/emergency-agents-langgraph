from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import structlog

from emergency_agents.llm.endpoint_manager import LLMEndpointConfig

_logger = structlog.get_logger(__name__)
DEFAULT_QDRANT_API_KEY = "qdrantzmkj123456"
DEFAULT_QDRANT_URL = "http://192.168.1.40:6333"

try:
    # 说明：统一从 APP_ENV 选择性加载环境文件；默认回退到 dev.env，保持兼容
    from dotenv import load_dotenv

    base_dir: str = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_dir: str = os.path.join(base_dir, 'config')

    # 1) 通用密钥与共享配置（不覆盖已有环境变量）
    load_dotenv(os.path.join(config_dir, 'llm_keys.env'), override=False)

    # 2) 环境选择：APP_ENV ∈ {external, internal, h100}；未设置时回退到 dev.env
    env_name: str = (os.getenv('APP_ENV') or '').strip().lower()
    if env_name in {"external", "internal", "h100"}:
        env_file: str = os.path.join(config_dir, f"env.{env_name}")
    else:
        env_file = os.path.join(config_dir, 'dev.env')

    # 加载选定环境文件（允许覆盖上一层）
    load_dotenv(env_file, override=True)
    _logger.info("dotenv_env_selected", app_env=env_name or "(default:dev)", file=env_file)

    # 3) 开发者本地覆盖层（可选，不存在时忽略）
    # 注意：此层仅在上层未定义时补充（override=False），避免覆盖所选环境文件
    load_dotenv(os.path.join(config_dir, 'dev.local.env'), override=False)
except Exception as exc:
    # dotenv 可选依赖；若加载失败不影响运行（保持现有环境变量）
    _logger.warning("dotenv_load_skipped", error=str(exc))


def _normalize_qdrant_url(url: str | None, api_key: str | None) -> str | None:
    if url is None or not url.strip():
        return DEFAULT_QDRANT_URL
    trimmed: str = url.strip().rstrip("/")
    if "://" not in trimmed:
        trimmed = f"http://{trimmed}"
    parsed = urlsplit(trimmed)
    normalized = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )
    return normalized


@dataclass(frozen=True)
class AppConfig:
    openai_base_url: str
    openai_api_key: str
    video_vllm_url: str
    video_vllm_api_key: str
    video_vllm_model: str
    llm_model: str
    intent_llm_model: str
    embedding_model: str
    embedding_dim: int
    postgres_dsn: str | None
    qdrant_url: str | None
    qdrant_api_key: str | None
    neo4j_uri: str | None
    neo4j_user: str | None
    neo4j_password: str | None
    checkpoint_sqlite_path: str
    tts_api_url: str
    tts_voice: str
    amap_api_key: str | None
    amap_backup_key: str | None
    amap_base_url: str
    amap_connect_timeout: float
    amap_read_timeout: float
    video_stream_map: dict[str, object]
    kg_api_url: str | None
    kg_api_key: str | None
    rag_api_url: str | None
    rag_api_key: str | None
    llm_endpoints: tuple[LLMEndpointConfig, ...]
    llm_endpoint_groups: dict[str, tuple[LLMEndpointConfig, ...]]
    llm_failure_threshold: int
    llm_recovery_seconds: int
    llm_max_concurrency: int
    llm_request_timeout_seconds: float
    adapter_base_url: str | None
    adapter_timeout: float
    default_robotdog_id: str | None
    recon_llm_model: str | None
    recon_llm_base_url: str | None
    recon_llm_api_key: str | None
    rag_openai_api_key: str
    rag_analysis_timeout: float
    intent_provider: str
    intent_rasa_url: str | None
    intent_setfit_url: str | None
    intent_provider_timeout: float
    intent_confidence_threshold: float
    intent_margin_threshold: float
    risk_cache_ttl_seconds: float
    risk_refresh_interval_seconds: float

    @staticmethod
    def load_from_env() -> "AppConfig":
        stream_map_raw = os.getenv("VIDEO_STREAM_MAP", "{}")
        try:
            parsed_stream_map = json.loads(stream_map_raw) if stream_map_raw else {}
        except json.JSONDecodeError:
            _logger.warning("video_stream_map_parse_failed", raw=stream_map_raw)
            parsed_stream_map = {}
        stream_map: dict[str, object] = {}
        if isinstance(parsed_stream_map, dict):
            for key, value in parsed_stream_map.items():
                stream_map[str(key)] = value
        else:
            stream_map = {}

        kg_api_url = os.getenv("KG_API_URL")
        rag_api_url = os.getenv("RAG_API_URL")

        openai_base_url = os.getenv("OPENAI_BASE_URL", "http://192.168.1.40:8000/v1")
        openai_api_key = os.getenv("OPENAI_API_KEY", "dummy")
        video_vllm_url = os.getenv("VIDEO_VLLM_URL", openai_base_url)
        video_vllm_api_key = os.getenv("VIDEO_VLLM_API_KEY", openai_api_key)
        video_vllm_model = os.getenv("VIDEO_VLLM_MODEL", "glm-4.5v")
        rag_openai_api_key = os.getenv("RAG_OPENAI_API_KEY", openai_api_key)
        intent_llm_model = os.getenv("INTENT_LLM_MODEL", os.getenv("LLM_MODEL", "glm-4-flash"))
        rag_analysis_timeout = float(os.getenv("RAG_ANALYSIS_TIMEOUT", "3"))
        qdrant_api_key = os.getenv("QDRANT_API_KEY", DEFAULT_QDRANT_API_KEY)
        if os.getenv("QDRANT_API_KEY") is None:
            _logger.info("using_default_qdrant_key", key=DEFAULT_QDRANT_API_KEY)
        qdrant_url = _normalize_qdrant_url(os.getenv("QDRANT_URL"), qdrant_api_key)

        try:
            llm_max_concurrency = int(os.getenv("LLM_MAX_CONCURRENCY", "5"))
        except ValueError:
            llm_max_concurrency = 1000
        try:
            llm_request_timeout_seconds = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "60"))
        except ValueError:
            llm_request_timeout_seconds = 60.0

        endpoints_env = os.getenv("LLM_ENDPOINTS")
        endpoints: list[LLMEndpointConfig] = []
        if endpoints_env:
            try:
                for idx, raw in enumerate(json.loads(endpoints_env)):
                    if not isinstance(raw, dict):
                        continue
                    name = str(raw.get("name") or f"endpoint-{idx}")
                    base_url = str(raw.get("base_url") or "")
                    if not base_url:
                        continue
                    api_key = str(raw.get("api_key") or openai_api_key)
                    priority = int(raw.get("priority", 100))
                    endpoints.append(
                        LLMEndpointConfig(
                            name=name,
                            base_url=base_url,
                            api_key=api_key,
                            priority=priority,
                            weight=int(raw.get("weight", 1)),
                        )
                    )
            except Exception:
                endpoints = []

        backup_url = os.getenv("OPENAI_BACKUP_URL")
        if backup_url:
            endpoints.append(
                LLMEndpointConfig(
                    name=os.getenv("OPENAI_BACKUP_NAME", "backup"),
                    base_url=backup_url,
                    api_key=os.getenv("OPENAI_BACKUP_KEY", openai_api_key),
                    priority=int(os.getenv("OPENAI_BACKUP_PRIORITY", "80")),
                )
            )

        if not endpoints:
            endpoints.append(
                LLMEndpointConfig(
                    name="primary",
                    base_url=openai_base_url,
                    api_key=openai_api_key,
                    priority=100,
                )
            )

        endpoint_groups: dict[str, tuple[LLMEndpointConfig, ...]] = {
            "default": tuple(endpoints),
        }
        groups_env = os.getenv("LLM_ENDPOINT_GROUPS")
        if groups_env:
            try:
                raw_groups = json.loads(groups_env)
                if isinstance(raw_groups, dict):
                    for scope, raw_list in raw_groups.items():
                        if not isinstance(raw_list, list):
                            continue
                        group_members: list[LLMEndpointConfig] = []
                        for idx, raw in enumerate(raw_list):
                            if not isinstance(raw, dict):
                                continue
                            base_url = str(raw.get("base_url") or "")
                            if not base_url:
                                continue
                            config_name = str(raw.get("name") or f"{scope}-{idx}")
                            api_key = str(raw.get("api_key") or openai_api_key)
                            group_members.append(
                                LLMEndpointConfig(
                                    name=config_name,
                                    base_url=base_url,
                                    api_key=api_key,
                                    priority=int(raw.get("priority", 100)),
                                    weight=int(raw.get("weight", 1)),
                                )
                            )
                        if group_members:
                            endpoint_groups[scope] = tuple(group_members)
            except Exception as exc:
                _logger.warning("llm_endpoint_groups_parse_failed", error=str(exc))

        return AppConfig(
            openai_base_url=os.getenv("OPENAI_BASE_URL", "http://192.168.1.40:8000/v1"),
            openai_api_key=os.getenv("OPENAI_API_KEY", "dummy"),
            video_vllm_url=video_vllm_url,
            video_vllm_api_key=video_vllm_api_key,
            video_vllm_model=video_vllm_model,
            llm_model=os.getenv("LLM_MODEL", "qwen2.5-7b-instruct"),
            intent_llm_model=intent_llm_model,
            embedding_model=os.getenv("EMBEDDING_MODEL", "bge-large-zh-v1.5"),
            embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),
            postgres_dsn=os.getenv("POSTGRES_DSN"),
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            neo4j_uri=os.getenv("NEO4J_URI"),
            neo4j_user=os.getenv("NEO4J_USER"),
            neo4j_password=os.getenv("NEO4J_PASSWORD"),
            checkpoint_sqlite_path=os.getenv("CHECKPOINT_SQLITE_PATH", "./checkpoints.sqlite3"),
            tts_api_url=os.getenv("VOICE_TTS_URL", "http://192.168.31.40:18002/api/tts"),
            tts_voice=os.getenv("VOICE_TTS_VOICE", "zh-CN-XiaoxiaoNeural"),
            amap_api_key=os.getenv("AMAP_API_KEY"),
            amap_backup_key=os.getenv("AMAP_API_BACKUP_KEY"),
            amap_base_url=os.getenv("AMAP_API_URL", "https://restapi.amap.com"),
            amap_connect_timeout=float(os.getenv("AMAP_API_CONNECT_TIMEOUT", "10")),
            amap_read_timeout=float(os.getenv("AMAP_API_READ_TIMEOUT", "10")),
            video_stream_map=stream_map,
            kg_api_url=kg_api_url,
            kg_api_key=os.getenv("KG_API_KEY"),
            rag_api_url=rag_api_url,
            rag_api_key=os.getenv("RAG_API_KEY"),
            llm_endpoints=tuple(endpoints),
            llm_endpoint_groups=endpoint_groups,
            llm_failure_threshold=int(os.getenv("LLM_FAILURE_THRESHOLD", "3")),
            llm_recovery_seconds=int(os.getenv("LLM_RECOVERY_SECONDS", "60")),
            llm_max_concurrency=llm_max_concurrency,
            llm_request_timeout_seconds=llm_request_timeout_seconds,
            adapter_base_url=os.getenv("ADAPTER_HUB_BASE_URL"),
            adapter_timeout=float(os.getenv("ADAPTER_HUB_TIMEOUT", "5")),
            default_robotdog_id=os.getenv("DEFAULT_ROBOTDOG_ID"),
            recon_llm_model=os.getenv("RECON_LLM_MODEL"),
            recon_llm_base_url=os.getenv("RECON_LLM_BASE_URL"),
            recon_llm_api_key=os.getenv("RECON_LLM_API_KEY"),
            rag_openai_api_key=rag_openai_api_key,
            rag_analysis_timeout=rag_analysis_timeout,
            intent_provider=os.getenv("INTENT_PROVIDER", "llm"),
            intent_rasa_url=os.getenv("INTENT_RASA_URL"),
            intent_setfit_url=os.getenv("INTENT_SETFIT_URL"),
            intent_provider_timeout=float(os.getenv("INTENT_PROVIDER_TIMEOUT", "1.5")),
            intent_confidence_threshold=float(os.getenv("INTENT_CONFIDENCE_THRESHOLD", "0.65")),
            intent_margin_threshold=float(os.getenv("INTENT_MARGIN_THRESHOLD", "0.20")),
            risk_cache_ttl_seconds=float(os.getenv("RISK_CACHE_TTL_SECONDS", "120")),
            risk_refresh_interval_seconds=float(os.getenv("RISK_REFRESH_INTERVAL_SECONDS", "60")),
        )
