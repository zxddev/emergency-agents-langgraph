# Langgraph - Concepts

**Pages:** 26

---

## Subgraphs¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/subgraphs/

**Contents:**
- Subgraphs¶

A subgraph is a graph that is used as a node in another graph — this is the concept of encapsulation applied to LangGraph. Subgraphs allow you to build complex systems with multiple components that are themselves graphs.

Some reasons for using subgraphs are:

The main question when adding subgraphs is how the parent graph and subgraph communicate, i.e. how they pass the state between each other during the graph execution. There are two scenarios:

**Examples:**

Example 1 (python):
```python
from langgraph.graph import StateGraph, MessagesState, START

# Subgraph

def call_model(state: MessagesState):
    response = model.invoke(state["messages"])
    return {"messages": response}

subgraph_builder = StateGraph(State)
subgraph_builder.add_node(call_model)
...
subgraph = subgraph_builder.compile()

# Parent graph

builder = StateGraph(State)
builder.add_node("subgraph_node", subgraph)
builder.add_edge(START, "subgraph_node")
graph = builder.compile()
...
graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
```

Example 2 (python):
```python
from typing_extensions import TypedDict, Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.graph.message import add_messages

class SubgraphMessagesState(TypedDict):
    subgraph_messages: Annotated[list[AnyMessage], add_messages]

# Subgraph

def call_model(state: SubgraphMessagesState):
    response = model.invoke(state["subgraph_messages"])
    return {"subgraph_messages": response}

subgraph_builder = StateGraph(SubgraphMessagesState)
subgraph_builder.add_node("call_model_from_subgraph", call_model)
subgraph_builder.add_edge(START, "call_model_from_subgraph")
...
subgraph = subgraph_builder.compile()

# Parent graph

def call_subgraph(state: MessagesState):
    response = subgraph.invoke({"subgraph_messages": state["messages"]})
    return {"messages": response["subgraph_messages"]}

builder = StateGraph(State)
builder.add_node("subgraph_node", call_subgraph)
builder.add_edge(START, "subgraph_node")
graph = builder.compile()
...
graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
```

---

## Durable Execution¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/durable_execution/

**Contents:**
- Durable Execution¶
- Requirements¶
- Determinism and Consistent Replay¶
- Durability modes¶
  - "exit"¶
  - "async"¶
  - "sync"¶
- Using tasks in nodes¶
- Resuming Workflows¶
- Starting Points for Resuming Workflows¶

Durable execution is a technique in which a process or workflow saves its progress at key points, allowing it to pause and later resume exactly where it left off. This is particularly useful in scenarios that require human-in-the-loop, where users can inspect, validate, or modify the process before continuing, and in long-running tasks that might encounter interruptions or errors (e.g., calls to an LLM timing out). By preserving completed work, durable execution enables a process to resume without reprocessing previous steps -- even after a significant delay (e.g., a week later).

LangGraph's built-in persistence layer provides durable execution for workflows, ensuring that the state of each execution step is saved to a durable store. This capability guarantees that if a workflow is interrupted -- whether by a system failure or for human-in-the-loop interactions -- it can be resumed from its last recorded state.

If you are using LangGraph with a checkpointer, you already have durable execution enabled. You can pause and resume workflows at any point, even after interruptions or failures. To make the most of durable execution, ensure that your workflow is designed to be deterministic and idempotent and wrap any side effects or non-deterministic operations inside tasks. You can use tasks from both the StateGraph (Graph API) and the Functional API.

To leverage durable execution in LangGraph, you need to:

Specify a thread identifier when executing a workflow. This will track the execution history for a particular instance of the workflow.

Wrap any non-deterministic operations (e.g., random number generation) or operations with side effects (e.g., file writes, API calls) inside tasks to ensure that when a workflow is resumed, these operations are not repeated for the particular run, and instead their results are retrieved from the persistence layer. For more information, see Determinism and Consistent Replay.

When you resume a workflow run, the code does NOT resume from the same line of code where execution stopped; instead, it will identify an appropriate starting point from which to pick up where it left off. This means that the workflow will replay all steps from the starting point until it reaches the point where it was stopped.

As a result, when you are writing a workflow for durable execution, you must wrap any non-deterministic operations (e.g., random number generation) and any operations with side effects (e.g., file writes, API calls) inside tasks or nodes.

To ensure that your workflow is deterministic and can be consistently replayed, follow these guidelines:

For some examples of pitfalls to avoid, see the Common Pitfalls section in the functional API, which shows how to structure your code using tasks to avoid these issues. The same principles apply to the StateGraph (Graph API).

LangGraph supports three durability modes that allow you to balance performance and data consistency based on your application's requirements. The durability modes, from least to most durable, are as follows:

A higher durability mode add more overhead to the workflow execution.

Added in version 0.6.0

Use the durability parameter instead of checkpoint_during (deprecated in v0.6.0) for persistence policy management:

for persistence policy management, with the following mapping:

Changes are persisted only when graph execution completes (either successfully or with an error). This provides the best performance for long-running graphs but means intermediate state is not saved, so you cannot recover from mid-execution failures or interrupt the graph execution.

Changes are persisted asynchronously while the next step executes. This provides good performance and durability, but there's a small risk that checkpoints might not be written if the process crashes during execution.

Changes are persisted synchronously before the next step starts. This ensures that every checkpoint is written before continuing execution, providing high durability at the cost of some performance overhead.

You can specify the durability mode when calling any graph execution method:

If a node contains multiple operations, you may find it easier to convert each operation into a task rather than refactor the operations into individual nodes.

Once you have enabled durable execution in your workflow, you can resume execution for the following scenarios:

**Examples:**

Example 1 (unknown):
```unknown
graph.stream(
    {"input": "test"}, 
    durability="sync"
)
```

Example 2 (python):
```python
from typing import NotRequired
from typing_extensions import TypedDict
import uuid

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
import requests

# Define a TypedDict to represent the state
class State(TypedDict):
    url: str
    result: NotRequired[str]

def call_api(state: State):
    """Example node that makes an API request."""
    result = requests.get(state['url']).text[:100]  # Side-effect
    return {
        "result": result
    }

# Create a StateGraph builder and add a node for the call_api function
builder = StateGraph(State)
builder.add_node("call_api", call_api)

# Connect the start and end nodes to the call_api node
builder.add_edge(START, "call_api")
builder.add_edge("call_api", END)

# Specify a checkpointer
checkpointer = InMemorySaver()

# Compile the graph with the checkpointer
graph = builder.compile(checkpointer=checkpointer)

# Define a config with a thread ID.
thread_id = uuid.uuid4()
config = {"configurable": {"thread_id": thread_id}}

# Invoke the graph
graph.invoke({"url": "https://www.example.com"}, config)
```

Example 3 (python):
```python
from typing import NotRequired
from typing_extensions import TypedDict
import uuid

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import task
from langgraph.graph import StateGraph, START, END
import requests

# Define a TypedDict to represent the state
class State(TypedDict):
    urls: list[str]
    result: NotRequired[list[str]]


@task
def _make_request(url: str):
    """Make a request."""
    return requests.get(url).text[:100]

def call_api(state: State):
    """Example node that makes an API request."""
    requests = [_make_request(url) for url in state['urls']]
    results = [request.result() for request in requests]
    return {
        "results": results
    }

# Create a StateGraph builder and add a node for the call_api function
builder = StateGraph(State)
builder.add_node("call_api", call_api)

# Connect the start and end nodes to the call_api node
builder.add_edge(START, "call_api")
builder.add_edge("call_api", END)

# Specify a checkpointer
checkpointer = InMemorySaver()

# Compile the graph with the checkpointer
graph = builder.compile(checkpointer=checkpointer)

# Define a config with a thread ID.
thread_id = uuid.uuid4()
config = {"configurable": {"thread_id": thread_id}}

# Invoke the graph
graph.invoke({"urls": ["https://www.example.com"]}, config)
```

---

## Multi-agent systems¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/multi_agent

**Contents:**
- Multi-agent systems¶
- Multi-agent architectures¶
  - Handoffs¶
    - Handoffs as tools¶
  - Network¶
  - Supervisor¶
  - Supervisor (tool-calling)¶
  - Hierarchical¶
  - Custom multi-agent workflow¶
- Communication and state management¶

An agent is a system that uses an LLM to decide the control flow of an application. As you develop these systems, they might grow more complex over time, making them harder to manage and scale. For example, you might run into the following problems:

To tackle these, you might consider breaking your application into multiple smaller, independent agents and composing them into a multi-agent system. These independent agents can be as simple as a prompt and an LLM call, or as complex as a ReAct agent (and more!).

The primary benefits of using multi-agent systems are:

There are several ways to connect agents in a multi-agent system:

In multi-agent architectures, agents can be represented as graph nodes. Each agent node executes its step(s) and decides whether to finish execution or route to another agent, including potentially routing to itself (e.g., running in a loop). A common pattern in multi-agent interactions is handoffs, where one agent hands off control to another. Handoffs allow you to specify:

To implement handoffs in LangGraph, agent nodes can return Command object that allows you to combine both control flow and state updates:

In a more complex scenario where each agent node is itself a graph (i.e., a subgraph), a node in one of the agent subgraphs might want to navigate to a different agent. For example, if you have two agents, alice and bob (subgraph nodes in a parent graph), and alice needs to navigate to bob, you can set graph=Command.PARENT in the Command object:

If you need to support visualization for subgraphs communicating using Command(graph=Command.PARENT) you would need to wrap them in a node function with Command annotation: Instead of this:

you would need to do this:

One of the most common agent types is a tool-calling agent. For those types of agents, a common pattern is wrapping a handoff in a tool call:

This is a special case of updating the graph state from tools where, in addition to the state update, the control flow is included as well.

If you want to use tools that return Command, you can use the prebuilt create_react_agent / ToolNode components, or else implement your own logic:

Let's now take a closer look at the different multi-agent architectures.

In this architecture, agents are defined as graph nodes. Each agent can communicate with every other agent (many-to-many connections) and can decide which agent to call next. This architecture is good for problems that do not have a clear hierarchy of agents or a specific sequence in which agents should be called.

API Reference: ChatOpenAI | Command | StateGraph | START | END

In this architecture, we define agents as nodes and add a supervisor node (LLM) that decides which agent nodes should be called next. We use Command to route execution to the appropriate agent node based on supervisor's decision. This architecture also lends itself well to running multiple agents in parallel or using map-reduce pattern.

API Reference: ChatOpenAI | Command | StateGraph | START | END

Check out this tutorial for an example of supervisor multi-agent architecture.

In this variant of the supervisor architecture, we define a supervisor agent which is responsible for calling sub-agents. The sub-agents are exposed to the supervisor as tools, and the supervisor agent decides which tool to call next. The supervisor agent follows a standard implementation as an LLM running in a while loop calling tools until it decides to stop.

API Reference: ChatOpenAI | InjectedState | create_react_agent

As you add more agents to your system, it might become too hard for the supervisor to manage all of them. The supervisor might start making poor decisions about which agent to call next, or the context might become too complex for a single supervisor to keep track of. In other words, you end up with the same problems that motivated the multi-agent architecture in the first place.

To address this, you can design your system hierarchically. For example, you can create separate, specialized teams of agents managed by individual supervisors, and a top-level supervisor to manage the teams.

API Reference: ChatOpenAI | StateGraph | START | END | Command

In this architecture we add individual agents as graph nodes and define the order in which agents are called ahead of time, in a custom workflow. In LangGraph the workflow can be defined in two ways:

Explicit control flow (normal edges): LangGraph allows you to explicitly define the control flow of your application (i.e. the sequence of how agents communicate) explicitly, via normal graph edges. This is the most deterministic variant of this architecture above — we always know which agent will be called next ahead of time.

Dynamic control flow (Command): in LangGraph you can allow LLMs to decide parts of your application control flow. This can be achieved by using Command. A special case of this is a supervisor tool-calling architecture. In that case, the tool-calling LLM powering the supervisor agent will make decisions about the order in which the tools (agents) are being called.

API Reference: ChatOpenAI | StateGraph | START

The most important thing when building multi-agent systems is figuring out how the agents communicate.

A common, generic way for agents to communicate is via a list of messages. This opens up the following questions:

Additionally, if you are dealing with more complex agents or wish to keep individual agent state separate from the multi-agent system state, you may need to use different state schemas.

What is the "payload" that is being passed around between agents? In most of the architectures discussed above, the agents communicate via handoffs and pass the graph state as part of the handoff payload. Specifically, agents pass around lists of messages as part of the graph state. In the case of the supervisor with tool-calling, the payloads are tool call arguments.

The most common way for agents to communicate is via a shared state channel, typically a list of messages. This assumes that there is always at least a single channel (key) in the state that is shared by the agents (e.g., messages). When communicating via a shared message list, there is an additional consideration: should the agents share the full history of their thought process or only the final result?

Agents can share the full history of their thought process (i.e., "scratchpad") with all other agents. This "scratchpad" would typically look like a list of messages. The benefit of sharing the full thought process is that it might help other agents make better decisions and improve reasoning ability for the system as a whole. The downside is that as the number of agents and their complexity grows, the "scratchpad" will grow quickly and might require additional strategies for memory management.

Agents can have their own private "scratchpad" and only share the final result with the rest of the agents. This approach might work better for systems with many agents or agents that are more complex. In this case, you would need to define agents with different state schemas.

For agents called as tools, the supervisor determines the inputs based on the tool schema. Additionally, LangGraph allows passing state to individual tools at runtime, so subordinate agents can access parent state, if needed.

It can be helpful to indicate which agent a particular AI message is from, especially for long message histories. Some LLM providers (like OpenAI) support adding a name parameter to messages — you can use that to attach the agent name to the message. If that is not supported, you can consider manually injecting the agent name into the message content, e.g., <agent>alice</agent><message>message from alice</message>.

Handoffs are typically done via the LLM calling a dedicated handoff tool. This is represented as an AI message with tool calls that is passed to the next agent (LLM). Most LLM providers don't support receiving AI messages with tool calls without corresponding tool messages.

You therefore have two options:

In practice, we see that most developers opt for option (1).

A common practice is to have multiple agents communicating on a shared message list, but only adding their final messages to the list. This means that any intermediate messages (e.g., tool calls) are not saved in this list.

What if you do want to save these messages so that if this particular subagent is invoked in the future you can pass those back in?

There are two high-level approaches to achieve that:

An agent might need to have a different state schema from the rest of the agents. For example, a search agent might only need to keep track of queries and retrieved documents. There are two ways to achieve this in LangGraph:

**Examples:**

Example 1 (python):
```python
def agent(state) -> Command[Literal["agent", "another_agent"]]:
    # the condition for routing/halting can be anything, e.g. LLM tool call / structured output, etc.
    goto = get_next_agent(...)  # 'agent' / 'another_agent'
    return Command(
        # Specify which agent to call next
        goto=goto,
        # Update the graph state
        update={"my_state_key": "my_state_value"}
    )
```

Example 2 (python):
```python
def some_node_inside_alice(state):
    return Command(
        goto="bob",
        update={"my_state_key": "my_state_value"},
        # specify which graph to navigate to (defaults to the current graph)
        graph=Command.PARENT,
    )
```

Example 3 (unknown):
```unknown
builder.add_node(alice)
```

Example 4 (python):
```python
def call_alice(state) -> Command[Literal["bob"]]:
    return alice.invoke(state)

builder.add_node("alice", call_alice)
```

---

## Agent architectures¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/agentic_concepts/

**Contents:**
- Agent architectures¶
- Router¶
  - Structured Output¶
- Tool-calling agent¶
  - Tool calling¶
  - Memory¶
  - Planning¶
- Custom agent architectures¶
  - Human-in-the-loop¶
  - Parallelization¶

Many LLM applications implement a particular control flow of steps before and / or after LLM calls. As an example, RAG performs retrieval of documents relevant to a user question, and passes those documents to an LLM in order to ground the model's response in the provided document context.

Instead of hard-coding a fixed control flow, we sometimes want LLM systems that can pick their own control flow to solve more complex problems! This is one definition of an agent: an agent is a system that uses an LLM to decide the control flow of an application. There are many ways that an LLM can control application:

As a result, there are many different types of agent architectures, which give an LLM varying levels of control.

A router allows an LLM to select a single step from a specified set of options. This is an agent architecture that exhibits a relatively limited level of control because the LLM usually focuses on making a single decision and produces a specific output from a limited set of pre-defined options. Routers typically employ a few different concepts to achieve this.

Structured outputs with LLMs work by providing a specific format or schema that the LLM should follow in its response. This is similar to tool calling, but more general. While tool calling typically involves selecting and using predefined functions, structured outputs can be used for any type of formatted response. Common methods to achieve structured outputs include:

Structured outputs are crucial for routing as they ensure the LLM's decision can be reliably interpreted and acted upon by the system. Learn more about structured outputs in this how-to guide.

While a router allows an LLM to make a single decision, more complex agent architectures expand the LLM's control in two key ways:

ReAct is a popular general purpose agent architecture that combines these expansions, integrating three core concepts.

This architecture allows for more complex and flexible agent behaviors, going beyond simple routing to enable dynamic problem-solving with multiple steps. Unlike the original paper, today's agents rely on LLMs' tool calling capabilities and operate on a list of messages.

In LangGraph, you can use the prebuilt agent to get started with tool-calling agents.

Tools are useful whenever you want an agent to interact with external systems. External systems (e.g., APIs) often require a particular input schema or payload, rather than natural language. When we bind an API, for example, as a tool, we give the model awareness of the required input schema. The model will choose to call a tool based upon the natural language input from the user and it will return an output that adheres to the tool's required schema.

Many LLM providers support tool calling and tool calling interface in LangChain is simple: you can simply pass any Python function into ChatModel.bind_tools(function).

Memory is crucial for agents, enabling them to retain and utilize information across multiple steps of problem-solving. It operates on different scales:

LangGraph provides full control over memory implementation:

This flexible approach allows you to tailor the memory system to your specific agent architecture needs. Effective memory management enhances an agent's ability to maintain context, learn from past experiences, and make more informed decisions over time. For a practical guide on adding and managing memory, see Memory.

In a tool-calling agent, an LLM is called repeatedly in a while-loop. At each step the agent decides which tools to call, and what the inputs to those tools should be. Those tools are then executed, and the outputs are fed back into the LLM as observations. The while-loop terminates when the agent decides it has enough information to solve the user request and it is not worth calling any more tools.

While routers and tool-calling agents (like ReAct) are common, customizing agent architectures often leads to better performance for specific tasks. LangGraph offers several powerful features for building tailored agent systems:

Human involvement can significantly enhance agent reliability, especially for sensitive tasks. This can involve:

Human-in-the-loop patterns are crucial when full automation isn't feasible or desirable. Learn more in our human-in-the-loop guide.

Parallel processing is vital for efficient multi-agent systems and complex tasks. LangGraph supports parallelization through its Send API, enabling:

For practical implementation, see our map-reduce tutorial

Subgraphs are essential for managing complex agent architectures, particularly in multi-agent systems. They allow:

Subgraphs communicate with the parent graph through overlapping keys in the state schema. This enables flexible, modular agent design. For implementation details, refer to our subgraph how-to guide.

Reflection mechanisms can significantly improve agent reliability by:

While often LLM-based, reflection can also use deterministic methods. For instance, in coding tasks, compilation errors can serve as feedback. This approach is demonstrated in this video using LangGraph for self-corrective code generation.

By leveraging these features, LangGraph enables the creation of sophisticated, task-specific agent architectures that can handle complex workflows, collaborate effectively, and continuously improve their performance.

---

## Streaming¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/streaming/

**Contents:**
- Streaming¶
- What’s possible with LangGraph streaming¶

LangGraph implements a streaming system to surface real-time updates, allowing for responsive and transparent user experiences.

LangGraph’s streaming system lets you surface live feedback from graph runs to your app. There are three main categories of data you can stream:

---

## Persistence¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/persistence/

**Contents:**
- Persistence¶
- Threads¶
- Checkpoints¶
  - Get state¶
  - Get state history¶
  - Replay¶
  - Update state¶
    - config¶
    - values¶
    - as_node¶

LangGraph has a built-in persistence layer, implemented through checkpointers. When you compile a graph with a checkpointer, the checkpointer saves a checkpoint of the graph state at every super-step. Those checkpoints are saved to a thread, which can be accessed after graph execution. Because threads allow access to graph's state after execution, several powerful capabilities including human-in-the-loop, memory, time travel, and fault-tolerance are all possible. Below, we'll discuss each of these concepts in more detail.

LangGraph API handles checkpointing automatically

When using the LangGraph API, you don't need to implement or configure checkpointers manually. The API handles all persistence infrastructure for you behind the scenes.

A thread is a unique ID or thread identifier assigned to each checkpoint saved by a checkpointer. It contains the accumulated state of a sequence of runs. When a run is executed, the state of the underlying graph of the assistant will be persisted to the thread.

When invoking a graph with a checkpointer, you must specify a thread_id as part of the configurable portion of the config:

A thread's current and historical state can be retrieved. To persist state, a thread must be created prior to executing a run. The LangGraph Platform API provides several endpoints for creating and managing threads and thread state. See the API reference for more details.

The state of a thread at a particular point in time is called a checkpoint. Checkpoint is a snapshot of the graph state saved at each super-step and is represented by StateSnapshot object with the following key properties:

Checkpoints are persisted and can be used to restore the state of a thread at a later time.

Let's see what checkpoints are saved when a simple graph is invoked as follows:

API Reference: StateGraph | START | END | InMemorySaver

After we run the graph, we expect to see exactly 4 checkpoints:

Note that we bar channel values contain outputs from both nodes as we have a reducer for bar channel.

When interacting with the saved graph state, you must specify a thread identifier. You can view the latest state of the graph by calling graph.get_state(config). This will return a StateSnapshot object that corresponds to the latest checkpoint associated with the thread ID provided in the config or a checkpoint associated with a checkpoint ID for the thread, if provided.

In our example, the output of get_state will look like this:

You can get the full history of the graph execution for a given thread by calling graph.get_state_history(config). This will return a list of StateSnapshot objects associated with the thread ID provided in the config. Importantly, the checkpoints will be ordered chronologically with the most recent checkpoint / StateSnapshot being the first in the list.

In our example, the output of get_state_history will look like this:

It's also possible to play-back a prior graph execution. If we invoke a graph with a thread_id and a checkpoint_id, then we will re-play the previously executed steps before a checkpoint that corresponds to the checkpoint_id, and only execute the steps after the checkpoint.

You must pass these when invoking the graph as part of the configurable portion of the config:

Importantly, LangGraph knows whether a particular step has been executed previously. If it has, LangGraph simply re-plays that particular step in the graph and does not re-execute the step, but only for the steps before the provided checkpoint_id. All of the steps after checkpoint_id will be executed (i.e., a new fork), even if they have been executed previously. See this how to guide on time-travel to learn more about replaying.

In addition to re-playing the graph from specific checkpoints, we can also edit the graph state. We do this using graph.update_state(). This method accepts three different arguments:

The config should contain thread_id specifying which thread to update. When only the thread_id is passed, we update (or fork) the current state. Optionally, if we include checkpoint_id field, then we fork that selected checkpoint.

These are the values that will be used to update the state. Note that this update is treated exactly as any update from a node is treated. This means that these values will be passed to the reducer functions, if they are defined for some of the channels in the graph state. This means that update_state does NOT automatically overwrite the channel values for every channel, but only for the channels without reducers. Let's walk through an example.

Let's assume you have defined the state of your graph with the following schema (see full example above):

Let's now assume the current state of the graph is

If you update the state as below:

Then the new state of the graph will be:

The foo key (channel) is completely changed (because there is no reducer specified for that channel, so update_state overwrites it). However, there is a reducer specified for the bar key, and so it appends "b" to the state of bar.

The final thing you can optionally specify when calling update_state is as_node. If you provided it, the update will be applied as if it came from node as_node. If as_node is not provided, it will be set to the last node that updated the state, if not ambiguous. The reason this matters is that the next steps to execute depend on the last node to have given an update, so this can be used to control which node executes next. See this how to guide on time-travel to learn more about forking state.

A state schema specifies a set of keys that are populated as a graph is executed. As discussed above, state can be written by a checkpointer to a thread at each graph step, enabling state persistence.

But, what if we want to retain some information across threads? Consider the case of a chatbot where we want to retain specific information about the user across all chat conversations (e.g., threads) with that user!

With checkpointers alone, we cannot share information across threads. This motivates the need for the Store interface. As an illustration, we can define an InMemoryStore to store information about a user across threads. We simply compile our graph with a checkpointer, as before, and with our new in_memory_store variable.

LangGraph API handles stores automatically

When using the LangGraph API, you don't need to implement or configure stores manually. The API handles all storage infrastructure for you behind the scenes.

First, let's showcase this in isolation without using LangGraph.

Memories are namespaced by a tuple, which in this specific example will be (<user_id>, "memories"). The namespace can be any length and represent anything, does not have to be user specific.

We use the store.put method to save memories to our namespace in the store. When we do this, we specify the namespace, as defined above, and a key-value pair for the memory: the key is simply a unique identifier for the memory (memory_id) and the value (a dictionary) is the memory itself.

We can read out memories in our namespace using the store.search method, which will return all memories for a given user as a list. The most recent memory is the last in the list.

Each memory type is a Python class (Item) with certain attributes. We can access it as a dictionary by converting via .dict as above.

The attributes it has are:

Beyond simple retrieval, the store also supports semantic search, allowing you to find memories based on meaning rather than exact matches. To enable this, configure the store with an embedding model:

API Reference: init_embeddings

Now when searching, you can use natural language queries to find relevant memories:

You can control which parts of your memories get embedded by configuring the fields parameter or by specifying the index parameter when storing memories:

With this all in place, we use the in_memory_store in LangGraph. The in_memory_store works hand-in-hand with the checkpointer: the checkpointer saves state to threads, as discussed above, and the in_memory_store allows us to store arbitrary information for access across threads. We compile the graph with both the checkpointer and the in_memory_store as follows.

API Reference: InMemorySaver

We invoke the graph with a thread_id, as before, and also with a user_id, which we'll use to namespace our memories to this particular user as we showed above.

We can access the in_memory_store and the user_id in any node by passing store: BaseStore and config: RunnableConfig as node arguments. Here's how we might use semantic search in a node to find relevant memories:

As we showed above, we can also access the store in any node and use the store.search method to get memories. Recall the memories are returned as a list of objects that can be converted to a dictionary.

We can access the memories and use them in our model call.

If we create a new thread, we can still access the same memories so long as the user_id is the same.

When we use the LangGraph Platform, either locally (e.g., in LangGraph Studio) or with LangGraph Platform, the base store is available to use by default and does not need to be specified during graph compilation. To enable semantic search, however, you do need to configure the indexing settings in your langgraph.json file. For example:

See the deployment guide for more details and configuration options.

Under the hood, checkpointing is powered by checkpointer objects that conform to BaseCheckpointSaver interface. LangGraph provides several checkpointer implementations, all implemented via standalone, installable libraries:

Each checkpointer conforms to BaseCheckpointSaver interface and implements the following methods:

If the checkpointer is used with asynchronous graph execution (i.e. executing the graph via .ainvoke, .astream, .abatch), asynchronous versions of the above methods will be used (.aput, .aput_writes, .aget_tuple, .alist).

For running your graph asynchronously, you can use InMemorySaver, or async versions of Sqlite/Postgres checkpointers -- AsyncSqliteSaver / AsyncPostgresSaver checkpointers.

When checkpointers save the graph state, they need to serialize the channel values in the state. This is done using serializer objects.

langgraph_checkpoint defines protocol for implementing serializers provides a default implementation (JsonPlusSerializer) that handles a wide variety of types, including LangChain and LangGraph primitives, datetimes, enums and more.

The default serializer, JsonPlusSerializer, uses ormsgpack and JSON under the hood, which is not suitable for all types of objects.

If you want to fallback to pickle for objects not currently supported by our msgpack encoder (such as Pandas dataframes), you can use the pickle_fallback argument of the JsonPlusSerializer:

API Reference: InMemorySaver | JsonPlusSerializer

Checkpointers can optionally encrypt all persisted state. To enable this, pass an instance of EncryptedSerializer to the serde argument of any BaseCheckpointSaver implementation. The easiest way to create an encrypted serializer is via from_pycryptodome_aes, which reads the AES key from the LANGGRAPH_AES_KEY environment variable (or accepts a key argument):

API Reference: SqliteSaver

API Reference: PostgresSaver

When running on LangGraph Platform, encryption is automatically enabled whenever LANGGRAPH_AES_KEY is present, so you only need to provide the environment variable. Other encryption schemes can be used by implementing CipherProtocol and supplying it to EncryptedSerializer.

First, checkpointers facilitate human-in-the-loop workflows workflows by allowing humans to inspect, interrupt, and approve graph steps. Checkpointers are needed for these workflows as the human has to be able to view the state of a graph at any point in time, and the graph has to be to resume execution after the human has made any updates to the state. See the how-to guides for examples.

Second, checkpointers allow for "memory" between interactions. In the case of repeated human interactions (like conversations) any follow up messages can be sent to that thread, which will retain its memory of previous ones. See Add memory for information on how to add and manage conversation memory using checkpointers.

Third, checkpointers allow for "time travel", allowing users to replay prior graph executions to review and / or debug specific graph steps. In addition, checkpointers make it possible to fork the graph state at arbitrary checkpoints to explore alternative trajectories.

Lastly, checkpointing also provides fault-tolerance and error recovery: if one or more nodes fail at a given superstep, you can restart your graph from the last successful step. Additionally, when a graph node fails mid-execution at a given superstep, LangGraph stores pending checkpoint writes from any other nodes that completed successfully at that superstep, so that whenever we resume graph execution from that superstep we don't re-run the successful nodes.

Additionally, when a graph node fails mid-execution at a given superstep, LangGraph stores pending checkpoint writes from any other nodes that completed successfully at that superstep, so that whenever we resume graph execution from that superstep we don't re-run the successful nodes.

**Examples:**

Example 1 (unknown):
```unknown
{"configurable": {"thread_id": "1"}}
```

Example 2 (python):
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class State(TypedDict):
    foo: str
    bar: Annotated[list[str], add]

def node_a(state: State):
    return {"foo": "a", "bar": ["a"]}

def node_b(state: State):
    return {"foo": "b", "bar": ["b"]}


workflow = StateGraph(State)
workflow.add_node(node_a)
workflow.add_node(node_b)
workflow.add_edge(START, "node_a")
workflow.add_edge("node_a", "node_b")
workflow.add_edge("node_b", END)

checkpointer = InMemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "1"}}
graph.invoke({"foo": ""}, config)
```

Example 3 (unknown):
```unknown
# get the latest state snapshot
config = {"configurable": {"thread_id": "1"}}
graph.get_state(config)

# get a state snapshot for a specific checkpoint_id
config = {"configurable": {"thread_id": "1", "checkpoint_id": "1ef663ba-28fe-6528-8002-5a559208592c"}}
graph.get_state(config)
```

Example 4 (unknown):
```unknown
StateSnapshot(
    values={'foo': 'b', 'bar': ['a', 'b']},
    next=(),
    config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28fe-6528-8002-5a559208592c'}},
    metadata={'source': 'loop', 'writes': {'node_b': {'foo': 'b', 'bar': ['b']}}, 'step': 2},
    created_at='2024-08-29T19:19:38.821749+00:00',
    parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f9-6ec4-8001-31981c2c39f8'}}, tasks=()
)
```

---

## Human-in-the-loop¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop

**Contents:**
- Human-in-the-loop¶
- Key capabilities¶
- Patterns¶

To review, edit, and approve tool calls in an agent or workflow, use LangGraph's human-in-the-loop features to enable human intervention at any point in a workflow. This is especially useful in large language model (LLM)-driven applications where model output may require validation, correction, or additional context.

For information on how to use human-in-the-loop, see Enable human intervention and Human-in-the-loop using Server API.

Persistent execution state: Interrupts use LangGraph's persistence layer, which saves the graph state, to indefinitely pause graph execution until you resume. This is possible because LangGraph checkpoints the graph state after each step, which allows the system to persist execution context and later resume the workflow, continuing from where it left off. This supports asynchronous human review or input without time constraints.

There are two ways to pause a graph:

An example graph consisting of 3 sequential steps with a breakpoint before step_3.

Flexible integration points: Human-in-the-loop logic can be introduced at any point in the workflow. This allows targeted human involvement, such as approving API calls, correcting outputs, or guiding conversations.

There are four typical design patterns that you can implement using interrupt and Command:

---

## Persistence¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/persistence

**Contents:**
- Persistence¶
- Threads¶
- Checkpoints¶
  - Get state¶
  - Get state history¶
  - Replay¶
  - Update state¶
    - config¶
    - values¶
    - as_node¶

LangGraph has a built-in persistence layer, implemented through checkpointers. When you compile a graph with a checkpointer, the checkpointer saves a checkpoint of the graph state at every super-step. Those checkpoints are saved to a thread, which can be accessed after graph execution. Because threads allow access to graph's state after execution, several powerful capabilities including human-in-the-loop, memory, time travel, and fault-tolerance are all possible. Below, we'll discuss each of these concepts in more detail.

LangGraph API handles checkpointing automatically

When using the LangGraph API, you don't need to implement or configure checkpointers manually. The API handles all persistence infrastructure for you behind the scenes.

A thread is a unique ID or thread identifier assigned to each checkpoint saved by a checkpointer. It contains the accumulated state of a sequence of runs. When a run is executed, the state of the underlying graph of the assistant will be persisted to the thread.

When invoking a graph with a checkpointer, you must specify a thread_id as part of the configurable portion of the config:

A thread's current and historical state can be retrieved. To persist state, a thread must be created prior to executing a run. The LangGraph Platform API provides several endpoints for creating and managing threads and thread state. See the API reference for more details.

The state of a thread at a particular point in time is called a checkpoint. Checkpoint is a snapshot of the graph state saved at each super-step and is represented by StateSnapshot object with the following key properties:

Checkpoints are persisted and can be used to restore the state of a thread at a later time.

Let's see what checkpoints are saved when a simple graph is invoked as follows:

API Reference: StateGraph | START | END | InMemorySaver

After we run the graph, we expect to see exactly 4 checkpoints:

Note that we bar channel values contain outputs from both nodes as we have a reducer for bar channel.

When interacting with the saved graph state, you must specify a thread identifier. You can view the latest state of the graph by calling graph.get_state(config). This will return a StateSnapshot object that corresponds to the latest checkpoint associated with the thread ID provided in the config or a checkpoint associated with a checkpoint ID for the thread, if provided.

In our example, the output of get_state will look like this:

You can get the full history of the graph execution for a given thread by calling graph.get_state_history(config). This will return a list of StateSnapshot objects associated with the thread ID provided in the config. Importantly, the checkpoints will be ordered chronologically with the most recent checkpoint / StateSnapshot being the first in the list.

In our example, the output of get_state_history will look like this:

It's also possible to play-back a prior graph execution. If we invoke a graph with a thread_id and a checkpoint_id, then we will re-play the previously executed steps before a checkpoint that corresponds to the checkpoint_id, and only execute the steps after the checkpoint.

You must pass these when invoking the graph as part of the configurable portion of the config:

Importantly, LangGraph knows whether a particular step has been executed previously. If it has, LangGraph simply re-plays that particular step in the graph and does not re-execute the step, but only for the steps before the provided checkpoint_id. All of the steps after checkpoint_id will be executed (i.e., a new fork), even if they have been executed previously. See this how to guide on time-travel to learn more about replaying.

In addition to re-playing the graph from specific checkpoints, we can also edit the graph state. We do this using graph.update_state(). This method accepts three different arguments:

The config should contain thread_id specifying which thread to update. When only the thread_id is passed, we update (or fork) the current state. Optionally, if we include checkpoint_id field, then we fork that selected checkpoint.

These are the values that will be used to update the state. Note that this update is treated exactly as any update from a node is treated. This means that these values will be passed to the reducer functions, if they are defined for some of the channels in the graph state. This means that update_state does NOT automatically overwrite the channel values for every channel, but only for the channels without reducers. Let's walk through an example.

Let's assume you have defined the state of your graph with the following schema (see full example above):

Let's now assume the current state of the graph is

If you update the state as below:

Then the new state of the graph will be:

The foo key (channel) is completely changed (because there is no reducer specified for that channel, so update_state overwrites it). However, there is a reducer specified for the bar key, and so it appends "b" to the state of bar.

The final thing you can optionally specify when calling update_state is as_node. If you provided it, the update will be applied as if it came from node as_node. If as_node is not provided, it will be set to the last node that updated the state, if not ambiguous. The reason this matters is that the next steps to execute depend on the last node to have given an update, so this can be used to control which node executes next. See this how to guide on time-travel to learn more about forking state.

A state schema specifies a set of keys that are populated as a graph is executed. As discussed above, state can be written by a checkpointer to a thread at each graph step, enabling state persistence.

But, what if we want to retain some information across threads? Consider the case of a chatbot where we want to retain specific information about the user across all chat conversations (e.g., threads) with that user!

With checkpointers alone, we cannot share information across threads. This motivates the need for the Store interface. As an illustration, we can define an InMemoryStore to store information about a user across threads. We simply compile our graph with a checkpointer, as before, and with our new in_memory_store variable.

LangGraph API handles stores automatically

When using the LangGraph API, you don't need to implement or configure stores manually. The API handles all storage infrastructure for you behind the scenes.

First, let's showcase this in isolation without using LangGraph.

Memories are namespaced by a tuple, which in this specific example will be (<user_id>, "memories"). The namespace can be any length and represent anything, does not have to be user specific.

We use the store.put method to save memories to our namespace in the store. When we do this, we specify the namespace, as defined above, and a key-value pair for the memory: the key is simply a unique identifier for the memory (memory_id) and the value (a dictionary) is the memory itself.

We can read out memories in our namespace using the store.search method, which will return all memories for a given user as a list. The most recent memory is the last in the list.

Each memory type is a Python class (Item) with certain attributes. We can access it as a dictionary by converting via .dict as above.

The attributes it has are:

Beyond simple retrieval, the store also supports semantic search, allowing you to find memories based on meaning rather than exact matches. To enable this, configure the store with an embedding model:

API Reference: init_embeddings

Now when searching, you can use natural language queries to find relevant memories:

You can control which parts of your memories get embedded by configuring the fields parameter or by specifying the index parameter when storing memories:

With this all in place, we use the in_memory_store in LangGraph. The in_memory_store works hand-in-hand with the checkpointer: the checkpointer saves state to threads, as discussed above, and the in_memory_store allows us to store arbitrary information for access across threads. We compile the graph with both the checkpointer and the in_memory_store as follows.

API Reference: InMemorySaver

We invoke the graph with a thread_id, as before, and also with a user_id, which we'll use to namespace our memories to this particular user as we showed above.

We can access the in_memory_store and the user_id in any node by passing store: BaseStore and config: RunnableConfig as node arguments. Here's how we might use semantic search in a node to find relevant memories:

As we showed above, we can also access the store in any node and use the store.search method to get memories. Recall the memories are returned as a list of objects that can be converted to a dictionary.

We can access the memories and use them in our model call.

If we create a new thread, we can still access the same memories so long as the user_id is the same.

When we use the LangGraph Platform, either locally (e.g., in LangGraph Studio) or with LangGraph Platform, the base store is available to use by default and does not need to be specified during graph compilation. To enable semantic search, however, you do need to configure the indexing settings in your langgraph.json file. For example:

See the deployment guide for more details and configuration options.

Under the hood, checkpointing is powered by checkpointer objects that conform to BaseCheckpointSaver interface. LangGraph provides several checkpointer implementations, all implemented via standalone, installable libraries:

Each checkpointer conforms to BaseCheckpointSaver interface and implements the following methods:

If the checkpointer is used with asynchronous graph execution (i.e. executing the graph via .ainvoke, .astream, .abatch), asynchronous versions of the above methods will be used (.aput, .aput_writes, .aget_tuple, .alist).

For running your graph asynchronously, you can use InMemorySaver, or async versions of Sqlite/Postgres checkpointers -- AsyncSqliteSaver / AsyncPostgresSaver checkpointers.

When checkpointers save the graph state, they need to serialize the channel values in the state. This is done using serializer objects.

langgraph_checkpoint defines protocol for implementing serializers provides a default implementation (JsonPlusSerializer) that handles a wide variety of types, including LangChain and LangGraph primitives, datetimes, enums and more.

The default serializer, JsonPlusSerializer, uses ormsgpack and JSON under the hood, which is not suitable for all types of objects.

If you want to fallback to pickle for objects not currently supported by our msgpack encoder (such as Pandas dataframes), you can use the pickle_fallback argument of the JsonPlusSerializer:

API Reference: InMemorySaver | JsonPlusSerializer

Checkpointers can optionally encrypt all persisted state. To enable this, pass an instance of EncryptedSerializer to the serde argument of any BaseCheckpointSaver implementation. The easiest way to create an encrypted serializer is via from_pycryptodome_aes, which reads the AES key from the LANGGRAPH_AES_KEY environment variable (or accepts a key argument):

API Reference: SqliteSaver

API Reference: PostgresSaver

When running on LangGraph Platform, encryption is automatically enabled whenever LANGGRAPH_AES_KEY is present, so you only need to provide the environment variable. Other encryption schemes can be used by implementing CipherProtocol and supplying it to EncryptedSerializer.

First, checkpointers facilitate human-in-the-loop workflows workflows by allowing humans to inspect, interrupt, and approve graph steps. Checkpointers are needed for these workflows as the human has to be able to view the state of a graph at any point in time, and the graph has to be to resume execution after the human has made any updates to the state. See the how-to guides for examples.

Second, checkpointers allow for "memory" between interactions. In the case of repeated human interactions (like conversations) any follow up messages can be sent to that thread, which will retain its memory of previous ones. See Add memory for information on how to add and manage conversation memory using checkpointers.

Third, checkpointers allow for "time travel", allowing users to replay prior graph executions to review and / or debug specific graph steps. In addition, checkpointers make it possible to fork the graph state at arbitrary checkpoints to explore alternative trajectories.

Lastly, checkpointing also provides fault-tolerance and error recovery: if one or more nodes fail at a given superstep, you can restart your graph from the last successful step. Additionally, when a graph node fails mid-execution at a given superstep, LangGraph stores pending checkpoint writes from any other nodes that completed successfully at that superstep, so that whenever we resume graph execution from that superstep we don't re-run the successful nodes.

Additionally, when a graph node fails mid-execution at a given superstep, LangGraph stores pending checkpoint writes from any other nodes that completed successfully at that superstep, so that whenever we resume graph execution from that superstep we don't re-run the successful nodes.

**Examples:**

Example 1 (unknown):
```unknown
{"configurable": {"thread_id": "1"}}
```

Example 2 (python):
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class State(TypedDict):
    foo: str
    bar: Annotated[list[str], add]

def node_a(state: State):
    return {"foo": "a", "bar": ["a"]}

def node_b(state: State):
    return {"foo": "b", "bar": ["b"]}


workflow = StateGraph(State)
workflow.add_node(node_a)
workflow.add_node(node_b)
workflow.add_edge(START, "node_a")
workflow.add_edge("node_a", "node_b")
workflow.add_edge("node_b", END)

checkpointer = InMemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "1"}}
graph.invoke({"foo": ""}, config)
```

Example 3 (unknown):
```unknown
# get the latest state snapshot
config = {"configurable": {"thread_id": "1"}}
graph.get_state(config)

# get a state snapshot for a specific checkpoint_id
config = {"configurable": {"thread_id": "1", "checkpoint_id": "1ef663ba-28fe-6528-8002-5a559208592c"}}
graph.get_state(config)
```

Example 4 (unknown):
```unknown
StateSnapshot(
    values={'foo': 'b', 'bar': ['a', 'b']},
    next=(),
    config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28fe-6528-8002-5a559208592c'}},
    metadata={'source': 'loop', 'writes': {'node_b': {'foo': 'b', 'bar': ['b']}}, 'step': 2},
    created_at='2024-08-29T19:19:38.821749+00:00',
    parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f9-6ec4-8001-31981c2c39f8'}}, tasks=()
)
```

---

## Use time-travel¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/time-travel/

**Contents:**
- Use time-travel¶
- In a workflow¶
  - Setup¶
  - 1. Run the graph¶
  - 2. Identify a checkpoint¶
  - 3. Update the state (optional)¶
  - 4. Resume execution from the checkpoint¶

To use time-travel in LangGraph:

For a conceptual overview of time-travel, see Time travel.

This example builds a simple LangGraph workflow that generates a joke topic and writes a joke using an LLM. It demonstrates how to run the graph, retrieve past execution checkpoints, optionally modify the state, and resume execution from a chosen checkpoint to explore alternate outcomes.

First we need to install the packages required

Next, we need to set API keys for Anthropic (the LLM we will use)

Set up LangSmith for LangGraph development

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started here.

API Reference: StateGraph | START | END | init_chat_model | InMemorySaver

update_state will create a new checkpoint. The new checkpoint will be associated with the same thread, but a new checkpoint ID.

**Examples:**

Example 1 (unknown):
```unknown
%%capture --no-stderr
%pip install --quiet -U langgraph langchain_anthropic
```

Example 2 (python):
```python
import getpass
import os


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("ANTHROPIC_API_KEY")
```

Example 3 (python):
```python
import uuid

from typing_extensions import TypedDict, NotRequired
from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver


class State(TypedDict):
    topic: NotRequired[str]
    joke: NotRequired[str]


llm = init_chat_model(
    "anthropic:claude-3-7-sonnet-latest",
    temperature=0,
)


def generate_topic(state: State):
    """LLM call to generate a topic for the joke"""
    msg = llm.invoke("Give me a funny topic for a joke")
    return {"topic": msg.content}


def write_joke(state: State):
    """LLM call to write a joke based on the topic"""
    msg = llm.invoke(f"Write a short joke about {state['topic']}")
    return {"joke": msg.content}


# Build workflow
workflow = StateGraph(State)

# Add nodes
workflow.add_node("generate_topic", generate_topic)
workflow.add_node("write_joke", write_joke)

# Add edges to connect nodes
workflow.add_edge(START, "generate_topic")
workflow.add_edge("generate_topic", "write_joke")
workflow.add_edge("write_joke", END)

# Compile
checkpointer = InMemorySaver()
graph = workflow.compile(checkpointer=checkpointer)
graph
```

Example 4 (unknown):
```unknown
config = {
    "configurable": {
        "thread_id": uuid.uuid4(),
    }
}
state = graph.invoke({}, config)

print(state["topic"])
print()
print(state["joke"])
```

---

## Multi-agent systems¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/multi_agent/

**Contents:**
- Multi-agent systems¶
- Multi-agent architectures¶
  - Handoffs¶
    - Handoffs as tools¶
  - Network¶
  - Supervisor¶
  - Supervisor (tool-calling)¶
  - Hierarchical¶
  - Custom multi-agent workflow¶
- Communication and state management¶

An agent is a system that uses an LLM to decide the control flow of an application. As you develop these systems, they might grow more complex over time, making them harder to manage and scale. For example, you might run into the following problems:

To tackle these, you might consider breaking your application into multiple smaller, independent agents and composing them into a multi-agent system. These independent agents can be as simple as a prompt and an LLM call, or as complex as a ReAct agent (and more!).

The primary benefits of using multi-agent systems are:

There are several ways to connect agents in a multi-agent system:

In multi-agent architectures, agents can be represented as graph nodes. Each agent node executes its step(s) and decides whether to finish execution or route to another agent, including potentially routing to itself (e.g., running in a loop). A common pattern in multi-agent interactions is handoffs, where one agent hands off control to another. Handoffs allow you to specify:

To implement handoffs in LangGraph, agent nodes can return Command object that allows you to combine both control flow and state updates:

In a more complex scenario where each agent node is itself a graph (i.e., a subgraph), a node in one of the agent subgraphs might want to navigate to a different agent. For example, if you have two agents, alice and bob (subgraph nodes in a parent graph), and alice needs to navigate to bob, you can set graph=Command.PARENT in the Command object:

If you need to support visualization for subgraphs communicating using Command(graph=Command.PARENT) you would need to wrap them in a node function with Command annotation: Instead of this:

you would need to do this:

One of the most common agent types is a tool-calling agent. For those types of agents, a common pattern is wrapping a handoff in a tool call:

This is a special case of updating the graph state from tools where, in addition to the state update, the control flow is included as well.

If you want to use tools that return Command, you can use the prebuilt create_react_agent / ToolNode components, or else implement your own logic:

Let's now take a closer look at the different multi-agent architectures.

In this architecture, agents are defined as graph nodes. Each agent can communicate with every other agent (many-to-many connections) and can decide which agent to call next. This architecture is good for problems that do not have a clear hierarchy of agents or a specific sequence in which agents should be called.

API Reference: ChatOpenAI | Command | StateGraph | START | END

In this architecture, we define agents as nodes and add a supervisor node (LLM) that decides which agent nodes should be called next. We use Command to route execution to the appropriate agent node based on supervisor's decision. This architecture also lends itself well to running multiple agents in parallel or using map-reduce pattern.

API Reference: ChatOpenAI | Command | StateGraph | START | END

Check out this tutorial for an example of supervisor multi-agent architecture.

In this variant of the supervisor architecture, we define a supervisor agent which is responsible for calling sub-agents. The sub-agents are exposed to the supervisor as tools, and the supervisor agent decides which tool to call next. The supervisor agent follows a standard implementation as an LLM running in a while loop calling tools until it decides to stop.

API Reference: ChatOpenAI | InjectedState | create_react_agent

As you add more agents to your system, it might become too hard for the supervisor to manage all of them. The supervisor might start making poor decisions about which agent to call next, or the context might become too complex for a single supervisor to keep track of. In other words, you end up with the same problems that motivated the multi-agent architecture in the first place.

To address this, you can design your system hierarchically. For example, you can create separate, specialized teams of agents managed by individual supervisors, and a top-level supervisor to manage the teams.

API Reference: ChatOpenAI | StateGraph | START | END | Command

In this architecture we add individual agents as graph nodes and define the order in which agents are called ahead of time, in a custom workflow. In LangGraph the workflow can be defined in two ways:

Explicit control flow (normal edges): LangGraph allows you to explicitly define the control flow of your application (i.e. the sequence of how agents communicate) explicitly, via normal graph edges. This is the most deterministic variant of this architecture above — we always know which agent will be called next ahead of time.

Dynamic control flow (Command): in LangGraph you can allow LLMs to decide parts of your application control flow. This can be achieved by using Command. A special case of this is a supervisor tool-calling architecture. In that case, the tool-calling LLM powering the supervisor agent will make decisions about the order in which the tools (agents) are being called.

API Reference: ChatOpenAI | StateGraph | START

The most important thing when building multi-agent systems is figuring out how the agents communicate.

A common, generic way for agents to communicate is via a list of messages. This opens up the following questions:

Additionally, if you are dealing with more complex agents or wish to keep individual agent state separate from the multi-agent system state, you may need to use different state schemas.

What is the "payload" that is being passed around between agents? In most of the architectures discussed above, the agents communicate via handoffs and pass the graph state as part of the handoff payload. Specifically, agents pass around lists of messages as part of the graph state. In the case of the supervisor with tool-calling, the payloads are tool call arguments.

The most common way for agents to communicate is via a shared state channel, typically a list of messages. This assumes that there is always at least a single channel (key) in the state that is shared by the agents (e.g., messages). When communicating via a shared message list, there is an additional consideration: should the agents share the full history of their thought process or only the final result?

Agents can share the full history of their thought process (i.e., "scratchpad") with all other agents. This "scratchpad" would typically look like a list of messages. The benefit of sharing the full thought process is that it might help other agents make better decisions and improve reasoning ability for the system as a whole. The downside is that as the number of agents and their complexity grows, the "scratchpad" will grow quickly and might require additional strategies for memory management.

Agents can have their own private "scratchpad" and only share the final result with the rest of the agents. This approach might work better for systems with many agents or agents that are more complex. In this case, you would need to define agents with different state schemas.

For agents called as tools, the supervisor determines the inputs based on the tool schema. Additionally, LangGraph allows passing state to individual tools at runtime, so subordinate agents can access parent state, if needed.

It can be helpful to indicate which agent a particular AI message is from, especially for long message histories. Some LLM providers (like OpenAI) support adding a name parameter to messages — you can use that to attach the agent name to the message. If that is not supported, you can consider manually injecting the agent name into the message content, e.g., <agent>alice</agent><message>message from alice</message>.

Handoffs are typically done via the LLM calling a dedicated handoff tool. This is represented as an AI message with tool calls that is passed to the next agent (LLM). Most LLM providers don't support receiving AI messages with tool calls without corresponding tool messages.

You therefore have two options:

In practice, we see that most developers opt for option (1).

A common practice is to have multiple agents communicating on a shared message list, but only adding their final messages to the list. This means that any intermediate messages (e.g., tool calls) are not saved in this list.

What if you do want to save these messages so that if this particular subagent is invoked in the future you can pass those back in?

There are two high-level approaches to achieve that:

An agent might need to have a different state schema from the rest of the agents. For example, a search agent might only need to keep track of queries and retrieved documents. There are two ways to achieve this in LangGraph:

**Examples:**

Example 1 (python):
```python
def agent(state) -> Command[Literal["agent", "another_agent"]]:
    # the condition for routing/halting can be anything, e.g. LLM tool call / structured output, etc.
    goto = get_next_agent(...)  # 'agent' / 'another_agent'
    return Command(
        # Specify which agent to call next
        goto=goto,
        # Update the graph state
        update={"my_state_key": "my_state_value"}
    )
```

Example 2 (python):
```python
def some_node_inside_alice(state):
    return Command(
        goto="bob",
        update={"my_state_key": "my_state_value"},
        # specify which graph to navigate to (defaults to the current graph)
        graph=Command.PARENT,
    )
```

Example 3 (unknown):
```unknown
builder.add_node(alice)
```

Example 4 (python):
```python
def call_alice(state) -> Command[Literal["bob"]]:
    return alice.invoke(state)

builder.add_node("alice", call_alice)
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/concepts/assistants/

---

## Human-in-the-loop¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/

**Contents:**
- Human-in-the-loop¶
- Key capabilities¶
- Patterns¶

To review, edit, and approve tool calls in an agent or workflow, use LangGraph's human-in-the-loop features to enable human intervention at any point in a workflow. This is especially useful in large language model (LLM)-driven applications where model output may require validation, correction, or additional context.

For information on how to use human-in-the-loop, see Enable human intervention and Human-in-the-loop using Server API.

Persistent execution state: Interrupts use LangGraph's persistence layer, which saves the graph state, to indefinitely pause graph execution until you resume. This is possible because LangGraph checkpoints the graph state after each step, which allows the system to persist execution context and later resume the workflow, continuing from where it left off. This supports asynchronous human review or input without time constraints.

There are two ways to pause a graph:

An example graph consisting of 3 sequential steps with a breakpoint before step_3.

Flexible integration points: Human-in-the-loop logic can be introduced at any point in the workflow. This allows targeted human involvement, such as approving API calls, correcting outputs, or guiding conversations.

There are four typical design patterns that you can implement using interrupt and Command:

---

## LangGraph

**URL:** https://langchain-ai.github.io/langgraph/

**Contents:**
- LangGraph
- Get started¶
- Core benefits¶
- LangGraph’s ecosystem¶
- Additional resources¶
- Acknowledgements¶

Trusted by companies shaping the future of agents – including Klarna, Replit, Elastic, and more – LangGraph is a low-level orchestration framework for building, managing, and deploying long-running, stateful agents.

Then, create an agent using prebuilt components:

API Reference: create_react_agent

For more information, see the Quickstart. Or, to learn how to build an agent workflow with a customizable architecture, long-term memory, and other complex task handling, see the LangGraph basics tutorials.

LangGraph provides low-level supporting infrastructure for any long-running, stateful workflow or agent. LangGraph does not abstract prompts or architecture, and provides the following central benefits:

While LangGraph can be used standalone, it also integrates seamlessly with any LangChain product, giving developers a full suite of tools for building agents. To improve your LLM application development, pair LangGraph with:

Looking for the JS version of LangGraph? See the JS repo and the JS docs.

LangGraph is inspired by Pregel and Apache Beam. The public interface draws inspiration from NetworkX. LangGraph is built by LangChain Inc, the creators of LangChain, but can be used without LangChain.

**Examples:**

Example 1 (unknown):
```unknown
pip install -U langgraph
```

Example 2 (python):
```python
# pip install -qU "langchain[anthropic]" to call the model

from langgraph.prebuilt import create_react_agent

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

agent = create_react_agent(
    model="anthropic:claude-3-7-sonnet-latest",
    tools=[get_weather],
    prompt="You are a helpful assistant"
)

# Run the agent
agent.invoke(
    {"messages": [{"role": "user", "content": "what is the weather in sf"}]}
)
```

---

## Time Travel ⏱️¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/time-travel/

**Contents:**
- Time Travel ⏱️¶

When working with non-deterministic systems that make model-based decisions (e.g., agents powered by LLMs), it can be useful to examine their decision-making process in detail:

LangGraph provides time travel functionality to support these use cases. Specifically, you can resume execution from a prior checkpoint — either replaying the same state or modifying it to explore alternatives. In all cases, resuming past execution produces a new fork in the history.

For information on how to use time travel, see Use time travel and Time travel using Server API.

---

## Graph API concepts¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/low_level/

**Contents:**
- Graph API concepts¶
- Graphs¶
  - StateGraph¶
  - Compiling your graph¶
- State¶
  - Schema¶
    - Multiple schemas¶
  - Reducers¶
    - Default Reducer¶
  - Working with Messages in Graph State¶

At its core, LangGraph models agent workflows as graphs. You define the behavior of your agents using three key components:

State: A shared data structure that represents the current snapshot of your application. It can be any data type, but is typically defined using a shared state schema.

Nodes: Functions that encode the logic of your agents. They receive the current state as input, perform some computation or side-effect, and return an updated state.

Edges: Functions that determine which Node to execute next based on the current state. They can be conditional branches or fixed transitions.

By composing Nodes and Edges, you can create complex, looping workflows that evolve the state over time. The real power, though, comes from how LangGraph manages that state. To emphasize: Nodes and Edges are nothing more than functions - they can contain an LLM or just good ol' code.

In short: nodes do the work, edges tell what to do next.

LangGraph's underlying graph algorithm uses message passing to define a general program. When a Node completes its operation, it sends messages along one or more edges to other node(s). These recipient nodes then execute their functions, pass the resulting messages to the next set of nodes, and the process continues. Inspired by Google's Pregel system, the program proceeds in discrete "super-steps."

A super-step can be considered a single iteration over the graph nodes. Nodes that run in parallel are part of the same super-step, while nodes that run sequentially belong to separate super-steps. At the start of graph execution, all nodes begin in an inactive state. A node becomes active when it receives a new message (state) on any of its incoming edges (or "channels"). The active node then runs its function and responds with updates. At the end of each super-step, nodes with no incoming messages vote to halt by marking themselves as inactive. The graph execution terminates when all nodes are inactive and no messages are in transit.

The StateGraph class is the main graph class to use. This is parameterized by a user defined State object.

To build your graph, you first define the state, you then add nodes and edges, and then you compile it. What exactly is compiling your graph and why is it needed?

Compiling is a pretty simple step. It provides a few basic checks on the structure of your graph (no orphaned nodes, etc). It is also where you can specify runtime args like checkpointers and breakpoints. You compile your graph by just calling the .compile method:

You MUST compile your graph before you can use it.

The first thing you do when you define a graph is define the State of the graph. The State consists of the schema of the graph as well as reducer functions which specify how to apply updates to the state. The schema of the State will be the input schema to all Nodes and Edges in the graph, and can be either a TypedDict or a Pydantic model. All Nodes will emit updates to the State which are then applied using the specified reducer function.

The main documented way to specify the schema of a graph is by using a TypedDict. If you want to provide default values in your state, use a dataclass. We also support using a Pydantic BaseModel as your graph state if you want recursive data validation (though note that pydantic is less performant than a TypedDict or dataclass).

By default, the graph will have the same input and output schemas. If you want to change this, you can also specify explicit input and output schemas directly. This is useful when you have a lot of keys, and some are explicitly for input and others for output. See the guide here for how to use.

Typically, all graph nodes communicate with a single schema. This means that they will read and write to the same state channels. But, there are cases where we want more control over this:

It is possible to have nodes write to private state channels inside the graph for internal node communication. We can simply define a private schema, PrivateState.

It is also possible to define explicit input and output schemas for a graph. In these cases, we define an "internal" schema that contains all keys relevant to graph operations. But, we also define input and output schemas that are sub-sets of the "internal" schema to constrain the input and output of the graph. See this guide for more detail.

Let's look at an example:

There are two subtle and important points to note here:

We pass state: InputState as the input schema to node_1. But, we write out to foo, a channel in OverallState. How can we write out to a state channel that is not included in the input schema? This is because a node can write to any state channel in the graph state. The graph state is the union of the state channels defined at initialization, which includes OverallState and the filters InputState and OutputState.

We initialize the graph with StateGraph(OverallState,input_schema=InputState,output_schema=OutputState). So, how can we write to PrivateState in node_2? How does the graph gain access to this schema if it was not passed in the StateGraph initialization? We can do this because nodes can also declare additional state channels as long as the state schema definition exists. In this case, the PrivateState schema is defined, so we can add bar as a new state channel in the graph and write to it.

Reducers are key to understanding how updates from nodes are applied to the State. Each key in the State has its own independent reducer function. If no reducer function is explicitly specified then it is assumed that all updates to that key should override it. There are a few different types of reducers, starting with the default type of reducer:

These two examples show how to use the default reducer:

In this example, no reducer functions are specified for any key. Let's assume the input to the graph is:

{"foo": 1, "bar": ["hi"]}. Let's then assume the first Node returns {"foo": 2}. This is treated as an update to the state. Notice that the Node does not need to return the whole State schema - just an update. After applying this update, the State would then be {"foo": 2, "bar": ["hi"]}. If the second node returns {"bar": ["bye"]} then the State would then be {"foo": 2, "bar": ["bye"]}

In this example, we've used the Annotated type to specify a reducer function (operator.add) for the second key (bar). Note that the first key remains unchanged. Let's assume the input to the graph is {"foo": 1, "bar": ["hi"]}. Let's then assume the first Node returns {"foo": 2}. This is treated as an update to the state. Notice that the Node does not need to return the whole State schema - just an update. After applying this update, the State would then be {"foo": 2, "bar": ["hi"]}. If the second node returns {"bar": ["bye"]} then the State would then be {"foo": 2, "bar": ["hi", "bye"]}. Notice here that the bar key is updated by adding the two lists together.

Most modern LLM providers have a chat model interface that accepts a list of messages as input. LangChain's ChatModel in particular accepts a list of Message objects as inputs. These messages come in a variety of forms such as HumanMessage (user input) or AIMessage (LLM response). To read more about what message objects are, please refer to this conceptual guide.

In many cases, it is helpful to store prior conversation history as a list of messages in your graph state. To do so, we can add a key (channel) to the graph state that stores a list of Message objects and annotate it with a reducer function (see messages key in the example below). The reducer function is vital to telling the graph how to update the list of Message objects in the state with each state update (for example, when a node sends an update). If you don't specify a reducer, every state update will overwrite the list of messages with the most recently provided value. If you wanted to simply append messages to the existing list, you could use operator.add as a reducer.

However, you might also want to manually update messages in your graph state (e.g. human-in-the-loop). If you were to use operator.add, the manual state updates you send to the graph would be appended to the existing list of messages, instead of updating existing messages. To avoid that, you need a reducer that can keep track of message IDs and overwrite existing messages, if updated. To achieve this, you can use the prebuilt add_messages function. For brand new messages, it will simply append to existing list, but it will also handle the updates for existing messages correctly.

In addition to keeping track of message IDs, the add_messages function will also try to deserialize messages into LangChain Message objects whenever a state update is received on the messages channel. See more information on LangChain serialization/deserialization here. This allows sending graph inputs / state updates in the following format:

Since the state updates are always deserialized into LangChain Messages when using add_messages, you should use dot notation to access message attributes, like state["messages"][-1].content. Below is an example of a graph that uses add_messages as its reducer function.

API Reference: AnyMessage | add_messages

Since having a list of messages in your state is so common, there exists a prebuilt state called MessagesState which makes it easy to use messages. MessagesState is defined with a single messages key which is a list of AnyMessage objects and uses the add_messages reducer. Typically, there is more state to track than just messages, so we see people subclass this state and add more fields, like:

In LangGraph, nodes are Python functions (either synchronous or asynchronous) that accept the following arguments:

Similar to NetworkX, you add these nodes to a graph using the add_node method:

API Reference: RunnableConfig | StateGraph

Behind the scenes, functions are converted to RunnableLambdas, which add batch and async support to your function, along with native tracing and debugging.

If you add a node to a graph without specifying a name, it will be given a default name equivalent to the function name.

The START Node is a special node that represents the node that sends user input to the graph. The main purpose for referencing this node is to determine which nodes should be called first.

The END Node is a special node that represents a terminal node. This node is referenced when you want to denote which edges have no actions after they are done.

LangGraph supports caching of tasks/nodes based on the input to the node. To use caching:

API Reference: StateGraph

Edges define how the logic is routed and how the graph decides to stop. This is a big part of how your agents work and how different nodes communicate with each other. There are a few key types of edges:

A node can have MULTIPLE outgoing edges. If a node has multiple out-going edges, all of those destination nodes will be executed in parallel as a part of the next superstep.

If you always want to go from node A to node B, you can use the add_edge method directly.

If you want to optionally route to 1 or more edges (or optionally terminate), you can use the add_conditional_edges method. This method accepts the name of a node and a "routing function" to call after that node is executed:

Similar to nodes, the routing_function accepts the current state of the graph and returns a value.

By default, the return value routing_function is used as the name of the node (or list of nodes) to send the state to next. All those nodes will be run in parallel as a part of the next superstep.

You can optionally provide a dictionary that maps the routing_function's output to the name of the next node.

Use Command instead of conditional edges if you want to combine state updates and routing in a single function.

The entry point is the first node(s) that are run when the graph starts. You can use the add_edge method from the virtual START node to the first node to execute to specify where to enter the graph.

A conditional entry point lets you start at different nodes depending on custom logic. You can use add_conditional_edges from the virtual START node to accomplish this.

You can optionally provide a dictionary that maps the routing_function's output to the name of the next node.

By default, Nodes and Edges are defined ahead of time and operate on the same shared state. However, there can be cases where the exact edges are not known ahead of time and/or you may want different versions of State to exist at the same time. A common example of this is with map-reduce design patterns. In this design pattern, a first node may generate a list of objects, and you may want to apply some other node to all those objects. The number of objects may be unknown ahead of time (meaning the number of edges may not be known) and the input State to the downstream Node should be different (one for each generated object).

To support this design pattern, LangGraph supports returning Send objects from conditional edges. Send takes two arguments: first is the name of the node, and second is the state to pass to that node.

It can be useful to combine control flow (edges) and state updates (nodes). For example, you might want to BOTH perform state updates AND decide which node to go to next in the SAME node. LangGraph provides a way to do so by returning a Command object from node functions:

With Command you can also achieve dynamic control flow behavior (identical to conditional edges):

When returning Command in your node functions, you must add return type annotations with the list of node names the node is routing to, e.g. Command[Literal["my_other_node"]]. This is necessary for the graph rendering and tells LangGraph that my_node can navigate to my_other_node.

Check out this how-to guide for an end-to-end example of how to use Command.

If you are using subgraphs, you might want to navigate from a node within a subgraph to a different subgraph (i.e. a different node in the parent graph). To do so, you can specify graph=Command.PARENT in Command:

Setting graph to Command.PARENT will navigate to the closest parent graph.

State updates with Command.PARENT

When you send updates from a subgraph node to a parent graph node for a key that's shared by both parent and subgraph state schemas, you must define a reducer for the key you're updating in the parent graph state. See this example.

This is particularly useful when implementing multi-agent handoffs.

Check out this guide for detail.

A common use case is updating graph state from inside a tool. For example, in a customer support application you might want to look up customer information based on their account number or ID in the beginning of the conversation.

Refer to this guide for detail.

Command is an important part of human-in-the-loop workflows: when using interrupt() to collect user input, Command is then used to supply the input and resume execution via Command(resume="User input"). Check out this conceptual guide for more information.

LangGraph can easily handle migrations of graph definitions (nodes, edges, and state) even when using a checkpointer to track state.

When creating a graph, you can specify a context_schema for runtime context passed to nodes. This is useful for passing information to nodes that is not part of the graph state. For example, you might want to pass dependencies such as model name or a database connection.

You can then pass this context into the graph using the context parameter of the invoke method.

You can then access and use this context inside a node or conditional edge:

See this guide for a full breakdown on configuration. :::

The recursion limit sets the maximum number of super-steps the graph can execute during a single execution. Once the limit is reached, LangGraph will raise GraphRecursionError. By default this value is set to 25 steps. The recursion limit can be set on any graph at runtime, and is passed to .invoke/.stream via the config dictionary. Importantly, recursion_limit is a standalone config key and should not be passed inside the configurable key as all other user-defined configuration. See the example below:

Read this how-to to learn more about how the recursion limit works.

It's often nice to be able to visualize graphs, especially as they get more complex. LangGraph comes with several built-in ways to visualize graphs. See this how-to guide for more info.

**Examples:**

Example 1 (unknown):
```unknown
graph = graph_builder.compile(...)
```

Example 2 (python):
```python
class InputState(TypedDict):
    user_input: str

class OutputState(TypedDict):
    graph_output: str

class OverallState(TypedDict):
    foo: str
    user_input: str
    graph_output: str

class PrivateState(TypedDict):
    bar: str

def node_1(state: InputState) -> OverallState:
    # Write to OverallState
    return {"foo": state["user_input"] + " name"}

def node_2(state: OverallState) -> PrivateState:
    # Read from OverallState, write to PrivateState
    return {"bar": state["foo"] + " is"}

def node_3(state: PrivateState) -> OutputState:
    # Read from PrivateState, write to OutputState
    return {"graph_output": state["bar"] + " Lance"}

builder = StateGraph(OverallState,input_schema=InputState,output_schema=OutputState)
builder.add_node("node_1", node_1)
builder.add_node("node_2", node_2)
builder.add_node("node_3", node_3)
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
builder.add_edge("node_2", "node_3")
builder.add_edge("node_3", END)

graph = builder.compile()
graph.invoke({"user_input":"My"})
# {'graph_output': 'My name is Lance'}
```

Example 3 (python):
```python
from typing_extensions import TypedDict

class State(TypedDict):
    foo: int
    bar: list[str]
```

Example 4 (python):
```python
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class State(TypedDict):
    foo: int
    bar: Annotated[list[str], add]
```

---

## Tools¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/tools/

**Contents:**
- Tools¶
- Tool calling¶
- Prebuilt tools¶
- Custom tools¶
- Tool execution¶

Many AI applications interact with users via natural language. However, some use cases require models to interface directly with external systems—such as APIs, databases, or file systems—using structured input. In these scenarios, tool calling enables models to generate requests that conform to a specified input schema.

Tools encapsulate a callable function and its input schema. These can be passed to compatible chat models, allowing the model to decide whether to invoke a tool and with what arguments.

Tool calling is typically conditional. Based on the user input and available tools, the model may choose to issue a tool call request. This request is returned in an AIMessage object, which includes a tool_calls field that specifies the tool name and input arguments:

If the input is unrelated to any tool, the model returns only a natural language message:

Importantly, the model does not execute the tool—it only generates a request. A separate executor (such as a runtime or agent) is responsible for handling the tool call and returning the result.

See the tool calling guide for more details.

LangChain provides prebuilt tool integrations for common external systems including APIs, databases, file systems, and web data.

Browse the integrations directory for available tools.

You can define custom tools using the @tool decorator or plain Python functions. For example:

See the tool calling guide for more details.

While the model determines when to call a tool, execution of the tool call must be handled by a runtime component.

LangGraph provides prebuilt components for this:

**Examples:**

Example 1 (unknown):
```unknown
llm_with_tools.invoke("What is 2 multiplied by 3?")
# -> AIMessage(tool_calls=[{'name': 'multiply', 'args': {'a': 2, 'b': 3}, ...}])
```

Example 2 (unknown):
```unknown
AIMessage(
  tool_calls=[
    ToolCall(name="multiply", args={"a": 2, "b": 3}),
    ...
  ]
)
```

Example 3 (unknown):
```unknown
llm_with_tools.invoke("Hello world!")  # -> AIMessage(content="Hello!")
```

Example 4 (python):
```python
from langchain_core.tools import tool

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
```

---

## Streaming¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/streaming

**Contents:**
- Streaming¶
- What’s possible with LangGraph streaming¶

LangGraph implements a streaming system to surface real-time updates, allowing for responsive and transparent user experiences.

LangGraph’s streaming system lets you surface live feedback from graph runs to your app. There are three main categories of data you can stream:

---

## Functional API concepts¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/functional_api

**Contents:**
- Functional API concepts¶
- Overview¶
- Functional API vs. Graph API¶
- Example¶
- Entrypoint¶
  - Definition¶
  - Injectable parameters¶
  - Executing¶
  - Resuming¶
  - Short-term memory¶

The Functional API allows you to add LangGraph's key features — persistence, memory, human-in-the-loop, and streaming — to your applications with minimal changes to your existing code.

It is designed to integrate these features into existing code that may use standard language primitives for branching and control flow, such as if statements, for loops, and function calls. Unlike many data orchestration frameworks that require restructuring code into an explicit pipeline or DAG, the Functional API allows you to incorporate these capabilities without enforcing a rigid execution model.

The Functional API uses two key building blocks:

This provides a minimal abstraction for building workflows with state management and streaming.

For information on how to use the functional API, see Use Functional API.

For users who prefer a more declarative approach, LangGraph's Graph API allows you to define workflows using a Graph paradigm. Both APIs share the same underlying runtime, so you can use them together in the same application.

Here are some key differences:

Below we demonstrate a simple application that writes an essay and interrupts to request human review.

API Reference: InMemorySaver | entrypoint | task | interrupt

This workflow will write an essay about the topic "cat" and then pause to get a review from a human. The workflow can be interrupted for an indefinite amount of time until a review is provided.

When the workflow is resumed, it executes from the very start, but because the result of the writeEssay task was already saved, the task result will be loaded from the checkpoint instead of being recomputed.

An essay has been written and is ready for review. Once the review is provided, we can resume the workflow:

The workflow has been completed and the review has been added to the essay.

The @entrypoint decorator can be used to create a workflow from a function. It encapsulates workflow logic and manages execution flow, including handling long-running tasks and interrupts.

An entrypoint is defined by decorating a function with the @entrypoint decorator.

The function must accept a single positional argument, which serves as the workflow input. If you need to pass multiple pieces of data, use a dictionary as the input type for the first argument.

Decorating a function with an entrypoint produces a Pregel instance which helps to manage the execution of the workflow (e.g., handles streaming, resumption, and checkpointing).

You will usually want to pass a checkpointer to the @entrypoint decorator to enable persistence and use features like human-in-the-loop.

The inputs and outputs of entrypoints must be JSON-serializable to support checkpointing. Please see the serialization section for more details.

When declaring an entrypoint, you can request access to additional parameters that will be injected automatically at run time. These parameters include:

Declare the parameters with the appropriate name and type annotation.

Using the @entrypoint yields a Pregel object that can be executed using the invoke, ainvoke, stream, and astream methods.

Resuming an execution after an interrupt can be done by passing a resume value to the Command primitive.

Resuming after an error

To resume after an error, run the entrypoint with a None and the same thread id (config).

This assumes that the underlying error has been resolved and execution can proceed successfully.

When an entrypoint is defined with a checkpointer, it stores information between successive invocations on the same thread id in checkpoints.

This allows accessing the state from the previous invocation using the previous parameter.

By default, the previous parameter is the return value of the previous invocation.

entrypoint.final is a special primitive that can be returned from an entrypoint and allows decoupling the value that is saved in the checkpoint from the return value of the entrypoint.

The first value is the return value of the entrypoint, and the second value is the value that will be saved in the checkpoint. The type annotation is entrypoint.final[return_type, save_type].

A task represents a discrete unit of work, such as an API call or data processing step. It has two key characteristics:

Tasks are defined using the @task decorator, which wraps a regular Python function.

The outputs of tasks must be JSON-serializable to support checkpointing.

Tasks can only be called from within an entrypoint, another task, or a state graph node.

Tasks cannot be called directly from the main application code.

When you call a task, it returns immediately with a future object. A future is a placeholder for a result that will be available later.

To obtain the result of a task, you can either wait for it synchronously (using result()) or await it asynchronously (using await).

Tasks are useful in the following scenarios:

There are two key aspects to serialization in LangGraph:

These requirements are necessary for enabling checkpointing and workflow resumption. Use python primitives like dictionaries, lists, strings, numbers, and booleans to ensure that your inputs and outputs are serializable.

Serialization ensures that workflow state, such as task results and intermediate values, can be reliably saved and restored. This is critical for enabling human-in-the-loop interactions, fault tolerance, and parallel execution.

Providing non-serializable inputs or outputs will result in a runtime error when a workflow is configured with a checkpointer.

To utilize features like human-in-the-loop, any randomness should be encapsulated inside of tasks. This guarantees that when execution is halted (e.g., for human in the loop) and then resumed, it will follow the same sequence of steps, even if task results are non-deterministic.

LangGraph achieves this behavior by persisting task and subgraph results as they execute. A well-designed workflow ensures that resuming execution follows the same sequence of steps, allowing previously computed results to be retrieved correctly without having to re-execute them. This is particularly useful for long-running tasks or tasks with non-deterministic results, as it avoids repeating previously done work and allows resuming from essentially the same.

While different runs of a workflow can produce different results, resuming a specific run should always follow the same sequence of recorded steps. This allows LangGraph to efficiently look up task and subgraph results that were executed prior to the graph being interrupted and avoid recomputing them.

Idempotency ensures that running the same operation multiple times produces the same result. This helps prevent duplicate API calls and redundant processing if a step is rerun due to a failure. Always place API calls inside tasks functions for checkpointing, and design them to be idempotent in case of re-execution. Re-execution can occur if a task starts, but does not complete successfully. Then, if the workflow is resumed, the task will run again. Use idempotency keys or verify existing results to avoid duplication.

Encapsulate side effects (e.g., writing to a file, sending an email) in tasks to ensure they are not executed multiple times when resuming a workflow.

In this example, a side effect (writing to a file) is directly included in the workflow, so it will be executed a second time when resuming the workflow.

In this example, the side effect is encapsulated in a task, ensuring consistent execution upon resumption.

Operations that might give different results each time (like getting current time or random numbers) should be encapsulated in tasks to ensure that on resume, the same result is returned.

This is especially important when using human-in-the-loop workflows with multiple interrupts calls. LangGraph keeps a list of resume values for each task/entrypoint. When an interrupt is encountered, it's matched with the corresponding resume value. This matching is strictly index-based, so the order of the resume values should match the order of the interrupts.

If order of execution is not maintained when resuming, one interrupt call may be matched with the wrong resume value, leading to incorrect results.

Please read the section on determinism for more details.

In this example, the workflow uses the current time to determine which task to execute. This is non-deterministic because the result of the workflow depends on the time at which it is executed.

In this example, the workflow uses the input t0 to determine which task to execute. This is deterministic because the result of the workflow depends only on the input.

**Examples:**

Example 1 (python):
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import interrupt

@task
def write_essay(topic: str) -> str:
    """Write an essay about the given topic."""
    time.sleep(1) # A placeholder for a long-running task.
    return f"An essay about topic: {topic}"

@entrypoint(checkpointer=InMemorySaver())
def workflow(topic: str) -> dict:
    """A simple workflow that writes an essay and asks for a review."""
    essay = write_essay("cat").result()
    is_approved = interrupt({
        # Any json-serializable payload provided to interrupt as argument.
        # It will be surfaced on the client side as an Interrupt when streaming data
        # from the workflow.
        "essay": essay, # The essay we want reviewed.
        # We can add any additional information that we need.
        # For example, introduce a key called "action" with some instructions.
        "action": "Please approve/reject the essay",
    })

    return {
        "essay": essay, # The essay that was generated
        "is_approved": is_approved, # Response from HIL
    }
```

Example 2 (python):
```python
import time
import uuid
from langgraph.func import entrypoint, task
from langgraph.types import interrupt
from langgraph.checkpoint.memory import InMemorySaver


@task
def write_essay(topic: str) -> str:
    """Write an essay about the given topic."""
    time.sleep(1)  # This is a placeholder for a long-running task.
    return f"An essay about topic: {topic}"

@entrypoint(checkpointer=InMemorySaver())
def workflow(topic: str) -> dict:
    """A simple workflow that writes an essay and asks for a review."""
    essay = write_essay("cat").result()
    is_approved = interrupt(
        {
            # Any json-serializable payload provided to interrupt as argument.
            # It will be surfaced on the client side as an Interrupt when streaming data
            # from the workflow.
            "essay": essay,  # The essay we want reviewed.
            # We can add any additional information that we need.
            # For example, introduce a key called "action" with some instructions.
            "action": "Please approve/reject the essay",
        }
    )
    return {
        "essay": essay,  # The essay that was generated
        "is_approved": is_approved,  # Response from HIL
    }


thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": thread_id}}
for item in workflow.stream("cat", config):
    print(item)
# > {'write_essay': 'An essay about topic: cat'}
# > {
# >     '__interrupt__': (
# >        Interrupt(
# >            value={
# >                'essay': 'An essay about topic: cat',
# >                'action': 'Please approve/reject the essay'
# >            },
# >            id='b9b2b9d788f482663ced6dc755c9e981'
# >        ),
# >    )
# > }
```

Example 3 (python):
```python
from langgraph.types import Command

# Get review from a user (e.g., via a UI)
# In this case, we're using a bool, but this can be any json-serializable value.
human_review = True

for item in workflow.stream(Command(resume=human_review), config):
    print(item)
```

Example 4 (unknown):
```unknown
{'workflow': {'essay': 'An essay about topic: cat', 'is_approved': False}}
```

---

## Memory¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/memory/

**Contents:**
- Memory¶
- Short-term memory¶
  - Manage short-term memory¶
- Long-term memory¶
  - Memory types¶
    - Semantic memory¶
      - Profile¶
      - Collection¶
    - Episodic memory¶
    - Procedural memory¶

Memory is a system that remembers information about previous interactions. For AI agents, memory is crucial because it lets them remember previous interactions, learn from feedback, and adapt to user preferences. As agents tackle more complex tasks with numerous user interactions, this capability becomes essential for both efficiency and user satisfaction.

This conceptual guide covers two types of memory, based on their recall scope:

Short-term memory, or thread-scoped memory, tracks the ongoing conversation by maintaining message history within a session. LangGraph manages short-term memory as a part of your agent's state. State is persisted to a database using a checkpointer so the thread can be resumed at any time. Short-term memory updates when the graph is invoked or a step is completed, and the State is read at the start of each step.

Long-term memory stores user-specific or application-level data across sessions and is shared across conversational threads. It can be recalled at any time and in any thread. Memories are scoped to any custom namespace, not just within a single thread ID. LangGraph provides stores (reference doc) to let you save and recall long-term memories.

Short-term memory lets your application remember previous interactions within a single thread or conversation. A thread organizes multiple interactions in a session, similar to the way email groups messages in a single conversation.

LangGraph manages short-term memory as part of the agent's state, persisted via thread-scoped checkpoints. This state can normally include the conversation history along with other stateful data, such as uploaded files, retrieved documents, or generated artifacts. By storing these in the graph's state, the bot can access the full context for a given conversation while maintaining separation between different threads.

Conversation history is the most common form of short-term memory, and long conversations pose a challenge to today's LLMs. A full history may not fit inside an LLM's context window, resulting in an irrecoverable error. Even if your LLM supports the full context length, most LLMs still perform poorly over long contexts. They get "distracted" by stale or off-topic content, all while suffering from slower response times and higher costs.

Chat models accept context using messages, which include developer provided instructions (a system message) and user inputs (human messages). In chat applications, messages alternate between human inputs and model responses, resulting in a list of messages that grows longer over time. Because context windows are limited and token-rich message lists can be costly, many applications can benefit from using techniques to manually remove or forget stale information.

For more information on common techniques for managing messages, see the Add and manage memory guide.

Long-term memory in LangGraph allows systems to retain information across different conversations or sessions. Unlike short-term memory, which is thread-scoped, long-term memory is saved within custom "namespaces."

Long-term memory is a complex challenge without a one-size-fits-all solution. However, the following questions provide a framework to help you navigate the different techniques:

What is the type of memory? Humans use memories to remember facts (semantic memory), experiences (episodic memory), and rules (procedural memory). AI agents can use memory in the same ways. For example, AI agents can use memory to remember specific facts about a user to accomplish a task.

When do you want to update memories? Memory can be updated as part of an agent's application logic (e.g., "on the hot path"). In this case, the agent typically decides to remember facts before responding to a user. Alternatively, memory can be updated as a background task (logic that runs in the background / asynchronously and generates memories). We explain the tradeoffs between these approaches in the section below.

Different applications require various types of memory. Although the analogy isn't perfect, examining human memory types can be insightful. Some research (e.g., the CoALA paper) have even mapped these human memory types to those used in AI agents.

Semantic memory, both in humans and AI agents, involves the retention of specific facts and concepts. In humans, it can include information learned in school and the understanding of concepts and their relationships. For AI agents, semantic memory is often used to personalize applications by remembering facts or concepts from past interactions.

Semantic memory is different from "semantic search," which is a technique for finding similar content using "meaning" (usually as embeddings). Semantic memory is a term from psychology, referring to storing facts and knowledge, while semantic search is a method for retrieving information based on meaning rather than exact matches.

Semantic memories can be managed in different ways. For example, memories can be a single, continuously updated "profile" of well-scoped and specific information about a user, organization, or other entity (including the agent itself). A profile is generally just a JSON document with various key-value pairs you've selected to represent your domain.

When remembering a profile, you will want to make sure that you are updating the profile each time. As a result, you will want to pass in the previous profile and ask the model to generate a new profile (or some JSON patch to apply to the old profile). This can be become error-prone as the profile gets larger, and may benefit from splitting a profile into multiple documents or strict decoding when generating documents to ensure the memory schemas remains valid.

Alternatively, memories can be a collection of documents that are continuously updated and extended over time. Each individual memory can be more narrowly scoped and easier to generate, which means that you're less likely to lose information over time. It's easier for an LLM to generate new objects for new information than reconcile new information with an existing profile. As a result, a document collection tends to lead to higher recall downstream.

However, this shifts some complexity memory updating. The model must now delete or update existing items in the list, which can be tricky. In addition, some models may default to over-inserting and others may default to over-updating. See the Trustcall package for one way to manage this and consider evaluation (e.g., with a tool like LangSmith) to help you tune the behavior.

Working with document collections also shifts complexity to memory search over the list. The Store currently supports both semantic search and filtering by content.

Finally, using a collection of memories can make it challenging to provide comprehensive context to the model. While individual memories may follow a specific schema, this structure might not capture the full context or relationships between memories. As a result, when using these memories to generate responses, the model may lack important contextual information that would be more readily available in a unified profile approach.

Regardless of memory management approach, the central point is that the agent will use the semantic memories to ground its responses, which often leads to more personalized and relevant interactions.

Episodic memory, in both humans and AI agents, involves recalling past events or actions. The CoALA paper frames this well: facts can be written to semantic memory, whereas experiences can be written to episodic memory. For AI agents, episodic memory is often used to help an agent remember how to accomplish a task.

In practice, episodic memories are often implemented through few-shot example prompting, where agents learn from past sequences to perform tasks correctly. Sometimes it's easier to "show" than "tell" and LLMs learn well from examples. Few-shot learning lets you "program" your LLM by updating the prompt with input-output examples to illustrate the intended behavior. While various best-practices can be used to generate few-shot examples, often the challenge lies in selecting the most relevant examples based on user input.

Note that the memory store is just one way to store data as few-shot examples. If you want to have more developer involvement, or tie few-shots more closely to your evaluation harness, you can also use a LangSmith Dataset to store your data. Then dynamic few-shot example selectors can be used out-of-the box to achieve this same goal. LangSmith will index the dataset for you and enable retrieval of few shot examples that are most relevant to the user input based upon keyword similarity (using a BM25-like algorithm for keyword based similarity).

See this how-to video for example usage of dynamic few-shot example selection in LangSmith. Also, see this blog post showcasing few-shot prompting to improve tool calling performance and this blog post using few-shot example to align an LLMs to human preferences.

Procedural memory, in both humans and AI agents, involves remembering the rules used to perform tasks. In humans, procedural memory is like the internalized knowledge of how to perform tasks, such as riding a bike via basic motor skills and balance. Episodic memory, on the other hand, involves recalling specific experiences, such as the first time you successfully rode a bike without training wheels or a memorable bike ride through a scenic route. For AI agents, procedural memory is a combination of model weights, agent code, and agent's prompt that collectively determine the agent's functionality.

In practice, it is fairly uncommon for agents to modify their model weights or rewrite their code. However, it is more common for agents to modify their own prompts.

One effective approach to refining an agent's instructions is through "Reflection" or meta-prompting. This involves prompting the agent with its current instructions (e.g., the system prompt) along with recent conversations or explicit user feedback. The agent then refines its own instructions based on this input. This method is particularly useful for tasks where instructions are challenging to specify upfront, as it allows the agent to learn and adapt from its interactions.

For example, we built a Tweet generator using external feedback and prompt re-writing to produce high-quality paper summaries for Twitter. In this case, the specific summarization prompt was difficult to specify a priori, but it was fairly easy for a user to critique the generated Tweets and provide feedback on how to improve the summarization process.

The below pseudo-code shows how you might implement this with the LangGraph memory store, using the store to save a prompt, the update_instructions node to get the current prompt (as well as feedback from the conversation with the user captured in state["messages"]), update the prompt, and save the new prompt back to the store. Then, the call_model get the updated prompt from the store and uses it to generate a response.

There are two primary methods for agents to write memories: "in the hot path" and "in the background".

Creating memories during runtime offers both advantages and challenges. On the positive side, this approach allows for real-time updates, making new memories immediately available for use in subsequent interactions. It also enables transparency, as users can be notified when memories are created and stored.

However, this method also presents challenges. It may increase complexity if the agent requires a new tool to decide what to commit to memory. In addition, the process of reasoning about what to save to memory can impact agent latency. Finally, the agent must multitask between memory creation and its other responsibilities, potentially affecting the quantity and quality of memories created.

As an example, ChatGPT uses a save_memories tool to upsert memories as content strings, deciding whether and how to use this tool with each user message. See our memory-agent template as an reference implementation.

Creating memories as a separate background task offers several advantages. It eliminates latency in the primary application, separates application logic from memory management, and allows for more focused task completion by the agent. This approach also provides flexibility in timing memory creation to avoid redundant work.

However, this method has its own challenges. Determining the frequency of memory writing becomes crucial, as infrequent updates may leave other threads without new context. Deciding when to trigger memory formation is also important. Common strategies include scheduling after a set time period (with rescheduling if new events occur), using a cron schedule, or allowing manual triggers by users or the application logic.

See our memory-service template as an reference implementation.

LangGraph stores long-term memories as JSON documents in a store. Each memory is organized under a custom namespace (similar to a folder) and a distinct key (like a file name). Namespaces often include user or org IDs or other labels that makes it easier to organize information. This structure enables hierarchical organization of memories. Cross-namespace searching is then supported through content filters.

For more information about the memory store, see the Persistence guide.

**Examples:**

Example 1 (python):
```python
# Node that *uses* the instructions
def call_model(state: State, store: BaseStore):
    namespace = ("agent_instructions", )
    instructions = store.get(namespace, key="agent_a")[0]
    # Application logic
    prompt = prompt_template.format(instructions=instructions.value["instructions"])
    ...

# Node that updates instructions
def update_instructions(state: State, store: BaseStore):
    namespace = ("instructions",)
    current_instructions = store.search(namespace)[0]
    # Memory logic
    prompt = prompt_template.format(instructions=current_instructions.value["instructions"], conversation=state["messages"])
    output = llm.invoke(prompt)
    new_instructions = output['new_instructions']
    store.put(("agent_instructions",), "agent_a", {"instructions": new_instructions})
    ...
```

Example 2 (python):
```python
from langgraph.store.memory import InMemoryStore


def embed(texts: list[str]) -> list[list[float]]:
    # Replace with an actual embedding function or LangChain embeddings object
    return [[1.0, 2.0] * len(texts)]


# InMemoryStore saves data to an in-memory dictionary. Use a DB-backed store in production use.
store = InMemoryStore(index={"embed": embed, "dims": 2})
user_id = "my-user"
application_context = "chitchat"
namespace = (user_id, application_context)
store.put(
    namespace,
    "a-memory",
    {
        "rules": [
            "User likes short, direct language",
            "User only speaks English & python",
        ],
        "my-key": "my-value",
    },
)
# get the "memory" by ID
item = store.get(namespace, "a-memory")
# search for "memories" within this namespace, filtering on content equivalence, sorted by vector similarity
items = store.search(
    namespace, filter={"my-key": "my-value"}, query="language preferences"
)
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/concepts/deployment_options/

---

## 

**URL:** https://langchain-ai.github.io/langgraph/concepts/langgraph_platform/

---

## Functional API concepts¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/functional_api/

**Contents:**
- Functional API concepts¶
- Overview¶
- Functional API vs. Graph API¶
- Example¶
- Entrypoint¶
  - Definition¶
  - Injectable parameters¶
  - Executing¶
  - Resuming¶
  - Short-term memory¶

The Functional API allows you to add LangGraph's key features — persistence, memory, human-in-the-loop, and streaming — to your applications with minimal changes to your existing code.

It is designed to integrate these features into existing code that may use standard language primitives for branching and control flow, such as if statements, for loops, and function calls. Unlike many data orchestration frameworks that require restructuring code into an explicit pipeline or DAG, the Functional API allows you to incorporate these capabilities without enforcing a rigid execution model.

The Functional API uses two key building blocks:

This provides a minimal abstraction for building workflows with state management and streaming.

For information on how to use the functional API, see Use Functional API.

For users who prefer a more declarative approach, LangGraph's Graph API allows you to define workflows using a Graph paradigm. Both APIs share the same underlying runtime, so you can use them together in the same application.

Here are some key differences:

Below we demonstrate a simple application that writes an essay and interrupts to request human review.

API Reference: InMemorySaver | entrypoint | task | interrupt

This workflow will write an essay about the topic "cat" and then pause to get a review from a human. The workflow can be interrupted for an indefinite amount of time until a review is provided.

When the workflow is resumed, it executes from the very start, but because the result of the writeEssay task was already saved, the task result will be loaded from the checkpoint instead of being recomputed.

An essay has been written and is ready for review. Once the review is provided, we can resume the workflow:

The workflow has been completed and the review has been added to the essay.

The @entrypoint decorator can be used to create a workflow from a function. It encapsulates workflow logic and manages execution flow, including handling long-running tasks and interrupts.

An entrypoint is defined by decorating a function with the @entrypoint decorator.

The function must accept a single positional argument, which serves as the workflow input. If you need to pass multiple pieces of data, use a dictionary as the input type for the first argument.

Decorating a function with an entrypoint produces a Pregel instance which helps to manage the execution of the workflow (e.g., handles streaming, resumption, and checkpointing).

You will usually want to pass a checkpointer to the @entrypoint decorator to enable persistence and use features like human-in-the-loop.

The inputs and outputs of entrypoints must be JSON-serializable to support checkpointing. Please see the serialization section for more details.

When declaring an entrypoint, you can request access to additional parameters that will be injected automatically at run time. These parameters include:

Declare the parameters with the appropriate name and type annotation.

Using the @entrypoint yields a Pregel object that can be executed using the invoke, ainvoke, stream, and astream methods.

Resuming an execution after an interrupt can be done by passing a resume value to the Command primitive.

Resuming after an error

To resume after an error, run the entrypoint with a None and the same thread id (config).

This assumes that the underlying error has been resolved and execution can proceed successfully.

When an entrypoint is defined with a checkpointer, it stores information between successive invocations on the same thread id in checkpoints.

This allows accessing the state from the previous invocation using the previous parameter.

By default, the previous parameter is the return value of the previous invocation.

entrypoint.final is a special primitive that can be returned from an entrypoint and allows decoupling the value that is saved in the checkpoint from the return value of the entrypoint.

The first value is the return value of the entrypoint, and the second value is the value that will be saved in the checkpoint. The type annotation is entrypoint.final[return_type, save_type].

A task represents a discrete unit of work, such as an API call or data processing step. It has two key characteristics:

Tasks are defined using the @task decorator, which wraps a regular Python function.

The outputs of tasks must be JSON-serializable to support checkpointing.

Tasks can only be called from within an entrypoint, another task, or a state graph node.

Tasks cannot be called directly from the main application code.

When you call a task, it returns immediately with a future object. A future is a placeholder for a result that will be available later.

To obtain the result of a task, you can either wait for it synchronously (using result()) or await it asynchronously (using await).

Tasks are useful in the following scenarios:

There are two key aspects to serialization in LangGraph:

These requirements are necessary for enabling checkpointing and workflow resumption. Use python primitives like dictionaries, lists, strings, numbers, and booleans to ensure that your inputs and outputs are serializable.

Serialization ensures that workflow state, such as task results and intermediate values, can be reliably saved and restored. This is critical for enabling human-in-the-loop interactions, fault tolerance, and parallel execution.

Providing non-serializable inputs or outputs will result in a runtime error when a workflow is configured with a checkpointer.

To utilize features like human-in-the-loop, any randomness should be encapsulated inside of tasks. This guarantees that when execution is halted (e.g., for human in the loop) and then resumed, it will follow the same sequence of steps, even if task results are non-deterministic.

LangGraph achieves this behavior by persisting task and subgraph results as they execute. A well-designed workflow ensures that resuming execution follows the same sequence of steps, allowing previously computed results to be retrieved correctly without having to re-execute them. This is particularly useful for long-running tasks or tasks with non-deterministic results, as it avoids repeating previously done work and allows resuming from essentially the same.

While different runs of a workflow can produce different results, resuming a specific run should always follow the same sequence of recorded steps. This allows LangGraph to efficiently look up task and subgraph results that were executed prior to the graph being interrupted and avoid recomputing them.

Idempotency ensures that running the same operation multiple times produces the same result. This helps prevent duplicate API calls and redundant processing if a step is rerun due to a failure. Always place API calls inside tasks functions for checkpointing, and design them to be idempotent in case of re-execution. Re-execution can occur if a task starts, but does not complete successfully. Then, if the workflow is resumed, the task will run again. Use idempotency keys or verify existing results to avoid duplication.

Encapsulate side effects (e.g., writing to a file, sending an email) in tasks to ensure they are not executed multiple times when resuming a workflow.

In this example, a side effect (writing to a file) is directly included in the workflow, so it will be executed a second time when resuming the workflow.

In this example, the side effect is encapsulated in a task, ensuring consistent execution upon resumption.

Operations that might give different results each time (like getting current time or random numbers) should be encapsulated in tasks to ensure that on resume, the same result is returned.

This is especially important when using human-in-the-loop workflows with multiple interrupts calls. LangGraph keeps a list of resume values for each task/entrypoint. When an interrupt is encountered, it's matched with the corresponding resume value. This matching is strictly index-based, so the order of the resume values should match the order of the interrupts.

If order of execution is not maintained when resuming, one interrupt call may be matched with the wrong resume value, leading to incorrect results.

Please read the section on determinism for more details.

In this example, the workflow uses the current time to determine which task to execute. This is non-deterministic because the result of the workflow depends on the time at which it is executed.

In this example, the workflow uses the input t0 to determine which task to execute. This is deterministic because the result of the workflow depends only on the input.

**Examples:**

Example 1 (python):
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import interrupt

@task
def write_essay(topic: str) -> str:
    """Write an essay about the given topic."""
    time.sleep(1) # A placeholder for a long-running task.
    return f"An essay about topic: {topic}"

@entrypoint(checkpointer=InMemorySaver())
def workflow(topic: str) -> dict:
    """A simple workflow that writes an essay and asks for a review."""
    essay = write_essay("cat").result()
    is_approved = interrupt({
        # Any json-serializable payload provided to interrupt as argument.
        # It will be surfaced on the client side as an Interrupt when streaming data
        # from the workflow.
        "essay": essay, # The essay we want reviewed.
        # We can add any additional information that we need.
        # For example, introduce a key called "action" with some instructions.
        "action": "Please approve/reject the essay",
    })

    return {
        "essay": essay, # The essay that was generated
        "is_approved": is_approved, # Response from HIL
    }
```

Example 2 (python):
```python
import time
import uuid
from langgraph.func import entrypoint, task
from langgraph.types import interrupt
from langgraph.checkpoint.memory import InMemorySaver


@task
def write_essay(topic: str) -> str:
    """Write an essay about the given topic."""
    time.sleep(1)  # This is a placeholder for a long-running task.
    return f"An essay about topic: {topic}"

@entrypoint(checkpointer=InMemorySaver())
def workflow(topic: str) -> dict:
    """A simple workflow that writes an essay and asks for a review."""
    essay = write_essay("cat").result()
    is_approved = interrupt(
        {
            # Any json-serializable payload provided to interrupt as argument.
            # It will be surfaced on the client side as an Interrupt when streaming data
            # from the workflow.
            "essay": essay,  # The essay we want reviewed.
            # We can add any additional information that we need.
            # For example, introduce a key called "action" with some instructions.
            "action": "Please approve/reject the essay",
        }
    )
    return {
        "essay": essay,  # The essay that was generated
        "is_approved": is_approved,  # Response from HIL
    }


thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": thread_id}}
for item in workflow.stream("cat", config):
    print(item)
# > {'write_essay': 'An essay about topic: cat'}
# > {
# >     '__interrupt__': (
# >        Interrupt(
# >            value={
# >                'essay': 'An essay about topic: cat',
# >                'action': 'Please approve/reject the essay'
# >            },
# >            id='b9b2b9d788f482663ced6dc755c9e981'
# >        ),
# >    )
# > }
```

Example 3 (python):
```python
from langgraph.types import Command

# Get review from a user (e.g., via a UI)
# In this case, we're using a bool, but this can be any json-serializable value.
human_review = True

for item in workflow.stream(Command(resume=human_review), config):
    print(item)
```

Example 4 (unknown):
```unknown
{'workflow': {'essay': 'An essay about topic: cat', 'is_approved': False}}
```

---

## Memory¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/memory

**Contents:**
- Memory¶
- Short-term memory¶
  - Manage short-term memory¶
- Long-term memory¶
  - Memory types¶
    - Semantic memory¶
      - Profile¶
      - Collection¶
    - Episodic memory¶
    - Procedural memory¶

Memory is a system that remembers information about previous interactions. For AI agents, memory is crucial because it lets them remember previous interactions, learn from feedback, and adapt to user preferences. As agents tackle more complex tasks with numerous user interactions, this capability becomes essential for both efficiency and user satisfaction.

This conceptual guide covers two types of memory, based on their recall scope:

Short-term memory, or thread-scoped memory, tracks the ongoing conversation by maintaining message history within a session. LangGraph manages short-term memory as a part of your agent's state. State is persisted to a database using a checkpointer so the thread can be resumed at any time. Short-term memory updates when the graph is invoked or a step is completed, and the State is read at the start of each step.

Long-term memory stores user-specific or application-level data across sessions and is shared across conversational threads. It can be recalled at any time and in any thread. Memories are scoped to any custom namespace, not just within a single thread ID. LangGraph provides stores (reference doc) to let you save and recall long-term memories.

Short-term memory lets your application remember previous interactions within a single thread or conversation. A thread organizes multiple interactions in a session, similar to the way email groups messages in a single conversation.

LangGraph manages short-term memory as part of the agent's state, persisted via thread-scoped checkpoints. This state can normally include the conversation history along with other stateful data, such as uploaded files, retrieved documents, or generated artifacts. By storing these in the graph's state, the bot can access the full context for a given conversation while maintaining separation between different threads.

Conversation history is the most common form of short-term memory, and long conversations pose a challenge to today's LLMs. A full history may not fit inside an LLM's context window, resulting in an irrecoverable error. Even if your LLM supports the full context length, most LLMs still perform poorly over long contexts. They get "distracted" by stale or off-topic content, all while suffering from slower response times and higher costs.

Chat models accept context using messages, which include developer provided instructions (a system message) and user inputs (human messages). In chat applications, messages alternate between human inputs and model responses, resulting in a list of messages that grows longer over time. Because context windows are limited and token-rich message lists can be costly, many applications can benefit from using techniques to manually remove or forget stale information.

For more information on common techniques for managing messages, see the Add and manage memory guide.

Long-term memory in LangGraph allows systems to retain information across different conversations or sessions. Unlike short-term memory, which is thread-scoped, long-term memory is saved within custom "namespaces."

Long-term memory is a complex challenge without a one-size-fits-all solution. However, the following questions provide a framework to help you navigate the different techniques:

What is the type of memory? Humans use memories to remember facts (semantic memory), experiences (episodic memory), and rules (procedural memory). AI agents can use memory in the same ways. For example, AI agents can use memory to remember specific facts about a user to accomplish a task.

When do you want to update memories? Memory can be updated as part of an agent's application logic (e.g., "on the hot path"). In this case, the agent typically decides to remember facts before responding to a user. Alternatively, memory can be updated as a background task (logic that runs in the background / asynchronously and generates memories). We explain the tradeoffs between these approaches in the section below.

Different applications require various types of memory. Although the analogy isn't perfect, examining human memory types can be insightful. Some research (e.g., the CoALA paper) have even mapped these human memory types to those used in AI agents.

Semantic memory, both in humans and AI agents, involves the retention of specific facts and concepts. In humans, it can include information learned in school and the understanding of concepts and their relationships. For AI agents, semantic memory is often used to personalize applications by remembering facts or concepts from past interactions.

Semantic memory is different from "semantic search," which is a technique for finding similar content using "meaning" (usually as embeddings). Semantic memory is a term from psychology, referring to storing facts and knowledge, while semantic search is a method for retrieving information based on meaning rather than exact matches.

Semantic memories can be managed in different ways. For example, memories can be a single, continuously updated "profile" of well-scoped and specific information about a user, organization, or other entity (including the agent itself). A profile is generally just a JSON document with various key-value pairs you've selected to represent your domain.

When remembering a profile, you will want to make sure that you are updating the profile each time. As a result, you will want to pass in the previous profile and ask the model to generate a new profile (or some JSON patch to apply to the old profile). This can be become error-prone as the profile gets larger, and may benefit from splitting a profile into multiple documents or strict decoding when generating documents to ensure the memory schemas remains valid.

Alternatively, memories can be a collection of documents that are continuously updated and extended over time. Each individual memory can be more narrowly scoped and easier to generate, which means that you're less likely to lose information over time. It's easier for an LLM to generate new objects for new information than reconcile new information with an existing profile. As a result, a document collection tends to lead to higher recall downstream.

However, this shifts some complexity memory updating. The model must now delete or update existing items in the list, which can be tricky. In addition, some models may default to over-inserting and others may default to over-updating. See the Trustcall package for one way to manage this and consider evaluation (e.g., with a tool like LangSmith) to help you tune the behavior.

Working with document collections also shifts complexity to memory search over the list. The Store currently supports both semantic search and filtering by content.

Finally, using a collection of memories can make it challenging to provide comprehensive context to the model. While individual memories may follow a specific schema, this structure might not capture the full context or relationships between memories. As a result, when using these memories to generate responses, the model may lack important contextual information that would be more readily available in a unified profile approach.

Regardless of memory management approach, the central point is that the agent will use the semantic memories to ground its responses, which often leads to more personalized and relevant interactions.

Episodic memory, in both humans and AI agents, involves recalling past events or actions. The CoALA paper frames this well: facts can be written to semantic memory, whereas experiences can be written to episodic memory. For AI agents, episodic memory is often used to help an agent remember how to accomplish a task.

In practice, episodic memories are often implemented through few-shot example prompting, where agents learn from past sequences to perform tasks correctly. Sometimes it's easier to "show" than "tell" and LLMs learn well from examples. Few-shot learning lets you "program" your LLM by updating the prompt with input-output examples to illustrate the intended behavior. While various best-practices can be used to generate few-shot examples, often the challenge lies in selecting the most relevant examples based on user input.

Note that the memory store is just one way to store data as few-shot examples. If you want to have more developer involvement, or tie few-shots more closely to your evaluation harness, you can also use a LangSmith Dataset to store your data. Then dynamic few-shot example selectors can be used out-of-the box to achieve this same goal. LangSmith will index the dataset for you and enable retrieval of few shot examples that are most relevant to the user input based upon keyword similarity (using a BM25-like algorithm for keyword based similarity).

See this how-to video for example usage of dynamic few-shot example selection in LangSmith. Also, see this blog post showcasing few-shot prompting to improve tool calling performance and this blog post using few-shot example to align an LLMs to human preferences.

Procedural memory, in both humans and AI agents, involves remembering the rules used to perform tasks. In humans, procedural memory is like the internalized knowledge of how to perform tasks, such as riding a bike via basic motor skills and balance. Episodic memory, on the other hand, involves recalling specific experiences, such as the first time you successfully rode a bike without training wheels or a memorable bike ride through a scenic route. For AI agents, procedural memory is a combination of model weights, agent code, and agent's prompt that collectively determine the agent's functionality.

In practice, it is fairly uncommon for agents to modify their model weights or rewrite their code. However, it is more common for agents to modify their own prompts.

One effective approach to refining an agent's instructions is through "Reflection" or meta-prompting. This involves prompting the agent with its current instructions (e.g., the system prompt) along with recent conversations or explicit user feedback. The agent then refines its own instructions based on this input. This method is particularly useful for tasks where instructions are challenging to specify upfront, as it allows the agent to learn and adapt from its interactions.

For example, we built a Tweet generator using external feedback and prompt re-writing to produce high-quality paper summaries for Twitter. In this case, the specific summarization prompt was difficult to specify a priori, but it was fairly easy for a user to critique the generated Tweets and provide feedback on how to improve the summarization process.

The below pseudo-code shows how you might implement this with the LangGraph memory store, using the store to save a prompt, the update_instructions node to get the current prompt (as well as feedback from the conversation with the user captured in state["messages"]), update the prompt, and save the new prompt back to the store. Then, the call_model get the updated prompt from the store and uses it to generate a response.

There are two primary methods for agents to write memories: "in the hot path" and "in the background".

Creating memories during runtime offers both advantages and challenges. On the positive side, this approach allows for real-time updates, making new memories immediately available for use in subsequent interactions. It also enables transparency, as users can be notified when memories are created and stored.

However, this method also presents challenges. It may increase complexity if the agent requires a new tool to decide what to commit to memory. In addition, the process of reasoning about what to save to memory can impact agent latency. Finally, the agent must multitask between memory creation and its other responsibilities, potentially affecting the quantity and quality of memories created.

As an example, ChatGPT uses a save_memories tool to upsert memories as content strings, deciding whether and how to use this tool with each user message. See our memory-agent template as an reference implementation.

Creating memories as a separate background task offers several advantages. It eliminates latency in the primary application, separates application logic from memory management, and allows for more focused task completion by the agent. This approach also provides flexibility in timing memory creation to avoid redundant work.

However, this method has its own challenges. Determining the frequency of memory writing becomes crucial, as infrequent updates may leave other threads without new context. Deciding when to trigger memory formation is also important. Common strategies include scheduling after a set time period (with rescheduling if new events occur), using a cron schedule, or allowing manual triggers by users or the application logic.

See our memory-service template as an reference implementation.

LangGraph stores long-term memories as JSON documents in a store. Each memory is organized under a custom namespace (similar to a folder) and a distinct key (like a file name). Namespaces often include user or org IDs or other labels that makes it easier to organize information. This structure enables hierarchical organization of memories. Cross-namespace searching is then supported through content filters.

For more information about the memory store, see the Persistence guide.

**Examples:**

Example 1 (python):
```python
# Node that *uses* the instructions
def call_model(state: State, store: BaseStore):
    namespace = ("agent_instructions", )
    instructions = store.get(namespace, key="agent_a")[0]
    # Application logic
    prompt = prompt_template.format(instructions=instructions.value["instructions"])
    ...

# Node that updates instructions
def update_instructions(state: State, store: BaseStore):
    namespace = ("instructions",)
    current_instructions = store.search(namespace)[0]
    # Memory logic
    prompt = prompt_template.format(instructions=current_instructions.value["instructions"], conversation=state["messages"])
    output = llm.invoke(prompt)
    new_instructions = output['new_instructions']
    store.put(("agent_instructions",), "agent_a", {"instructions": new_instructions})
    ...
```

Example 2 (python):
```python
from langgraph.store.memory import InMemoryStore


def embed(texts: list[str]) -> list[list[float]]:
    # Replace with an actual embedding function or LangChain embeddings object
    return [[1.0, 2.0] * len(texts)]


# InMemoryStore saves data to an in-memory dictionary. Use a DB-backed store in production use.
store = InMemoryStore(index={"embed": embed, "dims": 2})
user_id = "my-user"
application_context = "chitchat"
namespace = (user_id, application_context)
store.put(
    namespace,
    "a-memory",
    {
        "rules": [
            "User likes short, direct language",
            "User only speaks English & python",
        ],
        "my-key": "my-value",
    },
)
# get the "memory" by ID
item = store.get(namespace, "a-memory")
# search for "memories" within this namespace, filtering on content equivalence, sorted by vector similarity
items = store.search(
    namespace, filter={"my-key": "my-value"}, query="language preferences"
)
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/concepts/langgraph_studio/

---

## Template Applications¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/template_applications/

**Contents:**
- Template Applications¶
- Install the LangGraph CLI¶
- Available Templates¶
- 🌱 Create a LangGraph App¶
- Next Steps¶

Templates are open source reference applications designed to help you get started quickly when building with LangGraph. They provide working examples of common agentic workflows that can be customized to your needs.

You can create an application from a template using the LangGraph CLI.

Or via uv (recommended):

To create a new app from a template, use the langgraph new command.

Or via uv (recommended):

Review the README.md file in the root of your new LangGraph app for more information about the template and how to customize it.

After configuring the app properly and adding your API keys, you can start the app using the LangGraph CLI:

Or via uv (recommended):

Missing Local Package?

If you are not using uv and run into a "ModuleNotFoundError" or "ImportError", even after installing the local package (pip install -e .), it is likely the case that you need to install the CLI into your local virtual environment to make the CLI "aware" of the local package. You can do this by running python -m pip install "langgraph-cli[inmem]" and re-activating your virtual environment before running langgraph dev.

See the following guides for more information on how to deploy your app:

**Examples:**

Example 1 (unknown):
```unknown
pip install "langgraph-cli[inmem]" --upgrade
```

Example 2 (unknown):
```unknown
uvx --from "langgraph-cli[inmem]" langgraph dev --help
```

Example 3 (unknown):
```unknown
langgraph new
```

Example 4 (unknown):
```unknown
uvx --from "langgraph-cli[inmem]" langgraph new
```

---

## Overview¶

**URL:** https://langchain-ai.github.io/langgraph/concepts/why-langgraph/

**Contents:**
- Overview¶
- Learn LangGraph basics¶

LangGraph is built for developers who want to build powerful, adaptable AI agents. Developers choose LangGraph for:

To get acquainted with LangGraph's key concepts and features, complete the following LangGraph basics tutorials series:

In completing this series of tutorials, you will build a support chatbot in LangGraph that can:

---
