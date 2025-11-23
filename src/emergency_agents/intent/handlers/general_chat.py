# Copyright 2025 msq
"""通用对话处理器：处理闲聊、问候、测试等非业务对话场景。

本模块实现一个专门的对话Handler，使用专业的应急救援领域提示词，
让AI助手以应急救援指挥车智能助手的身份与用户对话。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Callable, Awaitable, Optional

import structlog

from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import GeneralChatSlots

logger = structlog.get_logger(__name__)

# 应急救援领域的专业对话提示词
GENERAL_CHAT_SYSTEM_PROMPT = """你是应急救援指挥车的智能助手，代号"应急AI"。你的职责是协助指挥员进行应急救援指挥与决策。

【身份与定位】
- 名称：应急AI（Emergency AI Assistant）
- 定位：应急救援指挥车载智能助手
- 职责：协助指挥员进行救援决策、设备调度、态势分析
- 技术架构：基于LangGraph的多智能体编排系统，集成GLM-4大模型

【核心能力】
1. **救援任务规划**：根据灾情生成救援方案和任务分配
2. **设备智能调度**：调度无人机、机器狗、无人船等智能设备
3. **态势实时分析**：分析灾情、预测次生灾害、评估风险
4. **多模态理解**：支持语音对话、视频分析、地图标注
5. **知识图谱推理**：基于知识图谱进行装备推荐和案例检索

【对话原则】
1. **专业严谨**：使用应急救援专业术语，保持专业形象
2. **简洁高效**：回答简洁明了，直击要点，不冗余
3. **主动引导**：当用户询问功能时，主动给出使用示例
4. **友好自然**：保持友好的语气，但不过度热情
5. **安全第一**：涉及操作指令时，强调安全和确认流程

【回答规范】
- 对于问候：简短回应，主动说明自己的身份和核心能力
- 对于能力询问：列举核心功能（2-3条），并给出具体示例
- 对于闲聊：礼貌回应，但适时引导回业务相关话题
- 对于测试：确认系统正常，说明当前状态
- 对于超出范围的问题：明确说明这不是应急救援范围，引导用户提出相关需求

【示例对话】
用户："你好"
助手："您好，我是应急AI，应急救援指挥车的智能助手。我可以协助您进行救援任务规划、设备调度、态势分析等工作。有什么可以帮您的吗？"

用户："你能做什么"
助手："我的核心能力包括：
1. 救援任务规划：根据灾情自动生成救援方案
2. 智能设备调度：调度无人机、机器狗等设备执行任务
3. 态势实时分析：分析灾情、预测次生灾害

例如，您可以说"到东经103.8度、北纬31.6度侦察"或"制定XX地震救援方案"。"

用户："你是什么大模型"
助手："我基于超越空间开发的猛士大模型构建，采用 LangGraph 多智能体编排架构，专门针对应急救援场景优化。我的核心是多个专业智能体的协作：态势感知、风险预测、方案生成、设备调度等，确保救援决策的准确性和时效性。"

【重要提醒】
- 不要编造未实现的功能
- 不要给出超出应急救援范围的建议
- 不要泄露系统内部技术细节（除非用户明确询问）
- 始终强调安全和人工确认的重要性
"""


@dataclass(slots=True)
class GeneralChatHandler(IntentHandler[GeneralChatSlots]):
    """通用对话处理器。

    使用专业的应急救援领域提示词，让AI以应急救援指挥车智能助手的身份与用户对话。
    继承IntentHandler基类，遵循标准的handle(slots, state)接口。

    Attributes:
        llm_client: LLM客户端（OpenAI兼容接口）
        llm_model: 模型名称（推荐glm-4-flash）
    """

    llm_client: Any
    llm_model: str
    async_llm_client: Any | None = None

    def __post_init__(self):
        """初始化后日志记录。"""
        logger.info(
            "general_chat_handler_initialized",
            llm_model=self.llm_model,
        )

    async def handle(self, slots: GeneralChatSlots, state: Dict[str, object]) -> Dict[str, object]:
        """处理通用对话请求。

        Args:
            slots: GeneralChatSlots实例（空槽位，不使用）
            state: 状态字典，包含raw_text、messages、thread_id等

        Returns:
            状态更新字典，包含response_text字段
        """
        # 从state提取数据
        raw_text = str(state.get("raw_text", ""))
        messages = state.get("messages", [])
        thread_id = state.get("thread_id")

        logger.info(
            "general_chat_handling",
            thread_id=thread_id,
            raw_text_preview=raw_text[:50] if raw_text else "",
        )

        # 构建对话历史（最近5轮）
        history = []
        if isinstance(messages, list) and messages:
            # 只保留最近5轮对话，避免上下文过长
            history.extend(messages[-5:])

        # 添加当前用户输入
        history.append({"role": "user", "content": raw_text})

        try:
            messages_payload = [
                {"role": "system", "content": GENERAL_CHAT_SYSTEM_PROMPT},
                *history,
            ]

            stream_sink: Optional[Callable[[str], Awaitable[None]]] = state.get("stream_sink")  # type: ignore[assignment]
            answer: str = ""

            input_tokens = 0
            output_tokens = 0

            # 语音通道可选流式：仅在提供 async_llm_client 和 stream_sink 时启用
            if stream_sink is not None and self.async_llm_client is not None:
                chunks: list[str] = []
                stream = await self.async_llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages_payload,
                    temperature=0.7,
                    max_tokens=500,
                    stream=True,
                )
                async for chunk in stream:
                    try:
                        delta = chunk.choices[0].delta.content or ""
                    except Exception:
                        delta = ""
                    if not delta:
                        continue
                    chunks.append(delta)
                    await stream_sink(delta)
                answer = "".join(chunks).strip()
            else:
                # 非流式路径：用于文本API或未启用流式的场景
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages_payload,
                    temperature=0.7,  # 对话可以稍微灵活一些
                    max_tokens=500,   # 限制回答长度，保持简洁
                )

                content = getattr(response.choices[0].message, "content", "") or ""
                answer = str(content).strip()
                input_tokens = getattr(getattr(response, "usage", None), "prompt_tokens", 0)
                output_tokens = getattr(getattr(response, "usage", None), "completion_tokens", 0)

            logger.info(
                "general_chat_success",
                thread_id=thread_id,
                answer_preview=answer[:100],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            # 返回标准格式（必须使用response_text字段）
            return {
                "response_text": answer,
                "intent_type": "general-chat",
                "confidence": 1.0,
                "source": "general_chat_handler",
            }

        except Exception as exc:
            logger.error(
                "general_chat_llm_error",
                thread_id=thread_id,
                error=str(exc),
                exc_info=True,
            )
            # 返回兜底回答
            fallback_answer = (
                "您好，我是应急AI，应急救援指挥车的智能助手。"
                "我可以协助您进行救援任务规划、设备调度、态势分析等工作。"
                "请问有什么可以帮您的吗？"
            )
            return {
                "response_text": fallback_answer,
                "intent_type": "general-chat",
                "confidence": 0.5,
                "source": "fallback",
                "error": str(exc),
            }
