"""Intent handler package。"""

from .base import IntentHandler  # noqa: F401
from .device_control import DeviceControlHandler, RobotDogControlHandler
from .device_status import DeviceStatusQueryHandler
from .disaster_overview import DisasterOverviewHandler
from .rescue_task_generation import (
    RescueSimulationHandler,
    RescueTaskGenerationHandler,
)
from .rescue_team_dispatch import RescueTeamDispatchHandler
from .scout_task_simple import SimpleScoutDispatchHandler
from .task_progress import TaskProgressQueryHandler
from .video_analysis import VideoAnalysisHandler
from .general_chat import GeneralChatHandler

__all__ = [
    "IntentHandler",
    "DeviceControlHandler",
    "RobotDogControlHandler",
    "DeviceStatusQueryHandler",
    "DisasterOverviewHandler",
    "RescueSimulationHandler",
    "RescueTaskGenerationHandler",
    "RescueTeamDispatchHandler",
    "SimpleScoutDispatchHandler",
    "TaskProgressQueryHandler",
    "VideoAnalysisHandler",
    "GeneralChatHandler",
]
