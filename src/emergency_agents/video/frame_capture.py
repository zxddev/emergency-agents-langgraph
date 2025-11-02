#!/usr/bin/env python3
# Copyright 2025 msq
"""
视频流帧截取工具 - 从 RTSP/RTMP/HTTP 视频流中截取当前帧

核心功能：
- 支持多种视频流协议（RTSP/RTMP/HTTP-FLV）
- 自动重连机制
- 帧质量检测
- Base64 编码输出

技术栈：
- OpenCV (cv2) 用于视频流处理
- 智能错误处理和超时控制
"""
from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from io import BytesIO
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class FrameCaptureResult:
    """帧截取结果"""

    success: bool
    image_base64: Optional[str] = None
    image_size: Optional[Tuple[int, int]] = None  # (width, height)
    capture_time: Optional[float] = None  # Unix timestamp
    error_message: Optional[str] = None


class VideoFrameCapture:
    """视频流帧截取器

    使用方法：
        capturer = VideoFrameCapture(stream_url="rtsp://192.168.1.100:554/stream")
        result = capturer.capture_frame()
        if result.success:
            print(f"截取帧成功: {result.image_size}")
            # 使用 result.image_base64 传给 GLM-4V
    """

    def __init__(
        self,
        stream_url: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        skip_frames: int = 5,
    ):
        """初始化视频帧截取器

        Args:
            stream_url: 视频流地址（支持 RTSP/RTMP/HTTP）
            timeout: 连接超时时间（秒）
            max_retries: 最大重试次数
            skip_frames: 跳过前N帧（避免获取到旧帧）
        """
        self.stream_url = stream_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.skip_frames = skip_frames

        logger.info(
            f"VideoFrameCapture initialized: stream_url={stream_url}, "
            f"timeout={timeout}s, max_retries={max_retries}"
        )

    def capture_frame(self) -> FrameCaptureResult:
        """截取视频流当前帧

        Returns:
            FrameCaptureResult: 截取结果（包含 Base64 编码的图像）
        """
        start_time = time.time()

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Attempting to capture frame (attempt {attempt}/{self.max_retries})"
                )

                # 打开视频流
                cap = cv2.VideoCapture(self.stream_url)

                if not cap.isOpened():
                    error_msg = f"无法打开视频流: {self.stream_url}"
                    logger.warning(error_msg)
                    if attempt == self.max_retries:
                        return FrameCaptureResult(
                            success=False,
                            error_message=error_msg,
                        )
                    time.sleep(1)  # 重试前等待
                    continue

                # 设置超时
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.timeout * 1000)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.timeout * 1000)

                # 跳过前几帧（确保获取最新帧）
                for _ in range(self.skip_frames):
                    cap.grab()

                # 读取帧
                ret, frame = cap.read()
                cap.release()

                if not ret or frame is None:
                    error_msg = "读取帧失败，可能视频流中断"
                    logger.warning(error_msg)
                    if attempt == self.max_retries:
                        return FrameCaptureResult(
                            success=False,
                            error_message=error_msg,
                        )
                    time.sleep(1)
                    continue

                # 帧质量检测（检测是否全黑或全白）
                if not self._is_valid_frame(frame):
                    error_msg = "截取到无效帧（全黑或全白）"
                    logger.warning(error_msg)
                    if attempt == self.max_retries:
                        return FrameCaptureResult(
                            success=False,
                            error_message=error_msg,
                        )
                    time.sleep(1)
                    continue

                # 转换为 Base64
                image_base64 = self._frame_to_base64(frame)

                # 获取帧尺寸
                height, width = frame.shape[:2]

                capture_duration = time.time() - start_time
                logger.info(
                    f"Frame captured successfully in {capture_duration:.2f}s: "
                    f"size={width}x{height}, attempt={attempt}"
                )

                return FrameCaptureResult(
                    success=True,
                    image_base64=image_base64,
                    image_size=(width, height),
                    capture_time=time.time(),
                )

            except Exception as e:
                error_msg = f"截取帧时发生异常: {e}"
                logger.error(error_msg, exc_info=True)
                if attempt == self.max_retries:
                    return FrameCaptureResult(
                        success=False,
                        error_message=error_msg,
                    )
                time.sleep(1)

        # 不应该到达这里
        return FrameCaptureResult(
            success=False,
            error_message="未知错误：所有重试尝试均失败",
        )

    def _is_valid_frame(self, frame: np.ndarray) -> bool:
        """检测帧是否有效（非全黑/全白）

        Args:
            frame: OpenCV 读取的帧（BGR格式）

        Returns:
            bool: True 表示有效帧
        """
        # 转换为灰度图
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 计算平均亮度
        mean_brightness = np.mean(gray)

        # 判断是否全黑（平均亮度 < 10）或全白（平均亮度 > 245）
        if mean_brightness < 10:
            logger.warning(f"Frame too dark: mean_brightness={mean_brightness:.1f}")
            return False
        if mean_brightness > 245:
            logger.warning(f"Frame too bright: mean_brightness={mean_brightness:.1f}")
            return False

        # 计算标准差（检测是否有内容变化）
        std_dev = np.std(gray)
        if std_dev < 5:
            logger.warning(f"Frame has low variance: std_dev={std_dev:.1f}")
            return False

        return True

    def _frame_to_base64(self, frame: np.ndarray) -> str:
        """将 OpenCV 帧转换为 Base64 编码的 JPEG

        Args:
            frame: OpenCV 读取的帧（BGR格式）

        Returns:
            str: Base64 编码的图像数据
        """
        # 将 BGR 转换为 RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 转换为 PIL Image
        pil_image = Image.fromarray(frame_rgb)

        # 编码为 JPEG（保存到内存）
        buffered = BytesIO()
        pil_image.save(buffered, format="JPEG", quality=85)

        # Base64 编码
        img_bytes = buffered.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode("utf-8")

        return img_base64
