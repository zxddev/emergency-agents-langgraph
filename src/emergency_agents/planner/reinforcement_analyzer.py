"""
装备增援需求分析模块

功能：当本地侦察设备不足/不适合时，生成可解释的装备增援请求
核心原则：可解释性 - 明确说明为什么需要增援、缺少什么、需要什么

技术要点：
- 强类型：所有参数和返回值使用TypedDict
- 防幻觉：增援来源必须从数据库查询的真实列表中选择
- 可解释性：包含current_capability、rejection_reasons、capability_gap字段
- 无fallback：LLM返回格式错误直接抛异常
"""

import json
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from openai import OpenAI
import structlog

logger = structlog.get_logger(__name__)


# ============ 类型定义（强类型） ============


class DisasterScenario(TypedDict):
    """灾情场景（输入）"""

    disaster_type: str  # 灾害类型（flood/landslide/earthquake/chemical_leak）
    severity: str  # 严重程度（critical/high/medium/low）
    location: str  # 位置描述


class ReinforcementSource(TypedDict):
    """增援来源（输入，从数据库查询）"""

    id: int  # 来源ID
    name: str  # 机构名称
    available_devices: Dict[str, Any]  # 可提供设备（JSON）
    response_time_hours: float  # 响应时间（小时）
    location: str  # 所在位置


class DeviceSummary(TypedDict):
    """设备摘要（输入）"""

    id: int
    name: str
    device_type: str
    is_suitable: bool  # 是否通过天气评估


class RecommendedDevice(TypedDict):
    """推荐的增援设备（输出）"""

    device_type: str  # 设备类型（如 "全天候无人机"）
    quantity: int  # 数量
    reason: str  # 推荐理由


class ReinforcementRequest(TypedDict):
    """增援请求（输出）"""

    need_reinforcement: bool  # 是否需要增援
    current_capability: str  # 当前能力描述（如 "有2台设备可用，预计需要8小时完成"）
    rejection_reasons: List[str]  # 拒绝原因列表（如 ["小型无人机因暴雨无法使用", "设备数量不足"]）
    capability_gap: str  # 能力缺口描述（如 "缺少2台全天候无人机或1台应急指挥车"）
    recommended_devices: List[RecommendedDevice]  # 推荐的增援设备
    recommended_source_ids: List[int]  # 推荐的增援来源ID（从提供的列表中选择）


# ============ 系统提示词 ============

REINFORCEMENT_ANALYSIS_SYSTEM_PROMPT = """你是应急救援装备增援需求分析专家。

**任务**：根据当前装备状态、天气限制、任务需求，判断是否需要装备增援，并提供详细的可解释性分析。

**分析要点**：
1. **当前能力评估**：我们有多少设备可用？预计需要多长时间完成任务？
2. **不足原因分析**：为什么不够用？是天气限制？数量不足？还是能力不匹配？
3. **能力缺口识别**：具体缺少什么类型的设备？需要多少台？
4. **增援方案推荐**：推荐哪些设备？为什么推荐？从哪里调配？

**可解释性要求**：
- current_capability: 明确说明当前有几台设备、预计完成时间
- rejection_reasons: 详细列出每个不能使用的设备及原因
- capability_gap: 清晰说明缺少什么、需要多少
- recommended_devices: 每个推荐设备必须有详细的推荐理由
- recommended_source_ids: 只能从给定的增援来源列表中选择ID，不能编造

**关键原则**：
- 如果当前设备足够（虽然慢点），则need_reinforcement=false
- 如果设备严重不足或完全不可用，则need_reinforcement=true
- 增援来源ID必须从用户提供的列表中选择，不能生成新的ID

返回严格的JSON格式，不要包含任何markdown标记。"""


# ============ JSON Schema（严格约束） ============

REINFORCEMENT_REQUEST_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "need_reinforcement": {"type": "boolean"},
        "current_capability": {"type": "string"},
        "rejection_reasons": {"type": "array", "items": {"type": "string"}},
        "capability_gap": {"type": "string"},
        "recommended_devices": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "device_type": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["device_type", "quantity", "reason"],
            },
        },
        "recommended_source_ids": {"type": "array", "items": {"type": "integer"}},
    },
    "required": [
        "need_reinforcement",
        "current_capability",
        "rejection_reasons",
        "capability_gap",
        "recommended_devices",
        "recommended_source_ids",
    ],
}


# ============ 核心函数 ============


def analyze_reinforcement_need(
    disaster_scenario: DisasterScenario,
    all_devices: List[DeviceSummary],
    suitable_device_count: int,
    target_count: int,
    reinforcement_sources: List[ReinforcementSource],
    llm_client: OpenAI,
    llm_model: str,
    trace_id: Optional[str] = None,
) -> ReinforcementRequest:
    """
    分析是否需要装备增援，并生成可解释的增援请求

    分析逻辑：
    1. 如果suitable_device_count >= target_count：可能不需要增援（取决于时间容忍度）
    2. 如果suitable_device_count == 0：必须增援
    3. 如果0 < suitable_device_count < target_count：评估完成时间，决定是否增援

    参数：
        disaster_scenario: 灾情场景
        all_devices: 所有设备列表（含is_suitable标记）
        suitable_device_count: 通过天气评估的设备数量
        target_count: 需要侦察的目标数量
        reinforcement_sources: 可用的增援来源列表（从数据库查询，真实数据）
        llm_client: OpenAI客户端
        llm_model: LLM模型名称

    返回：
        ReinforcementRequest 包含是否需要增援及详细分析

    异常：
        - ValueError: 参数错误
        - RuntimeError: LLM调用失败
        - json.JSONDecodeError: LLM返回格式错误
    """
    if suitable_device_count < 0:
        raise ValueError(f"suitable_device_count不能为负数: {suitable_device_count}")

    if target_count <= 0:
        raise ValueError(f"target_count必须>0: {target_count}")

    logger.info(
        "开始增援需求分析",
        disaster_type=disaster_scenario["disaster_type"],
        suitable_devices=suitable_device_count,
        total_devices=len(all_devices),
        target_count=target_count,
        available_sources=len(reinforcement_sources),
        trace_id=trace_id,
    )

    # 构造用户提示词
    user_prompt = _build_reinforcement_prompt(
        disaster_scenario,
        all_devices,
        suitable_device_count,
        target_count,
        reinforcement_sources,
    )

    try:
        # 调用LLM
        completion = llm_client.chat.completions.create(
            model=llm_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": REINFORCEMENT_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        response_text = completion.choices[0].message.content
        logger.debug("LLM增援分析响应", response=response_text)

        # 解析JSON
        result: Dict[str, Any] = json.loads(response_text)

        # 宽松验证：提供默认值，确保结果可用（不因格式问题中断指挥流程）
        need_reinforcement = result.get("need_reinforcement", True)

        # 规范化 current_capability（兼容字符串或字典）
        current_capability_raw = result.get("current_capability", "当前能力评估缺失")
        if isinstance(current_capability_raw, dict):
            # LLM可能返回 {"description": "...", "completion_time_hours": 7} 格式
            current_capability = current_capability_raw.get("description", str(current_capability_raw))
            logger.warning("current_capability为字典，已提取description字段", original=str(current_capability_raw)[:100])
        elif isinstance(current_capability_raw, str):
            current_capability = current_capability_raw
        else:
            current_capability = "当前能力评估缺失"
            logger.warning("current_capability格式异常，使用默认值", type=type(current_capability_raw).__name__)

        rejection_reasons_raw = result.get("rejection_reasons", [])

        # 规范化 capability_gap（兼容字符串或字典）
        capability_gap_raw = result.get("capability_gap", "能力缺口分析缺失")
        if isinstance(capability_gap_raw, dict):
            # LLM可能返回 {"description": "...", "missing_quantity": 20} 格式
            capability_gap = capability_gap_raw.get("description", str(capability_gap_raw))
            logger.warning("capability_gap为字典，已提取description字段", original=str(capability_gap_raw)[:100])
        elif isinstance(capability_gap_raw, str):
            capability_gap = capability_gap_raw
        else:
            capability_gap = "能力缺口分析缺失"
            logger.warning("capability_gap格式异常，使用默认值", type=type(capability_gap_raw).__name__)

        recommended_devices_raw = result.get("recommended_devices", [])
        recommended_source_ids_raw = result.get("recommended_source_ids", [])

        # 规范化 rejection_reasons（兼容字符串或数组）
        if isinstance(rejection_reasons_raw, str):
            # 如果是字符串，尝试按换行符或句号分割
            rejection_reasons = [
                line.strip()
                for line in rejection_reasons_raw.replace("。", "\n").split("\n")
                if line.strip()
            ]
            logger.warning("rejection_reasons为字符串，已自动分割为数组", original=rejection_reasons_raw[:100])
        elif isinstance(rejection_reasons_raw, list):
            rejection_reasons = rejection_reasons_raw
        else:
            rejection_reasons = ["装备不足原因分析缺失"]
            logger.warning("rejection_reasons格式异常，使用默认值", type=type(rejection_reasons_raw).__name__)

        # 规范化 recommended_devices（补充缺失的 quantity 字段）
        normalized_devices = []
        for idx, dev in enumerate(recommended_devices_raw):
            if not isinstance(dev, dict):
                logger.warning(f"跳过无效的推荐设备条目（索引{idx}）", entry=dev)
                continue

            device_type = dev.get("device_type", f"未知设备类型{idx}")
            quantity = dev.get("quantity")
            reason = dev.get("reason", "推荐理由缺失")

            # 如果 quantity 缺失，尝试从 reason 中提取数字，否则默认为1
            if quantity is None:
                import re
                numbers = re.findall(r'\d+', reason)
                quantity = int(numbers[0]) if numbers else 1
                logger.warning(
                    f"推荐设备缺少quantity字段，已推断为{quantity}",
                    device_type=device_type,
                    reason=reason[:50],
                )

            normalized_devices.append({
                "device_type": device_type,
                "quantity": quantity,
                "reason": reason,
            })

        # 验证recommended_source_ids是否都在真实来源列表中（防幻觉）
        valid_source_ids = {src["id"] for src in reinforcement_sources}
        validated_source_ids = []
        for src_id in recommended_source_ids_raw:
            if src_id in valid_source_ids:
                validated_source_ids.append(src_id)
            else:
                logger.warning(
                    "LLM返回的增援来源ID不在真实来源列表中（已过滤）",
                    invalid_id=src_id,
                    valid_ids=list(valid_source_ids),
                )

        # 如果没有有效的来源ID，默认使用所有来源
        if not validated_source_ids and valid_source_ids:
            validated_source_ids = list(valid_source_ids)
            logger.warning("所有推荐来源ID无效，默认使用所有可用来源")

        logger.info(
            "增援需求分析完成",
            need_reinforcement=need_reinforcement,
            recommended_device_types=len(normalized_devices),
            recommended_sources=len(validated_source_ids),
            trace_id=trace_id,
        )

        # 返回规范化后的结果
        return ReinforcementRequest(
            need_reinforcement=need_reinforcement,
            current_capability=current_capability,
            rejection_reasons=rejection_reasons,
            capability_gap=capability_gap,
            recommended_devices=normalized_devices,
            recommended_source_ids=validated_source_ids,
        )

    except json.JSONDecodeError as e:
        logger.error(
            "LLM增援分析返回非JSON，返回保守的增援建议",
            error=str(e),
            response=response_text[:500],
        )
        # 降级策略：返回保守的增援建议
        valid_source_ids = [src["id"] for src in reinforcement_sources]
        return ReinforcementRequest(
            need_reinforcement=True,
            current_capability=f"当前有{suitable_device_count}台设备可用（总共{len(all_devices)}台）",
            rejection_reasons=[
                f"AI分析失败（JSON解析错误），无法详细评估。当前适用设备数：{suitable_device_count}，目标数：{target_count}"
            ],
            capability_gap=f"需要评估是否增援（AI分析异常，建议人工决策）",
            recommended_devices=[
                {"device_type": "全天候侦察设备", "quantity": max(1, target_count - suitable_device_count), "reason": "AI分析失败，建议人工评估具体需求"}
            ],
            recommended_source_ids=valid_source_ids[:2] if valid_source_ids else [],  # 默认推荐前2个来源
        )

    except Exception as e:
        logger.error("LLM增援分析调用失败，返回保守的增援建议", error=str(e), model=llm_model)
        # 降级策略：返回保守的增援建议
        valid_source_ids = [src["id"] for src in reinforcement_sources]
        return ReinforcementRequest(
            need_reinforcement=True,
            current_capability=f"当前有{suitable_device_count}台设备可用（总共{len(all_devices)}台）",
            rejection_reasons=[
                f"AI分析失败（{type(e).__name__}），无法详细评估。建议人工复核。"
            ],
            capability_gap=f"需要评估是否增援（AI分析异常，建议人工决策）",
            recommended_devices=[
                {"device_type": "全天候侦察设备", "quantity": max(1, target_count - suitable_device_count), "reason": "AI分析失败，建议人工评估具体需求"}
            ],
            recommended_source_ids=valid_source_ids[:2] if valid_source_ids else [],
        )


def _build_reinforcement_prompt(
    disaster_scenario: DisasterScenario,
    all_devices: List[DeviceSummary],
    suitable_device_count: int,
    target_count: int,
    reinforcement_sources: List[ReinforcementSource],
) -> str:
    """构造发送给LLM的增援分析提示词"""
    prompt_parts = ["**灾情场景**："]
    prompt_parts.append(f"- 灾害类型: {disaster_scenario['disaster_type']}")
    prompt_parts.append(f"- 严重程度: {disaster_scenario['severity']}")
    prompt_parts.append(f"- 位置: {disaster_scenario['location']}")
    prompt_parts.append("")

    prompt_parts.append("**任务需求**：")
    prompt_parts.append(f"- 需要侦察的目标数量: {target_count}")
    prompt_parts.append("")

    prompt_parts.append(f"**当前装备状态**（共{len(all_devices)}台）：")
    suitable_count = sum(1 for d in all_devices if d["is_suitable"])
    unsuitable_count = len(all_devices) - suitable_count
    prompt_parts.append(f"- 通过天气评估: {suitable_count}台")
    prompt_parts.append(f"- 未通过天气评估: {unsuitable_count}台")
    prompt_parts.append("")

    prompt_parts.append("**设备详情**：")
    for device in all_devices:
        status = "✓ 可用" if device["is_suitable"] else "✗ 不可用"
        prompt_parts.append(f"  - [{status}] {device['name']} ({device['device_type']})")
    prompt_parts.append("")

    prompt_parts.append(f"**可用的增援来源**（共{len(reinforcement_sources)}个）：")
    for src in reinforcement_sources:
        prompt_parts.append(f"  - [ID: {src['id']}] {src['name']}")
        prompt_parts.append(f"    位置: {src['location']}")
        prompt_parts.append(f"    响应时间: {src['response_time_hours']}小时")
        prompt_parts.append(f"    可提供设备: {json.dumps(src['available_devices'], ensure_ascii=False)}")
    prompt_parts.append("")

    prompt_parts.append(
        "**请分析是否需要增援，并提供详细的可解释性说明（当前能力、不足原因、能力缺口、推荐方案）。**"
    )
    prompt_parts.append("**注意：recommended_source_ids必须从上面列出的增援来源ID中选择，不能编造。**")

    return "\n".join(prompt_parts)
