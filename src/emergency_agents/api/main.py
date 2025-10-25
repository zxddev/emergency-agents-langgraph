#!/usr/bin/env python3
# Copyright 2025 msq
from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional, Any, Dict, List

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram

from emergency_agents.config import AppConfig
from emergency_agents.graph.app import build_app
from emergency_agents.memory.mem0_facade import Mem0Config, MemoryFacade
from emergency_agents.llm.client import get_openai_client
from emergency_agents.rag.pipe import RagPipeline, RagChunk
from emergency_agents.graph.kg_service import KGService, KGConfig
from emergency_agents.audit.logger import get_audit_logger, log_human_approval
from langgraph.types import Command
from emergency_agents.voice.asr.service import ASRService
from emergency_agents.voice.asr.base import ASRConfig as ASRConfigModel


class Domain(str, Enum):
    """受支持的知识域。"""
    SPEC = "规范"
    CASE = "案例"
    GEO = "地理"
    EQUIP = "装备"


app = FastAPI(title="AI Emergency Brain API")
_cfg = AppConfig.load_from_env()
_graph_app = build_app(_cfg.checkpoint_sqlite_path, _cfg.postgres_dsn)

# metrics
Instrumentator().instrument(app).expose(app)

# custom metrics
_assist_counter = Counter('assist_answer_total', 'Total /assist/answer requests')
_assist_failures = Counter('assist_answer_failures_total', 'Total /assist/answer failures')
_assist_latency = Histogram('assist_answer_seconds', 'Latency of /assist/answer')

# memory facade singleton
_mem = MemoryFacade(
    Mem0Config(
        qdrant_url=_cfg.qdrant_url or "http://192.168.1.40:6333",
        qdrant_collection="mem0_collection",
        embedding_model=_cfg.embedding_model,
        embedding_dim=_cfg.embedding_dim,
        neo4j_uri=_cfg.neo4j_uri or "bolt://192.168.1.40:7687",
        neo4j_user=_cfg.neo4j_user or "neo4j",
        # pragma: allowlist secret - placeholder credential for development
        neo4j_password=_cfg.neo4j_password or "example-neo4j",
        openai_base_url=_cfg.openai_base_url,
        # pragma: allowlist secret - placeholder credential for development
        openai_api_key=_cfg.openai_api_key,
        graph_llm_model=_cfg.llm_model,
    )
)

# rag pipeline singleton
_rag = RagPipeline(
    qdrant_url=_cfg.qdrant_url or "http://192.168.1.40:6333",
    embedding_model=_cfg.embedding_model,
    embedding_dim=_cfg.embedding_dim,
    openai_base_url=_cfg.openai_base_url,
    openai_api_key=_cfg.openai_api_key,
    llm_model=_cfg.llm_model,
)

# kg service singleton
_kg = KGService(
    KGConfig(
        uri=_cfg.neo4j_uri or "bolt://192.168.1.40:7687",
        user=_cfg.neo4j_user or "neo4j",
        # pragma: allowlist secret - placeholder credential for development
        password=_cfg.neo4j_password or "example-neo4j",
    )
)

_asr = ASRService()


@app.on_event("startup")
async def startup_event():
    await _asr.start_health_check()


@app.on_event("shutdown")
async def shutdown_event():
    await _asr.stop_health_check()


class RagDoc(BaseModel):
    """RAG 文档输入。"""
    id: str
    text: str
    meta: Optional[Dict[str, Any]] = None


class RagIndexRequest(BaseModel):
    """批量索引请求。"""
    domain: Domain
    docs: List[RagDoc]


class RagQueryRequest(BaseModel):
    """RAG 检索请求。"""
    domain: Domain
    question: str
    top_k: int = Field(3, ge=1, le=10, description="返回片段数量上限")


class KGRecommendRequest(BaseModel):
    """装备推荐请求。"""
    hazard: str
    environment: Optional[str] = None
    top_k: int = Field(5, ge=1, le=20)


class KGCaseSearchRequest(BaseModel):
    """案例检索请求。"""
    keywords: str
    top_k: int = Field(5, ge=1, le=20)


class AssistAnswerRequest(BaseModel):
    """智能回答请求。"""
    user_id: str
    run_id: str
    domain: Domain
    question: str
    top_k: int = Field(3, ge=1, le=10)


class StartThreadRequest(BaseModel):
    """启动救援线程请求"""
    raw_report: str = Field(..., description="非结构化灾情报告")
    user_id: Optional[str] = Field(None, description="用户ID")


@app.post("/threads/start")
async def start_thread(rescue_id: str, req: StartThreadRequest):
    """创建救援线程并进入人工审批中断点。"""
    init_state = {
        "rescue_id": rescue_id,
        "user_id": req.user_id or "unknown",
        "raw_report": req.raw_report
    }
    result = _graph_app.invoke(init_state, config={"configurable": {"thread_id": f"rescue-{rescue_id}", "checkpoint_ns": f"tenant-{init_state['user_id']}"}})
    return {"rescue_id": rescue_id, "state": result}


class ApproveRequest(BaseModel):
    """审批请求"""
    approved_ids: List[str] = Field(..., description="批准的提案ID列表")
    comment: Optional[str] = Field(None, description="审批意见")


@app.post("/threads/approve")
async def approve_thread(rescue_id: str, user_id: str, req: ApproveRequest):
    """审批救援方案。"""
    log_human_approval(
        rescue_id=rescue_id,
        user_id=user_id,
        approved_ids=req.approved_ids,
        comment=req.comment,
        thread_id=f"rescue-{rescue_id}"
    )
    
    # 动态中断恢复：使用 Command(resume=[...]) 将批准的ID注入 await 节点
    result = _graph_app.invoke(
        Command(resume=req.approved_ids),
        config={"configurable": {"thread_id": f"rescue-{rescue_id}"}}
    )
    return {"rescue_id": rescue_id, "approved": True, "state": result}


@app.post("/threads/resume")
async def resume_thread(rescue_id: str):
    """继续执行指定救援线程。"""
    result = _graph_app.invoke(None, config={"configurable": {"thread_id": f"rescue-{rescue_id}"}})
    return {"rescue_id": rescue_id, "state": result}


@app.get("/audit/trail/{rescue_id}")
async def get_audit_trail(rescue_id: str):
    """获取审计轨迹。"""
    audit_logger = get_audit_logger()
    trail = audit_logger.get_trail(rescue_id)
    return {"rescue_id": rescue_id, "trail": trail, "count": len(trail)}


@app.get("/healthz")
async def healthz():
    """健康探针。"""
    return {"status": "ok"}


@app.post("/memory/add")
async def memory_add(content: str, user_id: str, run_id: Optional[str] = None, agent_id: Optional[str] = None):
    """新增记忆记录。"""
    _mem.add(content=content, user_id=user_id, run_id=run_id, agent_id=agent_id)
    return {"ok": True}


@app.get("/memory/search")
async def memory_search(query: str, user_id: str, run_id: Optional[str] = None, agent_id: Optional[str] = None, top_k: int = 5):
    """检索记忆记录。"""
    res = _mem.search(query=query, user_id=user_id, run_id=run_id, agent_id=agent_id, top_k=top_k)
    return {"results": res}


@app.post("/rag/index")
async def rag_index(req: RagIndexRequest):
    """批量索引文档到 RAG 存储。"""
    _rag.index_documents(req.domain.value, [d.model_dump() for d in req.docs])
    return {"ok": True, "count": len(req.docs), "trace_id": str(uuid.uuid4())}


@app.post("/rag/query")
async def rag_query(req: RagQueryRequest):
    """执行 RAG 相似度检索。"""
    chunks: List[RagChunk] = _rag.query(req.question, req.domain.value, req.top_k)
    return {"trace_id": str(uuid.uuid4()), "results": [
        {"text": c.text, "source": c.source, "loc": c.loc} for c in chunks
    ]}


@app.post("/asr/recognize")
async def asr_recognize(file: UploadFile = File(...), sample_rate: int = 16000, fmt: str = "pcm"):
    """上传单段音频并返回识别文本。

    ASR 使用自动故障转移机制:Aliyun(主)→ Local FunASR(备),后台健康检查每 30 秒执行一次。
    支持 PCM/WAV（若为 WAV，应由调用方传入裸音频数据或确保服务端获取到 PCM 数据）。
    """

    try:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="empty file")
        cfg = ASRConfigModel(format=fmt, sample_rate=sample_rate)
        result = await _asr.recognize(data, cfg)
        return {
            "provider": _asr.provider_name,
            "text": result.text,
            "latency_ms": result.latency_ms,
            "confidence": result.confidence,
            "metadata": result.metadata or {},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/kg/recommend")
async def kg_recommend(req: KGRecommendRequest):
    """根据危害/环境推荐装备。"""
    items = _kg.recommend_equipment(hazard=req.hazard, environment=req.environment, top_k=req.top_k)
    return {"trace_id": str(uuid.uuid4()), "recommendations": items}


@app.post("/kg/cases/search")
async def kg_search(req: KGCaseSearchRequest):
    """按关键词检索案例。"""
    items = _kg.search_cases(keywords=req.keywords, top_k=req.top_k)
    return {"trace_id": str(uuid.uuid4()), "results": items}


@app.post("/assist/answer")
async def assist_answer(req: AssistAnswerRequest):
    """结合 RAG 与记忆生成带引用的回答。"""
    _assist_counter.inc()
    trace_id = str(uuid.uuid4())
    with _assist_latency.time():
        try:
            # 1) 检索 RAG 片段
            rag_chunks: List[RagChunk] = _rag.query(req.question, req.domain.value, req.top_k)
            # 2) 检索 Mem0 记忆
            mem_results = _mem.search(query=req.question, user_id=req.user_id, run_id=req.run_id, top_k=req.top_k)
            # 3) 汇总证据并生成回答
            client = get_openai_client(_cfg)
            context_parts: List[str] = []
            for c in rag_chunks:
                context_parts.append(f"[RAG] {c.source}@{c.loc}: {c.text}")
            for m in mem_results or []:
                if isinstance(m, dict):
                    meta = m.get('metadata', {})
                    content = m.get('content', '')
                    context_parts.append(f"[MEM] {meta.get('run_id','')}: {content}")
                else:
                    context_parts.append(f"[MEM] {str(m)}")
            context = "\n".join(context_parts)
            messages = [
                {"role": "system", "content": "你是救援应急大脑，请基于给定证据回答，并在末尾列出引用。"},
                {"role": "user", "content": f"问题: {req.question}\n\n证据:\n{context}"},
            ]
            resp = client.chat.completions.create(model=_cfg.llm_model, messages=messages, temperature=0)
            answer = resp.choices[0].message.content if getattr(resp, 'choices', None) else ""
            return {
                "trace_id": trace_id,
                "answer": answer,
                "evidence": {
                    "rag": [{"text": c.text, "source": c.source, "loc": c.loc} for c in rag_chunks],
                    "memory": mem_results,
                },
            }
        except Exception:
            _assist_failures.inc()
            raise

# WebSocket 语音对话路由
@app.websocket("/ws/voice/chat")
async def voice_chat_endpoint(websocket: WebSocket) -> None:
    from emergency_agents.api.voice_chat import handle_voice_chat
    await handle_voice_chat(websocket)
