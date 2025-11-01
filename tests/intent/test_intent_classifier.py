from __future__ import annotations

from typing import Any, Dict

from emergency_agents.intent.classifier import IntentClassifierRuntime
from emergency_agents.intent.providers.base import IntentThresholds
from emergency_agents.intent.providers.llm import LLMIntentProvider


class _DummyChatCompletion:
    def __init__(self, content: str) -> None:
        self._content = content

    def create(self, *, model: str, messages: list[Dict[str, Any]], temperature: float) -> Any:
        class _Choice:
            def __init__(self, text: str) -> None:
                self.message = type("Message", (), {"content": text})

        class _Response:
            def __init__(self, text: str) -> None:
                self.choices = [_Choice(text)]

        return _Response(self._content)


class _DummyLLM:
    def __init__(self, content: str) -> None:
        self.chat = type("Chat", (), {"completions": _DummyChatCompletion(content)})


def test_llm_runtime_basic_intent() -> None:
    dummy_llm = _DummyLLM(
        '{"intent_type": "rescue_task_generate", "slots": {"location_name": "A点", "coordinates": {"lat": 31.2, "lng": 103.9}, "mission_type": "rescue", "situation_summary": "A点厂房倒塌有5人被困，需要破拆救援。"}, '
        '"meta": {"need_confirm": false, "confidence": 0.82}}'
    )
    provider = LLMIntentProvider(dummy_llm, "glm")
    runtime = IntentClassifierRuntime(
        provider=provider,
        fallback=provider,
        thresholds=IntentThresholds(confidence=0.60, margin=0.10),
    )
    state: Dict[str, Any] = {"messages": [{"role": "user", "content": "A点有人受困"}]}

    result = runtime(state)

    assert result["intent"]["intent_type"] == "rescue_task_generate"
    assert result["intent"]["meta"]["need_confirm"] is False
    assert result["intent"]["meta"]["confidence"] == 0.82


def test_llm_runtime_threshold_triggers_unknown() -> None:
    dummy_llm = _DummyLLM(
        '{"intent_type": "rescue_task_generate", "slots": {"mission_type": "rescue", "coordinates": {"lat": 31.1, "lng": 103.8}, "situation_summary": "南侧道路塌陷，需要紧急疏散并组织破拆救援。"}, '
        '"meta": {"need_confirm": false, "confidence": 0.50}}'
    )
    provider = LLMIntentProvider(dummy_llm, "glm")
    runtime = IntentClassifierRuntime(
        provider=provider,
        fallback=provider,
        thresholds=IntentThresholds(confidence=0.70, margin=0.20),
    )
    state: Dict[str, Any] = {"raw_report": "东侧发生滑坡"}  # 低置信度触发兜底

    result = runtime(state)

    assert result["intent"]["intent_type"] == "unknown"
    assert result["intent"]["meta"]["need_confirm"] is True


def test_llm_runtime_low_margin_sets_need_confirm() -> None:
    dummy_llm = _DummyLLM(
        '{"intent_type": "rescue_task_generate", '
        '"slots": {"coordinates": {"lat": 31.0, "lng": 104.0}, "mission_type": "rescue", "situation_summary": "机器人附近厂房坍塌，需派机器人进入搜索救援。"}, '
        '"meta": {"need_confirm": false, "confidence": 0.72, "margin": 0.05}, '
        '"ranking": ['
        '  {"intent": "rescue_task_generate", "confidence": 0.72},'
        '  {"intent": "hazard_report", "confidence": 0.68}'
        "]}"
    )
    provider = LLMIntentProvider(dummy_llm, "glm")
    runtime = IntentClassifierRuntime(
        provider=provider,
        fallback=provider,
        thresholds=IntentThresholds(confidence=0.60, margin=0.20),
    )
    state: Dict[str, Any] = {"messages": [{"role": "user", "content": "控制机器狗走到B区"}]}

    result = runtime(state)

    assert result["intent"]["intent_type"] == "unknown"
    assert result["intent"]["meta"]["need_confirm"] is True
    assert result["intent"]["meta"]["confidence"] == 0.72


class _FailingProvider(LLMIntentProvider):
    def predict(self, text: str) -> Dict[str, Any]:  # type: ignore[override]
        raise RuntimeError("primary provider failed")


def test_runtime_fallback_when_provider_raises() -> None:
    fallback_llm = _DummyLLM(
        '{"intent_type": "rescue_task_generate", '
        '"slots": {"mission_type": "rescue", "location_name": "C区", "coordinates": {"lat": 31.5, "lng": 103.6}, "situation_summary": "C区仓库倒塌，需调派救援力量并转运伤员。"}, '
        '"meta": {"need_confirm": false, "confidence": 0.83}}'
    )
    fallback_provider = LLMIntentProvider(fallback_llm, "glm")
    failing_provider = _FailingProvider(fallback_llm, "glm")
    runtime = IntentClassifierRuntime(
        provider=failing_provider,
        fallback=fallback_provider,
        thresholds=IntentThresholds(confidence=0.60, margin=0.10),
    )
    state: Dict[str, Any] = {"messages": [{"role": "user", "content": "安排救援队前往C区"}]}

    result = runtime(state)

    assert result["intent"]["intent_type"] == "rescue_task_generate"
    assert result["intent"]["meta"]["need_confirm"] is False
