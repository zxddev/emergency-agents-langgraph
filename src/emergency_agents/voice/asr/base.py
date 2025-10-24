# Copyright 2025 msq
from __future__ import annotations

"""ASR 抽象基类与数据模型。

摘要：定义语音识别契约，规范入参/出参与健康检查。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ASRResult:
    """ASR 识别结果。

    Args:
        text: 识别到的纯文本。
        confidence: 识别置信度，范围 [0, 1]。
        is_final: 是否为最终结果。
        provider: 提供方标识（如 "aliyun"、"local"）。
        latency_ms: 从发送到获取最终文本的耗时，毫秒。
        metadata: 扩展元数据（如 request_id、模型名等）。
    """

    text: str
    confidence: float = 1.0
    is_final: bool = True
    provider: str = ""
    latency_ms: int = 0
    metadata: Optional[dict[str, Any]] = None


@dataclass
class ASRConfig:
    """ASR 配置项。

    Args:
        format: 音频格式，例如 "pcm" 或 "wav"。
        sample_rate: 采样率，常见为 16000。
        channels: 声道数，常见为 1（单声道）。
        language: 语言代码，例如 "zh-CN"。
        enable_punctuation: 是否启用标点预测。
        enable_timestamps: 是否输出时间戳（如实现支持）。
    """

    format: str = "pcm"
    sample_rate: int = 16000
    channels: int = 1
    language: str = "zh-CN"
    enable_punctuation: bool = True
    enable_timestamps: bool = False


class ASRProvider(ABC):
    """ASR 提供方抽象基类。

    任何具体实现都必须提供最小的识别与健康检查契约，确保可替换性。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """返回提供方唯一名称。

        Returns:
            str: 提供方唯一名称（如 "aliyun"、"local"）。
        """

    @property
    def priority(self) -> int:
        """返回提供方优先级，数值越大表示越优先。

        Returns:
            int: 优先级，默认 0。
        """

        return 0

    @abstractmethod
    async def recognize(self, audio_data: bytes, config: ASRConfig | None = None) -> ASRResult:
        """执行语音识别。

        Args:
            audio_data: 原始音频二进制数据，通常为 PCM16 单声道，16k 采样。
            config: 识别配置，None 表示使用默认值。

        Returns:
            ASRResult: 识别结果对象。
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查。

        Returns:
            bool: True 表示服务可用，False 表示不可用。
        """


