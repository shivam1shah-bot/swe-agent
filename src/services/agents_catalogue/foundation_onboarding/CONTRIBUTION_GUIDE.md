# Foundation Onboarding - Contribution Guide

A LangGraph-based workflow for automating new service onboarding across infrastructure components.

---

## 📁 Module Structure

```
foundation_onboarding/
├── __init__.py          # Module exports
├── config.py            # Repository URLs, workflow settings
├── state.py             # FoundationOnboardingState TypedDict
├── models.py            # Pydantic request/response models
├── helper.py            # Utility functions (logging, formatting)
├── validator.py         # Parameter validation logic
├── workflow.py          # LangGraph workflow definition
├── service.py           # Main service (queue + async execution)
└── steps/               # Individual workflow steps
    ├── base.py          # BaseFoundationStep class
    ├── initialization.py
    ├── repo_creation.py
    ├── database_creation.py
    ├── kubemanifest.py
    ├── spinnaker_pipeline.py
    ├── consumer_topic_setup.py
    ├── edge_onboarding.py
    ├── authz_onboarding.py
    ├── monitoring_setup.py
    └── validation.py
```

---

## 🔄 Workflow Execution Order

```
Initialization → Repo Creation → Database Creation → Kubemanifest →
Spinnaker Pipeline → Consumer & Topic Setup → Edge Onboarding →
Authz Onboarding → Monitoring Setup → Validation → END
```

---

## 🛠️ Adding Business Logic to a Step

Each step follows this pattern:

```python
async def execute_step(self, state: FoundationOnboardingState) -> FoundationOnboardingState:
    task_id = state.get("task_id", "unknown")
    service_name = state.get("service_name", "unknown")

    try:
        # 1. Add your business logic here
        # 2. Update state with results (e.g., state["database_info"] = {...})
        # 3. Return state or call self._mark_step_success(state, result_dict)
        pass

    except Exception as e:
        logger.error(f"[STEP_NAME] Failed: {str(e)}")
        raise
```

### Key Methods in `BaseFoundationStep`:

| Method                              | Purpose                           |
| ----------------------------------- | --------------------------------- |
| `_mark_step_success(state, result)` | Mark step completed, store result |
| `_mark_step_skipped(state, reason)` | Skip step with reason             |
| `_handle_error(state, exception)`   | Handle and record failure         |
| `_is_step_execution_allowed(state)` | Override to add skip conditions   |

---

## 📝 State Fields

Update these in your step's `execute_step()`:

| Field               | Type   | Updated By             |
| ------------------- | ------ | ---------------------- |
| `repo_info`         | `Dict` | `repo_creation`        |
| `database_info`     | `Dict` | `database_creation`    |
| `kubemanifest_info` | `Dict` | `kubemanifest`         |
| `spinnaker_info`    | `Dict` | `spinnaker_pipeline`   |
| `kafka_info`        | `Dict` | `consumer_topic_setup` |
| `edge_info`         | `Dict` | `edge_onboarding`      |
| `authz_info`        | `Dict` | `authz_onboarding`     |
| `monitoring_info`   | `Dict` | `monitoring_setup`     |

---

## ✅ Checklist for Adding a New Step

1. **Create step file** in `steps/` extending `BaseFoundationStep`
2. **Implement `execute_step()`** with your business logic
3. **Override `_is_step_execution_allowed()`** if step can be skipped
4. **Export in `steps/__init__.py`**
5. **Add node in `workflow.py`** with proper edges
6. **Add state field** in `state.py` if step produces output
7. **Add Pydantic model** in `models.py` for input validation
