"""意图识别提供者集合。"""

from emergency_agents.intent.providers.base import IntentProvider, IntentThresholds
from emergency_agents.intent.providers.factory import build_providers
from emergency_agents.intent.providers.http import HttpIntentProvider
from emergency_agents.intent.providers.llm import LLMIntentProvider
from emergency_agents.intent.providers.rasa import RasaIntentProvider
from emergency_agents.intent.providers.setfit import SetFitIntentProvider
from emergency_agents.intent.providers.types import IntentCandidate, IntentPrediction

__all__ = [
    "IntentProvider",
    "IntentThresholds",
    "HttpIntentProvider",
    "LLMIntentProvider",
    "RasaIntentProvider",
    "SetFitIntentProvider",
    "IntentCandidate",
    "IntentPrediction",
    "build_providers",
]
