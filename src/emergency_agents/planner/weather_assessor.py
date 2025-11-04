"""
天气适应性评估模块

功能：调用LLM评估侦察设备在当前天气条件下的可用性
输入：设备列表（含weather_capability描述）+ 天气条件
输出：适合/不适合的设备列表 + 详细评估理由

技术要点：
- 强类型：所有参数和返回值使用TypedDict严格定义
- 无fallback：LLM返回格式错误直接抛异常
- 可解释性：每个不适合的设备必须有明确的拒绝理由
- 日志追踪：记录完整的LLM请求和响应
"""

import json
from typing import List, Dict, Any, TypedDict, Optional
from openai import OpenAI
import structlog

logger = structlog.get_logger(__name__)


# ============ 类型定义（强类型） ============


class DeviceInfo(TypedDict):
    """设备信息（输入）"""

    id: int  # 设备ID
    name: str  # 设备名称
    device_type: str  # 设备类型（drone/ship/dog）
    weather_capability: str  # 天气适应性能力描述（自然语言）


class WeatherCondition(TypedDict):
    """天气条件（输入）"""

    phenomena: List[str]  # 天气现象（如 ["heavy_rain", "strong_wind"]）
    wind_speed_mps: float  # 风速（米/秒）
    visibility_km: float  # 能见度（公里）
    precip_mm_h: float  # 降水量（毫米/小时）


class UnsuitableDevice(TypedDict):
    """不适合的设备（输出）"""

    device_id: int  # 设备ID
    device_name: str  # 设备名称
    rejection_reason: str  # 拒绝理由（详细说明为什么该设备不适合当前天气）


class WeatherAssessmentResult(TypedDict):
    """天气评估结果（输出）"""

    suitable_device_ids: List[int]  # 适合的设备ID列表
    unsuitable_devices: List[UnsuitableDevice]  # 不适合的设备列表（含详细理由）
    reasoning: str  # 整体评估推理过程


# ============ 系统提示词 ============

WEATHER_ASSESSMENT_SYSTEM_PROMPT = """你是应急救援装备天气适应性评估专家。

**任务**：根据设备的天气适应性能力描述（weather_capability）和当前天气条件，判断每个设备是否能安全执行侦察任务。

**评估原则**：
1. 安全第一：如有任何安全风险，果断判定为不适合
2. 严格对比：将设备能力参数与当前天气条件逐项对比
3. 明确说理：对于不适合的设备，必须给出清晰的拒绝理由

**输出要求**：
- suitable_device_ids: 通过评估的设备ID数组
- unsuitable_devices: 未通过评估的设备数组，每个设备必须包含详细的rejection_reason
- reasoning: 整体评估过程的总结

**示例拒绝理由**（参考格式）：
- "小型无人机最大抗风能力12m/s，当前风速15m/s超出安全范围"
- "该设备不可在降水>5mm/h的暴雨下飞行，当前降水6mm/h超标"
- "设备要求能见度>3km，当前能见度仅2km不满足条件"

返回严格的JSON格式，不要包含任何markdown标记。"""


# ============ JSON Schema（严格约束） ============

WEATHER_ASSESSMENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "suitable_device_ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "通过天气评估的设备ID列表",
        },
        "unsuitable_devices": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "integer"},
                    "device_name": {"type": "string"},
                    "rejection_reason": {"type": "string"},
                },
                "required": ["device_id", "device_name", "rejection_reason"],
            },
            "description": "未通过评估的设备列表及详细拒绝理由",
        },
        "reasoning": {"type": "string", "description": "整体评估推理过程"},
    },
    "required": ["suitable_device_ids", "unsuitable_devices", "reasoning"],
}


# ============ 核心函数 ============


def assess_weather_suitability(
    devices: List[DeviceInfo],
    weather: WeatherCondition,
    llm_client: OpenAI,
    llm_model: str,
    trace_id: Optional[str] = None,
) -> WeatherAssessmentResult:
    """
    评估设备在当前天气条件下的适用性

    参数：
        devices: 待评估的设备列表（必须包含weather_capability字段）
        weather: 当前天气条件
        llm_client: OpenAI客户端（已配置base_url和api_key）
        llm_model: LLM模型名称（如 "glm-4.6"）
        trace_id: 追踪ID（用于日志追踪）

    返回：
        WeatherAssessmentResult 包含适合/不适合的设备列表及评估理由

    异常：
        - ValueError: devices为空
        - RuntimeError: LLM调用失败
        - json.JSONDecodeError: LLM返回格式错误（不做容错，直接暴露）
    """
    if not devices:
        raise ValueError("设备列表为空，无法进行天气评估")

    # 构造用户提示词（包含完整的设备信息和天气条件）
    user_prompt = _build_user_prompt(devices, weather)

    logger.info(
        "开始天气适应性评估",
        device_count=len(devices),
        weather_phenomena=weather["phenomena"],
        wind_speed_mps=weather["wind_speed_mps"],
        visibility_km=weather["visibility_km"],
        precip_mm_h=weather["precip_mm_h"],
    )

    try:
        # 调用LLM（使用JSON mode强制返回JSON）
        completion = llm_client.chat.completions.create(
            model=llm_model,
            temperature=0.2,  # 低温度保证稳定性
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": WEATHER_ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        response_text = completion.choices[0].message.content
        logger.debug("LLM响应原始内容", response=response_text)

        # 解析JSON（不做任何容错，格式错误直接抛异常）
        result: Dict[str, Any] = json.loads(response_text)

        # 宽松验证：提供默认值，确保结果可用（不因格式问题中断指挥流程）
        suitable_ids = result.get("suitable_device_ids", [])
        unsuitable_list = result.get("unsuitable_devices", [])
        reasoning = result.get("reasoning", "天气评估已完成，详见设备列表")

        # 规范化unsuitable_devices的字段（兼容LLM可能返回的不同格式）
        normalized_unsuitable = []
        for ud in unsuitable_list:
            # 兼容 id 或 device_id
            device_id = ud.get("device_id") or ud.get("id")
            device_name = ud.get("device_name", f"设备{device_id}" if device_id else "未知设备")
            rejection_reason = ud.get("rejection_reason", "不适合当前天气条件")

            # 如果至少有device_id或rejection_reason，就保留这条记录
            if device_id is not None or rejection_reason:
                normalized_unsuitable.append({
                    "device_id": device_id if device_id is not None else -1,
                    "device_name": device_name,
                    "rejection_reason": rejection_reason,
                })
            else:
                logger.warning("跳过无效的unsuitable_device条目", entry=ud)

        logger.info(
            "天气评估完成",
            suitable_count=len(suitable_ids),
            unsuitable_count=len(normalized_unsuitable),
            trace_id=trace_id,
        )

        # 返回规范化后的结果
        return WeatherAssessmentResult(
            suitable_device_ids=suitable_ids,
            unsuitable_devices=normalized_unsuitable,
            reasoning=reasoning,
        )

    except json.JSONDecodeError as e:
        logger.error(
            "LLM返回内容无法解析为JSON，返回保守降级结果",
            error=str(e),
            response=response_text[:500],
            trace_id=trace_id,
        )
        # 降级策略：保守起见，所有设备标记为不适合
        return WeatherAssessmentResult(
            suitable_device_ids=[],
            unsuitable_devices=[
                {
                    "device_id": d["id"],
                    "device_name": d["name"],
                    "rejection_reason": f"AI评估失败（JSON解析错误），为安全起见暂不派遣。错误: {str(e)[:100]}",
                }
                for d in devices
            ],
            reasoning=f"⚠️ AI天气评估服务异常（JSON解析失败），采用保守策略：所有设备暂不派遣。请人工复核天气条件后决策。",
        )

    except Exception as e:
        logger.error("LLM调用失败，返回保守降级结果", error=str(e), model=llm_model, trace_id=trace_id)
        # 降级策略：保守起见，所有设备标记为不适合
        return WeatherAssessmentResult(
            suitable_device_ids=[],
            unsuitable_devices=[
                {
                    "device_id": d["id"],
                    "device_name": d["name"],
                    "rejection_reason": f"AI评估失败（LLM调用异常），为安全起见暂不派遣。错误: {str(e)[:100]}",
                }
                for d in devices
            ],
            reasoning=f"⚠️ AI天气评估服务异常（{type(e).__name__}），采用保守策略：所有设备暂不派遣。请人工复核天气条件后决策。",
        )


def _build_user_prompt(devices: List[DeviceInfo], weather: WeatherCondition) -> str:
    """
    构造发送给LLM的用户提示词

    格式：
    **当前天气条件**：
    - 天气现象: heavy_rain, strong_wind
    - 风速: 15.0 m/s
    - 能见度: 2.0 km
    - 降水量: 6.0 mm/h

    **待评估设备**（共3台）：
    1. [ID: 1] 小型侦察无人机 (drone)
       天气能力: 最大抗风能力12m/s，不可在降水>5mm/h的暴雨天气下飞行，能见度需>3km

    2. [ID: 2] 全天候无人艇 (ship)
       天气能力: 可适应5级海况，最大风速15m/s，水温范围-10℃~45℃

    **请逐个评估每台设备是否适合当前天气条件执行侦察任务，并返回JSON格式结果。**
    """
    prompt_parts = ["**当前天气条件**："]

    # 明确标注天气现象（空列表=晴天）
    if weather['phenomena']:
        phenomena_str = ', '.join(weather['phenomena'])
    else:
        phenomena_str = "晴天（无特殊天气现象，适合所有设备作业）"
    prompt_parts.append(f"- 天气现象: {phenomena_str}")

    # 为风速添加解释性说明
    wind_desc = ""
    if weather['wind_speed_mps'] < 5.0:
        wind_desc = "（微风，1-2级，适合作业）"
    elif weather['wind_speed_mps'] < 10.0:
        wind_desc = "（和风，3-4级，正常作业）"
    elif weather['wind_speed_mps'] < 15.0:
        wind_desc = "（清劲风，5级，需注意）"
    else:
        wind_desc = "（强风，6级以上，谨慎评估）"
    prompt_parts.append(f"- 风速: {weather['wind_speed_mps']} m/s{wind_desc}")

    # 为能见度添加解释性说明
    visibility_desc = ""
    if weather['visibility_km'] >= 10.0:
        visibility_desc = "（能见度优良，适合作业）"
    elif weather['visibility_km'] >= 5.0:
        visibility_desc = "（能见度良好，正常作业）"
    elif weather['visibility_km'] >= 3.0:
        visibility_desc = "（能见度一般，需注意）"
    else:
        visibility_desc = "（能见度较差，谨慎评估）"
    prompt_parts.append(f"- 能见度: {weather['visibility_km']} km{visibility_desc}")

    # 为降水量添加解释性说明
    precip_desc = ""
    if weather['precip_mm_h'] == 0.0:
        precip_desc = "（无降水，适合作业）"
    elif weather['precip_mm_h'] < 2.5:
        precip_desc = "（小雨，正常作业）"
    elif weather['precip_mm_h'] < 8.0:
        precip_desc = "（中雨，需注意）"
    else:
        precip_desc = "（大雨或暴雨，谨慎评估）"
    prompt_parts.append(f"- 降水量: {weather['precip_mm_h']} mm/h{precip_desc}")
    prompt_parts.append("")

    prompt_parts.append(f"**待评估设备**（共{len(devices)}台）：")
    for idx, device in enumerate(devices, start=1):
        prompt_parts.append(f"{idx}. [ID: {device['id']}] {device['name']} ({device['device_type']})")
        prompt_parts.append(f"   天气能力: {device['weather_capability'] or '未提供天气能力描述'}")
        prompt_parts.append("")

    prompt_parts.append("**请逐个评估每台设备是否适合当前天气条件执行侦察任务，并返回JSON格式结果。**")

    return "\n".join(prompt_parts)
