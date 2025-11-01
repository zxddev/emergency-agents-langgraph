from __future__ import annotations

import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, NonNegativeFloat, NonNegativeInt, PositiveInt

from emergency_agents.config import AppConfig
from emergency_agents.llm.client import get_openai_client
from emergency_agents.llm.prompts.rescue_assessment import build_rescue_assessment_prompt

logger = structlog.get_logger(__name__)


class DisasterType(str, Enum):
    FLOOD = "洪涝灾害"
    DROUGHT = "干旱灾害"
    TYPHOON = "台风灾害"
    WIND_HAIL = "风雹灾害"
    COLD_SNAP = "低温冷冻灾害"
    SNOW = "雪灾"
    SANDSTORM = "沙尘暴灾害"
    EARTHQUAKE = "地震灾害"
    GEOLOGICAL = "地质灾害"
    MARINE = "海洋灾害"
    FOREST_FIRE = "森林草原火灾"
    BIOLOGICAL = "生物灾害"


class BasicInfo(BaseModel):
    disaster_type: DisasterType = Field(..., description="灾种分类，应符合国家灾情统计体系。")
    occurrence_time: datetime = Field(..., description="灾害发生时间，需精确到分钟。")
    report_time: datetime = Field(..., description="本次汇报生成时间。")
    location: str = Field(..., description="灾害主要影响行政区。")
    command_unit: str = Field(..., description="执行前突任务的指挥单位名称。")
    frontline_overview: Optional[str] = Field(
        None,
        description="现场总体态势概述，例如地形、天气、交通可达性等。",
    )
    communication_status: Optional[str] = Field(None, description="现场通信状况补充说明。")
    weather_trend: Optional[str] = Field(None, description="未来 24-48 小时天气趋势。")


class CasualtyStats(BaseModel):
    affected_population: Optional[NonNegativeInt] = Field(None, description="受灾人口数量。")
    deaths: Optional[NonNegativeInt] = Field(None, description="因灾死亡人数。")
    missing: Optional[NonNegativeInt] = Field(None, description="因灾失踪人数。")
    injured: Optional[NonNegativeInt] = Field(None, description="受伤人数。")
    emergency_evacuation: Optional[NonNegativeInt] = Field(None, description="紧急避险转移人口。")
    emergency_resettlement: Optional[NonNegativeInt] = Field(None, description="紧急安置人口。")
    urgent_life_support: Optional[NonNegativeInt] = Field(None, description="需紧急生活救助人口。")
    requiring_support: Optional[NonNegativeInt] = Field(None, description="仍需持续救助人口。")
    casualty_notes: Optional[str] = Field(None, description="其他与人员相关的说明。")


class DisruptionStatus(BaseModel):
    road_blocked_villages: Optional[NonNegativeInt] = Field(None, description="道路中断的行政村/社区数量。")
    power_outage_villages: Optional[NonNegativeInt] = Field(None, description="供电中断的行政村/社区数量。")
    water_outage_villages: Optional[NonNegativeInt] = Field(None, description="供水中断的行政村/社区数量。")
    telecom_outage_villages: Optional[NonNegativeInt] = Field(None, description="通信中断的行政村/社区数量。")
    infrastructure_notes: Optional[str] = Field(None, description="其他基础设施或生命线受损情况补充。")


class InfrastructureDamage(BaseModel):
    collapsed_buildings: Optional[NonNegativeInt] = Field(None, description="倒塌房屋间数。")
    severely_damaged_buildings: Optional[NonNegativeInt] = Field(None, description="严重损坏房屋间数。")
    mildly_damaged_buildings: Optional[NonNegativeInt] = Field(None, description="一般损坏房屋间数。")
    transport_damage: Optional[str] = Field(None, description="交通设施受损情况。")
    communication_damage: Optional[str] = Field(None, description="通信设施受损情况。")
    energy_damage: Optional[str] = Field(None, description="电力、燃气等能源设施受损情况。")
    water_facility_damage: Optional[str] = Field(None, description="水利及供水设施受损情况。")
    public_service_damage: Optional[str] = Field(None, description="医院、学校等公共服务设施情况。")
    direct_economic_loss: Optional[NonNegativeFloat] = Field(
        None,
        description="直接经济损失（万元），如无法统计可为空。",
    )
    other_critical_damage: Optional[str] = Field(None, description="其它重点损毁信息。")


class AgricultureDamage(BaseModel):
    affected_area_ha: Optional[NonNegativeFloat] = Field(
        None, description="农作物受灾面积（公顷）。"
    )
    ruined_area_ha: Optional[NonNegativeFloat] = Field(
        None, description="农作物成灾面积（公顷）。"
    )
    destroyed_area_ha: Optional[NonNegativeFloat] = Field(
        None, description="农作物绝收面积（公顷）。"
    )
    livestock_loss: Optional[str] = Field(None, description="畜牧、水产等损失情况。")
    other_agri_loss: Optional[str] = Field(None, description="其他涉农损失说明。")


class ForceUnit(BaseModel):
    name: str = Field(..., description="力量名称，例如“消防救援总队一支队”。")
    personnel: Optional[PositiveInt] = Field(None, description="投入该力量的人数。")
    equipment: Optional[str] = Field(None, description="携带的主要装备。")
    tasks: Optional[str] = Field(None, description="承担的作战任务。")


class ResourceDeployment(BaseModel):
    deployed_forces: List[ForceUnit] = Field(
        default_factory=list,
        description="已投入的救援力量清单。",
    )
    air_support: Optional[str] = Field(None, description="航空或无人机支援情况。")
    waterborne_support: Optional[str] = Field(None, description="水面或水下救援力量情况。")
    medical_support: Optional[str] = Field(None, description="医疗救护与防疫力量部署。")
    engineering_support: Optional[str] = Field(None, description="工程抢险力量部署。")
    public_security_support: Optional[str] = Field(None, description="公安、武警等维稳力量部署。")
    logistics_support: Optional[str] = Field(None, description="后勤、物资发放、油料补给等情况。")


class SupportNeeds(BaseModel):
    reinforcement_forces: Optional[str] = Field(None, description="需追加的救援力量种类与规模。")
    material_shortages: Optional[str] = Field(None, description="亟需调拨的物资种类与数量。")
    infrastructure_requests: Optional[str] = Field(None, description="需上级协调的交通、通信、能源保障。")
    coordination_matters: Optional[str] = Field(None, description="需指挥部决策的重点事项。")


class RiskOutlook(BaseModel):
    aftershock_risk: Optional[str] = Field(None, description="余震、滑坡等地质次生风险评估。")
    meteorological_risk: Optional[str] = Field(None, description="降雨、降温、大风等气象风险。")
    hydrological_risk: Optional[str] = Field(None, description="堰塞湖、洪水、溃坝等水文风险。")
    hazardous_sources: Optional[str] = Field(None, description="危化品、油气管线等重大风险源。")
    safety_measures: Optional[str] = Field(None, description="拟采取的防范与安全措施。")


class OperationsProgress(BaseModel):
    completed_actions: Optional[str] = Field(None, description="已完成的救援行动。")
    ongoing_actions: Optional[str] = Field(None, description="正在推进的重点任务。")
    pending_actions: Optional[str] = Field(None, description="待指挥部批示的事项或下一步计划。")


class RescueAssessmentInput(BaseModel):
    basic: BasicInfo
    casualties: CasualtyStats
    disruptions: DisruptionStatus
    infrastructure: InfrastructureDamage
    agriculture: AgricultureDamage
    resources: ResourceDeployment
    support_needs: SupportNeeds
    risk_outlook: RiskOutlook
    operations: OperationsProgress


class RescueAssessmentResponse(BaseModel):
    report_text: str = Field(..., description="面向指挥大厅的完整灾情汇报，Markdown 格式。")
    key_points: List[str] = Field(
        default_factory=list,
        description="便于前端展示的要点摘要，可用于快速检索关键结论。",
    )


router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/rescue-assessment", response_model=RescueAssessmentResponse)
async def generate_rescue_assessment(payload: RescueAssessmentInput) -> RescueAssessmentResponse:
    """生成救援评估汇报。"""

    cfg = AppConfig.load_from_env()
    prompt_payload = _build_prompt_payload(payload)
    prompt = build_rescue_assessment_prompt(prompt_payload)

    llm_client = get_openai_client(cfg)
    started_at = time.perf_counter()

    try:
        completion = llm_client.chat.completions.create(
            model=cfg.llm_model,
            temperature=0.2,
            max_tokens=1500,
            presence_penalty=0,
            frequency_penalty=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名国家级应急救援指挥专家，擅长将复杂灾情转化为结构化的正式汇报。"
                        "务必严格遵循用户提供的数据，严禁虚构。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "rescue_assessment_generation_failed",
            latency_ms=elapsed_ms,
            disaster_type=payload.basic.disaster_type.value,
        )
        raise HTTPException(status_code=502, detail="模型生成失败，请稍后重试") from exc

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    content = completion.choices[0].message.content if completion.choices else None
    if not content:
        logger.error(
            "rescue_assessment_empty_response",
            latency_ms=elapsed_ms,
            disaster_type=payload.basic.disaster_type.value,
        )
        raise HTTPException(status_code=502, detail="模型未返回有效内容")

    key_points = _extract_key_points(payload)
    logger.info(
        "rescue_assessment_generated",
        latency_ms=elapsed_ms,
        disaster_type=payload.basic.disaster_type.value,
        key_points=key_points,
    )
    return RescueAssessmentResponse(report_text=content, key_points=key_points)


def _fmt_datetime(dt: datetime) -> str:
    return dt.strftime("%Y年%m月%d日%H时%M分")


def _compact_dict(entries: Dict[str, Any]) -> Dict[str, Any]:
    def _valid(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set)):
            return bool(value)
        return True

    return {key: value for key, value in entries.items() if _valid(value)}


def _build_prompt_payload(payload: RescueAssessmentInput) -> Dict[str, Any]:
    deployed_forces = [
        _compact_dict(
            {
                "名称": unit.name,
                "人员": unit.personnel,
                "装备": unit.equipment,
                "任务": unit.tasks,
            }
        )
        for unit in payload.resources.deployed_forces
    ]

    return _compact_dict(
        {
            "基础信息": _compact_dict(
                {
                    "灾种": payload.basic.disaster_type.value,
                    "发生时间": _fmt_datetime(payload.basic.occurrence_time),
                    "报告时间": _fmt_datetime(payload.basic.report_time),
                    "所在地区": payload.basic.location,
                    "前突指挥单位": payload.basic.command_unit,
                    "现场概况": payload.basic.frontline_overview,
                    "通讯态势": payload.basic.communication_status,
                    "天气趋势": payload.basic.weather_trend,
                }
            ),
            "人员与群众": _compact_dict(
                {
                    "受灾人口": payload.casualties.affected_population,
                    "死亡": payload.casualties.deaths,
                    "失踪": payload.casualties.missing,
                    "受伤": payload.casualties.injured,
                    "紧急避险转移": payload.casualties.emergency_evacuation,
                    "紧急安置": payload.casualties.emergency_resettlement,
                    "需紧急生活救助": payload.casualties.urgent_life_support,
                    "需持续救助": payload.casualties.requiring_support,
                    "补充说明": payload.casualties.casualty_notes,
                }
            ),
            "生命线受损": _compact_dict(
                {
                    "道路中断行政村数": payload.disruptions.road_blocked_villages,
                    "供电中断行政村数": payload.disruptions.power_outage_villages,
                    "供水中断行政村数": payload.disruptions.water_outage_villages,
                    "通信中断行政村数": payload.disruptions.telecom_outage_villages,
                    "补充说明": payload.disruptions.infrastructure_notes,
                }
            ),
            "基础设施与房屋损毁": _compact_dict(
                {
                    "倒塌房屋": payload.infrastructure.collapsed_buildings,
                    "严重损坏房屋": payload.infrastructure.severely_damaged_buildings,
                    "一般损坏房屋": payload.infrastructure.mildly_damaged_buildings,
                    "交通设施": payload.infrastructure.transport_damage,
                    "通信设施": payload.infrastructure.communication_damage,
                    "能源设施": payload.infrastructure.energy_damage,
                    "水利设施": payload.infrastructure.water_facility_damage,
                    "公共服务设施": payload.infrastructure.public_service_damage,
                    "直接经济损失(万元)": payload.infrastructure.direct_economic_loss,
                    "其它关键信息": payload.infrastructure.other_critical_damage,
                }
            ),
            "农业与产业损失": _compact_dict(
                {
                    "农作物受灾面积(公顷)": payload.agriculture.affected_area_ha,
                    "农作物成灾面积(公顷)": payload.agriculture.ruined_area_ha,
                    "农作物绝收面积(公顷)": payload.agriculture.destroyed_area_ha,
                    "牲畜及水产损失": payload.agriculture.livestock_loss,
                    "其他产业损失": payload.agriculture.other_agri_loss,
                }
            ),
            "救援力量部署": _compact_dict(
                {
                    "现场力量": deployed_forces,
                    "航空支援": payload.resources.air_support,
                    "水面/水下支援": payload.resources.waterborne_support,
                    "医疗防疫支援": payload.resources.medical_support,
                    "工程抢险支援": payload.resources.engineering_support,
                    "公安武警支援": payload.resources.public_security_support,
                    "后勤保障": payload.resources.logistics_support,
                }
            ),
            "后续支援需求": _compact_dict(
                {
                    "需要增援的力量": payload.support_needs.reinforcement_forces,
                    "物资缺口": payload.support_needs.material_shortages,
                    "基础设施保障诉求": payload.support_needs.infrastructure_requests,
                    "需协调事项": payload.support_needs.coordination_matters,
                }
            ),
            "风险研判": _compact_dict(
                {
                    "地质灾害风险": payload.risk_outlook.aftershock_risk,
                    "气象风险": payload.risk_outlook.meteorological_risk,
                    "水文风险": payload.risk_outlook.hydrological_risk,
                    "重大风险源": payload.risk_outlook.hazardous_sources,
                    "防范举措": payload.risk_outlook.safety_measures,
                }
            ),
            "行动进展": _compact_dict(
                {
                    "已完成行动": payload.operations.completed_actions,
                    "进行中行动": payload.operations.ongoing_actions,
                    "待批示事项": payload.operations.pending_actions,
                }
            ),
        }
    )


def _extract_key_points(payload: RescueAssessmentInput) -> List[str]:
    points: List[str] = []

    casualties = payload.casualties
    if casualties.deaths:
        points.append(f"死亡 {casualties.deaths} 人")
    if casualties.missing:
        points.append(f"失踪 {casualties.missing} 人")
    if casualties.emergency_resettlement:
        points.append(f"紧急安置 {casualties.emergency_resettlement} 人")

    infra = payload.infrastructure
    if infra.direct_economic_loss is not None:
        points.append(f"直接经济损失 {infra.direct_economic_loss} 万元")
    if infra.collapsed_buildings:
        points.append(f"倒塌房屋 {infra.collapsed_buildings} 间")

    disruptions = payload.disruptions
    if disruptions.road_blocked_villages:
        points.append(f"道路中断村(社区) {disruptions.road_blocked_villages} 个")

    support = payload.support_needs
    if support.reinforcement_forces:
        points.append(f"增援诉求：{support.reinforcement_forces}")
    if support.material_shortages:
        points.append(f"物资缺口：{support.material_shortages}")

    risk = payload.risk_outlook
    if risk.aftershock_risk:
        points.append(f"地质风险：{risk.aftershock_risk}")
    if risk.meteorological_risk:
        points.append(f"气象风险：{risk.meteorological_risk}")

    return points[:8]

