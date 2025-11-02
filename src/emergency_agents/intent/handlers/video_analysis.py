from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from emergency_agents.db.dao import DeviceDAO, serialize_dataclass
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import VideoAnalysisSlots
from emergency_agents.video.frame_capture import VideoFrameCapture
from emergency_agents.video.vision import VisionAnalyzer, DangerLevel

logger = logging.getLogger(__name__)


@dataclass
class VideoAnalysisHandler(IntentHandler[VideoAnalysisSlots]):
    device_dao: DeviceDAO
    stream_map: Mapping[str, str]
    vllm_url: str  # GLM-4V 视觉模型 API 地址

    async def handle(self, slots: VideoAnalysisSlots, state: dict[str, object]) -> dict[str, object]:
        """视频分析意图处理 - 基于 GLM-4V 视觉大模型

        流程：
        1. 查询设备信息和视频流地址
        2. 从视频流截取当前帧
        3. 调用 GLM-4V 进行场景分析
        4. 返回自然语言描述 + 结构化数据

        Args:
            slots: 视频分析槽位（设备ID、分析目标）
            state: 会话状态

        Returns:
            处理结果（包含分析结果和对话式回复）

        Reference:
            - video/vision.py: VisionAnalyzer 视觉分析器
            - video/frame_capture.py: VideoFrameCapture 帧截取工具
        """
        logger.info(
            "video_analysis_start",
            extra={
                "intent": "video-analysis",
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "device_id": slots.device_id,
                "analysis_goal": slots.analysis_goal,
            },
        )

        # 1. 查询设备信息
        device = await self.device_dao.fetch_video_device(slots.device_id)
        if device is None:
            return {
                "response_text": f"未找到设备 {slots.device_id}，请检查设备ID是否正确。",
                "video_analysis": {"status": "device_not_found"},
            }

        # 2. 获取视频流地址
        stream_url = device.stream_url or self.stream_map.get(device.id)
        if stream_url is None:
            return {
                "response_text": f"设备 {device.name or device.id} 缺少视频流地址，请联系运维人员配置 stream_url。",
                "video_analysis": {"status": "missing_stream_url"},
            }

        try:
            # 3. 截取视频帧
            logger.info(f"Capturing frame from stream: {stream_url}")
            capturer = VideoFrameCapture(stream_url=stream_url, timeout=10.0, max_retries=2)
            capture_result = capturer.capture_frame()

            if not capture_result.success:
                logger.error(f"Frame capture failed: {capture_result.error_message}")
                return {
                    "response_text": f"无法从设备 {device.name or device.id} 获取视频画面：{capture_result.error_message}",
                    "video_analysis": {
                        "status": "capture_failed",
                        "error": capture_result.error_message,
                    },
                }

            # 4. 调用 GLM-4V 视觉分析
            logger.info(f"Analyzing frame with GLM-4V: image_size={capture_result.image_size}")
            analyzer = VisionAnalyzer(
                vllm_url=self.vllm_url,
                model_name="glm-4v",  # 智谱 GLM-4V 视觉模型
                timeout=30.0,
                temperature=0.1,
            )

            analysis_result = await analyzer.analyze_drone_image(
                image_base64=capture_result.image_base64
            )

            await analyzer.close()

            # 5. 生成自然语言描述（对话式回复）
            response_text = self._format_analysis_response(
                device_name=device.name or device.id,
                analysis_goal=slots.analysis_goal,
                result=analysis_result,
            )

            # 6. 返回结果
            logger.info(
                "video_analysis_completed",
                extra={
                    "device_id": slots.device_id,
                    "danger_level": analysis_result.danger_level.value,
                    "persons_count": analysis_result.persons.count,
                    "vehicles_count": analysis_result.vehicles.total_count,
                    "latency_ms": analysis_result.latency_ms,
                },
            )

            return {
                "response_text": response_text,
                "video_analysis": {
                    "status": "success",
                    "device_id": slots.device_id,
                    "device_name": device.name,
                    "analysis_goal": slots.analysis_goal,
                    "danger_level": analysis_result.danger_level.value,
                    "persons": {
                        "count": analysis_result.persons.count,
                        "activities": analysis_result.persons.activities,
                    },
                    "vehicles": {
                        "total_count": analysis_result.vehicles.total_count,
                        "by_type": analysis_result.vehicles.by_type,
                    },
                    "buildings": {
                        "total": analysis_result.buildings.total_buildings,
                        "damaged": analysis_result.buildings.damaged_count,
                        "collapse_risk": analysis_result.buildings.collapse_risk,
                    },
                    "roads": {
                        "passable": analysis_result.roads.passable,
                        "blocked_sections": analysis_result.roads.blocked_sections,
                    },
                    "hazards": analysis_result.hazards,
                    "recommendations": analysis_result.recommendations,
                    "confidence_score": analysis_result.confidence_score,
                    "latency_ms": analysis_result.latency_ms,
                },
            }

        except Exception as e:
            logger.error(f"Video analysis failed: {e}", exc_info=True)
            return {
                "response_text": f"视频分析过程中发生错误：{str(e)}。请稍后重试或联系技术支持。",
                "video_analysis": {
                    "status": "error",
                    "error_message": str(e),
                },
            }

    def _format_analysis_response(
        self,
        device_name: str,
        analysis_goal: str | None,
        result: Any,  # VisionAnalysisResult
    ) -> str:
        """将视觉分析结果转换为自然语言描述

        Args:
            device_name: 设备名称
            analysis_goal: 用户指定的分析目标
            result: VisionAnalysisResult 分析结果

        Returns:
            str: 对话式的分析结果描述
        """
        # 危险等级描述
        danger_descriptions = {
            DangerLevel.L0: "正常，无明显危险",
            DangerLevel.L1: "低危，需要关注",
            DangerLevel.L2: "中危，需要准备预案",
            DangerLevel.L3: "高危，立即处置",
        }

        danger_desc = danger_descriptions.get(result.danger_level, "未知")

        # 构建回复文本
        parts = []

        # 1. 开场和危险等级
        parts.append(f"已完成设备 {device_name} 的视频分析。")
        parts.append(f"**危险等级**: {result.danger_level.value} - {danger_desc}")

        # 2. 人员情况
        if result.persons.count > 0:
            activities_str = "、".join(result.persons.activities[:3]) if result.persons.activities else "正常活动"
            parts.append(f"**人员情况**: 检测到 {result.persons.count} 人，主要活动：{activities_str}")
        else:
            parts.append("**人员情况**: 未检测到人员")

        # 3. 车辆情况
        if result.vehicles.total_count > 0:
            vehicle_types = "、".join(
                [f"{vtype} {count}辆" for vtype, count in result.vehicles.by_type.items()]
            )
            parts.append(f"**车辆情况**: 共 {result.vehicles.total_count} 辆，包括 {vehicle_types}")
        else:
            parts.append("**车辆情况**: 未检测到车辆")

        # 4. 建筑物状况
        if result.buildings.total_buildings > 0:
            damaged_ratio = (
                f"{result.buildings.damaged_count}/{result.buildings.total_buildings}"
            )
            collapse_warning = "，有倒塌风险" if result.buildings.collapse_risk else ""
            parts.append(f"**建筑物状况**: 检测到 {result.buildings.total_buildings} 栋建筑，损毁 {damaged_ratio}{collapse_warning}")
        else:
            parts.append("**建筑物状况**: 未检测到建筑物")

        # 5. 道路状态
        if result.roads.passable:
            parts.append("**道路状态**: 可通行")
        else:
            blocked = "、".join(result.roads.blocked_sections)
            parts.append(f"**道路状态**: 部分阻塞（{blocked}）")

        # 6. 危险因素
        if result.hazards:
            hazards_str = "、".join(result.hazards[:5])
            parts.append(f"**危险因素**: {hazards_str}")

        # 7. 建议行动
        if result.recommendations:
            recommendations_str = "、".join(result.recommendations[:3])
            parts.append(f"**建议行动**: {recommendations_str}")

        # 8. 分析目标回应（如果用户有指定）
        if analysis_goal:
            parts.append(f"\n针对您的分析目标「{analysis_goal}」，以上是当前现场情况。")

        return "\n".join(parts)
