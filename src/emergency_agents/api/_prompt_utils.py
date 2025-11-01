from __future__ import annotations

from typing import Dict, List, Tuple

# 缺字段时的默认提示模板，键为规范化意图名称
_DEFAULT_MISSING_FIELD_PROMPTS: Dict[str, str] = {
    "rescue_task_generate": "请补充缺失的信息，确保指挥系统能生成可执行的救援方案。",
    "rescue-task-generate": "请补充缺失的信息，确保指挥系统能生成可执行的救援方案。",
    "hazard_report": "请补充缺失的信息，确保灾情记录完整准确。",
}

# 槽位字段与对外展示文本的映射
_FIELD_DISPLAY_NAMES: Dict[str, str] = {
    "mission_type": "任务类型",
    "location": "现场位置（地点名称或经纬度）",
    "location_name": "现场位置（地点名称）",
    "location_text": "现场位置（文本描述）",
    "event_type": "灾害类型",
}


def resolve_missing_prompt(
    canonical_intent: str | None,
    prompt_text: str | None,
    missing_fields: List[str],
) -> Tuple[str, str]:
    """根据槽位缺口生成提示文本，返回(提示内容, 来源标记)"""
    if prompt_text and prompt_text.strip():
        return prompt_text.strip(), "llm"

    readable_fields: List[str] = []
    for field_name in missing_fields:
        display_name: str = _FIELD_DISPLAY_NAMES.get(field_name, field_name)
        readable_fields.append(display_name)

    fields_segment: str = "、".join(readable_fields) if readable_fields else "必要信息"
    template_key: str = canonical_intent or ""
    default_prompt: str = _DEFAULT_MISSING_FIELD_PROMPTS.get(
        template_key,
        "请补充缺失的信息，确保作业流程可以继续执行。",
    )
    if readable_fields:
        default_prompt = default_prompt.replace("缺失的信息", fields_segment)
    return default_prompt, "fallback"

