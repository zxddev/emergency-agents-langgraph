# Copyright 2025 msq
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from emergency_agents.voice.asr.manager import ASRManager
from emergency_agents.voice.asr.base import ASRProvider, ASRResult, ASRConfig


class MockPrimaryProvider(ASRProvider):
    def __init__(self, healthy: bool = True):
        self._healthy = healthy
        self._priority = 100
    
    @property
    def provider_name(self) -> str:
        return " mock_primary
