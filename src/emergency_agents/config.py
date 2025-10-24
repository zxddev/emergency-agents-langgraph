from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'dev.env'))
except Exception:
    # dotenv optional in runtime; ignore if missing
    pass


@dataclass(frozen=True)
class AppConfig:
    openai_base_url: str
    openai_api_key: str
    llm_model: str
    embedding_model: str
    embedding_dim: int
    postgres_dsn: str | None
    qdrant_url: str | None
    qdrant_api_key: str | None
    neo4j_uri: str | None
    neo4j_user: str | None
    neo4j_password: str | None
    checkpoint_sqlite_path: str

    @staticmethod
    def load_from_env() -> "AppConfig":
        return AppConfig(
            openai_base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1"),
            openai_api_key=os.getenv("OPENAI_API_KEY", "dummy"),
            llm_model=os.getenv("LLM_MODEL", "qwen2.5-7b-instruct"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "bge-large-zh-v1.5"),
            embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),
            postgres_dsn=os.getenv("POSTGRES_DSN"),
            qdrant_url=os.getenv("QDRANT_URL"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            neo4j_uri=os.getenv("NEO4J_URI"),
            neo4j_user=os.getenv("NEO4J_USER"),
            neo4j_password=os.getenv("NEO4J_PASSWORD"),
            checkpoint_sqlite_path=os.getenv("CHECKPOINT_SQLITE_PATH", "./checkpoints.sqlite3"),
        )
