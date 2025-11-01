# Handler Development Guides

**Purpose**: Comprehensive guides for AI-2/3/4 to implement intent handlers in parallel following the Handler-based architecture.

## 📚 Guide Structure

This directory contains phase-specific guides for the multi-AI parallel development workflow:

### Phase 1: Infrastructure (AI-1)
- **[phase1-infrastructure.md](./phase1-infrastructure.md)** - Infrastructure setup guide for AI-1
  - AsyncPostgresSaver integration
  - AsyncConversationDAO implementation
  - Handler framework (base.py + Registry)
  - Graph modification for auto-registration
  - Configuration updates

### Phase 2: Parallel Handler Development (AI-2/3/4)
- **[phase2-uav-handler.md](./phase2-uav-handler.md)** - UAV control handler guide for AI-2
  - Branch: `feature/uav-control-handler`
  - Spec: `specs/device-control-uav/spec.md`
  - Focus: UAV takeoff, landing, movement, hover, RTL commands

- **[phase2-robotdog-handler.md](./phase2-robotdog-handler.md)** - Robot dog handler guide for AI-3
  - Branch: `feature/robotdog-control-handler`
  - Spec: `specs/device-control-robotdog/spec.md`
  - Focus: Patrol, follow, guard, sit/stand, movement commands

- **[phase2-video-handler.md](./phase2-video-handler.md)** - Video analysis handler guide for AI-4
  - Branch: `feature/video-analysis-handler`
  - Spec: `specs/video-analysis/spec.md`
  - Focus: Video stream analysis task initiation and management

### Phase 3: Integration (AI-1)
- **[phase3-integration.md](./phase3-integration.md)** - Integration guide for AI-1
  - Merge strategy for parallel branches
  - Schema conflict resolution
  - Integration testing
  - Validation and deployment

## 🎯 Development Workflow

```
Phase 1 (AI-1)
    │
    ├─ AsyncPostgresSaver setup
    ├─ AsyncConversationDAO implementation
    ├─ Handler framework creation
    ├─ Graph auto-registration
    └─ Configuration updates
    │
    └──> Phase 1 Complete ✅
         │
         ├───> Phase 2 Parallel Development
         │     │
         │     ├─ AI-2: UAV Handler (branch: feature/uav-control-handler)
         │     ├─ AI-3: Robot Dog Handler (branch: feature/robotdog-control-handler)
         │     └─ AI-4: Video Handler (branch: feature/video-analysis-handler)
         │     │
         │     └──> All Handlers Complete ✅
         │          │
         └──────────> Phase 3 Integration (AI-1)
                      │
                      ├─ Merge feature branches
                      ├─ Resolve schema conflicts
                      ├─ Integration testing
                      └─ Deployment
                      │
                      └──> System Complete ✅
```

## ✅ Prerequisites for Each Phase

### Phase 1 Prerequisites (AI-1)
- [ ] Read `openspec/changes/conversation-management-v1/proposal.md`
- [ ] Read `openspec/changes/conversation-management-v1/design.md`
- [ ] Read `openspec/changes/conversation-management-v1/tasks.md`
- [ ] Read `openspec/changes/conversation-management-v1/specs/conversation-tracking/spec.md`
- [ ] Read `docs/reference/langgraph-best-practices.md`
- [ ] Read `docs/reference/psycopg3-dao-patterns.md`

### Phase 2 Prerequisites (AI-2/3/4)
- [ ] Read the corresponding capability spec (device-control-uav/robotdog/video-analysis)
- [ ] Read `docs/reference/handler-registry-api.md`
- [ ] Understand `IntentHandler` abstract base class contract
- [ ] Review logging standards (no emoji, text tags)
- [ ] Review type annotation requirements (100% mypy --strict)

### Phase 3 Prerequisites (AI-1)
- [ ] All Phase 2 handlers implemented and tested
- [ ] All handler branches have passing tests
- [ ] All handlers follow interface contract
- [ ] Review schema conflict markers in `src/emergency_agents/intent/schemas.py`

## 🔑 Key Architectural Principles

### 1. Handler Interface Contract
All handlers must implement the `IntentHandler` abstract base class:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, TypedDict

class IntentHandler(ABC):
    @classmethod
    @abstractmethod
    def get_intent_type(cls) -> str:
        """Return the intent type this handler handles"""
        pass

    @abstractmethod
    async def execute_action(
        self,
        slots: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """Execute the action for this intent"""
        pass
```

### 2. Handler Registry Auto-Discovery
Handlers are automatically discovered via `pkgutil.iter_modules()`:
- Place handler file in `src/emergency_agents/intent/handlers/`
- Implement `IntentHandler` interface
- No manual registration needed

### 3. Strong Typing Everywhere
- 100% type annotations enforced by `mypy --strict`
- Use `TypedDict` for all data structures
- Use `NotRequired[]` for optional fields
- No `Any` types without explicit justification

### 4. Logging Standards
- **NO EMOJI** - Absolute requirement
- Use text tags: `[MODULE][SUBMODULE][OPERATION]`
- Examples: `[UAV][CONTROL][ENTER]`, `[ROBOTDOG][CONTROL][SUCCESS]`

### 5. TODO Placeholders
- Phase 2 uses TODO placeholders for Java API calls
- TODOs must be grep-searchable: `grep "TODO:" src/`
- Format: `TODO: call POST {java_api_base}/endpoint`

## 📊 Testing Requirements

### Mandatory Tests for Each Handler
1. **Interface Contract Test**: Verify handler implements `IntentHandler`
2. **Logging Test**: Verify no emoji in logs (regex validation)
3. **Slot Validation Test**: Parameterized tests for all slot combinations
4. **Type Annotation Test**: Verify mypy --strict passes

### Test Execution
```bash
# Run handler-specific tests
pytest tests/test_uav_handler.py -v

# Run all handler tests
pytest tests/test_*_handler.py -v

# Check type annotations
mypy src/emergency_agents/intent/handlers/ --strict
```

## 🚨 Common Pitfalls to Avoid

### ❌ DO NOT
1. Use emoji in logs or code
2. Skip type annotations
3. Manually register handlers in app.py
4. Modify other handlers' files during Phase 2
5. Use synchronous I/O (always use async/await)
6. Ignore slot validation requirements
7. Return dict instead of ActionResult TypedDict

### ✅ DO
1. Follow the capability spec exactly
2. Use text tags for logging
3. Add 100% type annotations
4. Write parameterized tests
5. Use TODO placeholders for Java API
6. Validate slots according to business rules
7. Return ActionResult TypedDict

## 📞 Support and Questions

### During Development
- **Architecture Questions**: Refer to `design.md`
- **API Questions**: Refer to `docs/reference/handler-registry-api.md`
- **LangGraph Questions**: Refer to `docs/reference/langgraph-best-practices.md`
- **DAO Questions**: Refer to `docs/reference/psycopg3-dao-patterns.md`

### FAQs
See each phase guide for phase-specific FAQs.

## 📈 Success Criteria

### Phase 1 Success
- [ ] AsyncPostgresSaver successfully connects
- [ ] AsyncConversationDAO passes all tests
- [ ] HandlerRegistry discovers test handler
- [ ] Graph compiles without errors
- [ ] All infrastructure tests pass

### Phase 2 Success (Per Handler)
- [ ] Handler implements `IntentHandler` interface
- [ ] Handler passes interface contract test
- [ ] Handler logs have zero emoji matches
- [ ] Slot validation tests pass (all scenarios)
- [ ] mypy --strict passes
- [ ] Handler can be discovered by Registry

### Phase 3 Success
- [ ] All handlers registered successfully
- [ ] Schema conflicts resolved
- [ ] Integration tests pass (all handlers)
- [ ] End-to-end routing works
- [ ] System-level performance metrics met

## 🔄 Development Timeline

- **Phase 1 (AI-1)**: 1-2 days (infrastructure + tests)
- **Phase 2 (AI-2/3/4)**: 3-4 days (parallel development)
- **Phase 3 (AI-1)**: 1-2 days (merge + integration)
- **Total**: 5-8 days

## 📝 Version Control Strategy

### Branch Naming
- Phase 1: `master` (direct commits by AI-1)
- Phase 2:
  - `feature/uav-control-handler` (AI-2)
  - `feature/robotdog-control-handler` (AI-3)
  - `feature/video-analysis-handler` (AI-4)
- Phase 3: Merge all feature branches → `master`

### Commit Message Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

Examples:
```
feat(handler): implement UAVControlHandler

- Add UAVControlSlots TypedDict
- Implement slot validation for move action
- Add TODO placeholders for Java API

Ref: specs/device-control-uav/spec.md
```

## 🎓 Learning Path

**For AI-2/3/4 (Handler Developers)**:
1. Read your phase-specific guide first
2. Read your capability spec thoroughly
3. Review `IntentHandler` interface in base.py
4. Study the handler implementation example in your spec
5. Review test examples in your guide
6. Start implementation

**For AI-1 (Infrastructure + Integration)**:
1. Read phase1-infrastructure.md
2. Study LangGraph AsyncPostgresSaver docs
3. Study psycopg3 AsyncConnectionPool docs
4. Implement infrastructure step-by-step
5. Read phase3-integration.md when Phase 2 completes
6. Execute merge and integration strategy

---

**Remember**: Documentation-first, strong typing always, no emoji ever! 🚫
