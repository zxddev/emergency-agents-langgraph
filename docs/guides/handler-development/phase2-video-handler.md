# Phase 2: Video Analysis Handler Guide (AI-4)

**Assignee**: AI-4
**Duration**: 1-1.5 days
**Branch**: `feature/video-analysis-handler`
**Goal**: Implement VideoAnalysisHandler for natural language video stream analysis task initiation

## 📋 Prerequisites

Before starting, ensure you have read:
- [ ] `openspec/changes/conversation-management-v1/proposal.md`
- [ ] `openspec/changes/conversation-management-v1/specs/video-analysis/spec.md`
- [ ] `docs/guides/handler-development/README.md`
- [ ] `docs/reference/handler-registry-api.md`
- [ ] Phase 1 is complete (infrastructure ready)

## 🎯 Phase 2 Objectives

1. Create VideoAnalysisSlots TypedDict
2. Implement VideoAnalysisHandler
3. Write comprehensive tests (including camera_id/stream_url validation)
4. Ensure 100% type annotations (mypy --strict)
5. Verify no emoji in logs
6. Add TODO placeholders for Java API

## 📂 File Structure

```
src/emergency_agents/intent/
├── schemas.py (modify - add VideoAnalysisSlots)
└── handlers/
    └── video_analysis.py (create)

tests/
└── test_video_handler.py (create)
```

## 🔨 Implementation Steps

### Step 1: Create Branch

```bash
git checkout master
git pull
git checkout -b feature/video-analysis-handler
```

### Step 2: Add VideoAnalysisSlots to schemas.py

**File**: `src/emergency_agents/intent/schemas.py` (add at end)

```python
# ============================================================
# START: VideoAnalysisSlots (AI-4, feature/video-analysis-handler)
# ============================================================

class VideoAnalysisSlots(TypedDict):
    """Video analysis intent slots"""
    camera_id: NotRequired[str]  # Optional: Camera device ID (camera_id OR stream_url required)
    stream_url: NotRequired[str]  # Optional: Video stream URL (camera_id OR stream_url required)
    analysis_type: str  # Required: Analysis type (motion_detection/object_detection/anomaly_detection/face_recognition)
    target_classes: NotRequired[list[str]]  # Optional: Target object classes for object_detection
    sensitivity: NotRequired[str]  # Optional: Sensitivity level (low/medium/high)
    duration_minutes: NotRequired[int]  # Optional: Analysis duration (minutes), omit for continuous
    enable_recording: NotRequired[bool]  # Optional: Enable video recording
    storage_path: NotRequired[str]  # Optional: Recording storage path
    notify_on_event: NotRequired[bool]  # Optional: Enable event notifications
    notification_threshold: NotRequired[int]  # Optional: Event count threshold for notification
    frame_rate: NotRequired[int]  # Optional: Analysis frame rate (fps)

# ============================================================
# END: VideoAnalysisSlots (AI-4)
# ============================================================
```

**IMPORTANT**: Use comment separators to prevent merge conflicts with AI-2/3.

### Step 3: Implement VideoAnalysisHandler

**File**: `src/emergency_agents/intent/handlers/video_analysis.py`

```python
"""
VideoAnalysisHandler - Natural language video analysis intent handler

Handles video stream analysis task initiation: motion detection, object detection,
anomaly detection, face recognition
Phase 2: Uses TODO placeholders for Java API integration
"""
from typing import Dict, Any
from datetime import datetime
import logging

from emergency_agents.intent.handlers.base import IntentHandler, ActionResult
from emergency_agents.intent.schemas import VideoAnalysisSlots

logger = logging.getLogger(__name__)


class VideoAnalysisHandler(IntentHandler):
    """Handler for video_analysis_start intent"""

    @classmethod
    def get_intent_type(cls) -> str:
        return "video_analysis_start"

    def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Business-level slot validation

        Validation rules:
        - Must have either camera_id or stream_url (not both required)
        - stream_url must start with rtsp:// or http:// if provided
        - analysis_type is required

        Returns:
            tuple[bool, list[str]]: (is_valid, missing_fields)
        """
        missing: list[str] = []

        # Must have either camera_id or stream_url
        camera_id: str | None = slots.get("camera_id")
        stream_url: str | None = slots.get("stream_url")

        if camera_id is None and stream_url is None:
            missing.append("camera_id or stream_url")

        # Validate stream_url format if provided
        if stream_url is not None:
            if not (stream_url.startswith("rtsp://") or stream_url.startswith("http://")):
                missing.append("stream_url (invalid format)")

        # analysis_type is required
        if slots.get("analysis_type") is None:
            missing.append("analysis_type")

        return (len(missing) == 0, missing)

    async def execute_action(
        self,
        slots: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """
        Execute video analysis task initiation

        Phase 2: Logs TODO placeholder for Java API integration
        Phase 3: Will call actual Java Video Analysis API

        Args:
            slots: VideoAnalysisSlots (camera_id/stream_url, analysis_type, optional params)
            context: Execution context (java_api_base, conversation_dao, config)

        Returns:
            ActionResult with success=True, task_id, and TODO message
        """
        source: str = slots.get("camera_id", slots.get("stream_url", "unknown"))
        analysis_type: str = slots.get("analysis_type", "unknown")
        duration: int | None = slots.get("duration_minutes")

        logger.info(
            "[VIDEO][ANALYSIS][ENTER] source=%s | analysis_type=%s | duration=%s",
            source,
            analysis_type,
            duration if duration is not None else "continuous"
        )

        java_api_base: str = context.get("java_api_base", "http://localhost:8080/api")
        api_url: str = f"{java_api_base}/video/analysis/start"

        # Generate task_id (in real implementation, this comes from Java API)
        task_id: str = f"task-{source}-{int(datetime.now().timestamp())}"

        logger.info(
            "[VIDEO][ANALYSIS][SUCCESS] TODO: call POST %s",
            api_url
        )

        return ActionResult(
            success=True,
            message=f"视频分析任务已启动（TODO占位），任务ID：{task_id}",
            device_id=source,
            action_type="video_analysis",
            details={
                "task_id": task_id,
                "slots": slots,
                "java_api_url": api_url
            }
        )
```

### Step 4: Write Comprehensive Tests

**File**: `tests/test_video_handler.py`

```python
"""Tests for VideoAnalysisHandler"""
import pytest
import re
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.handlers.video_analysis import VideoAnalysisHandler


class TestVideoHandlerInterface:
    """Test VideoAnalysisHandler implements IntentHandler interface"""

    def test_video_handler_implements_interface(self):
        """Handler must implement IntentHandler"""
        assert issubclass(VideoAnalysisHandler, IntentHandler)

    def test_video_handler_get_intent_type(self):
        """Handler must return correct intent type"""
        assert VideoAnalysisHandler.get_intent_type() == "video_analysis_start"

    def test_video_handler_has_required_methods(self):
        """Handler must have validate_slots and execute_action"""
        handler = VideoAnalysisHandler()
        assert callable(handler.validate_slots)
        assert callable(handler.execute_action)


class TestVideoSlotValidation:
    """Test VideoAnalysisHandler.validate_slots"""

    @pytest.mark.parametrize("slots,expected_valid,expected_missing", [
        # Valid cases - camera_id
        ({"camera_id": "cam-001", "analysis_type": "motion_detection"}, True, []),
        ({"camera_id": "cam-001", "analysis_type": "object_detection"}, True, []),
        ({"camera_id": "cam-001", "analysis_type": "anomaly_detection"}, True, []),
        ({"camera_id": "cam-001", "analysis_type": "face_recognition"}, True, []),

        # Valid cases - stream_url
        ({"stream_url": "rtsp://192.168.1.100:554/stream", "analysis_type": "motion_detection"}, True, []),
        ({"stream_url": "http://192.168.1.100/video", "analysis_type": "object_detection"}, True, []),

        # Valid cases - with optional parameters
        ({"camera_id": "cam-001", "analysis_type": "object_detection", "target_classes": ["person", "vehicle"]}, True, []),
        ({"camera_id": "cam-001", "analysis_type": "motion_detection", "sensitivity": "high"}, True, []),
        ({"camera_id": "cam-001", "analysis_type": "anomaly_detection", "duration_minutes": 30}, True, []),

        # Invalid cases - missing source
        ({"analysis_type": "motion_detection"}, False, ["camera_id or stream_url"]),

        # Invalid cases - invalid stream_url format
        ({"stream_url": "invalid-url", "analysis_type": "motion_detection"}, False, ["stream_url (invalid format)"]),
        ({"stream_url": "ftp://192.168.1.100/video", "analysis_type": "motion_detection"}, False, ["stream_url (invalid format)"]),

        # Invalid cases - missing analysis_type
        ({"camera_id": "cam-001"}, False, ["analysis_type"]),
    ])
    def test_video_slot_validation(self, slots, expected_valid, expected_missing):
        """Test slot validation for all scenarios"""
        handler = VideoAnalysisHandler()
        is_valid, missing = handler.validate_slots(slots)

        assert is_valid == expected_valid
        assert set(missing) == set(expected_missing)


@pytest.mark.asyncio
class TestVideoActionExecution:
    """Test VideoAnalysisHandler.execute_action"""

    async def test_execute_motion_detection(self):
        """Should execute motion detection task"""
        handler = VideoAnalysisHandler()
        slots = {
            "camera_id": "cam-001",
            "analysis_type": "motion_detection",
            "sensitivity": "high"
        }
        context = {"java_api_base": "http://test-api"}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True
        assert result["device_id"] == "cam-001"
        assert result["action_type"] == "video_analysis"
        assert "TODO" in result["message"]
        assert "task_id" in result["details"]
        assert result["details"]["java_api_url"] == "http://test-api/video/analysis/start"

    async def test_execute_object_detection(self):
        """Should execute object detection with target classes"""
        handler = VideoAnalysisHandler()
        slots = {
            "stream_url": "rtsp://192.168.1.100:554/stream",
            "analysis_type": "object_detection",
            "target_classes": ["person", "vehicle"]
        }
        context = {}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True
        assert result["device_id"] == "rtsp://192.168.1.100:554/stream"
        assert result["details"]["slots"]["target_classes"] == ["person", "vehicle"]

    async def test_execute_with_duration(self):
        """Should execute analysis with duration limit"""
        handler = VideoAnalysisHandler()
        slots = {
            "camera_id": "cam-002",
            "analysis_type": "anomaly_detection",
            "duration_minutes": 30
        }
        context = {}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True
        assert result["details"]["slots"]["duration_minutes"] == 30

    async def test_execute_with_recording(self):
        """Should execute analysis with recording enabled"""
        handler = VideoAnalysisHandler()
        slots = {
            "camera_id": "cam-003",
            "analysis_type": "face_recognition",
            "enable_recording": True,
            "storage_path": "/data/videos"
        }
        context = {}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True
        assert result["details"]["slots"]["enable_recording"] is True


class TestVideoLogging:
    """Test VideoAnalysisHandler logging standards"""

    @pytest.mark.asyncio
    async def test_logs_no_emoji(self, caplog):
        """Logs must not contain emoji"""
        handler = VideoAnalysisHandler()
        slots = {"camera_id": "cam-001", "analysis_type": "motion_detection"}
        context = {}

        await handler.execute_action(slots, context)

        # Regex pattern to match emoji
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]"
        )

        for record in caplog.records:
            assert not emoji_pattern.search(record.message), \
                f"Emoji found in log: {record.message}"

    @pytest.mark.asyncio
    async def test_logs_use_text_tags(self, caplog):
        """Logs must use text tags format [VIDEO][ANALYSIS][OPERATION]"""
        handler = VideoAnalysisHandler()
        slots = {"camera_id": "cam-001", "analysis_type": "motion_detection"}
        context = {}

        await handler.execute_action(slots, context)

        # Check log format
        found_enter = False
        found_success = False

        for record in caplog.records:
            if "[VIDEO][ANALYSIS][ENTER]" in record.message:
                found_enter = True
            if "[VIDEO][ANALYSIS][SUCCESS]" in record.message:
                found_success = True

        assert found_enter, "Missing [VIDEO][ANALYSIS][ENTER] log"
        assert found_success, "Missing [VIDEO][ANALYSIS][SUCCESS] log"


class TestVideoTODOPlaceholders:
    """Test TODO placeholders are present and grep-searchable"""

    @pytest.mark.asyncio
    async def test_todo_placeholder_in_logs(self, caplog):
        """Logs must contain TODO placeholder for Java API"""
        handler = VideoAnalysisHandler()
        slots = {"camera_id": "cam-001", "analysis_type": "motion_detection"}
        context = {"java_api_base": "http://test"}

        await handler.execute_action(slots, context)

        # Check TODO in logs
        found_todo = False
        for record in caplog.records:
            if "TODO:" in record.message and "POST" in record.message:
                found_todo = True
                break

        assert found_todo, "TODO placeholder not found in logs"

    def test_todo_grep_searchable(self):
        """TODO must be grep-searchable in source code"""
        import emergency_agents.intent.handlers.video_analysis as video_module
        import inspect

        source = inspect.getsource(video_module)
        assert "TODO:" in source, "TODO: not found in source code"


class TestVideoTypeAnnotations:
    """Test 100% type annotations"""

    def test_validate_slots_return_type(self):
        """validate_slots must return tuple[bool, list[str]]"""
        handler = VideoAnalysisHandler()
        result = handler.validate_slots({"camera_id": "test", "analysis_type": "motion_detection"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)

    @pytest.mark.asyncio
    async def test_execute_action_return_type(self):
        """execute_action must return ActionResult (TypedDict)"""
        handler = VideoAnalysisHandler()
        result = await handler.execute_action(
            {"camera_id": "test", "analysis_type": "motion_detection"},
            {}
        )

        # Check ActionResult structure
        assert "success" in result
        assert "message" in result
        assert "device_id" in result
        assert "action_type" in result
        assert isinstance(result["success"], bool)
        assert isinstance(result["message"], str)
```

## ✅ Testing and Validation

### Run Tests
```bash
# Run video handler tests
pytest tests/test_video_handler.py -v

# Check type annotations
mypy src/emergency_agents/intent/handlers/video_analysis.py --strict

# Verify no emoji in logs
pytest tests/test_video_handler.py::TestVideoLogging -v
```

### Manual Validation
```bash
# Test handler discovery
python -c "
from emergency_agents.intent.registry import get_handler_registry

registry = get_handler_registry()
handler = registry.get_handler('video_analysis_start')
print(f'Video Handler: {handler}')
print(f'Intent Type: {handler.get_intent_type()}')
"

# Grep for TODO
grep -n "TODO:" src/emergency_agents/intent/handlers/video_analysis.py
```

## 📊 Success Criteria

- [ ] VideoAnalysisSlots defined in schemas.py with comment separators
- [ ] VideoAnalysisHandler implements IntentHandler interface
- [ ] All parameterized tests pass (including URL validation)
- [ ] Zero emoji in logs (regex validation passes)
- [ ] TODO placeholders present and grep-searchable
- [ ] mypy --strict passes
- [ ] Handler auto-discovered by Registry
- [ ] All tests pass: `pytest tests/test_video_handler.py -v`

## 🚨 Common Issues and Solutions

### Issue 1: Stream URL Validation
**Solution**: Check URL starts with rtsp:// or http://
```python
# Valid URLs
"rtsp://192.168.1.100:554/stream"
"http://192.168.1.100/video"

# Invalid URLs
"invalid-url"
"ftp://192.168.1.100/video"
```

### Issue 2: Either camera_id OR stream_url
**Solution**: At least one must be present, not both required
```python
# Valid
{"camera_id": "cam-001", ...}
{"stream_url": "rtsp://...", ...}

# Invalid
{}  # Neither present
```

### Issue 3: Task ID Generation
**Solution**: Use timestamp for unique task_id in Phase 2
```python
from datetime import datetime

task_id: str = f"task-{source}-{int(datetime.now().timestamp())}"
```

## 📚 References

- Capability Spec: `openspec/changes/conversation-management-v1/specs/video-analysis/spec.md`
- Handler Registry API: `docs/reference/handler-registry-api.md`
- Type Annotations Guide: Python typing module documentation

## ⏭️ Next Steps

After completing video analysis handler:
1. Run full test suite: `pytest tests/test_video_handler.py -v`
2. Commit changes: `git add . && git commit -m "feat(handler): implement VideoAnalysisHandler"`
3. Push branch: `git push origin feature/video-analysis-handler`
4. Create PR with title: `[Phase 2] VideoAnalysisHandler Implementation`
5. Wait for AI-1 to merge in Phase 3

## 🤝 Parallel Development Notes

### Avoiding Merge Conflicts

You are working in parallel with AI-2 (UAV) and AI-3 (robot dog). To minimize conflicts:

**schemas.py Strategy**:
- Use comment separators (see Step 2)
- Only modify your section (between START and END comments)
- Don't reformat other sections

**Branch Strategy**:
- Work only in `feature/video-analysis-handler`
- Don't merge other branches
- Don't modify shared files except schemas.py (with separators)

---

**Duration Estimate**: 1-1.5 days
**Complexity**: Medium
**Dependencies**: Phase 1 complete
**Parallel Work**: AI-2 (UAV), AI-3 (robot dog)
