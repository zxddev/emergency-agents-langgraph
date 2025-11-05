"""语音/文本实时对话 LangGraph 子图。"""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Dict, List, Optional

import structlog
from typing_extensions import NotRequired, Required, TypedDict

from langgraph.graph import StateGraph

from emergency_agents.config import AppConfig
from emergency_agents.graph.checkpoint_utils import create_async_postgres_checkpointer
from emergency_agents.llm.client import get_async_openai_client

logger = structlog.get_logger(__name__)


class DialogueState(TypedDict):
    """对话子图状态。"""

    thread_id: Required[str]
    user_id: Required[str]
    raw_text: Required[str]

    channel: NotRequired[str]
    conversation_history: NotRequired[List[Dict[str, Any]]]
    memory_hits: NotRequired[List[Dict[str, Any]]]
    context_block: NotRequired[str]
    audit_log: NotRequired[List[Dict[str, Any]]]
    response_text: NotRequired[str]
    suggestions: NotRequired[List[str]]


@dataclass(frozen=True)
class DialogueConfig:
    llm_model: str
    system_prompt: str


_DIALOGUE_SYSTEM_PROMPT = dedent(
    """
    你是“应急前线综合指挥助手”。场景：大型灾害现场，指挥车内气氛高压、信息快速变更。
    你的职责是协助现场总指挥实时研判态势、调度资源、触发救援/侦察/设备控制/视频分析等专用子图，并持续提醒潜在风险。

    工作守则：
    1. 优先理解最新输入，与 conversation_history 和 memory_hits 中的数据核对，引用历史信息时注明“历史记忆”并向指挥官确认是否仍有效。
    2. 根据指挥官诉求识别关键信息：
       - 救援任务：必须明确 coordinates.lat/lng、location_name、mission_type（缺省 rescue）、≥15 字的 situation_summary、disaster_type。
       - 侦察任务：target_type、coordinates 或地点、objective_summary、潜在风险。
       - 机器狗或设备控制：device_id、动作指令、作业区域。
       - 视频分析：设备标识、分析目标、期望产出。
       - 任务状态：task_id 或 task_code。
       - 设备状态：device_id 或唯一名称。
    3. 信息不足时必须追问，禁止臆测或编造；所有推断都要标注不确定性。
    4. 随时关注次生灾害风险，如余震、燃爆、危化品泄漏、堰塞湖等，引用依据或声明不确定。
    5. 当信息充分时，明确提示“可进入 XX 子图”并罗列已满足字段；信息不足则列出待补清单。
    6. 输出统一使用以下结构：
       现状：……（已确认事实及来源）
       建议：……（下一步行动，可包含“建议调用 xx 子图”或“等待人工确认”）
       待补：……（缺失的关键情报）
       风险预警：……（潜在风险，注明依据/不确定性）
    7. 语气务求简洁、指令式，不寒暄、不闲聊；如请求偏离救援业务，礼貌提醒职责范围并引导回主题。
    8. 任何未经确认的伤亡、资源、风险数据均不得擅自声明。
    """
)


def _append_audit(state: DialogueState, event: Dict[str, Any]) -> List[Dict[str, Any]]:
    trail = list(state.get("audit_log") or [])
    trail.append(event)
    return trail


def _render_history(messages: List[Dict[str, Any]], limit: int = 8) -> str:
    if not messages:
        return "（无）"
    lines: List[str] = []
    for item in messages[-limit:]:
        role = str(item.get("role", "user")).upper()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "（无）"


def _render_memories(memories: List[Dict[str, Any]], limit: int = 5) -> str:
    if not memories:
        return "（无）"
    lines: List[str] = []
    for item in memories[:limit]:
        if not isinstance(item, dict):
            lines.append(f"- {str(item)}")
            continue
        memory_text = item.get("memory") or item.get("content") or item.get("text") or item.get("value")
        metadata = item.get("metadata") or {}
        source = metadata.get("incident_id") or metadata.get("run_id") or metadata.get("agent")
        prefix = f"[{source}] " if source else ""
        if isinstance(memory_text, str) and memory_text.strip():
            lines.append(f"- {prefix}{memory_text.strip()}")
    return "\n".join(lines) if lines else "（无）"


def _build_user_prompt(raw_text: str, history_block: str, memory_block: str) -> str:
    return dedent(
        f"""
        【当前对话历史】
        {history_block if history_block else '（无）'}

        【历史记忆】
        {memory_block if memory_block else '（无）'}

        【最新指挥官输入】
        {raw_text.strip()}

        请依据系统守则给出响应，保持“现状/建议/待补/风险预警”四段格式。
        对于建议触发的子图或操作，请在“建议”段落中明确列出并说明所需字段是否齐备。
        """
    ).strip()


async def build_dialogue_graph(
    *,
    postgres_dsn: str,
    checkpoint_schema: str = "dialogue_checkpoint",
    system_prompt: str = _DIALOGUE_SYSTEM_PROMPT,
) -> Any:
    """构建应急语音/文本对话子图。"""

    if not postgres_dsn:
        raise ValueError("Dialogue graph requires POSTGRES_DSN")

    cfg = AppConfig.load_from_env()
    llm_model = cfg.llm_model
    llm_client = get_async_openai_client(cfg)
    dialogue_cfg = DialogueConfig(llm_model=llm_model, system_prompt=system_prompt)

    logger.info("dialogue_graph_init", schema=checkpoint_schema, model=dialogue_cfg.llm_model)

    graph = StateGraph(DialogueState)

    def ingest(state: DialogueState) -> Dict[str, Any]:
        raw_text = str(state.get("raw_text") or "").strip()
        if not raw_text:
            raise ValueError("对话输入为空，无法生成响应")
        audit = _append_audit(state, {"event": "dialogue_ingest", "text_preview": raw_text[:80]})
        return {
            "raw_text": raw_text,
            "audit_log": audit,
        }

    def prepare_context(state: DialogueState) -> Dict[str, Any]:
        history = state.get("conversation_history") or []
        memories = state.get("memory_hits") or []
        history_block = _render_history(history)
        memory_block = _render_memories(memories)
        context_block = _build_user_prompt(state["raw_text"], history_block, memory_block)
        audit = _append_audit(
            state,
            {
                "event": "dialogue_context_compiled",
                "history_count": len(history),
                "memory_count": len(memories),
            },
        )
        logger.info(
            "dialogue_context_compiled",
            thread_id=state.get("thread_id"),
            history_count=len(history),
            memory_count=len(memories),
        )
        return {
            "context_block": context_block,
            "audit_log": audit,
        }

    async def call_llm(state: DialogueState) -> Dict[str, Any]:
        context_block = state.get("context_block") or _build_user_prompt(state["raw_text"], "（无）", "（无）")
        messages = [
            {"role": "system", "content": dialogue_cfg.system_prompt},
            {"role": "user", "content": context_block},
        ]
        thread_id = state.get("thread_id")
        logger.info(
            "dialogue_llm_request",
            thread_id=thread_id,
            prompt_preview=context_block[:200],
        )
        response = await llm_client.chat.completions.create(
            model=dialogue_cfg.llm_model,
            messages=messages,
            temperature=0.2,
        )
        choice = response.choices[0]
        content = getattr(choice.message, "content", "") or ""
        usage = getattr(response, "usage", None)
        usage_dump: Any
        if usage is None:
            usage_dump = None
        elif hasattr(usage, "model_dump"):
            usage_dump = usage.model_dump()
        else:
            usage_dump = getattr(usage, "__dict__", str(usage))
        logger.info(
            "dialogue_llm_response",
            thread_id=thread_id,
            response_id=getattr(response, "id", None),
            finish_reason=getattr(choice, "finish_reason", None),
            usage=usage_dump,
            content_preview=content[:200],
        )
        audit = _append_audit(state, {"event": "dialogue_llm_completed"})
        return {
            "response_text": content.strip() or "收到。请继续说明。",
            "audit_log": audit,
        }

    graph.add_node("ingest", ingest)
    graph.add_node("prepare_context", prepare_context)
    graph.add_node("call_llm", call_llm)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "prepare_context")
    graph.add_edge("prepare_context", "call_llm")
    graph.add_edge("call_llm", "__end__")

    checkpointer, close_cb = await create_async_postgres_checkpointer(
        dsn=postgres_dsn,
        schema=checkpoint_schema,
        min_size=1,
        max_size=1,
    )
    compiled = graph.compile(checkpointer=checkpointer)
    setattr(compiled, "_checkpoint_close", close_cb)
    logger.info("dialogue_graph_ready", schema=checkpoint_schema)
    return compiled


__all__ = ["build_dialogue_graph", "DialogueState"]

