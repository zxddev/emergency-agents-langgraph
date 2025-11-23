from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import VideoAnalysisSlots
from emergency_agents.video.frame_capture import VideoFrameCapture
from emergency_agents.vehicle.vision import VisionAnalyzer, DangerLevel
from emergency_agents.video.stream_catalog import VideoStreamCatalog, VideoStreamEntry

logger = logging.getLogger(__name__)


@dataclass
class VideoAnalysisHandler(IntentHandler[VideoAnalysisSlots]):
    stream_catalog: VideoStreamCatalog
    vllm_url: str  # GLM-4V 视觉模型 API 地址
    vllm_api_key: str | None = None
    vllm_model: str = "glm-4.5-v"

    async def handle(self, slots: VideoAnalysisSlots, state: dict[str, object]) -> dict[str, object]:
        """视频分析意图处理 - 基于 GLM-4V 视觉大模型

        流程：
        1. 根据设备名称查询设备信息（获取device_id）
        2. 根据device_id获取视频流地址
        3. 从视频流截取当前帧
        4. 调用 GLM-4V 进行场景分析
        5. 返回自然语言描述 + 结构化数据

        Args:
            slots: 视频分析槽位（包含用户输入的device_name）
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
                "device_name": slots.device_name,
                "analysis_goal": slots.analysis_goal,
            },
        )

        device_entry: VideoStreamEntry | None = None
        candidates = self.stream_catalog.resolve(
            slots.device_name,
            device_type=slots.device_type,
        )
        if not candidates:
            fallback_candidates = self.stream_catalog.list_candidates()
            logger.warning(
                "video_analysis_device_not_found",
                extra={
                    "device_name": slots.device_name,
                    "device_type": slots.device_type,
                    "available": len(fallback_candidates),
                },
            )
            fallback_labels = "、".join(item["label"] for item in fallback_candidates) or "无可用设备"
            return {
                "response_text": (
                    f"未找到名为「{slots.device_name}」的设备。"
                    f"当前可用设备：{fallback_labels}。请确认名称后重试。"
                ),
                "video_analysis": {
                    "status": "device_not_found",
                    "query": slots.device_name,
                    "candidates": fallback_candidates,
                },
            }

        if len(candidates) > 1:
            logger.warning(
                "video_analysis_device_ambiguous",
                extra={
                    "device_name": slots.device_name,
                    "matches": [entry.device_id for entry in candidates],
                },
            )
            return {
                "response_text": (
                    f"设备名称「{slots.device_name}」存在歧义，请明确指定："
                    + "、".join(candidate.display_name for candidate in candidates)
                ),
                "video_analysis": {
                    "status": "ambiguous_device_name",
                    "query": slots.device_name,
                    "candidates": [candidate.to_candidate() for candidate in candidates],
                },
            }

        device_entry = candidates[0]

        # 2. 获取视频流地址
        stream_url = device_entry.stream_url
        if not stream_url:
            logger.error(
                "video_analysis_missing_stream_url",
                extra={
                    "device_id": device_entry.device_id,
                    "device_name": device_entry.display_name,
                },
            )
            return {
                "response_text": (
                    f"设备 {device_entry.display_name or device_entry.device_id} 缺少视频流地址，"
                    "请联系运维人员配置后再试。"
                ),
                "video_analysis": {
                    "status": "missing_stream_url",
                    "device_id": device_entry.device_id,
                },
            }

        try:
            # 3. 截取视频帧
            logger.info(
                "video_frame_capture_start",
                extra={
                    "device_id": device_entry.device_id,
                    "stream_url": stream_url,
                },
            )
            capturer = VideoFrameCapture(stream_url=stream_url, timeout=10.0, max_retries=2)
            capture_result = capturer.capture_frame()

            if not capture_result.success:
                logger.error(
                    "video_frame_capture_failed",
                    extra={
                        "device_id": device_entry.device_id,
                        "error": capture_result.error_message,
                    },
                )
                return {
                    "response_text": (
                        f"无法从设备 {device_entry.display_name or device_entry.device_id} 获取视频画面："
                        f"{capture_result.error_message}"
                    ),
                    "video_analysis": {
                        "status": "capture_failed",
                        "error": capture_result.error_message,
                    },
                }

            # 4. 调用 GLM-4V 视觉分析
            logger.info(
                "video_analysis_inference_start",
                extra={
                    "device_id": device_entry.device_id,
                    "image_size": capture_result.image_size,
                },
            )
            analyzer = VisionAnalyzer(
                vllm_url=self.vllm_url,
                model_name=self.vllm_model,
                api_key=self.vllm_api_key,
                timeout=30.0,
                temperature=0.1,
                enable_thinking=True,
            )

            analysis_result = await analyzer.analyze_drone_image(
                image_base64=capture_result.image_base64
            )

            await analyzer.close()

            # 5. 生成自然语言描述（对话式回复）
            response_text = self._format_analysis_response(
                device_name=device_entry.display_name or device_entry.device_id,
                analysis_goal=slots.analysis_goal,
                result=analysis_result,
            )

            # 6. 返回结果
            logger.info(
                "video_analysis_completed",
                extra={
                    "device_id": device_entry.device_id,
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
                    "device_id": device_entry.device_id,
                    "device_name": device_entry.display_name,
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
            logger.error(
                "video_analysis_failed",
                extra={
                    "device_id": device_entry.device_id if device_entry else None,
                    "error": str(e),
                },
                exc_info=True,
            )
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

        # 1. 开场和场景概述
        parts.append(f"已完成设备 {device_name} 的视频分析。")
        scene_summary = getattr(result, "scene_summary", None)
        if scene_summary:
            parts.append(f"**场景概述**: {scene_summary}")

        # 2. 危险等级
        parts.append(f"**危险等级**: {result.danger_level.value} - {danger_desc}")

        # 3. 人员情况（优先详细描述）
        if result.persons.count > 0:
            activities_str = "、".join(result.persons.activities[:3]) if result.persons.activities else "正常活动"
            parts.append(f"**人员情况**: 检测到 {result.persons.count} 人，主要活动/姿态：{activities_str}")
        else:
            parts.append("**人员情况**: 未检测到人员")

        # 4. 车辆情况
        if result.vehicles.total_count > 0:
            vehicle_types = "、".join(
                [f"{vtype} {count}辆" for vtype, count in result.vehicles.by_type.items()]
            )
            parts.append(f"**车辆情况**: 共 {result.vehicles.total_count} 辆，包括 {vehicle_types}")
        else:
            parts.append("**车辆情况**: 未检测到车辆")

        # 5. 建筑物状况
        if result.buildings.total_buildings > 0:
            damaged_ratio = (
                f"{result.buildings.damaged_count}/{result.buildings.total_buildings}"
            )
            collapse_warning = "，有倒塌风险" if result.buildings.collapse_risk else ""
            parts.append(f"**建筑物状况**: 检测到 {result.buildings.total_buildings} 栋建筑，损毁 {damaged_ratio}{collapse_warning}")
        else:
            parts.append("**建筑物状况**: 未检测到建筑物")

        # 6. 道路状态
        if result.roads.passable:
            parts.append("**道路状态**: 可通行")
        else:
            blocked = "、".join(result.roads.blocked_sections)
            parts.append(f"**道路状态**: 部分阻塞（{blocked}）")

        # 7. 危险因素
        if result.hazards:
            hazards_str = "、".join(result.hazards[:5])
            parts.append(f"**危险因素**: {hazards_str}")

        # 8. 建议行动
        if result.recommendations:
            recommendations_str = "、".join(result.recommendations[:3])
            parts.append(f"**建议行动**: {recommendations_str}")

        # 9. 分析目标回应（如果用户有指定）
        if analysis_goal:
            parts.append(f"\n针对您的分析目标「{analysis_goal}」，以上是当前现场情况。")

        return "\n".join(parts)
