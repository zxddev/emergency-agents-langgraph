# Copyright 2025 msq
import pytest
from emergency_agents.agents.situation import situation_agent, safe_json_parse
from emergency_agents.llm.client import get_openai_client
from emergency_agents.config import AppConfig


def test_safe_json_parse_direct():
    """测试直接JSON解析"""
    text = '{"key": "value", "number": 123}'
    result = safe_json_parse(text)
    assert result == {"key": "value", "number": 123}


def test_safe_json_parse_code_block():
    """测试代码块中的JSON"""
    text = '这是一些文字\n```json\n{"key": "value"}\n```\n其他文字'
    result = safe_json_parse(text)
    assert result == {"key": "value"}


def test_safe_json_parse_embedded():
    """测试嵌入式JSON"""
    text = '前面有文字 {"key": "value", "nested": {"inner": "data"}} 后面有文字'
    result = safe_json_parse(text)
    assert "key" in result
    assert result["key"] == "value"


def test_safe_json_parse_invalid():
    """测试无效JSON的容错"""
    text = 'this is completely not json at all'
    result = safe_json_parse(text)
    assert "parse_error" in result
    assert result["disaster_type"] == "unknown"


def test_safe_json_parse_chinese():
    """测试中文JSON"""
    text = '{"灾害类型": "地震", "震级": 7.8}'
    result = safe_json_parse(text)
    assert "灾害类型" in result
    assert result["灾害类型"] == "地震"


@pytest.mark.integration
def test_situation_agent_earthquake():
    """测试地震报告的态势感知
    
    Reference: docs/行动计划/ACTION-PLAN-DAY1.md lines 244-270
    """
    cfg = AppConfig.load_from_env()
    client = get_openai_client(cfg)
    
    state = {
        "rescue_id": "test_001",
        "raw_report": "四川汶川发生7.8级地震，震中位于北纬31.0度、东经103.4度，震源深度14公里。"
    }
    
    result = situation_agent(state, client, cfg.llm_model)
    
    assert "situation" in result
    sit = result["situation"]
    
    assert sit.get("disaster_type") in ["earthquake", "地震"]
    assert 7.0 <= sit.get("magnitude", 0) <= 8.5
    
    epicenter = sit.get("epicenter", {})
    assert 30.0 <= epicenter.get("lat", 0) <= 32.0
    assert 103.0 <= epicenter.get("lng", 0) <= 104.5
    
    print(f"✅ 态势感知测试通过: {sit}")


@pytest.mark.integration
def test_situation_agent_with_facilities():
    """测试识别附近设施
    
    Reference: docs/行动计划/ACTION-PLAN-DAY1.md lines 273-293
    """
    cfg = AppConfig.load_from_env()
    client = get_openai_client(cfg)
    
    state = {
        "raw_report": "汶川7.8级地震，震中附近有紫坪铺水库、多家化工厂和山区。"
    }
    
    result = situation_agent(state, client, cfg.llm_model)
    sit = result["situation"]
    
    facilities = sit.get("nearby_facilities", [])
    assert len(facilities) > 0
    
    facilities_str = str(facilities).lower()
    has_facility = any(keyword in facilities_str for keyword in ["水库", "化工", "山区", "reservoir", "chemical"])
    assert has_facility, f"Should identify facilities, got: {facilities}"
    
    print(f"✅ 设施识别测试通过: {facilities}")


@pytest.mark.integration
def test_situation_agent_idempotency():
    """测试幂等性"""
    cfg = AppConfig.load_from_env()
    client = get_openai_client(cfg)
    
    state = {
        "raw_report": "测试地震",
        "situation": {"disaster_type": "earthquake", "magnitude": 7.0}
    }
    
    result = situation_agent(state, client, cfg.llm_model)
    
    assert result["situation"]["magnitude"] == 7.0
    print("✅ 幂等性测试通过")


def test_situation_agent_empty_report():
    """测试空报告处理"""
    cfg = AppConfig.load_from_env()
    client = get_openai_client(cfg)
    
    state = {"rescue_id": "test_empty", "raw_report": ""}
    
    result = situation_agent(state, client, cfg.llm_model)
    
    assert "situation" in result
    assert "error" in result["situation"]
    print("✅ 空报告测试通过")


if __name__ == "__main__":
    test_safe_json_parse_direct()
    test_safe_json_parse_code_block()
    test_safe_json_parse_invalid()
    print("Unit tests passed, run integration tests with: pytest -m integration")

