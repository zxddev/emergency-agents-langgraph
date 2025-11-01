# Phase 2: Robot Dog Control Handler Guide (AI-3)

**Assignee**: AI-3
**Duration**: 1-1.5 days
**Branch**: `feature/robotdog-control-handler`
**Goal**: Implement RobotDogControlHandler for natural language robot dog control

## 📋 Prerequisites

Before starting, ensure you have read:
- [ ] `openspec/changes/conversation-management-v1/proposal.md`
- [ ] `openspec/changes/conversation-management-v1/specs/device-control-robotdog/spec.md`
- [ ] `docs/guides/handler-development/README.md`
- [ ] `docs/reference/handler-registry-api.md`
- [ ] Phase 1 is complete (infrastructure ready)

## 🎯 Phase 2 Objectives

1. Create RobotDogControlSlots TypedDict
2. Implement RobotDogControlHandler
3. Write comprehensive tests (including waypoint validation)
4. Ensure 100% type annotations (mypy --strict)
5. Verify no emoji in logs
6. Add TODO placeholders for Java API

## 📂 File Structure

```
src/emergency_agents/intent/
├── schemas.py (modify - add RobotDogControlSlots)
└── handlers/
    └── robotdog_control.py (create)

tests/
└── test_robotdog_handler.py (create)
```

## 🔨 Implementation Steps

### Step 1: Create Branch

```bash
git checkout master
git pull
git checkout -b feature/robotdog-control-handler
```

### Step 2: Add RobotDogControlSlots to schemas.py

**File**: `src/emergency_agents/intent/schemas.py` (add at end)

```python
# ============================================================
# START: RobotDogControlSlots (AI-3, feature/robotdog-control-handler)
# ============================================================

class RobotDogControlSlots(TypedDict):
    """Robot dog control intent slots"""
    device_id: str  # Required: Robot dog device ID
    action: str  # Required: Action type (patrol/follow/guard/sit/stand/move)
    waypoints: NotRequired[list[list[float]]]  # Optional: Patrol waypoints [[lat,lng], ...]
    target_id: NotRequired[str]  # Optional: Follow target ID (required for follow)
    target_type: NotRequired[str]  # Optional: Follow target type (person/vehicle)
    follow_distance_m: NotRequired[float]  # Optional: Follow distance (meters)
    guard_lat: NotRequired[float]  # Optional: Guard latitude (for guard at position)
    guard_lng: NotRequired[float]  # Optional: Guard longitude (for guard at position)
    target_lat: NotRequired[float]  # Optional: Target latitude (required for move)
    target_lng: NotRequired[float]  # Optional: Target longitude (required for move)
    speed_mps: NotRequired[float]  # Optional: Movement speed (meters/second)
    timeout_sec: NotRequired[int]  # Optional: Timeout (seconds)

# ============================================================
# END: RobotDogControlSlots (AI-3)
# ============================================================
```

**IMPORTANT**: Use comment separators to prevent merge conflicts with AI-2/4.

### Step 3: Implement RobotDogControlHandler

**File**: `src/emergency_agents/intent/handlers/robotdog_control.py`

```python
"""
RobotDogControlHandler - Natural language robot dog control intent handler

Handles robot dog operations: patrol, follow, guard, sit, stand, move
Phase 2: Uses TODO placeholders for Java API integration
"""
from typing import Dict, Any
import logging

from emergency_agents.intent.handlers.base import IntentHandler, ActionResult
from emergency_agents.intent.schemas import RobotDogControlSlots

logger = logging.getLogger(__name__)


class RobotDogControlHandler(IntentHandler):
    """Handler for device_control_robotdog intent"""

    @classmethod
    def get_intent_type(cls) -> str:
        return "device_control_robotdog"

    def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Business-level slot validation

        Validation rules:
        - patrol action requires waypoints (at least 2 points)
        - follow action requires target_id
        - guard action requires both guard_lat and guard_lng (if one is specified)
        - move action requires target_lat and target_lng

        Returns:
            tuple[bool, list[str]]: (is_valid, missing_fields)
        """
        missing: list[str] = []
        action: str | None = slots.get("action")

        if action == "patrol":
            waypoints: list[list[float]] | None = slots.get("waypoints")
            if waypoints is None or len(waypoints) < 2:
                missing.append("waypoints")  # Need at least 2 waypoints

        elif action == "follow":
            if slots.get("target_id") is None:
                missing.append("target_id")

        elif action == "guard":
            # Guard can work without coordinates (use current position)
            # But if one coordinate is specified, both must be specified
            guard_lat: float | None = slots.get("guard_lat")
            guard_lng: float | None = slots.get("guard_lng")
            if (guard_lat is None) != (guard_lng is None):
                missing.append("guard_lat" if guard_lat is None else "guard_lng")

        elif action == "move":
            if slots.get("target_lat") is None:
                missing.append("target_lat")
            if slots.get("target_lng") is None:
                missing.append("target_lng")

        return (len(missing) == 0, missing)

    async def execute_action(
        self,
        slots: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """
        Execute robot dog control action

        Phase 2: Logs TODO placeholder for Java API integration
        Phase 3: Will call actual Java Robot Dog Control API

        Args:
            slots: RobotDogControlSlots (device_id, action, optional params)
            context: Execution context (java_api_base, conversation_dao, config)

        Returns:
            ActionResult with success=True and TODO message
        """
        device_id: str = slots.get("device_id", "unknown")
        action: str = slots.get("action", "unknown")
        target_id: str | None = slots.get("target_id")

        logger.info(
            "[ROBOTDOG][CONTROL][ENTER] device_id=%s | action=%s | target_id=%s",
            device_id,
            action,
            target_id if target_id is not None else "N/A"
        )

        java_api_base: str = context.get("java_api_base", "http://localhost:8080/api")
        api_url: str = f"{java_api_base}/devices/robotdog/{device_id}/control"

        logger.info(
            "[ROBOTDOG][CONTROL][SUCCESS] TODO: call POST %s",
            api_url
        )

        return ActionResult(
            success=True,
            message=f"机器狗 {device_id} 控制指令已接收（TODO占位）",
            device_id=device_id,
            action_type="robotdog_control",
            details={
                "slots": slots,
                "java_api_url": api_url
            }
        )
```

### Step 4: Write Comprehensive Tests

**File**: `tests/test_robotdog_handler.py`

```python
"""Tests for RobotDogControlHandler"""
import pytest
import re
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.handlers.robotdog_control import RobotDogControlHandler


class TestRobotDogHandlerInterface:
    """Test RobotDogControlHandler implements IntentHandler interface"""

    def test_robotdog_handler_implements_interface(self):
        """Handler must implement IntentHandler"""
        assert issubclass(RobotDogControlHandler, IntentHandler)

    def test_robotdog_handler_get_intent_type(self):
        """Handler must return correct intent type"""
        assert RobotDogControlHandler.get_intent_type() == "device_control_robotdog"

    def test_robotdog_handler_has_required_methods(self):
        """Handler must have validate_slots and execute_action"""
        handler = RobotDogControlHandler()
        assert callable(handler.validate_slots)
        assert callable(handler.execute_action)


class TestRobotDogSlotValidation:
    """Test RobotDogControlHandler.validate_slots"""

    @pytest.mark.parametrize("slots,expected_valid,expected_missing", [
        # Valid cases - basic commands
        ({"device_id": "dog-001", "action": "sit"}, True, []),
        ({"device_id": "dog-001", "action": "stand"}, True, []),

        # Valid cases - patrol with sufficient waypoints
        ({"device_id": "dog-001", "action": "patrol", "waypoints": [[31.68, 103.85], [31.69, 103.86]]}, True, []),
        ({"device_id": "dog-001", "action": "patrol", "waypoints": [[31.68, 103.85], [31.69, 103.86], [31.68, 103.85]]}, True, []),

        # Invalid cases - patrol missing or insufficient waypoints
        ({"device_id": "dog-001", "action": "patrol"}, False, ["waypoints"]),
        ({"device_id": "dog-001", "action": "patrol", "waypoints": [[31.68, 103.85]]}, False, ["waypoints"]),

        # Valid cases - follow
        ({"device_id": "dog-001", "action": "follow", "target_id": "person-123"}, True, []),
        ({"device_id": "dog-001", "action": "follow", "target_id": "vehicle-456", "follow_distance_m": 5.0}, True, []),

        # Invalid cases - follow missing target_id
        ({"device_id": "dog-001", "action": "follow"}, False, ["target_id"]),

        # Valid cases - guard
        ({"device_id": "dog-001", "action": "guard"}, True, []),  # Current position guard
        ({"device_id": "dog-001", "action": "guard", "guard_lat": 31.68, "guard_lng": 103.85}, True, []),

        # Invalid cases - guard missing one coordinate
        ({"device_id": "dog-001", "action": "guard", "guard_lat": 31.68}, False, ["guard_lng"]),
        ({"device_id": "dog-001", "action": "guard", "guard_lng": 103.85}, False, ["guard_lat"]),

        # Valid cases - move
        ({"device_id": "dog-001", "action": "move", "target_lat": 31.68, "target_lng": 103.85}, True, []),

        # Invalid cases - move missing coordinates
        ({"device_id": "dog-001", "action": "move"}, False, ["target_lat", "target_lng"]),
        ({"device_id": "dog-001", "action": "move", "target_lat": 31.68}, False, ["target_lng"]),
    ])
    def test_robotdog_slot_validation(self, slots, expected_valid, expected_missing):
        """Test slot validation for all scenarios"""
        handler = RobotDogControlHandler()
        is_valid, missing = handler.validate_slots(slots)

        assert is_valid == expected_valid
        assert set(missing) == set(expected_missing)


@pytest.mark.asyncio
class TestRobotDogActionExecution:
    """Test RobotDogControlHandler.execute_action"""

    async def test_execute_patrol_action(self):
        """Should execute patrol action successfully"""
        handler = RobotDogControlHandler()
        slots = {
            "device_id": "dog-001",
            "action": "patrol",
            "waypoints": [[31.68, 103.85], [31.69, 103.86]]
        }
        context = {"java_api_base": "http://test-api"}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True
        assert result["device_id"] == "dog-001"
        assert result["action_type"] == "robotdog_control"
        assert "TODO" in result["message"]
        assert "details" in result
        assert result["details"]["java_api_url"] == "http://test-api/devices/robotdog/dog-001/control"

    async def test_execute_follow_action(self):
        """Should execute follow action with target"""
        handler = RobotDogControlHandler()
        slots = {
            "device_id": "dog-002",
            "action": "follow",
            "target_id": "person-123",
            "follow_distance_m": 3.0
        }
        context = {}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True
        assert result["device_id"] == "dog-002"
        assert result["details"]["slots"]["target_id"] == "person-123"

    async def test_execute_guard_action(self):
        """Should execute guard action"""
        handler = RobotDogControlHandler()
        slots = {
            "device_id": "dog-003",
            "action": "guard",
            "guard_lat": 31.68,
            "guard_lng": 103.85
        }
        context = {}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True
        assert result["action_type"] == "robotdog_control"

    async def test_execute_sit_action(self):
        """Should execute sit action"""
        handler = RobotDogControlHandler()
        slots = {"device_id": "dog-004", "action": "sit"}
        context = {}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True


class TestRobotDogLogging:
    """Test RobotDogControlHandler logging standards"""

    @pytest.mark.asyncio
    async def test_logs_no_emoji(self, caplog):
        """Logs must not contain emoji"""
        handler = RobotDogControlHandler()
        slots = {"device_id": "dog-001", "action": "sit"}
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
        """Logs must use text tags format [ROBOTDOG][CONTROL][OPERATION]"""
        handler = RobotDogControlHandler()
        slots = {"device_id": "dog-001", "action": "sit"}
        context = {}

        await handler.execute_action(slots, context)

        # Check log format
        found_enter = False
        found_success = False

        for record in caplog.records:
            if "[ROBOTDOG][CONTROL][ENTER]" in record.message:
                found_enter = True
            if "[ROBOTDOG][CONTROL][SUCCESS]" in record.message:
                found_success = True

        assert found_enter, "Missing [ROBOTDOG][CONTROL][ENTER] log"
        assert found_success, "Missing [ROBOTDOG][CONTROL][SUCCESS] log"


class TestRobotDogTODOPlaceholders:
    """Test TODO placeholders are present and grep-searchable"""

    @pytest.mark.asyncio
    async def test_todo_placeholder_in_logs(self, caplog):
        """Logs must contain TODO placeholder for Java API"""
        handler = RobotDogControlHandler()
        slots = {"device_id": "dog-001", "action": "sit"}
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
        import emergency_agents.intent.handlers.robotdog_control as robotdog_module
        import inspect

        source = inspect.getsource(robotdog_module)
        assert "TODO:" in source, "TODO: not found in source code"


class TestRobotDogTypeAnnotations:
    """Test 100% type annotations"""

    def test_validate_slots_return_type(self):
        """validate_slots must return tuple[bool, list[str]]"""
        handler = RobotDogControlHandler()
        result = handler.validate_slots({"device_id": "test", "action": "sit"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)

    @pytest.mark.asyncio
    async def test_execute_action_return_type(self):
        """execute_action must return ActionResult (TypedDict)"""
        handler = RobotDogControlHandler()
        result = await handler.execute_action(
            {"device_id": "test", "action": "sit"},
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
# Run robot dog handler tests
pytest tests/test_robotdog_handler.py -v

# Check type annotations
mypy src/emergency_agents/intent/handlers/robotdog_control.py --strict

# Verify no emoji in logs
pytest tests/test_robotdog_handler.py::TestRobotDogLogging -v
```

### Manual Validation
```bash
# Test handler discovery
python -c "
from emergency_agents.intent.registry import get_handler_registry

registry = get_handler_registry()
handler = registry.get_handler('device_control_robotdog')
print(f'Robot Dog Handler: {handler}')
print(f'Intent Type: {handler.get_intent_type()}')
"

# Grep for TODO
grep -n "TODO:" src/emergency_agents/intent/handlers/robotdog_control.py
```

## 📊 Success Criteria

- [ ] RobotDogControlSlots defined in schemas.py with comment separators
- [ ] RobotDogControlHandler implements IntentHandler interface
- [ ] All parameterized tests pass (including waypoint validation)
- [ ] Zero emoji in logs (regex validation passes)
- [ ] TODO placeholders present and grep-searchable
- [ ] mypy --strict passes
- [ ] Handler auto-discovered by Registry
- [ ] All tests pass: `pytest tests/test_robotdog_handler.py -v`

## 🚨 Common Issues and Solutions

### Issue 1: Waypoint Validation Edge Cases
**Solution**: Remember patrol needs at least 2 waypoints, single waypoint is invalid
```python
# Invalid
waypoints = [[31.68, 103.85]]  # Only 1 waypoint

# Valid
waypoints = [[31.68, 103.85], [31.69, 103.86]]  # 2+ waypoints
```

### Issue 2: Guard Coordinate Validation
**Solution**: Both coordinates must be present or both absent
```python
# Invalid - one coordinate specified
guard_lat = 31.68  # guard_lng is missing

# Valid - both specified
guard_lat = 31.68
guard_lng = 103.85

# Valid - both omitted (guard current position)
# No guard_lat, no guard_lng
```

### Issue 3: Type Errors with Nested Lists
**Solution**: Use `list[list[float]]` for waypoints type
```python
waypoints: list[list[float]] | None = slots.get("waypoints")
```

## 📚 References

- Capability Spec: `openspec/changes/conversation-management-v1/specs/device-control-robotdog/spec.md`
- Handler Registry API: `docs/reference/handler-registry-api.md`
- Type Annotations Guide: Python typing module documentation

## ⏭️ Next Steps

After completing robot dog handler:
1. Run full test suite: `pytest tests/test_robotdog_handler.py -v`
2. Commit changes: `git add . && git commit -m "feat(handler): implement RobotDogControlHandler"`
3. Push branch: `git push origin feature/robotdog-control-handler`
4. Create PR with title: `[Phase 2] RobotDogControlHandler Implementation`
5. Wait for AI-1 to merge in Phase 3

## 🤝 Parallel Development Notes

### Avoiding Merge Conflicts

You are working in parallel with AI-2 (UAV) and AI-4 (video analysis). To minimize conflicts:

**schemas.py Strategy**:
- Use comment separators (see Step 2)
- Only modify your section (between START and END comments)
- Don't reformat other sections

**Branch Strategy**:
- Work only in `feature/robotdog-control-handler`
- Don't merge other branches
- Don't modify shared files except schemas.py (with separators)

---

**Duration Estimate**: 1-1.5 days
**Complexity**: Medium
**Dependencies**: Phase 1 complete
**Parallel Work**: AI-2 (UAV), AI-4 (video analysis)
