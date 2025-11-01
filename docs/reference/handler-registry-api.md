# Handler Registry API Reference

**Purpose**: Complete API reference for HandlerRegistry, IntentHandler interface, and auto-discovery mechanism.

**Target Audience**: All AIs (AI-1/2/3/4), developers implementing intent handlers

## 📚 Table of Contents

1. [IntentHandler Interface](#intenthandler-interface)
2. [HandlerRegistry API](#handlerregistry-api)
3. [Auto-Discovery Mechanism](#auto-discovery-mechanism)
4. [create_handler_node Factory](#create_handler_node-factory)
5. [ActionResult TypedDict](#actionresult-typeddict)
6. [Handler Implementation Patterns](#handler-implementation-patterns)
7. [Testing Patterns](#testing-patterns)
8. [Troubleshooting](#troubleshooting)

---

## IntentHandler Interface

### Abstract Base Class

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, TypedDict, NotRequired

class ActionResult(TypedDict):
    """Handler execution result"""
    success: bool
    message: str
    device_id: str
    action_type: str
    details: NotRequired[dict[str, Any] | None]


class IntentHandler(ABC):
    """Abstract base class for all intent handlers"""

    @classmethod
    @abstractmethod
    def get_intent_type(cls) -> str:
        """
        Return the intent type this handler handles

        Returns:
            str: Intent type identifier (e.g., "device_control_uav")

        Example:
            @classmethod
            def get_intent_type(cls) -> str:
                return "device_control_uav"
        """
        pass

    @abstractmethod
    def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate intent slots (business-level validation)

        Args:
            slots: Intent slots dictionary (device_id, action, parameters)

        Returns:
            tuple[bool, list[str]]: (is_valid, missing_fields)

        Example:
            def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
                missing = []
                if slots.get("action") == "move":
                    if slots.get("target_lat") is None:
                        missing.append("target_lat")
                return (len(missing) == 0, missing)
        """
        pass

    @abstractmethod
    async def execute_action(
        self,
        slots: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """
        Execute the action for this intent

        Args:
            slots: Intent slots (device_id, action, parameters)
            context: Execution context
                - java_api_base: str (Java API base URL)
                - conversation_dao: AsyncConversationDAO
                - config: AppConfig

        Returns:
            ActionResult: Execution result with success status

        Example:
            async def execute_action(
                self,
                slots: Dict[str, Any],
                context: Dict[str, Any]
            ) -> ActionResult:
                device_id = slots["device_id"]
                action = slots["action"]

                # Execute action (TODO in Phase 2)
                logger.info("[UAV][CONTROL][ENTER] device_id=%s", device_id)

                return ActionResult(
                    success=True,
                    message=f"UAV {device_id} action executed",
                    device_id=device_id,
                    action_type="uav_control",
                    details={"slots": slots}
                )
        """
        pass
```

### Interface Contract

All handlers **MUST**:
1. Inherit from `IntentHandler`
2. Implement `get_intent_type()` class method
3. Implement `validate_slots()` method
4. Implement `execute_action()` async method
5. Return `ActionResult` TypedDict from `execute_action()`
6. Have 100% type annotations

All handlers **MUST NOT**:
1. Use emoji in logs
2. Return plain `dict` instead of `ActionResult`
3. Skip slot validation

---

## HandlerRegistry API

### Class: HandlerRegistry

Auto-discovery registry for intent handlers.

```python
class HandlerRegistry:
    """Registry for auto-discovered intent handlers"""

    def __init__(self) -> None:
        """Initialize registry and auto-discover handlers"""
        self._handlers: Dict[str, Type[IntentHandler]] = {}
        self._node_mapping: Dict[str, str] = {}
        self._discover_handlers()
```

### Methods

#### `get_handler(intent_type: str) -> Type[IntentHandler] | None`

Get handler class by intent type.

**Parameters**:
- `intent_type` (str): Intent type identifier (e.g., "device_control_uav")

**Returns**:
- `Type[IntentHandler] | None`: Handler class or None if not found

**Example**:
```python
from emergency_agents.intent.registry import get_handler_registry

registry = get_handler_registry()
handler_class = registry.get_handler("device_control_uav")

if handler_class:
    handler = handler_class()
    result = await handler.execute_action(slots, context)
```

#### `get_node_name(intent_type: str) -> str | None`

Get LangGraph node name for intent type.

**Parameters**:
- `intent_type` (str): Intent type identifier

**Returns**:
- `str | None`: Node name (e.g., "device_control_uav_node") or None

**Example**:
```python
registry = get_handler_registry()
node_name = registry.get_node_name("device_control_uav")
# Returns: "device_control_uav_node"
```

#### `get_all_handlers() -> Dict[str, Type[IntentHandler]]`

Get all registered handlers.

**Returns**:
- `Dict[str, Type[IntentHandler]]`: Mapping of intent_type → handler_class

**Example**:
```python
registry = get_handler_registry()
handlers = registry.get_all_handlers()

for intent_type, handler_class in handlers.items():
    print(f"{intent_type} → {handler_class.__name__}")

# Output:
# device_control_uav → UAVControlHandler
# device_control_robotdog → RobotDogControlHandler
# video_analysis_start → VideoAnalysisHandler
```

#### `is_registered(intent_type: str) -> bool`

Check if intent type is registered.

**Parameters**:
- `intent_type` (str): Intent type to check

**Returns**:
- `bool`: True if registered, False otherwise

**Example**:
```python
registry = get_handler_registry()
if registry.is_registered("device_control_uav"):
    print("UAV handler is registered")
```

### Singleton Access

```python
from emergency_agents.intent.registry import get_handler_registry

# ✅ Always use singleton accessor
registry = get_handler_registry()

# ❌ Don't instantiate directly
# registry = HandlerRegistry()  # Wrong!
```

---

## Auto-Discovery Mechanism

### How Discovery Works

```python
def _discover_handlers(self) -> None:
    """Auto-discover all IntentHandler implementations"""
    import emergency_agents.intent.handlers as handlers_package
    import pkgutil
    import importlib

    # ✅ Iterate over all modules in handlers package
    module_iter: Iterator[tuple[Any, str, bool]] = pkgutil.iter_modules(
        handlers_package.__path__
    )

    for module_finder, module_name, is_pkg in module_iter:
        if module_name == "base":
            continue  # Skip base module

        # Import module
        full_module_name: str = f"emergency_agents.intent.handlers.{module_name}"
        module: ModuleType = importlib.import_module(full_module_name)

        # Find IntentHandler subclasses
        for attr_name in dir(module):
            attr: Any = getattr(module, attr_name)

            # ✅ Check if it's an IntentHandler subclass
            if (isinstance(attr, type) and
                issubclass(attr, IntentHandler) and
                attr is not IntentHandler):

                handler_class: Type[IntentHandler] = attr
                intent_type: str = handler_class.get_intent_type()
                node_name: str = f"{intent_type}_node"

                # Register handler
                self._handlers[intent_type] = handler_class
                self._node_mapping[intent_type] = node_name

                logger.info(
                    "[REGISTRY][DISCOVER] intent_type=%s | handler=%s | node=%s",
                    intent_type,
                    handler_class.__name__,
                    node_name
                )
```

### Discovery Requirements

For a handler to be discovered, it must:
1. **Be in the handlers package**: `src/emergency_agents/intent/handlers/`
2. **Inherit from IntentHandler**: `class MyHandler(IntentHandler)`
3. **Not be named "base"**: File cannot be `base.py`
4. **Have `__init__.py`**: Package must have `__init__.py` file

### Example Directory Structure

```
src/emergency_agents/intent/handlers/
├── __init__.py (required)
├── base.py (skipped by discovery)
├── uav_control.py (discovered ✅)
├── robotdog_control.py (discovered ✅)
└── video_analysis.py (discovered ✅)
```

---

## create_handler_node Factory

### Function Signature

```python
def create_handler_node(
    handler_class: Type[IntentHandler],
    context: Dict[str, Any]
) -> Callable:
    """
    Factory function to create a LangGraph node from handler class

    Args:
        handler_class: IntentHandler subclass
        context: Execution context
            - java_api_base: str
            - conversation_dao: AsyncConversationDAO
            - config: AppConfig

    Returns:
        Callable node function for LangGraph
    """
```

### Implementation

```python
def create_handler_node(
    handler_class: Type[IntentHandler],
    context: Dict[str, Any]
) -> Callable:
    """Create LangGraph node from handler"""

    async def handler_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph node function"""
        handler = handler_class()
        slots: Dict[str, Any] = state.get("slots", {})

        # Validate slots
        is_valid, missing = handler.validate_slots(slots)
        if not is_valid:
            return state | {
                "validation_error": f"Missing required slots: {missing}"
            }

        # Execute action
        result = await handler.execute_action(slots, context)
        return state | {"action_result": result}

    return handler_node
```

### Usage in app.py

```python
from emergency_agents.intent.registry import get_handler_registry, create_handler_node

async def build_emergency_graph(cfg: AppConfig):
    """Build LangGraph with auto-registered handlers"""

    handler_context: Dict[str, Any] = {
        "java_api_base": cfg.java_api_base_url,
        "conversation_dao": conversation_dao,
        "config": cfg
    }

    builder = StateGraph(EmergencyState)

    # ✅ Auto-register all handlers
    registry = get_handler_registry()
    for intent_type, handler_class in registry.get_all_handlers().items():
        node_name = registry.get_node_name(intent_type)
        node_function = create_handler_node(handler_class, handler_context)
        builder.add_node(node_name, node_function)
        builder.add_edge(node_name, END)

    return builder.compile(checkpointer=checkpointer)
```

---

## ActionResult TypedDict

### Definition

```python
from typing import TypedDict, NotRequired, Dict, Any

class ActionResult(TypedDict):
    """Handler execution result"""
    success: bool                          # Required: Execution success status
    message: str                           # Required: Human-readable message
    device_id: str                         # Required: Device/source identifier
    action_type: str                       # Required: Action type (uav_control/robotdog_control/video_analysis)
    details: NotRequired[dict[str, Any] | None]  # Optional: Additional details (slots, URLs, task_id)
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `success` | `bool` | ✅ | Execution success status (always `true` in Phase 2) |
| `message` | `str` | ✅ | Human-readable message (Chinese for users) |
| `device_id` | `str` | ✅ | Device/camera/source identifier |
| `action_type` | `str` | ✅ | Handler type: `"uav_control"`, `"robotdog_control"`, `"video_analysis"` |
| `details` | `dict | None` | ❌ | Additional info (slots, java_api_url, task_id) |

### Example ActionResult

```python
# UAV Control Result
result = ActionResult(
    success=True,
    message="无人机 uav-001 控制指令已接收（TODO占位）",
    device_id="uav-001",
    action_type="uav_control",
    details={
        "slots": {"device_id": "uav-001", "action": "takeoff", "altitude_m": 50},
        "java_api_url": "http://localhost:8080/api/devices/uav/uav-001/control"
    }
)

# Robot Dog Control Result
result = ActionResult(
    success=True,
    message="机器狗 dog-001 控制指令已接收（TODO占位）",
    device_id="dog-001",
    action_type="robotdog_control",
    details={
        "slots": {"device_id": "dog-001", "action": "patrol", "waypoints": [[31.68, 103.85], [31.69, 103.86]]},
        "java_api_url": "http://localhost:8080/api/devices/robotdog/dog-001/control"
    }
)

# Video Analysis Result
result = ActionResult(
    success=True,
    message="视频分析任务已启动（TODO占位），任务ID：task-cam-001-1730000000",
    device_id="cam-001",
    action_type="video_analysis",
    details={
        "task_id": "task-cam-001-1730000000",
        "slots": {"camera_id": "cam-001", "analysis_type": "motion_detection"},
        "java_api_url": "http://localhost:8080/api/video/analysis/start"
    }
)
```

---

## Handler Implementation Patterns

### Pattern 1: Basic Handler

```python
class MyHandler(IntentHandler):
    """Simple handler implementation"""

    @classmethod
    def get_intent_type(cls) -> str:
        return "my_intent_type"

    def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
        missing = []
        if slots.get("required_field") is None:
            missing.append("required_field")
        return (len(missing) == 0, missing)

    async def execute_action(
        self,
        slots: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        device_id = slots["device_id"]

        logger.info("[MY][HANDLER][ENTER] device_id=%s", device_id)

        return ActionResult(
            success=True,
            message=f"Action executed for {device_id}",
            device_id=device_id,
            action_type="my_action",
            details={"slots": slots}
        )
```

### Pattern 2: Handler with Complex Validation

```python
class ComplexHandler(IntentHandler):
    """Handler with business-level validation"""

    @classmethod
    def get_intent_type(cls) -> str:
        return "complex_intent"

    def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
        missing = []
        action = slots.get("action")

        # Action-specific validation
        if action == "move":
            if slots.get("target_lat") is None:
                missing.append("target_lat")
            if slots.get("target_lng") is None:
                missing.append("target_lng")

        elif action == "follow":
            if slots.get("target_id") is None:
                missing.append("target_id")

        return (len(missing) == 0, missing)

    async def execute_action(
        self,
        slots: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        # Implementation
        ...
```

### Pattern 3: Handler with Context Usage

```python
class ContextAwareHandler(IntentHandler):
    """Handler using execution context"""

    @classmethod
    def get_intent_type(cls) -> str:
        return "context_aware"

    def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
        return (True, [])

    async def execute_action(
        self,
        slots: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        # ✅ Access context
        java_api_base = context.get("java_api_base")
        conversation_dao = context.get("conversation_dao")
        config = context.get("config")

        # Log to conversation
        if conversation_dao:
            await conversation_dao.add_message(
                conversation_id=slots.get("conversation_id"),
                role="assistant",
                content=f"Executing action: {slots['action']}"
            )

        return ActionResult(
            success=True,
            message="Action with context",
            device_id=slots["device_id"],
            action_type="context_aware",
            details={}
        )
```

---

## Testing Patterns

### Test 1: Interface Contract

```python
def test_handler_implements_interface():
    """Handler must implement IntentHandler interface"""
    from emergency_agents.intent.handlers.base import IntentHandler
    from emergency_agents.intent.handlers.my_handler import MyHandler

    assert issubclass(MyHandler, IntentHandler)
```

### Test 2: Handler Discovery

```python
def test_handler_discovered_by_registry():
    """Handler must be discovered by registry"""
    from emergency_agents.intent.registry import get_handler_registry

    registry = get_handler_registry()
    handler_class = registry.get_handler("my_intent_type")

    assert handler_class is not None
    assert handler_class.get_intent_type() == "my_intent_type"
```

### Test 3: Slot Validation

```python
@pytest.mark.parametrize("slots,expected_valid,expected_missing", [
    ({"device_id": "test", "action": "move", "target_lat": 1.0, "target_lng": 2.0}, True, []),
    ({"device_id": "test", "action": "move"}, False, ["target_lat", "target_lng"]),
])
def test_slot_validation(slots, expected_valid, expected_missing):
    """Test slot validation"""
    handler = MyHandler()
    is_valid, missing = handler.validate_slots(slots)

    assert is_valid == expected_valid
    assert set(missing) == set(expected_missing)
```

### Test 4: Handler Execution

```python
@pytest.mark.asyncio
async def test_execute_action():
    """Test handler execution"""
    handler = MyHandler()
    slots = {"device_id": "test-001", "action": "test"}
    context = {"java_api_base": "http://test"}

    result = await handler.execute_action(slots, context)

    assert result["success"] is True
    assert result["device_id"] == "test-001"
    assert result["action_type"] == "my_action"
```

---

## Troubleshooting

### Issue 1: Handler Not Discovered

**Symptoms**: Registry doesn't find handler

**Checklist**:
- [ ] Handler file is in `src/emergency_agents/intent/handlers/`
- [ ] Handler class inherits from `IntentHandler`
- [ ] `__init__.py` exists in handlers package
- [ ] Handler file is not named `base.py`
- [ ] `get_intent_type()` is implemented

**Debug**:
```python
# Check what was discovered
from emergency_agents.intent.registry import get_handler_registry

registry = get_handler_registry()
print("Discovered handlers:", list(registry.get_all_handlers().keys()))
```

### Issue 2: Type Errors

**Symptoms**: mypy --strict fails

**Solution**: Ensure all methods have explicit type annotations
```python
# ❌ Wrong
def validate_slots(self, slots):
    ...

# ✅ Correct
def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
    ...
```

### Issue 3: ActionResult Type Mismatch

**Symptoms**: TypeError when returning result

**Solution**: Use ActionResult TypedDict, not plain dict
```python
# ❌ Wrong
return {
    "success": True,
    ...
}

# ✅ Correct
return ActionResult(
    success=True,
    ...
)
```

### Issue 4: Node Not Created

**Symptoms**: Handler registered but node not in graph

**Solution**: Verify handler is registered before graph compilation
```python
# ✅ Ensure registry is initialized before building graph
registry = get_handler_registry()  # Triggers discovery

# Then build graph
graph = await build_emergency_graph(cfg)
```

---

## 📚 Official References

1. **Python ABC Module**
   - https://docs.python.org/3/library/abc.html
   - Abstract base classes

2. **pkgutil Module**
   - https://docs.python.org/3/library/pkgutil.html
   - Package discovery utilities

3. **Python typing Module**
   - https://docs.python.org/3/library/typing.html
   - TypedDict, Type[T], Callable

---

**Last Updated**: 2025-10-27
**Maintained By**: AI-1
**Version**: 1.0.0
