# Phase 3: Integration Guide (AI-1)

**Assignee**: AI-1
**Duration**: 1-2 days
**Branch**: `master` (merge target)
**Goal**: Integrate all Phase 2 handlers, resolve conflicts, validate system-wide functionality

## 📋 Prerequisites

Before starting Phase 3, ensure:
- [ ] Phase 1 infrastructure complete and deployed
- [ ] All Phase 2 handlers complete (AI-2/3/4 PRs created)
- [ ] All handler tests passing in their branches
- [ ] All handlers follow interface contract
- [ ] No emoji in any handler logs
- [ ] All handlers have TODO placeholders

## 🎯 Phase 3 Objectives

1. Review all Phase 2 handler PRs
2. Merge handlers sequentially (one at a time)
3. Resolve schema conflicts in schemas.py
4. Verify handler auto-discovery
5. Run integration tests
6. Validate end-to-end routing
7. Deploy and monitor

## 📂 Merge Order

**IMPORTANT**: Merge handlers sequentially, not all at once. This makes conflict resolution easier.

```
1. feature/uav-control-handler (AI-2)
   ↓ Test auto-discovery
2. feature/robotdog-control-handler (AI-3)
   ↓ Test auto-discovery
3. feature/video-analysis-handler (AI-4)
   ↓ Test all handlers registered
```

## 🔨 Implementation Steps

### Step 1: Review Handler PRs

For each PR, verify the following checklist:

#### UAV Handler PR Review (AI-2)
- [ ] `src/emergency_agents/intent/schemas.py` has UAVControlSlots with comment separators
- [ ] `src/emergency_agents/intent/handlers/uav_control.py` exists
- [ ] `tests/test_uav_handler.py` exists and all tests pass
- [ ] Interface contract test passes
- [ ] No emoji in logs (regex test passes)
- [ ] TODO placeholders present and grep-searchable
- [ ] mypy --strict passes

#### Robot Dog Handler PR Review (AI-3)
- [ ] `src/emergency_agents/intent/schemas.py` has RobotDogControlSlots with comment separators
- [ ] `src/emergency_agents/intent/handlers/robotdog_control.py` exists
- [ ] `tests/test_robotdog_handler.py` exists and all tests pass
- [ ] Interface contract test passes
- [ ] No emoji in logs
- [ ] TODO placeholders present
- [ ] mypy --strict passes

#### Video Handler PR Review (AI-4)
- [ ] `src/emergency_agents/intent/schemas.py` has VideoAnalysisSlots with comment separators
- [ ] `src/emergency_agents/intent/handlers/video_analysis.py` exists
- [ ] `tests/test_video_handler.py` exists and all tests pass
- [ ] Interface contract test passes
- [ ] No emoji in logs
- [ ] TODO placeholders present
- [ ] mypy --strict passes

### Step 2: Merge UAV Handler (First)

```bash
# Update master
git checkout master
git pull

# Merge UAV handler
git merge --no-ff feature/uav-control-handler

# If merge conflict in schemas.py, resolve manually (see Step 3)
```

**Post-Merge Validation**:
```bash
# Verify handler registered
python -c "
from emergency_agents.intent.registry import get_handler_registry

registry = get_handler_registry()
handlers = registry.get_all_handlers()
print(f'Registered handlers: {list(handlers.keys())}')
assert 'device_control_uav' in handlers
"

# Run tests
pytest tests/test_uav_handler.py -v

# Type check
mypy src/emergency_agents/intent/ --strict
```

### Step 3: Resolve Schema Conflicts (Critical)

**Scenario**: All three AI-2/3/4 modified `schemas.py` with comment separators.

**Conflict Resolution Strategy**:

**File**: `src/emergency_agents/intent/schemas.py` (after all merges)

```python
# ... existing schemas ...

# ============================================================
# START: UAVControlSlots (AI-2, feature/uav-control-handler)
# ============================================================

class UAVControlSlots(TypedDict):
    """UAV control intent slots"""
    device_id: str
    action: str
    altitude_m: NotRequired[float]
    target_lat: NotRequired[float]
    target_lng: NotRequired[float]
    speed_mps: NotRequired[float]
    timeout_sec: NotRequired[int]

# ============================================================
# END: UAVControlSlots (AI-2)
# ============================================================


# ============================================================
# START: RobotDogControlSlots (AI-3, feature/robotdog-control-handler)
# ============================================================

class RobotDogControlSlots(TypedDict):
    """Robot dog control intent slots"""
    device_id: str
    action: str
    waypoints: NotRequired[list[list[float]]]
    target_id: NotRequired[str]
    target_type: NotRequired[str]
    follow_distance_m: NotRequired[float]
    guard_lat: NotRequired[float]
    guard_lng: NotRequired[float]
    target_lat: NotRequired[float]
    target_lng: NotRequired[float]
    speed_mps: NotRequired[float]
    timeout_sec: NotRequired[int]

# ============================================================
# END: RobotDogControlSlots (AI-3)
# ============================================================


# ============================================================
# START: VideoAnalysisSlots (AI-4, feature/video-analysis-handler)
# ============================================================

class VideoAnalysisSlots(TypedDict):
    """Video analysis intent slots"""
    camera_id: NotRequired[str]
    stream_url: NotRequired[str]
    analysis_type: str
    target_classes: NotRequired[list[str]]
    sensitivity: NotRequired[str]
    duration_minutes: NotRequired[int]
    enable_recording: NotRequired[bool]
    storage_path: NotRequired[str]
    notify_on_event: NotRequired[bool]
    notification_threshold: NotRequired[int]
    frame_rate: NotRequired[int]

# ============================================================
# END: VideoAnalysisSlots (AI-4)
# ============================================================
```

**Resolution Steps**:
1. Keep all three sections separated by comment blocks
2. Preserve blank lines between sections
3. Don't reformat any section
4. Verify no duplicate TypedDict names

### Step 4: Merge Robot Dog Handler (Second)

```bash
git checkout master
git pull

# Merge robot dog handler
git merge --no-ff feature/robotdog-control-handler

# Resolve schema conflicts if any (follow Step 3 strategy)
```

**Post-Merge Validation**:
```bash
# Verify both handlers registered
python -c "
from emergency_agents.intent.registry import get_handler_registry

registry = get_handler_registry()
handlers = registry.get_all_handlers()
print(f'Registered handlers: {list(handlers.keys())}')
assert 'device_control_uav' in handlers
assert 'device_control_robotdog' in handlers
"

# Run all tests
pytest tests/test_uav_handler.py tests/test_robotdog_handler.py -v
```

### Step 5: Merge Video Handler (Third)

```bash
git checkout master
git pull

# Merge video handler
git merge --no-ff feature/video-analysis-handler

# Resolve schema conflicts if any
```

**Post-Merge Validation**:
```bash
# Verify all three handlers registered
python -c "
from emergency_agents.intent.registry import get_handler_registry

registry = get_handler_registry()
handlers = registry.get_all_handlers()
print(f'Registered handlers: {list(handlers.keys())}')
assert 'device_control_uav' in handlers
assert 'device_control_robotdog' in handlers
assert 'video_analysis_start' in handlers
print('✅ All handlers registered successfully')
"

# Run all handler tests
pytest tests/test_*_handler.py -v
```

### Step 6: Integration Testing

**File**: `tests/test_handler_integration.py` (create)

```python
"""Integration tests for all handlers"""
import pytest
from emergency_agents.intent.registry import get_handler_registry


class TestHandlerIntegration:
    """Test all handlers work together"""

    def test_all_handlers_registered(self):
        """All three handlers must be registered"""
        registry = get_handler_registry()
        handlers = registry.get_all_handlers()

        assert 'device_control_uav' in handlers
        assert 'device_control_robotdog' in handlers
        assert 'video_analysis_start' in handlers

    def test_all_handlers_have_nodes(self):
        """All handlers must have LangGraph node names"""
        registry = get_handler_registry()

        assert registry.get_node_name('device_control_uav') == 'device_control_uav_node'
        assert registry.get_node_name('device_control_robotdog') == 'device_control_robotdog_node'
        assert registry.get_node_name('video_analysis_start') == 'video_analysis_start_node'

    def test_all_handlers_implement_interface(self):
        """All handlers must implement IntentHandler interface"""
        from emergency_agents.intent.handlers.base import IntentHandler
        registry = get_handler_registry()

        for intent_type, handler_class in registry.get_all_handlers().items():
            assert issubclass(handler_class, IntentHandler), \
                f"Handler for {intent_type} doesn't implement IntentHandler"

    @pytest.mark.asyncio
    async def test_all_handlers_executable(self):
        """All handlers must be executable without errors"""
        registry = get_handler_registry()

        # Test UAV handler
        uav_handler = registry.get_handler('device_control_uav')()
        result = await uav_handler.execute_action(
            {"device_id": "test", "action": "takeoff"},
            {}
        )
        assert result["success"] is True

        # Test robot dog handler
        dog_handler = registry.get_handler('device_control_robotdog')()
        result = await dog_handler.execute_action(
            {"device_id": "test", "action": "sit"},
            {}
        )
        assert result["success"] is True

        # Test video handler
        video_handler = registry.get_handler('video_analysis_start')()
        result = await video_handler.execute_action(
            {"camera_id": "test", "analysis_type": "motion_detection"},
            {}
        )
        assert result["success"] is True


class TestEndToEndRouting:
    """Test end-to-end intent routing"""

    @pytest.mark.asyncio
    async def test_graph_compilation(self):
        """LangGraph should compile with all handlers"""
        from emergency_agents.graph.app import build_emergency_graph
        from emergency_agents.config import AppConfig

        cfg = AppConfig.load_from_env()
        graph = await build_emergency_graph(cfg)

        assert graph is not None
        # Graph compilation succeeded

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_uav_intent_routing(self):
        """UAV intent should route to correct handler"""
        # This test requires full system setup
        # Implement after graph integration
        pass


class TestSchemaConflicts:
    """Verify schema definitions don't conflict"""

    def test_schemas_importable(self):
        """All schema TypedDicts should be importable"""
        from emergency_agents.intent.schemas import (
            UAVControlSlots,
            RobotDogControlSlots,
            VideoAnalysisSlots
        )

        assert UAVControlSlots is not None
        assert RobotDogControlSlots is not None
        assert VideoAnalysisSlots is not None

    def test_no_duplicate_slot_names(self):
        """Ensure no conflicting TypedDict names"""
        import emergency_agents.intent.schemas as schemas_module

        type_dict_names = [
            name for name in dir(schemas_module)
            if name.endswith('Slots') and not name.startswith('_')
        ]

        # Should have at least 3 handler slots
        assert len(type_dict_names) >= 3

        # No duplicates
        assert len(type_dict_names) == len(set(type_dict_names))
```

### Step 7: Validation Checklist

**Run Full Test Suite**:
```bash
# Unit tests
pytest -m unit -v

# Integration tests
pytest -m integration -v

# All handler tests
pytest tests/test_*_handler.py -v

# Integration test
pytest tests/test_handler_integration.py -v

# Type checking
mypy src/emergency_agents/ --strict
```

**Manual Validation**:
```bash
# 1. Verify registry discovers all handlers
python -c "
from emergency_agents.intent.registry import get_handler_registry

registry = get_handler_registry()
handlers = registry.get_all_handlers()
print('Registered Handlers:')
for intent_type, handler_class in handlers.items():
    node_name = registry.get_node_name(intent_type)
    print(f'  - {intent_type} → {handler_class.__name__} → {node_name}')
"

# 2. Verify no emoji in logs
grep -rn "[\U0001F600-\U0001F64F]" src/emergency_agents/intent/handlers/*.py || echo "✅ No emoji found"

# 3. Verify TODO placeholders
grep -rn "TODO:" src/emergency_agents/intent/handlers/*.py

# 4. Count test coverage
pytest --cov=src/emergency_agents/intent/handlers tests/test_*_handler.py --cov-report=term-missing
```

### Step 8: Performance Testing

**File**: `tests/test_handler_performance.py` (create)

```python
"""Performance tests for handler execution"""
import pytest
import time
from emergency_agents.intent.registry import get_handler_registry


@pytest.mark.asyncio
class TestHandlerPerformance:
    """Test handler execution performance"""

    async def test_uav_handler_latency(self):
        """UAV handler should execute in < 100ms"""
        registry = get_handler_registry()
        handler = registry.get_handler('device_control_uav')()

        start = time.time()
        await handler.execute_action(
            {"device_id": "test", "action": "takeoff"},
            {}
        )
        latency_ms = (time.time() - start) * 1000

        assert latency_ms < 100, f"UAV handler took {latency_ms:.2f}ms"

    async def test_registry_initialization_time(self):
        """Registry should initialize in < 1 second"""
        start = time.time()
        registry = get_handler_registry()
        init_time_ms = (time.time() - start) * 1000

        assert init_time_ms < 1000, f"Registry init took {init_time_ms:.2f}ms"
        assert len(registry.get_all_handlers()) >= 3
```

## 📊 Success Criteria

### Functionality
- [ ] All three handlers registered in HandlerRegistry
- [ ] All handler tests pass individually
- [ ] Integration tests pass
- [ ] LangGraph compiles with all handlers
- [ ] End-to-end routing works (manual test)

### Code Quality
- [ ] mypy --strict passes for all handler code
- [ ] Zero emoji in any handler logs
- [ ] TODO placeholders present in all handlers
- [ ] schemas.py has no duplicate TypedDict names
- [ ] Comment separators preserved in schemas.py

### Performance
- [ ] Registry initialization < 1 second
- [ ] Handler execution latency < 100ms (with TODO placeholders)
- [ ] LangGraph compilation < 5 seconds

## 🚨 Common Issues and Solutions

### Issue 1: Merge Conflict in schemas.py
**Solution**: Keep all three sections with comment separators, don't reformat

### Issue 2: Handler Not Discovered After Merge
**Solution**: Verify `__init__.py` exists in handlers package and handler file is in correct location

### Issue 3: Duplicate TypedDict Names
**Solution**: Each handler should have unique slot TypedDict name (e.g., UAVControlSlots, not ControlSlots)

### Issue 4: Import Errors After Merge
**Solution**: Run `python -c "import emergency_agents.intent.schemas"` to verify schemas are importable

### Issue 5: Tests Pass Individually But Fail Together
**Solution**: Check for global state pollution, ensure each test is independent

## 📚 Testing Matrix

| Test Category | Command | Expected Result |
|--------------|---------|-----------------|
| UAV Handler | `pytest tests/test_uav_handler.py -v` | All pass |
| Robot Dog Handler | `pytest tests/test_robotdog_handler.py -v` | All pass |
| Video Handler | `pytest tests/test_video_handler.py -v` | All pass |
| Integration | `pytest tests/test_handler_integration.py -v` | All pass |
| Performance | `pytest tests/test_handler_performance.py -v` | All pass |
| Type Check | `mypy src/emergency_agents/intent/ --strict` | No errors |
| Coverage | `pytest --cov=src/emergency_agents/intent/handlers` | > 85% |

## 🚀 Deployment Steps

### Step 1: Final Validation
```bash
# Run full test suite
pytest -v

# Type check
mypy src/emergency_agents/ --strict

# Check for TODOs
grep -rn "TODO:" src/emergency_agents/intent/handlers/
```

### Step 2: Tag Release
```bash
git tag -a phase2-complete -m "Phase 2: All handlers integrated and tested"
git push origin phase2-complete
```

### Step 3: Update Documentation
Update `README.md` to reflect new handlers:
```markdown
## Available Intent Handlers

- **UAV Control** (`device_control_uav`): Takeoff, landing, movement, hover, RTL
- **Robot Dog Control** (`device_control_robotdog`): Patrol, follow, guard, sit, stand
- **Video Analysis** (`video_analysis_start`): Motion/object/anomaly detection, face recognition
```

### Step 4: Monitor System
```bash
# Start development server
./scripts/dev-run.sh

# Test handler discovery
curl http://localhost:8008/healthz

# Check logs
tail -f temp/server.log | grep -i "REGISTRY\|UAV\|ROBOTDOG\|VIDEO"
```

## 📈 Metrics to Monitor

### Development Metrics
- Total Lines of Code: ~1500 lines (handlers + tests)
- Test Coverage: Target > 85%
- Type Annotation Coverage: 100%

### Runtime Metrics
- Handler Registration Time: < 1 second
- Handler Execution Time: < 100ms (with TODO)
- LangGraph Compilation Time: < 5 seconds

## ⏭️ Next Steps (Phase 3 Complete)

1. **Java API Integration** (not covered in this proposal):
   - Replace TODO placeholders with actual API calls
   - Implement HTTP client with retry logic
   - Add comprehensive error handling

2. **Production Readiness**:
   - Add authentication/authorization
   - Implement rate limiting
   - Add monitoring and alerting
   - Set up CI/CD pipeline

3. **Feature Enhancements**:
   - Add more intent handlers
   - Implement batch operations
   - Add webhook notifications

## 📞 Communication

### Status Updates
After each merge:
1. Notify AI-2/3/4 of merge completion
2. Report any conflicts encountered
3. Share integration test results

### Issue Escalation
If integration fails:
1. Document the specific failure
2. Identify which handler(s) caused the issue
3. Create detailed bug report
4. Request fix from responsible AI

---

**Duration Estimate**: 1-2 days
**Complexity**: Medium-High
**Dependencies**: Phase 1 + Phase 2 (all handlers) complete
**Critical Path**: Yes (blocks deployment)

## 🎉 Phase 3 Completion Criteria

- [ ] All three handlers merged to master
- [ ] All tests passing
- [ ] mypy --strict passes
- [ ] No emoji in any logs
- [ ] Integration tests created and passing
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] System deployed and monitored
- [ ] Phase 2 release tagged

**When all checkboxes are ticked, Phase 3 is complete! 🚀**
