# Copyright 2025 msq
"""装备信息提取器。

职责：
- 从RAG检索到的历史案例中提取装备信息
- 使用LLM结构化输出（JSON模式）确保可靠解析
- 提供完整追溯：装备名称、数量、上下文、置信度
- 强类型注解，不做降级或fallback
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from emergency_agents.rag.pipe import RagChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractedEquipment:
    """从RAG案例中提取的装备信息（不可变）。

    Attributes:
        name: 装备名称（如"生命探测仪"、"绳索救援器材"）。
        quantity: 装备数量，None表示未提及具体数量。
        context: 装备出现的上下文片段（用于追溯验证）。
        confidence: LLM提取置信度（0.0-1.0），反映装备信息的明确程度。
        source_chunk_id: RAG原始文本块标识（用于回溯到Qdrant）。
    """
    name: str
    quantity: Optional[int]
    context: str
    confidence: float
    source_chunk_id: str

    def __post_init__(self) -> None:
        """运行时验证约束条件。"""
        if not self.name or not self.name.strip():
            raise ValueError("装备名称不能为空")
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError(f"置信度必须在[0.0, 1.0]范围内，当前值: {self.confidence}")
        if self.quantity is not None and self.quantity < 0:
            raise ValueError(f"装备数量不能为负数，当前值: {self.quantity}")
        if not self.context or not self.context.strip():
            raise ValueError("上下文不能为空")
        if not self.source_chunk_id or not self.source_chunk_id.strip():
            raise ValueError("源chunk_id不能为空")


def extract_equipment_from_cases(
    cases: List[RagChunk],
    llm_client: Any,
    llm_model: str
) -> List[ExtractedEquipment]:
    """从RAG检索到的历史案例中提取装备信息。

    使用LLM的JSON模式结构化输出，确保返回格式可靠。不做降级或fallback，
    如果LLM无法提取则返回空列表。

    Args:
        cases: RAG检索到的历史案例片段列表。
        llm_client: OpenAI兼容的LLM客户端。
        llm_model: 模型名称（如"glm-4-flash"）。

    Returns:
        提取到的装备信息列表，按置信度降序排列。如果LLM无法提取或案例为空，返回空列表。

    Raises:
        ValueError: 当LLM返回格式无效且无法解析时。
        RuntimeError: 当LLM API调用失败时。

    Example:
        >>> cases = [RagChunk(text="使用生命探测仪18台...", source="wenchuan_2008", loc="p1")]
        >>> extracted = extract_equipment_from_cases(cases, llm_client, "glm-4-flash")
        >>> extracted[0].name
        '生命探测仪'
        >>> extracted[0].quantity
        18
    """
    if not cases:
        logger.info("无RAG案例，跳过装备提取")
        return []

    # 构建案例文本，保留chunk索引用于追溯
    cases_text_parts: List[str] = []
    for idx, chunk in enumerate(cases):
        cases_text_parts.append(
            f"[案例{idx+1}] 来源: {chunk.source}, 位置: {chunk.loc}\n{chunk.text}\n"
        )
    cases_text = "\n---\n".join(cases_text_parts)

    prompt = f"""你是应急救援装备分析专家。请从以下历史救援案例中提取装备信息。

## 历史案例
{cases_text}

## 提取要求
1. 提取所有明确提及的装备名称和数量
2. 如果数量未提及，quantity字段设为null
3. context字段填写装备出现的原文片段（30-80字）
4. confidence字段反映装备信息的明确程度：
   - 1.0: 明确提及装备名称和具体数量
   - 0.8-0.9: 明确装备名称，数量模糊（如"若干"、"多台"）
   - 0.6-0.7: 装备名称需要推断（如"探测设备"推断为"生命探测仪"）
   - <0.6: 高度模糊或不确定
5. source_chunk_id格式为"case_N"，N为案例编号（从1开始）

## 输出格式
返回JSON数组，每个元素包含：
{{
  "name": "装备名称",
  "quantity": 数量或null,
  "context": "原文片段",
  "confidence": 0.0-1.0,
  "source_chunk_id": "case_N"
}}

示例：
[
  {{
    "name": "生命探测仪",
    "quantity": 18,
    "context": "调用生命探测仪18台，用于搜救被困人员",
    "confidence": 1.0,
    "source_chunk_id": "case_1"
  }},
  {{
    "name": "绳索救援器材",
    "quantity": null,
    "context": "携带若干绳索救援器材，用于高空救援",
    "confidence": 0.85,
    "source_chunk_id": "case_2"
  }}
]

只返回JSON数组，不要包含其他内容。如果没有装备信息，返回空数组[]。"""

    try:
        # 使用temperature=0确保稳定输出
        response = llm_client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}  # 强制JSON输出
        )

        llm_output = response.choices[0].message.content.strip()

        if not llm_output:
            logger.warning("LLM返回空输出，可能无装备信息可提取")
            return []

        try:
            # 尝试直接解析JSON
            parsed = json.loads(llm_output)
        except json.JSONDecodeError as e:
            # JSON解析失败，尝试提取数组部分
            import re
            match = re.search(r'\[.*\]', llm_output, re.DOTALL)
            if not match:
                raise ValueError(f"LLM输出无法解析为JSON数组: {llm_output[:200]}") from e
            parsed = json.loads(match.group(0))

        # 如果返回的是对象而非数组（某些模型会包装），尝试提取
        if isinstance(parsed, dict):
            if "equipment" in parsed:
                parsed = parsed["equipment"]
            elif "items" in parsed:
                parsed = parsed["items"]
            else:
                logger.warning("LLM返回对象而非数组，且无equipment/items字段，可能无装备: %s", parsed)
                return []

        if not isinstance(parsed, list):
            raise ValueError(f"LLM输出格式错误：期望数组，实际为 {type(parsed)}")

        # 验证并构建ExtractedEquipment对象
        extracted_list: List[ExtractedEquipment] = []
        for item in parsed:
            if not isinstance(item, dict):
                logger.warning("跳过无效项（非对象）: %s", item)
                continue

            # 必需字段验证
            if "name" not in item or "confidence" not in item or "context" not in item or "source_chunk_id" not in item:
                logger.warning("跳过缺失必需字段的项: %s", item)
                continue

            try:
                equipment = ExtractedEquipment(
                    name=str(item["name"]).strip(),
                    quantity=int(item["quantity"]) if item.get("quantity") is not None else None,
                    context=str(item["context"]).strip(),
                    confidence=float(item["confidence"]),
                    source_chunk_id=str(item["source_chunk_id"]).strip()
                )
                extracted_list.append(equipment)
            except (ValueError, TypeError) as e:
                logger.warning("跳过无效装备项: %s, 错误: %s", item, e)
                continue

        # 按置信度降序排列
        extracted_list.sort(key=lambda eq: eq.confidence, reverse=True)

        logger.info("从%d个RAG案例中提取到%d项装备信息", len(cases), len(extracted_list))
        return extracted_list

    except json.JSONDecodeError as e:
        error_msg = f"LLM输出JSON解析失败: {e}, 输出内容: {llm_output[:200] if 'llm_output' in locals() else 'N/A'}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e
    except Exception as e:
        error_msg = f"装备提取失败: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        raise RuntimeError(error_msg) from e
