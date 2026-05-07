---
name: LangGraph Workflows
description: Design and implement complex state machine workflows using LangGraph for SDLC automation
version: 1.0.0
---

## Overview

This skill covers the design, implementation, and optimization of LangGraph state machine workflows for complex software development lifecycle automation tasks. LangGraph enables building robust, stateful workflows with conditional logic, error handling, and parallel execution.

**When to Use This Skill:**
- Designing multi-step development workflows
- Implementing conditional branching based on results
- Creating resumable workflows with checkpoints
- Orchestrating parallel task execution
- Building complex SDLC automation pipelines

## Core Concepts

### LangGraph Fundamentals

#### State Graphs
LangGraph workflows are built using `StateGraph`, which manages state transitions between nodes:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List

# Define state schema
class WorkflowState(TypedDict):
    task_id: str
    input: str
    analysis: str | None
    plan: dict | None
    implementation: dict | None
    test_results: dict | None
    errors: List[str]
    retry_count: int

# Create graph
workflow = StateGraph(WorkflowState)
```

#### Nodes
Nodes are functions that process state and return updated state:

```python
async def analyze_node(state: WorkflowState) -> WorkflowState:
    """Analyze requirements and update state"""
    analysis_result = await perform_analysis(state["input"])

    return {
        **state,
        "analysis": analysis_result
    }

# Add node to workflow
workflow.add_node("analyze", analyze_node)
```

#### Edges
Edges define transitions between nodes:

```python
# Simple edge: always goes to next node
workflow.add_edge("analyze", "plan")

# Conditional edge: route based on logic
def should_retry(state: WorkflowState) -> str:
    if state["retry_count"] >= 3:
        return "fail"
    elif state["test_results"]["passed"]:
        return "success"
    else:
        return "retry"

workflow.add_conditional_edges(
    "test",
    should_retry,
    {
        "retry": "implement",
        "success": "finalize",
        "fail": "error_handler"
    }
)
```

## Workflow Patterns

### Pattern 1: Linear Workflow

Sequential execution with clear stages:

```python
from langgraph.graph import StateGraph, END

class LinearWorkflowState(TypedDict):
    step: int
    data: dict
    results: List[dict]

async def step_1(state: LinearWorkflowState) -> LinearWorkflowState:
    result = await process_step_1(state["data"])
    return {
        **state,
        "step": 1,
        "results": state["results"] + [{"step": 1, "result": result}]
    }

async def step_2(state: LinearWorkflowState) -> LinearWorkflowState:
    result = await process_step_2(state["results"][-1])
    return {
        **state,
        "step": 2,
        "results": state["results"] + [{"step": 2, "result": result}]
    }

async def step_3(state: LinearWorkflowState) -> LinearWorkflowState:
    result = await process_step_3(state["results"][-1])
    return {
        **state,
        "step": 3,
        "results": state["results"] + [{"step": 3, "result": result}]
    }

# Build workflow
workflow = StateGraph(LinearWorkflowState)
workflow.add_node("step_1", step_1)
workflow.add_node("step_2", step_2)
workflow.add_node("step_3", step_3)

workflow.set_entry_point("step_1")
workflow.add_edge("step_1", "step_2")
workflow.add_edge("step_2", "step_3")
workflow.add_edge("step_3", END)

app = workflow.compile()
```

### Pattern 2: Branching Workflow

Conditional execution paths:

```python
class BranchingState(TypedDict):
    task_type: str
    complexity: str
    result: dict | None

async def analyze_task(state: BranchingState) -> BranchingState:
    complexity = await determine_complexity(state["task_type"])
    return {
        **state,
        "complexity": complexity
    }

async def simple_implementation(state: BranchingState) -> BranchingState:
    result = await implement_simple(state)
    return {**state, "result": result}

async def complex_implementation(state: BranchingState) -> BranchingState:
    result = await implement_complex(state)
    return {**state, "result": result}

def route_by_complexity(state: BranchingState) -> str:
    """Route to appropriate implementation based on complexity"""
    if state["complexity"] == "simple":
        return "simple_impl"
    else:
        return "complex_impl"

# Build workflow
workflow = StateGraph(BranchingState)
workflow.add_node("analyze", analyze_task)
workflow.add_node("simple_impl", simple_implementation)
workflow.add_node("complex_impl", complex_implementation)

workflow.set_entry_point("analyze")
workflow.add_conditional_edges(
    "analyze",
    route_by_complexity,
    {
        "simple_impl": "simple_impl",
        "complex_impl": "complex_impl"
    }
)
workflow.add_edge("simple_impl", END)
workflow.add_edge("complex_impl", END)

app = workflow.compile()
```

### Pattern 3: Loop/Retry Workflow

Implement retry logic with loop detection:

```python
class RetryState(TypedDict):
    input: str
    attempt: int
    max_attempts: int
    result: dict | None
    success: bool
    error: str | None

async def execute_operation(state: RetryState) -> RetryState:
    """Execute operation with error handling"""
    try:
        result = await perform_operation(state["input"])
        return {
            **state,
            "result": result,
            "success": True,
            "attempt": state["attempt"] + 1
        }
    except Exception as e:
        return {
            **state,
            "success": False,
            "error": str(e),
            "attempt": state["attempt"] + 1
        }

def should_retry(state: RetryState) -> str:
    """Determine if we should retry"""
    if state["success"]:
        return "success"
    elif state["attempt"] >= state["max_attempts"]:
        return "failed"
    else:
        return "retry"

# Build workflow
workflow = StateGraph(RetryState)
workflow.add_node("execute", execute_operation)

workflow.set_entry_point("execute")
workflow.add_conditional_edges(
    "execute",
    should_retry,
    {
        "retry": "execute",  # Loop back to execute
        "success": END,
        "failed": END
    }
)

app = workflow.compile()
```

### Pattern 4: Parallel Execution Workflow

Execute multiple operations concurrently:

```python
class ParallelState(TypedDict):
    input: str
    task_a_result: dict | None
    task_b_result: dict | None
    task_c_result: dict | None
    combined_result: dict | None

async def task_a(state: ParallelState) -> ParallelState:
    result = await execute_task_a(state["input"])
    return {**state, "task_a_result": result}

async def task_b(state: ParallelState) -> ParallelState:
    result = await execute_task_b(state["input"])
    return {**state, "task_b_result": result}

async def task_c(state: ParallelState) -> ParallelState:
    result = await execute_task_c(state["input"])
    return {**state, "task_c_result": result}

async def combine_results(state: ParallelState) -> ParallelState:
    combined = await merge_results(
        state["task_a_result"],
        state["task_b_result"],
        state["task_c_result"]
    )
    return {**state, "combined_result": combined}

# Build workflow with parallel execution
workflow = StateGraph(ParallelState)
workflow.add_node("task_a", task_a)
workflow.add_node("task_b", task_b)
workflow.add_node("task_c", task_c)
workflow.add_node("combine", combine_results)

# Fan-out: All three tasks start from entry point
workflow.set_entry_point("task_a")
workflow.set_entry_point("task_b")
workflow.set_entry_point("task_c")

# Fan-in: All tasks feed into combine
workflow.add_edge("task_a", "combine")
workflow.add_edge("task_b", "combine")
workflow.add_edge("task_c", "combine")
workflow.add_edge("combine", END)

app = workflow.compile()
```

### Pattern 5: Human-in-the-Loop Workflow

Workflows that require human approval:

```python
class HumanLoopState(TypedDict):
    plan: dict | None
    approval_status: str | None  # "pending", "approved", "rejected"
    implementation: dict | None
    feedback: str | None

async def create_plan(state: HumanLoopState) -> HumanLoopState:
    plan = await generate_plan(state)
    return {
        **state,
        "plan": plan,
        "approval_status": "pending"
    }

async def wait_for_approval(state: HumanLoopState) -> HumanLoopState:
    """Wait for human approval (would integrate with UI)"""
    approval = await request_human_approval(state["plan"])
    return {
        **state,
        "approval_status": approval["status"],
        "feedback": approval.get("feedback")
    }

async def implement_plan(state: HumanLoopState) -> HumanLoopState:
    implementation = await execute_implementation(state["plan"])
    return {**state, "implementation": implementation}

async def revise_plan(state: HumanLoopState) -> HumanLoopState:
    revised_plan = await revise_based_on_feedback(
        state["plan"],
        state["feedback"]
    )
    return {
        **state,
        "plan": revised_plan,
        "approval_status": "pending"
    }

def check_approval(state: HumanLoopState) -> str:
    if state["approval_status"] == "approved":
        return "implement"
    else:
        return "revise"

# Build workflow
workflow = StateGraph(HumanLoopState)
workflow.add_node("plan", create_plan)
workflow.add_node("approval", wait_for_approval)
workflow.add_node("implement", implement_plan)
workflow.add_node("revise", revise_plan)

workflow.set_entry_point("plan")
workflow.add_edge("plan", "approval")
workflow.add_conditional_edges(
    "approval",
    check_approval,
    {
        "implement": "implement",
        "revise": "revise"
    }
)
workflow.add_edge("revise", "approval")  # Loop back for re-approval
workflow.add_edge("implement", END)

app = workflow.compile()
```

## Complete SDLC Workflow Example

### Feature Implementation Workflow

```python
class FeatureWorkflowState(TypedDict):
    # Input
    feature_description: str
    repository_path: str

    # Analysis phase
    requirements: dict | None
    affected_files: List[str]
    complexity_score: int

    # Planning phase
    implementation_plan: dict | None
    test_plan: dict | None

    # Implementation phase
    code_changes: dict | None
    tests_written: bool

    # Verification phase
    test_results: dict | None
    all_tests_passed: bool

    # Finalization
    pr_created: bool
    pr_url: str | None

    # Error handling
    errors: List[str]
    retry_count: int

# Analysis nodes
async def analyze_requirements(state: FeatureWorkflowState) -> FeatureWorkflowState:
    requirements = await extract_requirements(state["feature_description"])
    affected_files = await identify_affected_files(requirements, state["repository_path"])
    complexity = await calculate_complexity(requirements, affected_files)

    return {
        **state,
        "requirements": requirements,
        "affected_files": affected_files,
        "complexity_score": complexity
    }

# Planning nodes
async def create_implementation_plan(state: FeatureWorkflowState) -> FeatureWorkflowState:
    plan = await generate_implementation_plan(
        requirements=state["requirements"],
        affected_files=state["affected_files"],
        complexity=state["complexity_score"]
    )
    return {**state, "implementation_plan": plan}

async def create_test_plan(state: FeatureWorkflowState) -> FeatureWorkflowState:
    test_plan = await generate_test_plan(
        requirements=state["requirements"],
        implementation_plan=state["implementation_plan"]
    )
    return {**state, "test_plan": test_plan}

# Implementation nodes
async def implement_code(state: FeatureWorkflowState) -> FeatureWorkflowState:
    try:
        changes = await execute_implementation(
            plan=state["implementation_plan"],
            repository_path=state["repository_path"]
        )
        return {
            **state,
            "code_changes": changes,
            "errors": state.get("errors", [])
        }
    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [str(e)],
            "retry_count": state.get("retry_count", 0) + 1
        }

async def write_tests(state: FeatureWorkflowState) -> FeatureWorkflowState:
    await create_tests(
        test_plan=state["test_plan"],
        code_changes=state["code_changes"],
        repository_path=state["repository_path"]
    )
    return {**state, "tests_written": True}

# Verification nodes
async def run_tests(state: FeatureWorkflowState) -> FeatureWorkflowState:
    test_results = await execute_tests(state["repository_path"])
    return {
        **state,
        "test_results": test_results,
        "all_tests_passed": test_results["passed"] == test_results["total"]
    }

# Finalization nodes
async def create_pull_request(state: FeatureWorkflowState) -> FeatureWorkflowState:
    pr = await create_pr(
        title=f"Feature: {state['feature_description'][:50]}",
        body=generate_pr_body(state),
        changes=state["code_changes"]
    )
    return {
        **state,
        "pr_created": True,
        "pr_url": pr["url"]
    }

# Conditional routing
def should_retry_implementation(state: FeatureWorkflowState) -> str:
    if state.get("errors") and state.get("retry_count", 0) < 3:
        return "retry"
    elif state.get("errors"):
        return "fail"
    else:
        return "continue"

def tests_passed_check(state: FeatureWorkflowState) -> str:
    if state["all_tests_passed"]:
        return "create_pr"
    elif state.get("retry_count", 0) < 2:
        return "retry_implementation"
    else:
        return "fail"

# Build complete workflow
workflow = StateGraph(FeatureWorkflowState)

# Add all nodes
workflow.add_node("analyze", analyze_requirements)
workflow.add_node("plan_implementation", create_implementation_plan)
workflow.add_node("plan_tests", create_test_plan)
workflow.add_node("implement", implement_code)
workflow.add_node("write_tests", write_tests)
workflow.add_node("run_tests", run_tests)
workflow.add_node("create_pr", create_pull_request)

# Define flow
workflow.set_entry_point("analyze")
workflow.add_edge("analyze", "plan_implementation")
workflow.add_edge("plan_implementation", "plan_tests")

workflow.add_conditional_edges(
    "plan_tests",
    lambda s: "implement",
    {"implement": "implement"}
)

workflow.add_conditional_edges(
    "implement",
    should_retry_implementation,
    {
        "retry": "plan_implementation",
        "continue": "write_tests",
        "fail": END
    }
)

workflow.add_edge("write_tests", "run_tests")

workflow.add_conditional_edges(
    "run_tests",
    tests_passed_check,
    {
        "create_pr": "create_pr",
        "retry_implementation": "implement",
        "fail": END
    }
)

workflow.add_edge("create_pr", END)

# Compile workflow
feature_workflow_app = workflow.compile()

# Execute
result = await feature_workflow_app.ainvoke({
    "feature_description": "Add user authentication middleware",
    "repository_path": "/path/to/repo",
    "errors": [],
    "retry_count": 0
})
```

## Advanced Techniques

### Checkpointing and Persistence

```python
from langgraph.checkpoint import MemorySaver

# Add checkpoint support
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# Execute with checkpoints
config = {"configurable": {"thread_id": f"task-{task_id}"}}
result = await app.ainvoke(initial_state, config=config)

# Resume from checkpoint
result = await app.ainvoke(None, config=config)  # Continues from last checkpoint
```

### Streaming Output

```python
# Stream workflow execution
async for event in app.astream(initial_state):
    node_name = event["node"]
    output = event["output"]
    logger.info(f"Node {node_name} completed: {output}")
```

### Error Handling

```python
class ErrorHandlingState(TypedDict):
    data: str
    result: dict | None
    error: str | None
    error_recovery_attempted: bool

async def error_handler(state: ErrorHandlingState) -> ErrorHandlingState:
    """Handle errors and attempt recovery"""
    recovery_result = await attempt_error_recovery(state["error"])

    if recovery_result["recovered"]:
        return {
            **state,
            "error": None,
            "error_recovery_attempted": True,
            "result": recovery_result["data"]
        }
    else:
        return {
            **state,
            "error_recovery_attempted": True
        }
```

## Best Practices

1. **Clear State Schema**: Define comprehensive TypedDict with all possible state fields
2. **Immutable Updates**: Always return new state dict, don't mutate existing state
3. **Error Fields**: Include error tracking in state schema
4. **Logging**: Log state transitions and decisions
5. **Testing**: Test each node function independently
6. **Visualization**: Use LangGraph visualization tools to debug workflows
7. **Checkpoints**: Use checkpointing for long-running workflows
8. **Timeout Handling**: Implement timeouts for nodes that might hang

## Integration with SWE Agent

```python
# In src/services/workflow_service.py
class WorkflowService:
    async def execute_feature_workflow(self, task: Task) -> TaskResult:
        """Execute feature implementation workflow"""

        initial_state = {
            "feature_description": task.description,
            "repository_path": task.workspace_path,
            "errors": [],
            "retry_count": 0
        }

        app = self.build_feature_workflow()

        result = await app.ainvoke(initial_state)

        return TaskResult(
            task_id=task.id,
            success=result.get("pr_created", False),
            data=result
        )
```

## Reference

- LangGraph documentation: https://langchain-ai.github.io/langgraph/
- Workflow examples: `src/services/workflows/`
- State definitions: `src/models/workflow_state.py`
- Project patterns: `.claude/context/memory/patterns.md`
