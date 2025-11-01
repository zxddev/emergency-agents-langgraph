# LangGraph

LangGraph is a low-level orchestration framework for building, managing, and deploying long-running, stateful AI agents on top of LangChain components.

## Description

LangGraph gives you fine-grained control over agent state, routing, and lifecycle while integrating with the LangChain ecosystem. It is designed for production use cases that need durable execution, human review, multi-agent coordination, and strong observability.

**Repository:** [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
**Language:** Python core with extensive Jupyter-based examples and docs
**Stars:** ≈20k (GitHub)
**License:** MIT
**Homepage:** https://langchain-ai.github.io/langgraph/
**Latest Commit:** a6dde39 (2025-10-30)

### Language Mix (local scan)
- **Jupyter:** ~66%
- **Python:** ~21%
- **Markdown:** ~11%
- **JSON / YAML / TOML:** remainder

## When to Use This Skill

Use this skill when you need to:
- Design stateful LLM agents or workflows that must resume safely after failures or human review.
- Combine LangChain tools with durable storage, routing, and multi-agent coordination primitives.
- Add human-in-the-loop approval steps, streaming responses, or persistent memory to production agent apps.
- Understand the LangGraph API surface, configuration options, and deployment patterns.

## Quick Reference

### Installation
```bash
pip install -U langgraph
```

### Prebuilt ReAct Agent
```python
from langgraph.prebuilt import create_react_agent

def get_weather(city: str) -> str:
    return f"It's always sunny in {city}!"

agent = create_react_agent(
    model="anthropic:claude-3-7-sonnet-latest",
    tools=[get_weather],
    prompt="You are a helpful assistant",
)

agent.invoke({"messages": [{"role": "user", "content": "weather in sf"}]})
```

### Build a Custom StateGraph with Durable Execution
```python
import uuid
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver

class ChatState(TypedDict):
    messages: Annotated[list, add_messages]

def chatbot(state: ChatState):
    last = state["messages"][-1]["content"]
    return {"messages": [{"role": "assistant", "content": f"Echo: {last}"}]}

builder = StateGraph(ChatState)
builder.add_node("chatbot", chatbot)
builder.add_edge(START, "chatbot")
builder.add_edge("chatbot", END)

checkpointer = InMemorySaver()
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
graph = builder.compile(checkpointer=checkpointer)

for event in graph.stream(
    {"messages": [{"role": "user", "content": "hello"}]},
    config=config,
    durability="sync",
):
    print(event)
```

### Human-in-the-Loop Interrupt Pattern
```python
import uuid
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt

class ReviewState(TypedDict):
    messages: Annotated[list, add_messages]

def review(state: ReviewState):
    value = interrupt({"text_to_revise": state["messages"][-1]["content"]})
    return {"messages": [value]}

builder = StateGraph(ReviewState)
builder.add_node("human_review", review)
builder.add_edge(START, "human_review")

graph = builder.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": uuid.uuid4()}}
result = graph.invoke({"messages": [{"role": "user", "content": "draft email"}]}, config)

# Later, resume with human feedback
graph.invoke(Command(resume={"role": "assistant", "content": "Edited email"}), config)
```

### Persist Checkpoints in SQLite
```python
from langgraph.checkpoint.sqlite import SqliteSaver

# Reuse `builder` / `ChatState` from the custom graph example above
with SqliteSaver.from_conn_string("checkpoints.sqlite") as saver:
    graph = builder.compile(checkpointer=saver)
    config = {"configurable": {"thread_id": "customer-123"}}
    graph.invoke(
        {"messages": [{"role": "user", "content": "store this"}]},
        config,
    )
```

### Deploy via LangGraph Cloud CLI
```bash
pip install -U langgraph-cli
langgraph login
langgraph deploy --project my-agent --graph path/to/app.py
```

## Available References

- `references/README.md` – LangGraph overview, core benefits, and ecosystem links.
- `references/tutorial-build-basic-chatbot.md` – Step-by-step tutorial for constructing a chatbot with StateGraph.
- `references/concept-durable-execution.md` – Durable execution requirements, durability modes, and best practices.
- `references/concept-human-in-the-loop.md` – Patterns and guidance for pausing graphs for manual review.
- `references/concept-memory.md` – Memory architecture, reducers, and strategies for long-term persistence.
- `references/reference-graphs.md` – API reference for graph primitives, nodes, edges, and reducers.

## Working with This Skill

- **Beginner:** Start with the basic chatbot tutorial, using in-memory checkpointers and LangSmith visualization to understand state updates.
- **Intermediate:** Add persistence, branching, and tool integrations; experiment with `durability` modes, thread IDs, and resume flows.
- **Advanced:** Design multi-agent or distributed workflows, plug in external stores/checkpointers, and integrate human-in-the-loop review or LangGraph Cloud deployment pipelines.

## Key Concepts

- **StateGraph & Reducers:** Typed state plus reducer functions control how updates merge across nodes and threads.
- **Durable Execution:** Checkpointers and durability policies (`exit`, `async`, `sync`) ensure resumable, long-running workflows.
- **Human Interrupts:** `interrupt`, `Command`, and breakpoints pause execution for manual review, editing, or approval.
- **Memory & Persistence:** Pair checkpoints with stores to persist long-term context across user sessions.
- **Deployment & Observability:** Works with LangSmith, LangGraph Cloud, and self-hosted control/data planes for production rollouts.

---

**Generated manually using Skill Seeker workflow (git clone + LangGraph docs).**
