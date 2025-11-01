# Phase 2: UAV Control Handler Guide (AI-2)

**Assignee**: AI-2
**Duration**: 1-1.5 days
**Branch**: `feature/uav-control-handler`
**Goal**: Implement UAVControlHandler for natural language UAV control

## 📋 Prerequisites

Before starting, ensure you have read:
- [ ] `openspec/changes/conversation-management-v1/proposal.md`
- [ ] `openspec/changes/conversation-management-v1/specs/device-control-uav/spec.md`
- [ ] `docs/guides/handler-development/README.md`
- [ ] `docs/reference/handler-registry-api.md`
- [ ] Phase 1 is complete (infrastructure ready)

## 🎯 Phase 2 Objectives

1. Create UAVControlSlots TypedDict
2. Implement UAVControlHandler
3. Write comprehensive tests
4. Ensure 100% type annotations (mypy --strict)
5. Verify no emoji in logs
6. Add TODO placeholders for Java API

## 📂 File Structure

```
src/emergency_agents/intent/
├── schemas.py (modify - add UAVControlSlots)
└── handlers/
    └── uav_control.py (create)

tests/
└── test_uav_handler.py (create)
```

## 🔨 Implementation Steps

### Step 1: Create Branch

```bash
git checkout master
git pull
git checkout -b feature/uav-control-handler
```

### Step 2: Add UAVControlSlots to schemas.py

**File**: `src/emergency_agents/intent/schemas.py` (add at end)

```python
# ============================================================
# START: UAVControlSlots (AI-2, feature/uav-control-handler)
# ============================================================

class UAVControlSlots(TypedDict):
    """UAV control intent slots"""
    device_id: str  # Required: UAV device ID
    action: str  # Required: Action type (takeoff/land/move/hover/rtl)
    altitude_m: NotRequired[float]  # Optional: Target altitude (meters)
    target_lat: NotRequired[float]  # Optional: Target latitude (required for move)
    target_lng: NotRequired[float]  # Optional: Target longitude (required for move)
    speed_mps: NotRequired[float]  # Optional: Flight speed (meters/second)
    timeout_sec: NotRequired[int]  # Optional: Timeout (seconds)

# ============================================================
# END: UAVControlSlots (AI-2)
# ============================================================
```

**IMPORTANT**: Use comment separators to prevent merge conflicts with AI-3/4.

### Step 3: Implement UAVControlHandler

**File**: `src/emergency_agents/intent/handlers/uav_control.py`

```python
"""
UAVControlHandler - Natural language UAV control intent handler

Handles UAV operations: takeoff, land, move, hover, return-to-launch (RTL)
Phase 2: Uses TODO placeholders for Java API integration
"""
from typing import Dict, Any
import logging

from emergency_agents.intent.handlers.base import IntentHandler, ActionResult
from emergency_agents.intent.schemas import UAVControlSlots

logger = logging.getLogger(__name__)


class UAVControlHandler(IntentHandler):
    """Handler for device_control_uav intent"""

    @classmethod
    def get_intent_type(cls) -> str:
        return "device_control_uav"

    def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Business-level slot validation

        Validation rules:
        - move action requires target_lat and target_lng
        - Other actions have no additional requirements

        Returns:
            tuple[bool, list[str]]: (is_valid, missing_fields)
        """
        missing: list[str] = []
        action: str | None = slots.get("action")

        if action == "move":
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
        Execute UAV control action

        Phase 2: Logs TODO placeholder for Java API integration
        Phase 3: Will call actual Java UAV Control API

        Args:
            slots: UAVControlSlots (device_id, action, optional params)
            context: Execution context (java_api_base, conversation_dao, config)

        Returns:
            ActionResult with success=True and TODO message
        """
        device_id: str = slots.get("device_id", "unknown")
        action: str = slots.get("action", "unknown")
        altitude_m: float | None = slots.get("altitude_m")

        logger.info(
            "[UAV][CONTROL][ENTER] device_id=%s | action=%s | altitude_m=%s",
            device_id,
            action,
            altitude_m if altitude_m is not None else "N/A"
        )

        java_api_base: str = context.get("java_api_base", "http://localhost:8080/api")
        api_url: str = f"{java_api_base}/devices/uav/{device_id}/control"

        logger.info(
            "[UAV][CONTROL][SUCCESS] TODO: call POST %s",
            api_url
        )

        return ActionResult(
            success=True,
            message=f"无人机 {device_id} 控制指令已接收（TODO占位）",
            device_id=device_id,
            action_type="uav_control",
            details={
                "slots": slots,
                "java_api_url": api_url
            }
        )
```

### Step 4: Write Comprehensive Tests

**File**: `tests/test_uav_handler.py`

```python
"""Tests for UAVControlHandler"""
import pytest
import re
from unittest.mock import MagicMock
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.handlers.uav_control import UAVControlHandler


class TestUAVHandlerInterface:
    """Test UAVControlHandler implements IntentHandler interface"""

    def test_uav_handler_implements_interface(self):
        """Handler must implement IntentHandler"""
        assert issubclass(UAVControlHandler, IntentHandler)

    def test_uav_handler_get_intent_type(self):
        """Handler must return correct intent type"""
        assert UAVControlHandler.get_intent_type() == "device_control_uav"

    def test_uav_handler_has_required_methods(self):
        """Handler must have validate_slots and execute_action"""
        handler = UAVControlHandler()
        assert callable(handler.validate_slots)
        assert callable(handler.execute_action)


class TestUAVSlotValidation:
    """Test UAVControlHandler.validate_slots"""

    @pytest.mark.parametrize("slots,expected_valid,expected_missing", [
        # Valid cases
        ({"device_id": "uav-001", "action": "takeoff"}, True, []),
        ({"device_id": "uav-001", "action": "takeoff", "altitude_m": 50}, True, []),
        ({"device_id": "uav-001", "action": "land"}, True, []),
        ({"device_id": "uav-001", "action": "hover"}, True, []),
        ({"device_id": "uav-001", "action": "rtl"}, True, []),
        ({"device_id": "uav-001", "action": "move", "target_lat": 31.68, "target_lng": 103.85}, True, []),

        # Invalid cases - missing coordinates for move
        ({"device_id": "uav-001", "action": "move"}, False, ["target_lat", "target_lng"]),
        ({"device_id": "uav-001", "action": "move", "target_lat": 31.68}, False, ["target_lng"]),
        ({"device_id": "uav-001", "action": "move", "target_lng": 103.85}, False, ["target_lat"]),
    ])
    def test_uav_slot_validation(self, slots, expected_valid, expected_missing):
        """Test slot validation for all scenarios"""
        handler = UAVControlHandler()
        is_valid, missing = handler.validate_slots(slots)

        assert is_valid == expected_valid
        assert set(missing) == set(expected_missing)


@pytest.mark.asyncio
class TestUAVActionExecution:
    """Test UAVControlHandler.execute_action"""

    async def test_execute_takeoff_action(self):
        """Should execute takeoff action successfully"""
        handler = UAVControlHandler()
        slots = {"device_id": "uav-001", "action": "takeoff", "altitude_m": 50}
        context = {"java_api_base": "http://test-api"}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True
        assert result["device_id"] == "uav-001"
        assert result["action_type"] == "uav_control"
        assert "TODO" in result["message"]
        assert "details" in result
        assert result["details"]["java_api_url"] == "http://test-api/devices/uav/uav-001/control"

    async def test_execute_move_action(self):
        """Should execute move action with coordinates"""
        handler = UAVControlHandler()
        slots = {
            "device_id": "uav-002",
            "action": "move",
            "target_lat": 31.68,
            "target_lng": 103.85
        }
        context = {}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True
        assert result["device_id"] == "uav-002"

    async def test_execute_rtl_action(self):
        """Should execute return-to-launch action"""
        handler = UAVControlHandler()
        slots = {"device_id": "uav-003", "action": "rtl"}
        context = {}

        result = await handler.execute_action(slots, context)

        assert result["success"] is True
        assert result["action_type"] == "uav_control"


class TestUAVLogging:
    """Test UAVControlHandler logging standards"""

    @pytest.mark.asyncio
    async def test_logs_no_emoji(self, caplog):
        """Logs must not contain emoji"""
        handler = UAVControlHandler()
        slots = {"device_id": "uav-001", "action": "takeoff"}
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
        """Logs must use text tags format [UAV][CONTROL][OPERATION]"""
        handler = UAVControlHandler()
        slots = {"device_id": "uav-001", "action": "takeoff"}
        context = {}

        await handler.execute_action(slots, context)

        # Check log format
        found_enter = False
        found_success = False

        for record in caplog.records:
            if "[UAV][CONTROL][ENTER]" in record.message:
                found_enter = True
            if "[UAV][CONTROL][SUCCESS]" in record.message:
                found_success = True

        assert found_enter, "Missing [UAV][CONTROL][ENTER] log"
        assert found_success, "Missing [UAV][CONTROL][SUCCESS] log"


class TestUAVTODOPlaceholders:
    """Test TODO placeholders are present and grep-searchable"""

    @pytest.mark.asyncio
    async def test_todo_placeholder_in_logs(self, caplog):
        """Logs must contain TODO placeholder for Java API"""
        handler = UAVControlHandler()
        slots = {"device_id": "uav-001", "action": "takeoff"}
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
        import emergency_agents.intent.handlers.uav_control as uav_module
        import inspect

        source = inspect.getsource(uav_module)
        assert "TODO:" in source, "TODO: not found in source code"


class TestUAVTypeAnnotations:
    """Test 100% type annotations"""

    def test_validate_slots_return_type(self):
        """validate_slots must return tuple[bool, list[str]]"""
        handler = UAVControlHandler()
        result = handler.validate_slots({"device_id": "test", "action": "takeoff"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)

    @pytest.mark.asyncio
    async def test_execute_action_return_type(self):
        """execute_action must return ActionResult (TypedDict)"""
        handler = UAVControlHandler()
        result = await handler.execute_action(
            {"device_id": "test", "action": "takeoff"},
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
# Run UAV handler tests
pytest tests/test_uav_handler.py -v

# Check type annotations
mypy src/emergency_agents/intent/handlers/uav_control.py --strict

# Verify no emoji in logs (run full test suite)
pytest tests/test_uav_handler.py::TestUAVLogging -v
```

### Manual Validation
```bash
# Test handler discovery
python -c "
from emergency_agents.intent.registry import get_handler_registry

registry = get_handler_registry()
handler = registry.get_handler('device_control_uav')
print(f'UAV Handler: {handler}')
print(f'Intent Type: {handler.get_intent_type()}')
"

# Grep for TODO
grep -n "TODO:" src/emergency_agents/intent/handlers/uav_control.py
```

## 📊 Success Criteria

- [ ] UAVControlSlots defined in schemas.py with comment separators
- [ ] UAVControlHandler implements IntentHandler interface
- [ ] All parameterized tests pass (valid and invalid slots)
- [ ] Zero emoji in logs (regex validation passes)
- [ ] TODO placeholders present and grep-searchable
- [ ] mypy --strict passes
- [ ] Handler auto-discovered by Registry
- [ ] All tests pass: `pytest tests/test_uav_handler.py -v`

## 🚨 Common Issues and Solutions

### Issue 1: Handler Not Discovered
**Solution**: Ensure `__init__.py` exists in handlers package and handler class name ends with "Handler"

### Issue 2: Type Errors with mypy
**Solution**: Add explicit type annotations for all parameters and return values
```python
# Wrong
def validate_slots(self, slots):
    ...

# Correct
def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
    ...
```

### Issue 3: Emoji Found in Logs
**Solution**: Use text tags only, remove all emoji
```python
# Wrong
logger.info("🚁 UAV takeoff")

# Correct
logger.info("[UAV][CONTROL][ENTER] device_id=%s | action=takeoff", device_id)
```

### Issue 4: TODO Not Grep-Searchable
**Solution**: Use format `TODO: call POST {url}` in logs

## 📚 References

- Capability Spec: `openspec/changes/conversation-management-v1/specs/device-control-uav/spec.md`
- Handler Registry API: `docs/reference/handler-registry-api.md`
- Type Annotations Guide: Python typing module documentation

## ⏭️ Next Steps

After completing UAV handler:
1. Run full test suite: `pytest tests/test_uav_handler.py -v`
2. Commit changes: `git add . && git commit -m "feat(handler): implement UAVControlHandler"`
3. Push branch: `git push origin feature/uav-control-handler`
4. Create PR with title: `[Phase 2] UAVControlHandler Implementation`
5. Wait for AI-1 to merge in Phase 3

## 🤝 Parallel Development Notes

### Avoiding Merge Conflicts

You are working in parallel with AI-3 (robot dog) and AI-4 (video analysis). To minimize conflicts:

**schemas.py Strategy**:
- Use comment separators (see Step 2)
- Only modify your section
- Don't reformat other sections

**Branch Strategy**:
- Work only in `feature/uav-control-handler`
- Don't merge other branches
- Don't modify shared files except schemas.py (with separators)

**Communication**:
- If you need to modify shared infrastructure, wait for Phase 3
- Ask AI-1 if uncertain about changes

---

**Duration Estimate**: 1-1.5 days
**Complexity**: Medium
**Dependencies**: Phase 1 complete
**Parallel Work**: AI-3 (robot dog), AI-4 (video analysis)
