#!/usr/bin/env python3
# Copyright 2025 msq
"""验证统一意图处理配置加载正确性。

使用方法：
    python scripts/validate_unified_config.py

预期输出：
    ✅ 所有配置项正确加载
    或显示具体的配置问题

参考：
    - config/dev.env
    - openspec/changes/unify-intent-processing/tasks.md (Phase 2.2)
"""
import os
import sys
from pathlib import Path


def load_env_file(env_path: Path) -> None:
    """加载.env文件到环境变量"""
    if not env_path.exists():
        print(f"❌ 配置文件不存在: {env_path}")
        sys.exit(1)

    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()


def validate_config():
    """验证统一意图处理相关配置"""
    print("=" * 60)
    print("统一意图处理配置验证")
    print("=" * 60)

    # 加载dev.env
    project_root = Path(__file__).parent.parent
    env_path = project_root / "config" / "dev.env"
    load_env_file(env_path)

    issues = []
    warnings = []

    # 验证 INTENT_UNIFIED_MODE
    unified_mode = os.getenv("INTENT_UNIFIED_MODE", "").lower()
    if unified_mode not in ["true", "false"]:
        issues.append(f"❌ INTENT_UNIFIED_MODE 值无效: '{unified_mode}' (应为 'true' 或 'false')")
    else:
        mode_text = "统一模式" if unified_mode == "true" else "旧版模式"
        print(f"✅ INTENT_UNIFIED_MODE: {unified_mode} ({mode_text})")

    # 验证 UNKNOWN_CONFIDENCE_THRESHOLD
    threshold_str = os.getenv("UNKNOWN_CONFIDENCE_THRESHOLD", "")
    try:
        threshold = float(threshold_str)
        if not (0.0 <= threshold <= 1.0):
            issues.append(f"❌ UNKNOWN_CONFIDENCE_THRESHOLD 超出范围: {threshold} (应在 0.0-1.0 之间)")
        else:
            print(f"✅ UNKNOWN_CONFIDENCE_THRESHOLD: {threshold}")
    except ValueError:
        issues.append(f"❌ UNKNOWN_CONFIDENCE_THRESHOLD 不是有效数字: '{threshold_str}'")

    # 验证 INTENT_UNIFIED_FALLBACK
    fallback = os.getenv("INTENT_UNIFIED_FALLBACK", "").lower()
    if fallback not in ["true", "false"]:
        issues.append(f"❌ INTENT_UNIFIED_FALLBACK 值无效: '{fallback}' (应为 'true' 或 'false')")
    else:
        fallback_text = "启用" if fallback == "true" else "禁用"
        print(f"✅ INTENT_UNIFIED_FALLBACK: {fallback} (自动降级: {fallback_text})")

    # 验证提示词文件存在
    prompt_path = project_root / "config" / "prompts" / "emergency_command_expert.txt"
    if not prompt_path.exists():
        issues.append(f"❌ 专家提示词文件不存在: {prompt_path}")
    else:
        prompt_size = prompt_path.stat().st_size
        print(f"✅ 专家提示词文件存在: {prompt_path.name} ({prompt_size} bytes)")

    # 验证核心模块文件存在
    unified_intent_path = project_root / "src" / "emergency_agents" / "intent" / "unified_intent.py"
    if not unified_intent_path.exists():
        issues.append(f"❌ 统一意图模块不存在: {unified_intent_path}")
    else:
        print(f"✅ 统一意图模块存在: {unified_intent_path.name}")

    expert_consult_path = project_root / "src" / "emergency_agents" / "intent" / "expert_consult.py"
    if not expert_consult_path.exists():
        issues.append(f"❌ 专家咨询模块不存在: {expert_consult_path}")
    else:
        print(f"✅ 专家咨询模块存在: {expert_consult_path.name}")

    # 验证LLM配置
    llm_model = os.getenv("LLM_MODEL", "")
    if not llm_model:
        warnings.append("⚠️  LLM_MODEL 未配置")
    else:
        print(f"✅ LLM_MODEL: {llm_model}")
        if llm_model not in ["glm-4.5-air", "glm-4.5", "glm-4"]:
            warnings.append(f"⚠️  推荐使用 glm-4.5-air 以获得最佳性能，当前: {llm_model}")

    # 验证OpenAI兼容端点
    openai_base_url = os.getenv("OPENAI_BASE_URL", "")
    if not openai_base_url:
        issues.append("❌ OPENAI_BASE_URL 未配置")
    else:
        print(f"✅ OPENAI_BASE_URL: {openai_base_url}")

    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_api_key:
        issues.append("❌ OPENAI_API_KEY 未配置")
    else:
        masked_key = openai_api_key[:8] + "..." + openai_api_key[-4:] if len(openai_api_key) > 12 else "***"
        print(f"✅ OPENAI_API_KEY: {masked_key}")

    print("\n" + "=" * 60)

    # 输出结果
    if issues:
        print("❌ 配置验证失败:")
        for issue in issues:
            print(f"  {issue}")
        if warnings:
            print("\n⚠️  警告:")
            for warning in warnings:
                print(f"  {warning}")
        print("\n请修复上述问题后重新验证。")
        sys.exit(1)
    elif warnings:
        print("✅ 配置验证通过（有警告）:")
        for warning in warnings:
            print(f"  {warning}")
        print("\n建议解决警告项以获得最佳体验。")
    else:
        print("✅ 配置验证完全通过")
        print("\n所有配置项正确，系统可以正常运行。")

    print("=" * 60)


if __name__ == "__main__":
    validate_config()
