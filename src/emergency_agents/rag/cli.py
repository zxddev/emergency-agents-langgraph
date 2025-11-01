# Copyright 2025 msq
from __future__ import annotations

import argparse
import json
from typing import Dict, Any, List

from emergency_agents.config import AppConfig
from emergency_agents.rag.pipe import RagPipeline


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            docs.append(json.loads(line))
    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk index documents into Qdrant via RagPipeline")
    parser.add_argument("input", help="JSONL file with fields: id, text, meta, domain (optional if --domain set)")
    parser.add_argument("--domain", help="Override domain for all docs (规范/案例/地理/装备)")
    args = parser.parse_args()

    cfg = AppConfig.load_from_env()
    if cfg.qdrant_url is None:
        raise RuntimeError("QDRANT_URL must be configured before indexing documents")
    rag = RagPipeline(
        qdrant_url=cfg.qdrant_url,
        qdrant_api_key=cfg.qdrant_api_key,
        embedding_model=cfg.embedding_model,
        embedding_dim=cfg.embedding_dim,
        openai_base_url=cfg.openai_base_url,
        openai_api_key=cfg.openai_api_key,
        llm_model=cfg.llm_model,
    )

    all_docs = load_jsonl(args.input)
    if args.domain:
        rag.index_documents(args.domain, all_docs)
    else:
        # group by domain from doc["domain"]
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for d in all_docs:
            dom = d.get("domain", "其他")
            groups.setdefault(dom, []).append(d)
        for dom, docs in groups.items():
            rag.index_documents(dom, docs)


if __name__ == "__main__":
    main()

