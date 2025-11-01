# Langgraph - Workflows

**Pages:** 28

---

## 

**URL:** https://langchain-ai.github.io/langgraph/cloud/how-tos/stream_events/

---

## Add human-in-the-loop controls¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/get-started/4-human-in-the-loop/

**Contents:**
- Add human-in-the-loop controls¶
- 1. Add the human_assistance tool¶
- 2. Compile the graph¶
- 3. Visualize the graph (optional)¶
- 4. Prompt the chatbot¶
- 5. Resume execution¶
- Next steps¶

Agents can be unreliable and may need human input to successfully accomplish tasks. Similarly, for some actions, you may want to require human approval before running to ensure that everything is running as intended.

LangGraph's persistence layer supports human-in-the-loop workflows, allowing execution to pause and resume based on user feedback. The primary interface to this functionality is the interrupt function. Calling interrupt inside a node will pause execution. Execution can be resumed, together with new input from a human, by passing in a Command.

interrupt is ergonomically similar to Python's built-in input(), with some caveats.

This tutorial builds on Add memory.

Starting with the existing code from the Add memory to the chatbot tutorial, add the human_assistance tool to the chatbot. This tool uses interrupt to receive information from a human.

Let's first select a chat model:

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["OPENAI_API_KEY"] = "sk-..." llm = init_chat_model("openai:gpt-4.1")

👉 Read the OpenAI integration docs

pip install -U "langchain[anthropic]" import os from langchain.chat_models import init_chat_model os.environ["ANTHROPIC_API_KEY"] = "sk-..." llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

👉 Read the Anthropic integration docs

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["AZURE_OPENAI_API_KEY"] = "..." os.environ["AZURE_OPENAI_ENDPOINT"] = "..." os.environ["OPENAI_API_VERSION"] = "2025-03-01-preview" llm = init_chat_model( "azure_openai:gpt-4.1", azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"], )

👉 Read the Azure integration docs

pip install -U "langchain[google-genai]" import os from langchain.chat_models import init_chat_model os.environ["GOOGLE_API_KEY"] = "..." llm = init_chat_model("google_genai:gemini-2.0-flash")

👉 Read the Google GenAI integration docs

pip install -U "langchain[aws]" from langchain.chat_models import init_chat_model # Follow the steps here to configure your credentials: # https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html llm = init_chat_model( "anthropic.claude-3-5-sonnet-20240620-v1:0", model_provider="bedrock_converse", )

👉 Read the AWS Bedrock integration docs

We can now incorporate it into our StateGraph with an additional tool:

For more information and examples of human-in-the-loop workflows, see Human-in-the-loop.

We compile the graph with a checkpointer, as before:

Visualizing the graph, you get the same layout as before – just with the added tool!

Now, prompt the chatbot with a question that will engage the new human_assistance tool:

The chatbot generated a tool call, but then execution has been interrupted. If you inspect the graph state, you see that it stopped at the tools node:

Take a closer look at the human_assistance tool:

Similar to Python's built-in input() function, calling interrupt inside the tool will pause execution. Progress is persisted based on the checkpointer; so if it is persisting with Postgres, it can resume at any time as long as the database is alive. In this example, it is persisting with the in-memory checkpointer and can resume any time if the Python kernel is running.

To resume execution, pass a Command object containing data expected by the tool. The format of this data can be customized based on needs.

For this example, use a dict with a key "data":

The input has been received and processed as a tool message. Review this call's LangSmith trace to see the exact work that was done in the above call. Notice that the state is loaded in the first step so that our chatbot can continue where it left off.

Congratulations! You've used an interrupt to add human-in-the-loop execution to your chatbot, allowing for human oversight and intervention when needed. This opens up the potential UIs you can create with your AI systems. Since you have already added a checkpointer, as long as the underlying persistence layer is running, the graph can be paused indefinitely and resumed at any time as if nothing had happened.

Check out the code snippet below to review the graph from this tutorial:

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["OPENAI_API_KEY"] = "sk-..." llm = init_chat_model("openai:gpt-4.1")

👉 Read the OpenAI integration docs

pip install -U "langchain[anthropic]" import os from langchain.chat_models import init_chat_model os.environ["ANTHROPIC_API_KEY"] = "sk-..." llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

👉 Read the Anthropic integration docs

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["AZURE_OPENAI_API_KEY"] = "..." os.environ["AZURE_OPENAI_ENDPOINT"] = "..." os.environ["OPENAI_API_VERSION"] = "2025-03-01-preview" llm = init_chat_model( "azure_openai:gpt-4.1", azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"], )

👉 Read the Azure integration docs

pip install -U "langchain[google-genai]" import os from langchain.chat_models import init_chat_model os.environ["GOOGLE_API_KEY"] = "..." llm = init_chat_model("google_genai:gemini-2.0-flash")

👉 Read the Google GenAI integration docs

pip install -U "langchain[aws]" from langchain.chat_models import init_chat_model # Follow the steps here to configure your credentials: # https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html llm = init_chat_model( "anthropic.claude-3-5-sonnet-20240620-v1:0", model_provider="bedrock_converse", )

👉 Read the AWS Bedrock integration docs

API Reference: TavilySearch | tool | InMemorySaver | StateGraph | START | END | add_messages | ToolNode | tools_condition | Command | interrupt

So far, the tutorial examples have relied on a simple state with one entry: a list of messages. You can go far with this simple state, but if you want to define complex behavior without relying on the message list, you can add additional fields to the state.

**Examples:**

Example 1 (unknown):
```unknown
pip install -U "langchain[openai]"
```

Example 2 (python):
```python
import os
from langchain.chat_models import init_chat_model

os.environ["OPENAI_API_KEY"] = "sk-..."

llm = init_chat_model("openai:gpt-4.1")
```

Example 3 (unknown):
```unknown
pip install -U "langchain[anthropic]"
```

Example 4 (python):
```python
import os
from langchain.chat_models import init_chat_model

os.environ["ANTHROPIC_API_KEY"] = "sk-..."

llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/cloud/how-tos/human_in_the_loop_time_travel/

---

## Functional API

**URL:** https://langchain-ai.github.io/langgraph/reference/func/

**Contents:**
- Functional API
- entrypoint ¶
      - Function signature¶
      - Injectable parameters¶
      - State management¶
  - final dataclass ¶
    - value instance-attribute ¶
    - save instance-attribute ¶
  - __init__ ¶
  - __call__ ¶

Define a LangGraph workflow using the entrypoint decorator.

Define a LangGraph task using the task decorator.

Bases: Generic[ContextT]

Define a LangGraph workflow using the entrypoint decorator.

The decorated function must accept a single parameter, which serves as the input to the function. This input parameter can be of any type. Use a dictionary to pass multiple parameters to the function.

The decorated function can request access to additional parameters that will be injected automatically at run time. These parameters include:

The entrypoint decorator can be applied to sync functions or async functions.

The previous parameter can be used to access the return value of the previous invocation of the entrypoint on the same thread id. This value is only available when a checkpointer is provided.

If you want previous to be different from the return value, you can use the entrypoint.final object to return a value while saving a different value to the checkpoint.

Specify a checkpointer to create a workflow that can persist its state across runs.

A generalized key-value store. Some implementations may support semantic search capabilities through an optional index configuration.

A cache to use for caching the results of the workflow.

Specifies the schema for the context object that will be passed to the workflow.

A cache policy to use for caching the results of the workflow.

A retry policy (or list of policies) to use for the workflow in case of a failure.

config_schema Deprecated

The config_schema parameter is deprecated in v0.6.0 and support will be removed in v2.0.0. Please use context_schema instead to specify the schema for run-scoped context.

When a checkpointer is enabled the function can access the previous return value of the previous invocation on the same thread id.

The entrypoint.final object allows you to return a value while saving a different value to the checkpoint. This value will be accessible in the next invocation of the entrypoint via the previous parameter, as long as the same thread id is used.

A primitive that can be returned from an entrypoint.

Initialize the entrypoint decorator.

Convert a function into a Pregel graph.

A primitive that can be returned from an entrypoint.

This primitive allows to save a value to the checkpointer distinct from the return value from the entrypoint.

Value to return. A value will always be returned even if it is None.

The value for the state for the next checkpoint.

Value to return. A value will always be returned even if it is None.

The value for the state for the next checkpoint.

A value will always be saved even if it is None.

Initialize the entrypoint decorator.

Convert a function into a Pregel graph.

The function to convert. Support both sync and async functions.

Define a LangGraph task using the task decorator.

Requires python 3.11 or higher for async functions

The task decorator supports both sync and async functions. To use async functions, ensure that you are using Python 3.11 or higher.

Tasks can only be called from within an entrypoint or from within a StateGraph. A task can be called like a regular function with the following differences:

An optional name for the task. If not provided, the function name will be used.

An optional retry policy (or list of policies) to use for the task in case of a failure.

An optional cache policy to use for the task. This allows caching of the task results.

A callable function when used as a decorator.

**Examples:**

Example 1 (python):
```python
import time

from langgraph.func import entrypoint, task
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver

@task
def compose_essay(topic: str) -> str:
    time.sleep(1.0)  # Simulate slow operation
    return f"An essay about {topic}"

@entrypoint(checkpointer=InMemorySaver())
def review_workflow(topic: str) -> dict:
    """Manages the workflow for generating and reviewing an essay.

    The workflow includes:
    1. Generating an essay about the given topic.
    2. Interrupting the workflow for human review of the generated essay.

    Upon resuming the workflow, compose_essay task will not be re-executed
    as its result is cached by the checkpointer.

    Args:
        topic: The subject of the essay.

    Returns:
        dict: A dictionary containing the generated essay and the human review.
    """
    essay_future = compose_essay(topic)
    essay = essay_future.result()
    human_review = interrupt({
        "question": "Please provide a review",
        "essay": essay
    })
    return {
        "essay": essay,
        "review": human_review,
    }

# Example configuration for the workflow
config = {
    "configurable": {
        "thread_id": "some_thread"
    }
}

# Topic for the essay
topic = "cats"

# Stream the workflow to generate the essay and await human review
for result in review_workflow.stream(topic, config):
    print(result)

# Example human review provided after the interrupt
human_review = "This essay is great."

# Resume the workflow with the provided human review
for result in review_workflow.stream(Command(resume=human_review), config):
    print(result)
```

Example 2 (python):
```python
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver

from langgraph.func import entrypoint


@entrypoint(checkpointer=InMemorySaver())
def my_workflow(input_data: str, previous: Optional[str] = None) -> str:
    return "world"


config = {"configurable": {"thread_id": "some_thread"}}
my_workflow.invoke("hello", config)
```

Example 3 (python):
```python
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from langgraph.func import entrypoint


@entrypoint(checkpointer=InMemorySaver())
def my_workflow(
    number: int,
    *,
    previous: Any = None,
) -> entrypoint.final[int, int]:
    previous = previous or 0
    # This will return the previous value to the caller, saving
    # 2 * number to the checkpoint, which will be used in the next invocation
    # for the `previous` parameter.
    return entrypoint.final(value=previous, save=2 * number)


config = {"configurable": {"thread_id": "some_thread"}}

my_workflow.invoke(3, config)  # 0 (previous was None)
my_workflow.invoke(1, config)  # 6 (previous was 3 * 2 from the previous invocation)
```

Example 4 (python):
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint


@entrypoint(checkpointer=InMemorySaver())
def my_workflow(
    number: int,
    *,
    previous: Any = None,
) -> entrypoint.final[int, int]:
    previous = previous or 0
    # This will return the previous value to the caller, saving
    # 2 * number to the checkpoint, which will be used in the next invocation
    # for the `previous` parameter.
    return entrypoint.final(value=previous, save=2 * number)


config = {"configurable": {"thread_id": "1"}}

my_workflow.invoke(3, config)  # 0 (previous was None)
my_workflow.invoke(1, config)  # 6 (previous was 3 * 2 from the previous invocation)
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/how-tos/branching/

---

## 

**URL:** https://langchain-ai.github.io/langgraph/cloud/reference/cli/

---

## Use the functional API¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/use-functional-api/

**Contents:**
- Use the functional API¶
- Creating a simple workflow¶
- Parallel execution¶
- Calling graphs¶
- Call other entrypoints¶
- Streaming¶
- Retry policy¶
- Caching Tasks¶
- Resuming after an error¶
- Human-in-the-loop¶

The Functional API allows you to add LangGraph's key features — persistence, memory, human-in-the-loop, and streaming — to your applications with minimal changes to your existing code.

For conceptual information on the functional API, see Functional API.

When defining an entrypoint, input is restricted to the first argument of the function. To pass multiple inputs, you can use a dictionary.

This example demonstrates how to use the @task and @entrypoint decorators syntactically. Given that a checkpointer is provided, the workflow results will be persisted in the checkpointer.

Tasks can be executed in parallel by invoking them concurrently and waiting for the results. This is useful for improving performance in IO bound tasks (e.g., calling APIs for LLMs).

This example demonstrates how to run multiple LLM calls in parallel using @task. Each call generates a paragraph on a different topic, and results are joined into a single text output.

This example uses LangGraph's concurrency model to improve execution time, especially when tasks involve I/O like LLM completions.

The Functional API and the Graph API can be used together in the same application as they share the same underlying runtime.

API Reference: entrypoint | StateGraph

You can call other entrypoints from within an entrypoint or a task.

The Functional API uses the same streaming mechanism as the Graph API. Please read the streaming guide section for more details.

Example of using the streaming API to stream both updates and custom data.

API Reference: entrypoint | InMemorySaver | get_stream_writer

Async with Python < 3.11

If using Python < 3.11 and writing async code, using get_stream_writer() will not work. Instead please use the StreamWriter class directly. See Async with Python < 3.11 for more details.

API Reference: InMemorySaver | entrypoint | task | RetryPolicy

API Reference: entrypoint | task

API Reference: InMemorySaver | entrypoint | task | StreamWriter

When we resume execution, we won't need to re-run the slow_task as its result is already saved in the checkpoint.

The functional API supports human-in-the-loop workflows using the interrupt function and the Command primitive.

We will create three tasks:

API Reference: entrypoint | task | Command | interrupt

We can now compose these tasks in an entrypoint:

API Reference: InMemorySaver

interrupt() is called inside a task, enabling a human to review and edit the output of the previous task. The results of prior tasks-- in this case step_1-- are persisted, so that they are not run again following the interrupt.

Let's send in a query string:

Note that we've paused with an interrupt after step_1. The interrupt provides instructions to resume the run. To resume, we issue a Command containing the data expected by the human_feedback task.

After resuming, the run proceeds through the remaining step and terminates as expected.

To review tool calls before execution, we add a review_tool_call function that calls interrupt. When this function is called, execution will be paused until we issue a command to resume it.

Given a tool call, our function will interrupt for human review. At that point we can either:

We can now update our entrypoint to review the generated tool calls. If a tool call is accepted or revised, we execute in the same way as before. Otherwise, we just append the ToolMessage supplied by the human. The results of prior tasks — in this case the initial model call — are persisted, so that they are not run again following the interrupt.

API Reference: InMemorySaver | add_messages | Command | interrupt

Short-term memory allows storing information across different invocations of the same thread id. See short-term memory for more details.

You can view and delete the information stored by the checkpointer.

Use entrypoint.final to decouple what is returned to the caller from what is persisted in the checkpoint. This is useful when:

API Reference: entrypoint | InMemorySaver

An example of a simple chatbot using the functional API and the InMemorySaver checkpointer. The bot is able to remember the previous conversation and continue from where it left off.

API Reference: BaseMessage | add_messages | entrypoint | task | InMemorySaver | ChatAnthropic

How to add thread-level persistence (functional API): Shows how to add thread-level persistence to a functional API workflow and implements a simple chatbot.

long-term memory allows storing information across different thread ids. This could be useful for learning information about a given user in one conversation and using it in another.

How to add cross-thread persistence (functional API): Shows how to add cross-thread persistence to a functional API workflow and implements a simple chatbot.

**Examples:**

Example 1 (python):
```python
@entrypoint(checkpointer=checkpointer)
def my_workflow(inputs: dict) -> int:
    value = inputs["value"]
    another_value = inputs["another_value"]
    ...

my_workflow.invoke({"value": 1, "another_value": 2})
```

Example 2 (python):
```python
import uuid
from langgraph.func import entrypoint, task
from langgraph.checkpoint.memory import InMemorySaver

# Task that checks if a number is even
@task
def is_even(number: int) -> bool:
    return number % 2 == 0

# Task that formats a message
@task
def format_message(is_even: bool) -> str:
    return "The number is even." if is_even else "The number is odd."

# Create a checkpointer for persistence
checkpointer = InMemorySaver()

@entrypoint(checkpointer=checkpointer)
def workflow(inputs: dict) -> str:
    """Simple workflow to classify a number."""
    even = is_even(inputs["number"]).result()
    return format_message(even).result()

# Run the workflow with a unique thread ID
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
result = workflow.invoke({"number": 7}, config=config)
print(result)
```

Example 3 (python):
```python
import uuid
from langchain.chat_models import init_chat_model
from langgraph.func import entrypoint, task
from langgraph.checkpoint.memory import InMemorySaver

llm = init_chat_model('openai:gpt-3.5-turbo')

# Task: generate essay using an LLM
@task
def compose_essay(topic: str) -> str:
    """Generate an essay about the given topic."""
    return llm.invoke([
        {"role": "system", "content": "You are a helpful assistant that writes essays."},
        {"role": "user", "content": f"Write an essay about {topic}."}
    ]).content

# Create a checkpointer for persistence
checkpointer = InMemorySaver()

@entrypoint(checkpointer=checkpointer)
def workflow(topic: str) -> str:
    """Simple workflow that generates an essay with an LLM."""
    return compose_essay(topic).result()

# Execute the workflow
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
result = workflow.invoke("the history of flight", config=config)
print(result)
```

Example 4 (python):
```python
@task
def add_one(number: int) -> int:
    return number + 1

@entrypoint(checkpointer=checkpointer)
def graph(numbers: list[int]) -> list[str]:
    futures = [add_one(i) for i in numbers]
    return [f.result() for f in futures]
```

---

## Python SDK Reference¶

**URL:** https://langchain-ai.github.io/langgraph/cloud/reference/sdk/python_sdk_ref/

**Contents:**
- Python SDK Reference¶
- LangGraphClient ¶
  - __aenter__ async ¶
  - __aexit__ async ¶
  - aclose async ¶
- HttpClient ¶
  - get async ¶
  - post async ¶
  - put async ¶
  - patch async ¶

The LangGraph client implementations connect to the LangGraph API.

This module provides both asynchronous (get_client(url="http://localhost:2024")) or LangGraphClient) and synchronous (get_sync_client(url="http://localhost:2024")) or SyncLanggraphClient) clients to interacting with the LangGraph API's core resources such as Assistants, Threads, Runs, and Cron jobs, as well as its persistent document Store.

Top-level client for LangGraph API.

Handle async requests to the LangGraph API.

Client for managing assistants in LangGraph.

Client for managing threads in LangGraph.

Client for managing runs in LangGraph.

Client for managing recurrent runs (cron jobs) in LangGraph.

Client for interacting with the graph's shared storage.

Synchronous client for interacting with the LangGraph API.

Handle synchronous requests to the LangGraph API.

Client for managing assistants in LangGraph synchronously.

Synchronous client for managing threads in LangGraph.

Synchronous client for managing runs in LangGraph.

Synchronous client for managing cron jobs in LangGraph.

A client for synchronous operations on a key-value store.

Create and configure a LangGraphClient.

Get a synchronous LangGraphClient instance.

Top-level client for LangGraph API.

Manages versioned configuration for your graphs.

Handles (potentially) multi-turn interactions, such as conversational threads.

Controls individual invocations of the graph.

Manages scheduled operations.

Interfaces with persistent, shared data storage.

Enter the async context manager.

Exit the async context manager.

Close the underlying HTTP client.

Enter the async context manager.

Exit the async context manager.

Close the underlying HTTP client.

Handle async requests to the LangGraph API.

Adds additional error messaging & content handling above the provided httpx client.

Underlying HTTPX async client.

Send a PATCH request.

Send a DELETE request.

Send a request that automatically reconnects to Location header.

Stream results using SSE.

Send a PATCH request.

Send a DELETE request.

Send a request that automatically reconnects to Location header.

Stream results using SSE.

Client for managing assistants in LangGraph.

This class provides methods to interact with assistants, which are versioned configurations of your graph.

Get an assistant by ID.

Get the graph of an assistant by ID.

Get the schemas of an assistant by ID.

Get the schemas of an assistant by ID.

Create a new assistant.

Search for assistants.

Count assistants matching filters.

List all versions of an assistant.

Change the version of an assistant.

Get an assistant by ID.

The ID of the assistant to get.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Get the graph of an assistant by ID.

The ID of the assistant to get the graph of.

Include graph representation of subgraphs. If an integer value is provided, only subgraphs with a depth less than or equal to the value will be included.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The graph information for the assistant in JSON format.

Get the schemas of an assistant by ID.

The ID of the assistant to get the schema of.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The graph schema for the assistant.

Get the schemas of an assistant by ID.

The ID of the assistant to get the schema of.

Optional namespace to filter by.

Whether to recursively get subgraphs.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The graph schema for the assistant.

Create a new assistant.

Useful when graph is configurable and you want to create different assistants based on different configurations.

The ID of the graph the assistant should use. The graph ID is normally set in your langgraph.json configuration.

Configuration to use for the graph.

Metadata to add to assistant.

Static context to add to the assistant.

Added in version 0.6.0

Assistant ID to use, will default to a random UUID if not provided.

How to handle duplicate creation. Defaults to 'raise' under the hood. Must be either 'raise' (raise error if duplicate), or 'do_nothing' (return existing assistant).

The name of the assistant. Defaults to 'Untitled' under the hood.

Optional custom headers to include with the request.

Optional description of the assistant. The description field is available for langgraph-api server version>=0.0.45

Optional query parameters to include with the request.

The created assistant.

Use this to point to a different graph, update the configuration, or change the metadata of an assistant.

The ID of the graph the assistant should use. The graph ID is normally set in your langgraph.json configuration. If None, assistant will keep pointing to same graph.

Configuration to use for the graph.

Static context to add to the assistant.

Added in version 0.6.0

Metadata to merge with existing assistant metadata.

The new name for the assistant.

Optional custom headers to include with the request.

Optional description of the assistant. The description field is available for langgraph-api server version>=0.0.45

Optional query parameters to include with the request.

The updated assistant.

The assistant ID to delete.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Search for assistants.

Metadata to filter by. Exact match filter for each KV pair.

The ID of the graph to filter by. The graph ID is normally set in your langgraph.json configuration.

The maximum number of results to return.

The number of results to skip.

The field to sort by.

The order to sort by.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

A list of assistants.

Count assistants matching filters.

Metadata to filter by. Exact match for each key/value.

Optional graph id to filter by.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Number of assistants matching the criteria.

List all versions of an assistant.

The assistant ID to get versions for.

Metadata to filter versions by. Exact match filter for each KV pair.

The maximum number of versions to return.

The number of versions to skip.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

A list of assistant versions.

Change the version of an assistant.

The assistant ID to delete.

The version to change to.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Client for managing threads in LangGraph.

A thread maintains the state of a graph across multiple interactions/invocations (aka runs). It accumulates and persists the graph's state, allowing for continuity between separate invocations of the graph.

Count threads matching filters.

Get the state of a thread.

Update the state of a thread.

Get the state history of a thread.

Get a stream of events for a thread.

The ID of the thread to get.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Metadata to add to thread.

ID of thread. If None, ID will be a randomly generated UUID.

How to handle duplicate creation. Defaults to 'raise' under the hood. Must be either 'raise' (raise error if duplicate), or 'do_nothing' (return existing thread).

Apply a list of supersteps when creating a thread, each containing a sequence of updates. Each update has values or command and as_node. Used for copying a thread between deployments.

Optional graph ID to associate with the thread.

Optional time-to-live in minutes for the thread. You can pass an integer (minutes) or a mapping with keys ttl and optional strategy (defaults to "delete").

Optional custom headers to include with the request.

Optional query parameters to include with the request.

ID of thread to update.

Metadata to merge with existing thread metadata.

Optional time-to-live in minutes for the thread. You can pass an integer (minutes) or a mapping with keys ttl and optional strategy (defaults to "delete").

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The ID of the thread to delete.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Thread metadata to filter on.

State values to filter on.

List of thread IDs to filter by.

Thread status to filter on. Must be one of 'idle', 'busy', 'interrupted' or 'error'.

Limit on number of threads to return.

Offset in threads table to start search from.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

List of the threads matching the search parameters.

Count threads matching filters.

Thread metadata to filter on.

State values to filter on.

Thread status to filter on.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Number of threads matching the criteria.

The ID of the thread to copy.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Get the state of a thread.

The ID of the thread to get the state of.

The checkpoint to get the state of.

(deprecated) The checkpoint ID to get the state of.

Include subgraphs states.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The thread of the state.

Update the state of a thread.

The ID of the thread to update.

The values to update the state with.

Update the state as if this node had just executed.

The checkpoint to update the state of.

(deprecated) The checkpoint ID to update the state of.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Response after updating a thread's state.

client = get_client(url="http://localhost:2024) response = await client.threads.update_state( thread_id="my_thread_id", values={"messages":[{"role": "user", "content": "hello!"}]}, as_node="my_node", ) print(response) ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- { 'checkpoint': { 'thread_id': 'e2496803-ecd5-4e0c-a779-3226296181c2', 'checkpoint_ns': '', 'checkpoint_id': '1ef4a9b8-e6fb-67b1-8001-abd5184439d1', 'checkpoint_map': {} } }

Get the state history of a thread.

The ID of the thread to get the state history for.

Return states for this subgraph. If empty defaults to root.

The maximum number of states to return.

Return states before this checkpoint.

Filter states by metadata key-value pairs.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The state history of the thread.

Get a stream of events for a thread.

The ID of the thread to get the stream for.

The ID of the last event to get.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

An iterator of stream parts.

Client for managing runs in LangGraph.

A run is a single assistant invocation with optional input, config, context, and metadata. This client manages runs, which can be stateful (on threads) or stateless.

Create a run and stream the results.

Create a background run.

Create a batch of stateless background runs.

Create a run, wait until it finishes and return the final state.

Block until a run is done. Returns the final state of the thread.

Stream output from a run in real-time, until the run is done.

Create a run and stream the results.

the thread ID to assign to the thread. If None will create a stateless run.

The assistant ID or graph name to stream from. If using graph name, will default to first assistant created from that graph.

The input to the graph.

A command to execute. Cannot be combined with input.

The stream mode(s) to use.

Whether to stream output from subgraphs.

Whether the stream is considered resumable. If true, the stream can be resumed and replayed in its entirety even after disconnection.

Metadata to assign to the run.

The configuration for the assistant.

Static context to add to the assistant.

Added in version 0.6.0

The checkpoint to resume from.

(deprecated) Whether to checkpoint during the run (or only at the end/interruption).

Nodes to interrupt immediately before they get executed.

Nodes to Nodes to interrupt immediately after they get executed.

Feedback keys to assign to run.

The disconnect mode to use. Must be one of 'cancel' or 'continue'.

Whether to delete or keep the thread created for a stateless run. Must be one of 'delete' or 'keep'.

Webhook to call after LangGraph API call is done.

Multitask strategy to use. Must be one of 'reject', 'interrupt', 'rollback', or 'enqueue'.

How to handle missing thread. Defaults to 'reject'. Must be either 'reject' (raise error if missing), or 'create' (create new thread).

The number of seconds to wait before starting the run. Use to schedule future runs.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Callback when a run is created.

The durability to use for the run. Values are "sync", "async", or "exit". "async" means checkpoints are persisted async while next graph step executes, replaces checkpoint_during=True "sync" means checkpoints are persisted sync after graph step executes, replaces checkpoint_during=False "exit" means checkpoints are only persisted when the run exits, does not save intermediate steps

Asynchronous iterator of stream results.

Create a background run.

the thread ID to assign to the thread. If None will create a stateless run.

The assistant ID or graph name to stream from. If using graph name, will default to first assistant created from that graph.

The input to the graph.

A command to execute. Cannot be combined with input.

The stream mode(s) to use.

Whether to stream output from subgraphs.

Whether the stream is considered resumable. If true, the stream can be resumed and replayed in its entirety even after disconnection.

Metadata to assign to the run.

The configuration for the assistant.

Static context to add to the assistant.

Added in version 0.6.0

The checkpoint to resume from.

(deprecated) Whether to checkpoint during the run (or only at the end/interruption).

Nodes to interrupt immediately before they get executed.

Nodes to Nodes to interrupt immediately after they get executed.

Webhook to call after LangGraph API call is done.

Multitask strategy to use. Must be one of 'reject', 'interrupt', 'rollback', or 'enqueue'.

Whether to delete or keep the thread created for a stateless run. Must be one of 'delete' or 'keep'.

How to handle missing thread. Defaults to 'reject'. Must be either 'reject' (raise error if missing), or 'create' (create new thread).

The number of seconds to wait before starting the run. Use to schedule future runs.

Optional custom headers to include with the request.

Optional callback to call when a run is created.

The durability to use for the run. Values are "sync", "async", or "exit". "async" means checkpoints are persisted async while next graph step executes, replaces checkpoint_during=True "sync" means checkpoints are persisted sync after graph step executes, replaces checkpoint_during=False "exit" means checkpoints are only persisted when the run exits, does not save intermediate steps

The created background run.

Create a batch of stateless background runs.

Create a run, wait until it finishes and return the final state.

the thread ID to create the run on. If None will create a stateless run.

The assistant ID or graph name to run. If using graph name, will default to first assistant created from that graph.

The input to the graph.

A command to execute. Cannot be combined with input.

Metadata to assign to the run.

The configuration for the assistant.

Static context to add to the assistant.

Added in version 0.6.0

The checkpoint to resume from.

(deprecated) Whether to checkpoint during the run (or only at the end/interruption).

Nodes to interrupt immediately before they get executed.

Nodes to Nodes to interrupt immediately after they get executed.

Webhook to call after LangGraph API call is done.

The disconnect mode to use. Must be one of 'cancel' or 'continue'.

Whether to delete or keep the thread created for a stateless run. Must be one of 'delete' or 'keep'.

Multitask strategy to use. Must be one of 'reject', 'interrupt', 'rollback', or 'enqueue'.

How to handle missing thread. Defaults to 'reject'. Must be either 'reject' (raise error if missing), or 'create' (create new thread).

The number of seconds to wait before starting the run. Use to schedule future runs.

Optional custom headers to include with the request.

Optional callback to call when a run is created.

The durability to use for the run. Values are "sync", "async", or "exit". "async" means checkpoints are persisted async while next graph step executes, replaces checkpoint_during=True "sync" means checkpoints are persisted sync after graph step executes, replaces checkpoint_during=False "exit" means checkpoints are only persisted when the run exits, does not save intermediate steps

The output of the run.

The thread ID to list runs for.

The maximum number of results to return.

The number of results to skip.

The status of the run to filter by.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The runs for the thread.

The thread ID to get.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The thread ID to cancel.

The run ID to cancel.

Whether to wait until run has completed.

Action to take when cancelling the run. Possible values are interrupt or rollback. Default is interrupt.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Block until a run is done. Returns the final state of the thread.

The thread ID to join.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Stream output from a run in real-time, until the run is done. Output is not buffered, so any output produced before this call will not be received here.

The thread ID to join.

Whether to cancel the run when the stream is disconnected.

The stream mode(s) to use. Must be a subset of the stream modes passed when creating the run. Background runs default to having the union of all stream modes.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The last event ID to use for the stream.

The thread ID to delete.

The run ID to delete.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Client for managing recurrent runs (cron jobs) in LangGraph.

A run is a single invocation of an assistant with optional input, config, and context. This client allows scheduling recurring runs to occur automatically.

The crons client functionality is not supported on all licenses. Please check the relevant license documentation for the most up-to-date details on feature availability.

Create a cron job for a thread.

Get a list of cron jobs.

Count cron jobs matching filters.

Create a cron job for a thread.

the thread ID to run the cron job on.

The assistant ID or graph name to use for the cron job. If using graph name, will default to first assistant created from that graph.

The cron schedule to execute this job on.

The input to the graph.

Metadata to assign to the cron job runs.

The configuration for the assistant.

Static context to add to the assistant.

Added in version 0.6.0

Whether to checkpoint during the run (or only at the end/interruption).

Nodes to interrupt immediately before they get executed.

Nodes to Nodes to interrupt immediately after they get executed.

Webhook to call after LangGraph API call is done.

Multitask strategy to use. Must be one of 'reject', 'interrupt', 'rollback', or 'enqueue'.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The assistant ID or graph name to use for the cron job. If using graph name, will default to first assistant created from that graph.

The cron schedule to execute this job on.

The input to the graph.

Metadata to assign to the cron job runs.

The configuration for the assistant.

Static context to add to the assistant.

Added in version 0.6.0

Whether to checkpoint during the run (or only at the end/interruption).

Nodes to interrupt immediately before they get executed.

Nodes to Nodes to interrupt immediately after they get executed.

Webhook to call after LangGraph API call is done.

Multitask strategy to use. Must be one of 'reject', 'interrupt', 'rollback', or 'enqueue'.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The cron ID to delete.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Get a list of cron jobs.

The assistant ID or graph name to search for.

the thread ID to search for.

The maximum number of results to return.

The number of results to skip.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The list of cron jobs returned by the search,

client = get_client(url="http://localhost:2024") cron_jobs = await client.crons.search( assistant_id="my_assistant_id", thread_id="my_thread_id", limit=5, offset=5, ) print(cron_jobs) ---------------------------------------------------------- [ { 'cron_id': '1ef3cefa-4c09-6926-96d0-3dc97fd5e39b', 'assistant_id': 'my_assistant_id', 'thread_id': 'my_thread_id', 'user_id': None, 'payload': { 'input': {'start_time': ''}, 'schedule': '4 * * * *', 'assistant_id': 'my_assistant_id' }, 'schedule': '4 * * * *', 'next_run_date': '2024-07-25T17:04:00+00:00', 'end_time': None, 'created_at': '2024-07-08T06:02:23.073257+00:00', 'updated_at': '2024-07-08T06:02:23.073257+00:00' } ]

Count cron jobs matching filters.

Assistant ID to filter by.

Thread ID to filter by.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Number of crons matching the criteria.

Client for interacting with the graph's shared storage.

The Store provides a key-value storage system for persisting data across graph executions, allowing for stateful operations and data sharing across threads.

Store or update an item.

Retrieve a single item.

Search for items within a namespace prefix.

List namespaces with optional match conditions.

Store or update an item.

A list of strings representing the namespace path.

The unique identifier for the item within the namespace.

A dictionary containing the item's data.

Controls search indexing - None (use defaults), False (disable), or list of field paths to index.

Optional time-to-live in minutes for the item, or None for no expiration.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Retrieve a single item.

The unique identifier for the item.

Optional list of strings representing the namespace path.

Whether to refresh the TTL on this read operation. If None, uses the store's default behavior.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

client = get_client(url="http://localhost:2024") item = await client.store.get_item( ["documents", "user123"], key="item456", ) print(item) ---------------------------------------------------------------- { 'namespace': ['documents', 'user123'], 'key': 'item456', 'value': {'title': 'My Document', 'content': 'Hello World'}, 'created_at': '2024-07-30T12:00:00Z', 'updated_at': '2024-07-30T12:00:00Z' }

The unique identifier for the item.

Optional list of strings representing the namespace path.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Search for items within a namespace prefix.

List of strings representing the namespace prefix.

Optional dictionary of key-value pairs to filter results.

Maximum number of items to return (default is 10).

Number of items to skip before returning results (default is 0).

Optional query for natural language search.

Whether to refresh the TTL on items returned by this search. If None, uses the store's default behavior.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

A list of items matching the search criteria.

client = get_client(url="http://localhost:2024") items = await client.store.search_items( ["documents"], filter={"author": "John Doe"}, limit=5, offset=0 ) print(items) ---------------------------------------------------------------- { "items": [ { "namespace": ["documents", "user123"], "key": "item789", "value": { "title": "Another Document", "author": "John Doe" }, "created_at": "2024-07-30T12:00:00Z", "updated_at": "2024-07-30T12:00:00Z" }, # ... additional items ... ] }

List namespaces with optional match conditions.

Optional list of strings representing the prefix to filter namespaces.

Optional list of strings representing the suffix to filter namespaces.

Optional integer specifying the maximum depth of namespaces to return.

Maximum number of namespaces to return (default is 100).

Number of namespaces to skip before returning results (default is 0).

Optional custom headers to include with the request.

Optional query parameters to include with the request.

A list of namespaces matching the criteria.

Synchronous client for interacting with the LangGraph API.

This class provides synchronous access to LangGraph API endpoints for managing assistants, threads, runs, cron jobs, and data storage.

Enter the sync context manager.

Exit the sync context manager.

Close the underlying HTTP client.

Enter the sync context manager.

Exit the sync context manager.

Close the underlying HTTP client.

Handle synchronous requests to the LangGraph API.

Provides error messaging and content handling enhancements above the underlying httpx client, mirroring the interface of HttpClient but for sync usage.

Underlying HTTPX sync client.

Send a PATCH request.

Send a DELETE request.

Send a request that automatically reconnects to Location header.

Stream the results of a request using SSE.

Send a PATCH request.

Send a DELETE request.

Send a request that automatically reconnects to Location header.

Stream the results of a request using SSE.

Client for managing assistants in LangGraph synchronously.

This class provides methods to interact with assistants, which are versioned configurations of your graph.

Get an assistant by ID.

Get the graph of an assistant by ID.

Get the schemas of an assistant by ID.

Get the schemas of an assistant by ID.

Create a new assistant.

Search for assistants.

Count assistants matching filters.

List all versions of an assistant.

Change the version of an assistant.

Get an assistant by ID.

The ID of the assistant to get OR the name of the graph (to use the default assistant).

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Get the graph of an assistant by ID.

The ID of the assistant to get the graph of.

Include graph representation of subgraphs. If an integer value is provided, only subgraphs with a depth less than or equal to the value will be included.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The graph information for the assistant in JSON format.

Get the schemas of an assistant by ID.

The ID of the assistant to get the schema of.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The graph schema for the assistant.

client = get_sync_client(url="http://localhost:2024") schema = client.assistants.get_schemas( assistant_id="my_assistant_id" ) print(schema) ---------------------------------------------------------------------------------------------------------------------------- { 'graph_id': 'agent', 'state_schema': { 'title': 'LangGraphInput', '$ref': '#/definitions/AgentState', 'definitions': { 'BaseMessage': { 'title': 'BaseMessage', 'description': 'Base abstract Message class. Messages are the inputs and outputs of ChatModels.', 'type': 'object', 'properties': { 'content': { 'title': 'Content', 'anyOf': [ {'type': 'string'}, {'type': 'array','items': {'anyOf': [{'type': 'string'}, {'type': 'object'}]}} ] }, 'additional_kwargs': { 'title': 'Additional Kwargs', 'type': 'object' }, 'response_metadata': { 'title': 'Response Metadata', 'type': 'object' }, 'type': { 'title': 'Type', 'type': 'string' }, 'name': { 'title': 'Name', 'type': 'string' }, 'id': { 'title': 'Id', 'type': 'string' } }, 'required': ['content', 'type'] }, 'AgentState': { 'title': 'AgentState', 'type': 'object', 'properties': { 'messages': { 'title': 'Messages', 'type': 'array', 'items': {'$ref': '#/definitions/BaseMessage'} } }, 'required': ['messages'] } } }, 'config_schema': { 'title': 'Configurable', 'type': 'object', 'properties': { 'model_name': { 'title': 'Model Name', 'enum': ['anthropic', 'openai'], 'type': 'string' } } }, 'context_schema': { 'title': 'Context', 'type': 'object', 'properties': { 'model_name': { 'title': 'Model Name', 'enum': ['anthropic', 'openai'], 'type': 'string' } } } }

Get the schemas of an assistant by ID.

The ID of the assistant to get the schema of.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The graph schema for the assistant.

Create a new assistant.

Useful when graph is configurable and you want to create different assistants based on different configurations.

The ID of the graph the assistant should use. The graph ID is normally set in your langgraph.json configuration.

Configuration to use for the graph.

Static context to add to the assistant.

Added in version 0.6.0

Metadata to add to assistant.

Assistant ID to use, will default to a random UUID if not provided.

How to handle duplicate creation. Defaults to 'raise' under the hood. Must be either 'raise' (raise error if duplicate), or 'do_nothing' (return existing assistant).

The name of the assistant. Defaults to 'Untitled' under the hood.

Optional custom headers to include with the request.

Optional description of the assistant. The description field is available for langgraph-api server version>=0.0.45

Optional query parameters to include with the request.

The created assistant.

Use this to point to a different graph, update the configuration, or change the metadata of an assistant.

The ID of the graph the assistant should use. The graph ID is normally set in your langgraph.json configuration. If None, assistant will keep pointing to same graph.

Configuration to use for the graph.

Static context to add to the assistant.

Added in version 0.6.0

Metadata to merge with existing assistant metadata.

The new name for the assistant.

Optional custom headers to include with the request.

Optional description of the assistant. The description field is available for langgraph-api server version>=0.0.45

The updated assistant.

The assistant ID to delete.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Search for assistants.

Metadata to filter by. Exact match filter for each KV pair.

The ID of the graph to filter by. The graph ID is normally set in your langgraph.json configuration.

The maximum number of results to return.

The number of results to skip.

Optional custom headers to include with the request.

A list of assistants.

Count assistants matching filters.

Metadata to filter by. Exact match for each key/value.

Optional graph id to filter by.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Number of assistants matching the criteria.

List all versions of an assistant.

The assistant ID to get versions for.

Metadata to filter versions by. Exact match filter for each KV pair.

The maximum number of versions to return.

The number of versions to skip.

Optional custom headers to include with the request.

A list of assistants.

Change the version of an assistant.

The assistant ID to delete.

The version to change to.

Optional custom headers to include with the request.

Synchronous client for managing threads in LangGraph.

This class provides methods to create, retrieve, and manage threads, which represent conversations or stateful interactions.

Count threads matching filters.

Get the state of a thread.

Update the state of a thread.

Get the state history of a thread.

Get a stream of events for a thread.

The ID of the thread to get.

Optional custom headers to include with the request.

client = get_sync_client(url="http://localhost:2024") thread = client.threads.get( thread_id="my_thread_id" ) print(thread) ----------------------------------------------------- { 'thread_id': 'my_thread_id', 'created_at': '2024-07-18T18:35:15.540834+00:00', 'updated_at': '2024-07-18T18:35:15.540834+00:00', 'metadata': {'graph_id': 'agent'} }

Metadata to add to thread.

ID of thread. If None, ID will be a randomly generated UUID.

How to handle duplicate creation. Defaults to 'raise' under the hood. Must be either 'raise' (raise error if duplicate), or 'do_nothing' (return existing thread).

Apply a list of supersteps when creating a thread, each containing a sequence of updates. Each update has values or command and as_node. Used for copying a thread between deployments.

Optional graph ID to associate with the thread.

Optional time-to-live in minutes for the thread. You can pass an integer (minutes) or a mapping with keys ttl and optional strategy (defaults to "delete").

Optional custom headers to include with the request.

client = get_sync_client(url="http://localhost:2024") thread = client.threads.create( metadata={"number":1}, thread_id="my-thread-id", if_exists="raise" ) )

ID of thread to update.

Metadata to merge with existing thread metadata.

Optional time-to-live in minutes for the thread. You can pass an integer (minutes) or a mapping with keys ttl and optional strategy (defaults to "delete").

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The ID of the thread to delete.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Thread metadata to filter on.

State values to filter on.

List of thread IDs to filter by.

Thread status to filter on. Must be one of 'idle', 'busy', 'interrupted' or 'error'.

Limit on number of threads to return.

Offset in threads table to start search from.

Optional custom headers to include with the request.

List of the threads matching the search parameters.

Count threads matching filters.

Thread metadata to filter on.

State values to filter on.

Thread status to filter on.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Number of threads matching the criteria.

The ID of the thread to copy.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Get the state of a thread.

The ID of the thread to get the state of.

The checkpoint to get the state of.

Include subgraphs states.

Optional custom headers to include with the request.

The thread of the state.

Update the state of a thread.

The ID of the thread to update.

The values to update the state with.

Update the state as if this node had just executed.

The checkpoint to update the state of.

Optional custom headers to include with the request.

Response after updating a thread's state.

Get the state history of a thread.

The ID of the thread to get the state history for.

Return states for this subgraph. If empty defaults to root.

The maximum number of states to return.

Return states before this checkpoint.

Filter states by metadata key-value pairs.

Optional custom headers to include with the request.

The state history of the Thread.

Get a stream of events for a thread.

The ID of the thread to get the stream for.

The ID of the last event to get.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

An iterator of stream parts.

Synchronous client for managing runs in LangGraph.

This class provides methods to create, retrieve, and manage runs, which represent individual executions of graphs.

Create a run and stream the results.

Create a background run.

Create a batch of stateless background runs.

Create a run, wait until it finishes and return the final state.

Block until a run is done. Returns the final state of the thread.

Stream output from a run in real-time, until the run is done.

Create a run and stream the results.

the thread ID to assign to the thread. If None will create a stateless run.

The assistant ID or graph name to stream from. If using graph name, will default to first assistant created from that graph.

The input to the graph.

The command to execute.

The stream mode(s) to use.

Whether to stream output from subgraphs.

Whether the stream is considered resumable. If true, the stream can be resumed and replayed in its entirety even after disconnection.

Metadata to assign to the run.

The configuration for the assistant.

Static context to add to the assistant.

Added in version 0.6.0

The checkpoint to resume from.

(deprecated) Whether to checkpoint during the run (or only at the end/interruption).

Nodes to interrupt immediately before they get executed.

Nodes to Nodes to interrupt immediately after they get executed.

Feedback keys to assign to run.

The disconnect mode to use. Must be one of 'cancel' or 'continue'.

Whether to delete or keep the thread created for a stateless run. Must be one of 'delete' or 'keep'.

Webhook to call after LangGraph API call is done.

Multitask strategy to use. Must be one of 'reject', 'interrupt', 'rollback', or 'enqueue'.

How to handle missing thread. Defaults to 'reject'. Must be either 'reject' (raise error if missing), or 'create' (create new thread).

The number of seconds to wait before starting the run. Use to schedule future runs.

Optional custom headers to include with the request.

Optional callback to call when a run is created.

The durability to use for the run. Values are "sync", "async", or "exit". "async" means checkpoints are persisted async while next graph step executes, replaces checkpoint_during=True "sync" means checkpoints are persisted sync after graph step executes, replaces checkpoint_during=False "exit" means checkpoints are only persisted when the run exits, does not save intermediate steps

Iterator of stream results.

client = get_sync_client(url="http://localhost:2024") async for chunk in client.runs.stream( thread_id=None, assistant_id="agent", input={"messages": [{"role": "user", "content": "how are you?"}]}, stream_mode=["values","debug"], metadata={"name":"my_run"}, context={"model_name": "anthropic"}, interrupt_before=["node_to_stop_before_1","node_to_stop_before_2"], interrupt_after=["node_to_stop_after_1","node_to_stop_after_2"], feedback_keys=["my_feedback_key_1","my_feedback_key_2"], webhook="https://my.fake.webhook.com", multitask_strategy="interrupt" ): print(chunk) ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ StreamPart(event='metadata', data={'run_id': '1ef4a9b8-d7da-679a-a45a-872054341df2'}) StreamPart(event='values', data={'messages': [{'content': 'how are you?', 'additional_kwargs': {}, 'response_metadata': {}, 'type': 'human', 'name': None, 'id': 'fe0a5778-cfe9-42ee-b807-0adaa1873c10', 'example': False}]}) StreamPart(event='values', data={'messages': [{'content': 'how are you?', 'additional_kwargs': {}, 'response_metadata': {}, 'type': 'human', 'name': None, 'id': 'fe0a5778-cfe9-42ee-b807-0adaa1873c10', 'example': False}, {'content': "I'm doing well, thanks for asking! I'm an AI assistant created by Anthropic to be helpful, honest, and harmless.", 'additional_kwargs': {}, 'response_metadata': {}, 'type': 'ai', 'name': None, 'id': 'run-159b782c-b679-4830-83c6-cef87798fe8b', 'example': False, 'tool_calls': [], 'invalid_tool_calls': [], 'usage_metadata': None}]}) StreamPart(event='end', data=None)

Create a background run.

the thread ID to assign to the thread. If None will create a stateless run.

The assistant ID or graph name to stream from. If using graph name, will default to first assistant created from that graph.

The input to the graph.

The command to execute.

The stream mode(s) to use.

Whether to stream output from subgraphs.

Whether the stream is considered resumable. If true, the stream can be resumed and replayed in its entirety even after disconnection.

Metadata to assign to the run.

The configuration for the assistant.

Static context to add to the assistant.

Added in version 0.6.0

The checkpoint to resume from.

(deprecated) Whether to checkpoint during the run (or only at the end/interruption).

Nodes to interrupt immediately before they get executed.

Nodes to Nodes to interrupt immediately after they get executed.

Webhook to call after LangGraph API call is done.

Multitask strategy to use. Must be one of 'reject', 'interrupt', 'rollback', or 'enqueue'.

Whether to delete or keep the thread created for a stateless run. Must be one of 'delete' or 'keep'.

How to handle missing thread. Defaults to 'reject'. Must be either 'reject' (raise error if missing), or 'create' (create new thread).

The number of seconds to wait before starting the run. Use to schedule future runs.

Optional custom headers to include with the request.

Optional callback to call when a run is created.

The durability to use for the run. Values are "sync", "async", or "exit". "async" means checkpoints are persisted async while next graph step executes, replaces checkpoint_during=True "sync" means checkpoints are persisted sync after graph step executes, replaces checkpoint_during=False "exit" means checkpoints are only persisted when the run exits, does not save intermediate steps

The created background Run.

Create a batch of stateless background runs.

Create a run, wait until it finishes and return the final state.

the thread ID to create the run on. If None will create a stateless run.

The assistant ID or graph name to run. If using graph name, will default to first assistant created from that graph.

The input to the graph.

The command to execute.

Metadata to assign to the run.

The configuration for the assistant.

Static context to add to the assistant.

Added in version 0.6.0

The checkpoint to resume from.

(deprecated) Whether to checkpoint during the run (or only at the end/interruption).

Nodes to interrupt immediately before they get executed.

Nodes to Nodes to interrupt immediately after they get executed.

Webhook to call after LangGraph API call is done.

The disconnect mode to use. Must be one of 'cancel' or 'continue'.

Whether to delete or keep the thread created for a stateless run. Must be one of 'delete' or 'keep'.

Multitask strategy to use. Must be one of 'reject', 'interrupt', 'rollback', or 'enqueue'.

How to handle missing thread. Defaults to 'reject'. Must be either 'reject' (raise error if missing), or 'create' (create new thread).

The number of seconds to wait before starting the run. Use to schedule future runs.

Whether to raise an error if the run fails.

Optional custom headers to include with the request.

Optional callback to call when a run is created.

The durability to use for the run. Values are "sync", "async", or "exit". "async" means checkpoints are persisted async while next graph step executes, replaces checkpoint_during=True "sync" means checkpoints are persisted sync after graph step executes, replaces checkpoint_during=False "exit" means checkpoints are only persisted when the run exits, does not save intermediate steps

The output of the Run.

The thread ID to list runs for.

The maximum number of results to return.

The number of results to skip.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The runs for the thread.

The thread ID to get.

Optional custom headers to include with the request.

The thread ID to cancel.

The run ID to cancel.

Whether to wait until run has completed.

Action to take when cancelling the run. Possible values are interrupt or rollback. Default is interrupt.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Block until a run is done. Returns the final state of the thread.

The thread ID to join.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Stream output from a run in real-time, until the run is done. Output is not buffered, so any output produced before this call will not be received here.

The thread ID to join.

The stream mode(s) to use. Must be a subset of the stream modes passed when creating the run. Background runs default to having the union of all stream modes.

Whether to cancel the run when the stream is disconnected.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The last event ID to use for the stream.

The thread ID to delete.

The run ID to delete.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Synchronous client for managing cron jobs in LangGraph.

This class provides methods to create and manage scheduled tasks (cron jobs) for automated graph executions.

The crons client functionality is not supported on all licenses. Please check the relevant license documentation for the most up-to-date details on feature availability.

Create a cron job for a thread.

Get a list of cron jobs.

Count cron jobs matching filters.

Create a cron job for a thread.

the thread ID to run the cron job on.

The assistant ID or graph name to use for the cron job. If using graph name, will default to first assistant created from that graph.

The cron schedule to execute this job on.

The input to the graph.

Metadata to assign to the cron job runs.

The configuration for the assistant.

Static context to add to the assistant.

Added in version 0.6.0

Whether to checkpoint during the run (or only at the end/interruption).

Nodes to interrupt immediately before they get executed.

Nodes to Nodes to interrupt immediately after they get executed.

Webhook to call after LangGraph API call is done.

Multitask strategy to use. Must be one of 'reject', 'interrupt', 'rollback', or 'enqueue'.

Optional custom headers to include with the request.

The assistant ID or graph name to use for the cron job. If using graph name, will default to first assistant created from that graph.

The cron schedule to execute this job on.

The input to the graph.

Metadata to assign to the cron job runs.

The configuration for the assistant.

Static context to add to the assistant.

Added in version 0.6.0

Whether to checkpoint during the run (or only at the end/interruption).

Nodes to interrupt immediately before they get executed.

Nodes to Nodes to interrupt immediately after they get executed.

Webhook to call after LangGraph API call is done.

Multitask strategy to use. Must be one of 'reject', 'interrupt', 'rollback', or 'enqueue'.

Optional custom headers to include with the request.

The cron ID to delete.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Get a list of cron jobs.

The assistant ID or graph name to search for.

the thread ID to search for.

The maximum number of results to return.

The number of results to skip.

Optional custom headers to include with the request.

The list of cron jobs returned by the search,

Count cron jobs matching filters.

Assistant ID to filter by.

Thread ID to filter by.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Number of crons matching the criteria.

A client for synchronous operations on a key-value store.

Provides methods to interact with a remote key-value store, allowing storage and retrieval of items within namespaced hierarchies.

Store or update an item.

Retrieve a single item.

Search for items within a namespace prefix.

List namespaces with optional match conditions.

Store or update an item.

A list of strings representing the namespace path.

The unique identifier for the item within the namespace.

A dictionary containing the item's data.

Controls search indexing - None (use defaults), False (disable), or list of field paths to index.

Optional time-to-live in minutes for the item, or None for no expiration.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Retrieve a single item.

The unique identifier for the item.

Optional list of strings representing the namespace path.

Whether to refresh the TTL on this read operation. If None, uses the store's default behavior.

Optional custom headers to include with the request.

The unique identifier for the item.

Optional list of strings representing the namespace path.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

Search for items within a namespace prefix.

List of strings representing the namespace prefix.

Optional dictionary of key-value pairs to filter results.

Maximum number of items to return (default is 10).

Number of items to skip before returning results (default is 0).

Optional query for natural language search.

Whether to refresh the TTL on items returned by this search. If None, uses the store's default behavior.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

A list of items matching the search criteria.

client = get_sync_client(url="http://localhost:8123") items = client.store.search_items( ["documents"], filter={"author": "John Doe"}, limit=5, offset=0 ) print(items) ---------------------------------------------------------------- { "items": [ { "namespace": ["documents", "user123"], "key": "item789", "value": { "title": "Another Document", "author": "John Doe" }, "created_at": "2024-07-30T12:00:00Z", "updated_at": "2024-07-30T12:00:00Z" }, # ... additional items ... ] }

List namespaces with optional match conditions.

Optional list of strings representing the prefix to filter namespaces.

Optional list of strings representing the suffix to filter namespaces.

Optional integer specifying the maximum depth of namespaces to return.

Maximum number of namespaces to return (default is 100).

Number of namespaces to skip before returning results (default is 0).

Optional custom headers to include with the request.

A list of namespaces matching the criteria.

Create and configure a LangGraphClient.

The client provides programmatic access to LangSmith Deployment. It supports both remote servers and local in-process connections (when running inside a LangGraph server).

Base URL of the LangGraph API. – If None, the client first attempts an in-process connection via ASGI transport. If that fails, it falls back to http://localhost:8123.

API key for authentication. If omitted, the client reads from environment variables in the following order: 1. Function argument 2. LANGGRAPH_API_KEY 3. LANGSMITH_API_KEY 4. LANGCHAIN_API_KEY

Additional HTTP headers to include in requests. Merged with authentication headers.

HTTP timeout configuration. May be: – httpx.Timeout instance – float (total seconds) – tuple (connect, read, write, pool) in seconds Defaults: connect=5, read=300, write=300, pool=5.

A top-level client exposing sub-clients for assistants, threads, runs, and cron operations.

Get a synchronous LangGraphClient instance.

The URL of the LangGraph API.

The API key. If not provided, it will be read from the environment. Precedence: 1. explicit argument 2. LANGGRAPH_API_KEY 3. LANGSMITH_API_KEY 4. LANGCHAIN_API_KEY

Optional custom headers

Optional timeout configuration for the HTTP client. Accepts an httpx.Timeout instance, a float (seconds), or a tuple of timeouts. Tuple format is (connect, read, write, pool) If not provided, defaults to connect=5s, read=300s, write=300s, and pool=5s.

Returns: SyncLangGraphClient: The top-level synchronous client for accessing AssistantsClient, ThreadsClient, RunsClient, and CronClient.

Data models for interacting with the LangGraph API.

Configuration options for a call.

Represents a checkpoint in the execution process.

Defines the structure and properties of a graph.

Base model for an assistant.

Represents a specific version of an assistant.

Represents an assistant with additional properties.

Represents an interruption in the execution flow.

Represents a conversation thread.

Represents a task within a thread.

Represents the state of a thread.

Represents the response from updating a thread's state.

Represents a single execution run.

Represents a scheduled task.

Defines the parameters for initiating a background run.

Represents a single document or data entry in the graph's Store.

Response structure for listing namespaces.

Item with an optional relevance score from search operations.

Response structure for searching items.

Represents a part of a stream response.

Represents a message to be sent to a specific node in the graph.

Represents one or more commands to control graph execution flow and state.

Metadata for a run creation request.

Represents a JSON-like structure, which can be None or a dictionary with string keys and any values.

Represents the status of a run:

Represents the status of a thread:

Defines the mode of streaming:

Defines the mode of streaming:

Specifies behavior on disconnection:

Defines how to handle multiple tasks:

Specifies behavior on conflict:

Defines action after completion:

Durability mode for the graph execution.

Represents a wildcard or 'all' selector.

Specifies behavior if the thread doesn't exist:

Action to take when cancelling the run.

The field to sort by.

The field to sort by.

The field to sort by.

The order to sort by.

Represents a JSON-like structure, which can be None or a dictionary with string keys and any values.

Represents the status of a run: - "pending": The run is waiting to start. - "running": The run is currently executing. - "error": The run encountered an error and stopped. - "success": The run completed successfully. - "timeout": The run exceeded its time limit. - "interrupted": The run was manually stopped or interrupted.

Represents the status of a thread: - "idle": The thread is not currently processing any task. - "busy": The thread is actively processing a task. - "interrupted": The thread's execution was interrupted. - "error": An exception occurred during task processing.

Defines the mode of streaming: - "run_modes": Stream the same events as the runs on thread, as well as run_done events. - "lifecycle": Stream only run start/end events. - "state_update": Stream state updates on the thread.

Defines the mode of streaming: - "values": Stream only the values. - "messages": Stream complete messages. - "updates": Stream updates to the state. - "events": Stream events occurring during execution. - "checkpoints": Stream checkpoints as they are created. - "tasks": Stream task start and finish events. - "debug": Stream detailed debug information. - "custom": Stream custom events.

Specifies behavior on disconnection: - "cancel": Cancel the operation on disconnection. - "continue": Continue the operation even if disconnected.

Defines how to handle multiple tasks: - "reject": Reject new tasks when busy. - "interrupt": Interrupt current task for new ones. - "rollback": Roll back current task and start new one. - "enqueue": Queue new tasks for later execution.

Specifies behavior on conflict: - "raise": Raise an exception when a conflict occurs. - "do_nothing": Ignore conflicts and proceed.

Defines action after completion: - "delete": Delete resources after completion. - "keep": Retain resources after completion.

Durability mode for the graph execution. - "sync": Changes are persisted synchronously before the next step starts. - "async": Changes are persisted asynchronously while the next step executes. - "exit": Changes are persisted only when the graph exits.

Represents a wildcard or 'all' selector.

Specifies behavior if the thread doesn't exist: - "create": Create a new thread if it doesn't exist. - "reject": Reject the operation if the thread doesn't exist.

Action to take when cancelling the run. - "interrupt": Simply cancel the run. - "rollback": Cancel the run. Then delete the run and associated checkpoints.

The field to sort by.

The field to sort by.

The field to sort by.

The order to sort by.

Configuration options for a call.

Tags for this call and any sub-calls (eg. a Chain calling an LLM).

Maximum number of times a call can recurse. If not provided, defaults to 25.

Runtime values for attributes previously made configurable on this Runnable,

Tags for this call and any sub-calls (eg. a Chain calling an LLM). You can use these to filter calls.

Maximum number of times a call can recurse. If not provided, defaults to 25.

Runtime values for attributes previously made configurable on this Runnable, or sub-Runnables, through .configurable_fields() or .configurable_alternatives(). Check .output_schema() for a description of the attributes that have been made configurable.

Represents a checkpoint in the execution process.

Unique identifier for the thread associated with this checkpoint.

Namespace for the checkpoint; used internally to manage subgraph state.

Optional unique identifier for the checkpoint itself.

Optional dictionary containing checkpoint-specific data.

Unique identifier for the thread associated with this checkpoint.

Namespace for the checkpoint; used internally to manage subgraph state.

Optional unique identifier for the checkpoint itself.

Optional dictionary containing checkpoint-specific data.

Defines the structure and properties of a graph.

The schema for the graph input.

The schema for the graph output.

The schema for the graph state.

The schema for the graph config.

The schema for the graph context.

The schema for the graph input. Missing if unable to generate JSON schema from graph.

The schema for the graph output. Missing if unable to generate JSON schema from graph.

The schema for the graph state. Missing if unable to generate JSON schema from graph.

The schema for the graph config. Missing if unable to generate JSON schema from graph.

The schema for the graph context. Missing if unable to generate JSON schema from graph.

Base model for an assistant.

The ID of the assistant.

The assistant config.

The static context of the assistant.

The time the assistant was created.

The assistant metadata.

The version of the assistant

The name of the assistant

The description of the assistant

The ID of the assistant.

The assistant config.

The static context of the assistant.

The time the assistant was created.

The assistant metadata.

The version of the assistant

The name of the assistant

The description of the assistant

Represents a specific version of an assistant.

The ID of the assistant.

The assistant config.

The static context of the assistant.

The time the assistant was created.

The assistant metadata.

The version of the assistant

The name of the assistant

The description of the assistant

The ID of the assistant.

The assistant config.

The static context of the assistant.

The time the assistant was created.

The assistant metadata.

The version of the assistant

The name of the assistant

The description of the assistant

Represents an assistant with additional properties.

The last time the assistant was updated.

The ID of the assistant.

The assistant config.

The static context of the assistant.

The time the assistant was created.

The assistant metadata.

The version of the assistant

The name of the assistant

The description of the assistant

The last time the assistant was updated.

The ID of the assistant.

The assistant config.

The static context of the assistant.

The time the assistant was created.

The assistant metadata.

The version of the assistant

The name of the assistant

The description of the assistant

Represents an interruption in the execution flow.

The value associated with the interrupt.

The ID of the interrupt. Can be used to resume the interrupt.

The value associated with the interrupt.

The ID of the interrupt. Can be used to resume the interrupt.

Represents a conversation thread.

The ID of the thread.

The time the thread was created.

The last time the thread was updated.

The status of the thread, one of 'idle', 'busy', 'interrupted'.

The current state of the thread.

Mapping of task ids to interrupts that were raised in that task.

The ID of the thread.

The time the thread was created.

The last time the thread was updated.

The status of the thread, one of 'idle', 'busy', 'interrupted'.

The current state of the thread.

Mapping of task ids to interrupts that were raised in that task.

Represents a task within a thread.

Represents the state of a thread.

The next nodes to execute. If empty, the thread is done until new input is

The ID of the checkpoint.

Metadata for this state

Timestamp of state creation

The ID of the parent checkpoint. If missing, this is the root checkpoint.

Tasks to execute in this step. If already attempted, may contain an error.

Interrupts which were thrown in this thread.

The next nodes to execute. If empty, the thread is done until new input is received.

The ID of the checkpoint.

Metadata for this state

Timestamp of state creation

The ID of the parent checkpoint. If missing, this is the root checkpoint.

Tasks to execute in this step. If already attempted, may contain an error.

Interrupts which were thrown in this thread.

Represents the response from updating a thread's state.

Checkpoint of the latest state.

Checkpoint of the latest state.

Represents a single execution run.

The ID of the thread.

The assistant that was used for this run.

The time the run was created.

The last time the run was updated.

The status of the run. One of 'pending', 'running', "error", 'success', "timeout", "interrupted".

Strategy to handle concurrent runs on the same thread.

The ID of the thread.

The assistant that was used for this run.

The time the run was created.

The last time the run was updated.

The status of the run. One of 'pending', 'running', "error", 'success', "timeout", "interrupted".

Strategy to handle concurrent runs on the same thread.

Represents a scheduled task.

The ID of the assistant.

The ID of the thread.

The end date to stop running the cron.

The schedule to run, cron format.

The time the cron was created.

The last time the cron was updated.

The run payload to use for creating new run.

The user ID of the cron.

The next run date of the cron.

The metadata of the cron.

The ID of the assistant.

The ID of the thread.

The end date to stop running the cron.

The schedule to run, cron format.

The time the cron was created.

The last time the cron was updated.

The run payload to use for creating new run.

The user ID of the cron.

The next run date of the cron.

The metadata of the cron.

Defines the parameters for initiating a background run.

The identifier of the thread to run. If not provided, the run is stateless.

The identifier of the assistant to use for this run.

Initial input data for the run.

Additional metadata to associate with the run.

Configuration options for the run.

The static context of the run.

The identifier of a checkpoint to resume from.

List of node names to interrupt execution before.

List of node names to interrupt execution after.

URL to send webhook notifications about the run's progress.

Strategy for handling concurrent runs on the same thread.

The identifier of the thread to run. If not provided, the run is stateless.

The identifier of the assistant to use for this run.

Initial input data for the run.

Additional metadata to associate with the run.

Configuration options for the run.

The static context of the run.

The identifier of a checkpoint to resume from.

List of node names to interrupt execution before.

List of node names to interrupt execution after.

URL to send webhook notifications about the run's progress.

Strategy for handling concurrent runs on the same thread.

Represents a single document or data entry in the graph's Store.

Items are used to store cross-thread memories.

The namespace of the item. A namespace is analogous to a document's directory.

The unique identifier of the item within its namespace.

The value stored in the item. This is the document itself.

The timestamp when the item was created.

The timestamp when the item was last updated.

The namespace of the item. A namespace is analogous to a document's directory.

The unique identifier of the item within its namespace.

In general, keys needn't be globally unique.

The value stored in the item. This is the document itself.

The timestamp when the item was created.

The timestamp when the item was last updated.

Response structure for listing namespaces.

A list of namespace paths, where each path is a list of strings.

A list of namespace paths, where each path is a list of strings.

Item with an optional relevance score from search operations.

Relevance/similarity score. Included when searching a compatible store with a natural language query.

The namespace of the item. A namespace is analogous to a document's directory.

The unique identifier of the item within its namespace.

In general, keys needn't be globally unique.

The value stored in the item. This is the document itself.

The timestamp when the item was created.

The timestamp when the item was last updated.

Response structure for searching items.

A list of items matching the search criteria.

A list of items matching the search criteria.

Represents a part of a stream response.

The type of event for this stream part.

The data payload associated with the event.

The type of event for this stream part.

The data payload associated with the event.

Represents a message to be sent to a specific node in the graph.

This type is used to explicitly send messages to nodes in the graph, typically used within Command objects to control graph execution flow.

The name of the target node to send the message to.

Optional dictionary containing the input data to be passed to the node.

The name of the target node to send the message to.

Optional dictionary containing the input data to be passed to the node.

If None, the node will be called with no input.

Represents one or more commands to control graph execution flow and state.

This type defines the control commands that can be returned by nodes to influence graph execution. It lets you navigate to other nodes, update graph state, and resume from interruptions.

Specifies where execution should continue. Can be:

Updates to apply to the graph's state. Can be:

Value to resume execution with after an interruption.

Specifies where execution should continue. Can be:

Updates to apply to the graph's state. Can be:

Value to resume execution with after an interruption. Used in conjunction with interrupt() to implement control flow.

Metadata for a run creation request.

The ID of the thread.

The ID of the thread.

Exceptions used in the auth system.

Authentication and authorization types for LangGraph.

Add custom authentication and authorization management to your LangGraph application.

Add custom authentication and authorization management to your LangGraph application.

The Auth class provides a unified system for handling authentication and authorization in LangGraph applications. It supports custom user authentication protocols and fine-grained authorization rules for different resources and actions.

To use, create a separate python file and add the path to the file to your LangGraph API configuration file (langgraph.json). Within that file, create an instance of the Auth class and register authentication and authorization handlers as needed.

Example langgraph.json file:

Then the LangGraph server will load your auth file and run it server-side whenever a request comes in.

This allows you to set default behavior with a global handler while overriding specific routes as needed.

Register an authentication handler function.

Reference to auth type definitions.

Reference to auth exception definitions.

Entry point for authorization handlers that control access to specific resources.

Reference to auth type definitions.

Provides access to all type definitions used in the auth system, like ThreadsCreate, AssistantsRead, etc.

Reference to auth exception definitions.

Provides access to all exception definitions used in the auth system, like HTTPException, etc.

Entry point for authorization handlers that control access to specific resources.

The on class provides a flexible way to define authorization rules for different resources and actions in your application. It supports three main usage patterns:

The handler should return one of:

Global handler for all requests:

Resource-specific handler. This would take precedence over the global handler for all actions on the threads resource:

Resource and action specific handler:

Multiple resources or actions:

Auth for the store resource is a bit different since its structure is developer defined. You typically want to enforce user creds in the namespace.

Register an authentication handler function.

The authentication handler is responsible for verifying credentials and returning user scopes. It can accept any of the following parameters by name:

The authentication handler function to register. Must return a representation of the user. This could be a: - string (the user id) - dict containing {"identity": str, "permissions": list[str]} - or an object with identity and permissions properties Permissions can be optionally used by your handlers downstream.

The registered handler function.

If an authentication handler is already registered.

Basic token authentication:

Accept the full request context:

Return user name and permissions:

Authentication and authorization types for LangGraph.

This module defines the core types used for authentication, authorization, and request handling in LangGraph. It includes user protocols, authentication contexts, and typed dictionaries for various API operations.

All typing.TypedDict classes use total=False to make all fields typing.Optional by default.

Parameters for creating a new thread.

Parameters for reading thread state or run information.

Parameters for updating a thread or run.

Parameters for deleting a thread.

Parameters for searching threads.

Payload for creating a run.

Payload for creating an assistant.

Payload for reading an assistant.

Payload for updating an assistant.

Payload for deleting an assistant.

Payload for searching assistants.

Operation to retrieve a specific item by its namespace and key.

Operation to search for items within a specified namespace hierarchy.

Operation to list and filter namespaces in the store.

Operation to store, update, or delete an item in the store.

Operation to delete an item from the store.

Namespace for type definitions of different API operations.

Type for arbitrary metadata attached to entities.

Status of a run execution.

Strategy for handling multiple concurrent tasks.

Behavior when encountering conflicts.

Behavior when an entity doesn't exist.

Response type for authorization handlers.

Subset containment is only supported by newer versions of the LangGraph dev server; install langgraph-runtime-inmem >= 0.14.1 to use this filter variant.

Simple exact match filter for the resource owner:

Explicit version of the exact match filter:

Containment (membership of a single element):

Containment (subset containment; all values must be present, but order doesn't matter):

Combining filters (treated as a logical AND):

Type for arbitrary metadata attached to entities.

Allows storing custom key-value pairs with any entity. Keys must be strings, values can be any JSON-serializable type.

The result of a handler can be: * None | True: accept the request. * False: reject the request with a 403 error * FilterType: filter to apply

Type for authentication functions.

An authenticator can return either: 1. A string (user_id) 2. A dict containing {"identity": str, "permissions": list[str]} 3. An object with identity and permissions properties

Permissions can be used downstream by your authorization logic to determine access permissions to different resources.

The authenticate decorator will automatically inject any of the following parameters by name if they are included in your function signature:

The raw ASGI request object

The parsed request body

The HTTP method (GET, POST, etc.)

The Authorization header value (e.g. "Bearer ")

Basic authentication with token:

Authentication with multiple parameters:

Accepting the raw ASGI request:

User objects must at least expose the identity property.

The unique identifier for the user.

The unique identifier for the user.

This could be a username, email, or any other unique identifier used to distinguish between different users in the system.

The dictionary representation of a user.

The required unique identifier for the user.

The typing.Optional display name for the user.

Whether the user is authenticated. Defaults to True.

A list of permissions associated with the user.

The required unique identifier for the user.

The typing.Optional display name for the user.

Whether the user is authenticated. Defaults to True.

A list of permissions associated with the user.

You can use these in your @auth.on authorization logic to determine access permissions to different resources.

The base ASGI user protocol

Get a key from your minimal user dict.

Check if a property exists.

Iterate over the keys of the user.

Whether the user is authenticated.

The display name of the user.

The unique identifier for the user.

The permissions associated with the user.

Whether the user is authenticated.

The display name of the user.

The unique identifier for the user.

The permissions associated with the user.

Get a key from your minimal user dict.

Check if a property exists.

Iterate over the keys of the user.

A user object that's populated from authenticated requests from the LangGraph studio.

Note: Studio auth can be disabled in your langgraph.json config.

You can use isinstance checks in your authorization handlers (@auth.on) to control access specifically for developers accessing the instance from the LangGraph Studio UI.

Base class for authentication context.

Provides the fundamental authentication information needed for authorization decisions.

The permissions granted to the authenticated user.

The authenticated user.

The permissions granted to the authenticated user.

The authenticated user.

Bases: BaseAuthContext

Complete authentication context with resource and action information.

Extends BaseAuthContext with specific resource and action being accessed, allowing for fine-grained access control decisions.

The resource being accessed.

The action being performed on the resource.

The permissions granted to the authenticated user.

The authenticated user.

The resource being accessed.

The action being performed on the resource.

Most resources support the following actions: - create: Create a new resource - read: Read information about a resource - update: Update an existing resource - delete: Delete a resource - search: Search for resources

The store supports the following actions: - put: Add or update a document in the store - get: Get a document from the store - list_namespaces: List the namespaces in the store

The permissions granted to the authenticated user.

The authenticated user.

Time-to-live configuration for a thread.

Matches the OpenAPI schema where TTL is represented as an object with an optional strategy and a time value in minutes.

TTL strategy. Currently only 'delete' is supported.

Time-to-live in minutes from now until the thread should be swept.

TTL strategy. Currently only 'delete' is supported.

Time-to-live in minutes from now until the thread should be swept.

Parameters for creating a new thread.

Unique identifier for the thread.

typing.Optional metadata to attach to the thread.

Behavior when a thread with the same ID already exists.

Optional TTL configuration for the thread.

Unique identifier for the thread.

typing.Optional metadata to attach to the thread.

Behavior when a thread with the same ID already exists.

Optional TTL configuration for the thread.

Parameters for reading thread state or run information.

This type is used in three contexts: 1. Reading thread, thread version, or thread state information: Only thread_id is provided 2. Reading run information: Both thread_id and run_id are provided

Unique identifier for the thread.

Run ID to filter by. Only used when reading run information within a thread.

Unique identifier for the thread.

Run ID to filter by. Only used when reading run information within a thread.

Parameters for updating a thread or run.

Called for updates to a thread, thread version, or run cancellation.

Unique identifier for the thread.

typing.Optional metadata to update.

typing.Optional action to perform on the thread.

Unique identifier for the thread.

typing.Optional metadata to update.

typing.Optional action to perform on the thread.

Parameters for deleting a thread.

Called for deletes to a thread, thread version, or run

Unique identifier for the thread.

typing.Optional run ID to filter by.

Unique identifier for the thread.

typing.Optional run ID to filter by.

Parameters for searching threads.

Called for searches to threads or runs.

typing.Optional metadata to filter by.

typing.Optional values to filter by.

typing.Optional status to filter by.

Maximum number of results to return.

Offset for pagination.

typing.Optional list of thread IDs to filter by.

typing.Optional thread ID to filter by.

typing.Optional metadata to filter by.

typing.Optional values to filter by.

typing.Optional status to filter by.

Maximum number of results to return.

Offset for pagination.

typing.Optional list of thread IDs to filter by.

typing.Optional thread ID to filter by.

Payload for creating a run.

typing.Optional assistant ID to use for this run.

typing.Optional thread ID to use for this run.

typing.Optional run ID to use for this run.

typing.Optional status for this run.

typing.Optional metadata for the run.

Prevent inserting a new run if one is already in flight.

Multitask strategy for this run.

IfNotExists for this run.

Number of seconds to wait before creating the run.

Keyword arguments to pass to the run.

Action to take if updating an existing run.

typing.Optional assistant ID to use for this run.

typing.Optional thread ID to use for this run.

typing.Optional run ID to use for this run.

typing.Optional status for this run.

typing.Optional metadata for the run.

Prevent inserting a new run if one is already in flight.

Multitask strategy for this run.

IfNotExists for this run.

Number of seconds to wait before creating the run.

Keyword arguments to pass to the run.

Action to take if updating an existing run.

Payload for creating an assistant.

Unique identifier for the assistant.

Graph ID to use for this assistant.

typing.Optional configuration for the assistant.

typing.Optional metadata to attach to the assistant.

Behavior when an assistant with the same ID already exists.

Name of the assistant.

Unique identifier for the assistant.

Graph ID to use for this assistant.

typing.Optional configuration for the assistant.

typing.Optional metadata to attach to the assistant.

Behavior when an assistant with the same ID already exists.

Name of the assistant.

Payload for reading an assistant.

Unique identifier for the assistant.

typing.Optional metadata to filter by.

Unique identifier for the assistant.

typing.Optional metadata to filter by.

Payload for updating an assistant.

Unique identifier for the assistant.

typing.Optional graph ID to update.

typing.Optional configuration to update.

The static context of the assistant.

typing.Optional metadata to update.

typing.Optional name to update.

typing.Optional version to update.

Unique identifier for the assistant.

typing.Optional graph ID to update.

typing.Optional configuration to update.

The static context of the assistant.

typing.Optional metadata to update.

typing.Optional name to update.

typing.Optional version to update.

Payload for deleting an assistant.

Unique identifier for the assistant.

Unique identifier for the assistant.

Payload for searching assistants.

typing.Optional graph ID to filter by.

typing.Optional metadata to filter by.

Maximum number of results to return.

Offset for pagination.

typing.Optional graph ID to filter by.

typing.Optional metadata to filter by.

Maximum number of results to return.

Offset for pagination.

Payload for creating a cron job.

Payload for the cron job.

Schedule for the cron job.

typing.Optional unique identifier for the cron job.

typing.Optional thread ID to use for this cron job.

typing.Optional user ID to use for this cron job.

typing.Optional end time for the cron job.

Payload for the cron job.

Schedule for the cron job.

typing.Optional unique identifier for the cron job.

typing.Optional thread ID to use for this cron job.

typing.Optional user ID to use for this cron job.

typing.Optional end time for the cron job.

Payload for deleting a cron job.

Unique identifier for the cron job.

Unique identifier for the cron job.

Payload for reading a cron job.

Unique identifier for the cron job.

Unique identifier for the cron job.

Payload for updating a cron job.

Unique identifier for the cron job.

typing.Optional payload to update.

typing.Optional schedule to update.

Unique identifier for the cron job.

typing.Optional payload to update.

typing.Optional schedule to update.

Payload for searching cron jobs.

typing.Optional assistant ID to filter by.

typing.Optional thread ID to filter by.

Maximum number of results to return.

Offset for pagination.

typing.Optional assistant ID to filter by.

typing.Optional thread ID to filter by.

Maximum number of results to return.

Offset for pagination.

Operation to retrieve a specific item by its namespace and key.

Hierarchical path that uniquely identifies the item's location.

Unique identifier for the item within its specific namespace.

Hierarchical path that uniquely identifies the item's location.

Unique identifier for the item within its specific namespace.

Operation to search for items within a specified namespace hierarchy.

Prefix filter for defining the search scope.

Key-value pairs for filtering results based on exact matches or comparison operators.

Maximum number of items to return in the search results.

Number of matching items to skip for pagination.

Naturalj language search query for semantic search capabilities.

Prefix filter for defining the search scope.

Key-value pairs for filtering results based on exact matches or comparison operators.

Maximum number of items to return in the search results.

Number of matching items to skip for pagination.

Naturalj language search query for semantic search capabilities.

Operation to list and filter namespaces in the store.

Prefix filter namespaces.

Optional conditions for filtering namespaces.

Maximum depth of namespace hierarchy to return.

Maximum number of namespaces to return.

Number of namespaces to skip for pagination.

Prefix filter namespaces.

Optional conditions for filtering namespaces.

Maximum depth of namespace hierarchy to return.

Namespaces deeper than this level will be truncated.

Maximum number of namespaces to return.

Number of namespaces to skip for pagination.

Operation to store, update, or delete an item in the store.

Hierarchical path that identifies the location of the item.

Unique identifier for the item within its namespace.

The data to store, or None to mark the item for deletion.

Optional index configuration for full-text search.

Hierarchical path that identifies the location of the item.

Unique identifier for the item within its namespace.

The data to store, or None to mark the item for deletion.

Optional index configuration for full-text search.

Operation to delete an item from the store.

Hierarchical path that uniquely identifies the item's location.

Unique identifier for the item within its specific namespace.

Hierarchical path that uniquely identifies the item's location.

Unique identifier for the item within its specific namespace.

Namespace for type definitions of different API operations.

This class organizes type definitions for create, read, update, delete, and search operations across different resources (threads, assistants, crons).

Types for thread-related operations.

Types for assistant-related operations.

Types for cron-related operations.

Types for store-related operations.

Types for thread-related operations.

Type for thread creation parameters.

Type for creating or streaming a run.

Type for thread read parameters.

Type for thread update parameters.

Type for thread deletion parameters.

Type for thread search parameters.

Type for thread creation parameters.

Type for creating or streaming a run.

Type for thread read parameters.

Type for thread update parameters.

Type for thread deletion parameters.

Type for thread search parameters.

Types for assistant-related operations.

Type for assistant creation parameters.

Type for assistant read parameters.

Type for assistant update parameters.

Type for assistant deletion parameters.

Type for assistant search parameters.

Type for assistant creation parameters.

Type for assistant read parameters.

Type for assistant update parameters.

Type for assistant deletion parameters.

Type for assistant search parameters.

Types for cron-related operations.

Type for cron creation parameters.

Type for cron read parameters.

Type for cron update parameters.

Type for cron deletion parameters.

Type for cron search parameters.

Type for cron creation parameters.

Type for cron read parameters.

Type for cron update parameters.

Type for cron deletion parameters.

Type for cron search parameters.

Types for store-related operations.

Type for store put parameters.

Type for store get parameters.

Type for store search parameters.

Type for store delete parameters.

Type for store list namespaces parameters.

Type for store put parameters.

Type for store get parameters.

Type for store search parameters.

Type for store delete parameters.

Type for store list namespaces parameters.

Exceptions used in the auth system.

HTTP exception that you can raise to return a specific HTTP error response.

HTTP exception that you can raise to return a specific HTTP error response.

Since this is defined in the auth module, we default to a 401 status code.

HTTP status code for the error. Defaults to 401 "Unauthorized".

Detailed error message. If None, uses a default message based on the status code.

Additional HTTP headers to include in the error response.

Default: raise HTTPException() # HTTPException(status_code=401, detail='Unauthorized')

Add headers: raise HTTPException(headers={"X-Custom-Header": "Custom Value"}) # HTTPException(status_code=401, detail='Unauthorized', headers={"WWW-Authenticate": "Bearer"})

Custom error: raise HTTPException(status_code=404, detail="Not found")

**Examples:**

Example 1 (unknown):
```unknown
__aenter__() -> LangGraphClient
```

Example 2 (unknown):
```unknown
__aexit__(
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: TracebackType | None,
) -> None
```

Example 3 (unknown):
```unknown
aclose() -> None
```

Example 4 (unknown):
```unknown
get(
    path: str,
    *,
    params: QueryParamTypes | None = None,
    headers: Mapping[str, str] | None = None,
    on_response: Callable[[Response], None] | None = None
) -> Any
```

---

## Js ts sdk ref

**URL:** https://langchain-ai.github.io/langgraph/cloud/reference/sdk/js_ts_sdk_ref/

**Contents:**
- Js ts sdk ref
- @langchain/langgraph-sdk¶
  - Classes¶
  - Interfaces¶
  - Functions¶
- langchain/langgraph-sdk/auth¶
  - Classes¶
  - Interfaces¶
  - Type Aliases¶
- Class: Auth\<TExtra, TAuthReturn, TUser>¶

@langchain/langgraph-sdk

langchain/langgraph-sdk

@langchain/langgraph-sdk

@langchain/langgraph-sdk / Auth

Defined in: src/auth/index.ts:11

• TAuthReturn extends BaseAuthReturn = BaseAuthReturn

• TUser extends BaseUser = ToUserLike\<TAuthReturn>

new Auth\<TExtra, TAuthReturn, TUser>(): Auth\<TExtra, TAuthReturn, TUser>

Auth\<TExtra, TAuthReturn, TUser>

authenticate\<T>(cb): Auth\<TExtra, T>

Defined in: src/auth/index.ts:25

• T extends BaseAuthReturn

AuthenticateCallback\<T>

on\<T>(event, callback): this

Defined in: src/auth/index.ts:32

• T extends CallbackEvent

OnCallback\<T, TUser>

@langchain/langgraph-sdk

@langchain/langgraph-sdk / HTTPException

Defined in: src/auth/error.ts:66

new HTTPException(status, options?): HTTPException

Defined in: src/auth/error.ts:70

optional cause: unknown

Defined in: node_modules/typescript/lib/lib.es2022.error.d.ts:24

Defined in: src/auth/error.ts:68

Defined in: node_modules/typescript/lib/lib.es5.d.ts:1077

Defined in: node_modules/typescript/lib/lib.es5.d.ts:1076

optional stack: string

Defined in: node_modules/typescript/lib/lib.es5.d.ts:1078

Defined in: src/auth/error.ts:67

static optional prepareStackTrace: (err, stackTraces) => any

Defined in: node_modules/types/node/globals.d.ts:28

Optional override for formatting stack traces

https://v8.dev/docs/stack-trace-api#customizing-stack-traces

Error.prepareStackTrace

static stackTraceLimit: number

Defined in: node_modules/types/node/globals.d.ts:30

Error.stackTraceLimit

static captureStackTrace(targetObject, constructorOpt?): void

Defined in: node_modules/types/node/globals.d.ts:21

Create .stack property on a target object

Error.captureStackTrace

@langchain/langgraph-sdk

@langchain/langgraph-sdk / AuthEventValueMap

Defined in: src/auth/types.ts:218

assistants:create: object

Defined in: src/auth/types.ts:226

optional assistant_id: Maybe\<string>

optional config: Maybe\<AssistantConfig>

optional if_exists: Maybe\<"raise" | "do_nothing">

optional metadata: Maybe\<Record\<string, unknown>>

optional name: Maybe\<string>

assistants:delete: object

Defined in: src/auth/types.ts:229

assistants:read: object

Defined in: src/auth/types.ts:227

optional metadata: Maybe\<Record\<string, unknown>>

assistants:search: object

Defined in: src/auth/types.ts:230

optional graph_id: Maybe\<string>

optional limit: Maybe\<number>

optional metadata: Maybe\<Record\<string, unknown>>

optional offset: Maybe\<number>

assistants:update: object

Defined in: src/auth/types.ts:228

optional config: Maybe\<AssistantConfig>

optional graph_id: Maybe\<string>

optional metadata: Maybe\<Record\<string, unknown>>

optional name: Maybe\<string>

optional version: Maybe\<number>

Defined in: src/auth/types.ts:232

optional cron_id: Maybe\<string>

optional end_time: Maybe\<string>

optional payload: Maybe\<Record\<string, unknown>>

optional thread_id: Maybe\<string>

optional user_id: Maybe\<string>

Defined in: src/auth/types.ts:235

Defined in: src/auth/types.ts:233

Defined in: src/auth/types.ts:236

optional assistant_id: Maybe\<string>

optional limit: Maybe\<number>

optional offset: Maybe\<number>

optional thread_id: Maybe\<string>

Defined in: src/auth/types.ts:234

optional payload: Maybe\<Record\<string, unknown>>

optional schedule: Maybe\<string>

Defined in: src/auth/types.ts:242

optional namespace: Maybe\<string[]>

Defined in: src/auth/types.ts:239

namespace: Maybe\<string[]>

store:list_namespaces: object

Defined in: src/auth/types.ts:241

optional limit: Maybe\<number>

optional max_depth: Maybe\<number>

optional namespace: Maybe\<string[]>

optional offset: Maybe\<number>

optional suffix: Maybe\<string[]>

Defined in: src/auth/types.ts:238

value: Record\<string, unknown>

Defined in: src/auth/types.ts:240

optional filter: Maybe\<Record\<string, unknown>>

optional limit: Maybe\<number>

optional namespace: Maybe\<string[]>

optional offset: Maybe\<number>

optional query: Maybe\<string>

threads:create: object

Defined in: src/auth/types.ts:219

optional if_exists: Maybe\<"raise" | "do_nothing">

optional metadata: Maybe\<Record\<string, unknown>>

optional thread_id: Maybe\<string>

threads:create_run: object

Defined in: src/auth/types.ts:224

optional after_seconds: Maybe\<number>

optional if_not_exists: Maybe\<"reject" | "create">

kwargs: Record\<string, unknown>

optional metadata: Maybe\<Record\<string, unknown>>

optional multitask_strategy: Maybe\<"reject" | "interrupt" | "rollback" | "enqueue">

optional prevent_insert_if_inflight: Maybe\<boolean>

status: Maybe\<"pending" | "running" | "error" | "success" | "timeout" | "interrupted">

optional thread_id: Maybe\<string>

threads:delete: object

Defined in: src/auth/types.ts:222

optional run_id: Maybe\<string>

optional thread_id: Maybe\<string>

Defined in: src/auth/types.ts:220

optional thread_id: Maybe\<string>

threads:search: object

Defined in: src/auth/types.ts:223

optional limit: Maybe\<number>

optional metadata: Maybe\<Record\<string, unknown>>

optional offset: Maybe\<number>

optional status: Maybe\<"error" | "interrupted" | "idle" | "busy" | string & object>

optional thread_id: Maybe\<string>

optional values: Maybe\<Record\<string, unknown>>

threads:update: object

Defined in: src/auth/types.ts:221

optional action: Maybe\<"interrupt" | "rollback">

optional metadata: Maybe\<Record\<string, unknown>>

optional thread_id: Maybe\<string>

@langchain/langgraph-sdk

@langchain/langgraph-sdk / AuthFilters

AuthFilters\<TKey>: { [key in TKey]: string | { [op in "\(contains" \| "\)eq"]?: string } }

Defined in: src/auth/types.ts:367

• TKey extends string | number | symbol

@langchain/langgraph-sdk

@langchain/langgraph-sdk / AssistantsClient

Defined in: client.ts:294

new AssistantsClient(config?): AssistantsClient

Defined in: client.ts:88

BaseClient.constructor

create(payload): Promise\<Assistant>

Defined in: client.ts:359

Create a new assistant.

Payload for creating an assistant.

The created assistant.

delete(assistantId): Promise\<void>

Defined in: client.ts:415

get(assistantId): Promise\<Assistant>

Defined in: client.ts:301

Get an assistant by ID.

The ID of the assistant.

getGraph(assistantId, options?): Promise\<AssistantGraph>

Defined in: client.ts:311

Get the JSON representation of the graph assigned to a runnable

The ID of the assistant.

Whether to include subgraphs in the serialized graph representation. If an integer value is provided, only subgraphs with a depth less than or equal to the value will be included.

Promise\<AssistantGraph>

getSchemas(assistantId): Promise\<GraphSchema>

Defined in: client.ts:325

Get the state and config schema of the graph assigned to a runnable

The ID of the assistant.

Promise\<GraphSchema>

getSubgraphs(assistantId, options?): Promise\<Subgraphs>

Defined in: client.ts:336

Get the schemas of an assistant by ID.

The ID of the assistant to get the schema of.

Additional options for getting subgraphs, such as namespace or recursion extraction.

The subgraphs of the assistant.

getVersions(assistantId, payload?): Promise\<AssistantVersion[]>

Defined in: client.ts:453

List all versions of an assistant.

Promise\<AssistantVersion[]>

List of assistant versions.

search(query?): Promise\<Assistant[]>

Defined in: client.ts:426

Promise\<Assistant[]>

setLatest(assistantId, version): Promise\<Assistant>

Defined in: client.ts:481

Change the version of an assistant.

The version to change to.

The updated assistant.

update(assistantId, payload): Promise\<Assistant>

Defined in: client.ts:388

Payload for updating the assistant.

The updated assistant.

@langchain/langgraph-sdk

@langchain/langgraph-sdk / Client

Defined in: client.ts:1448

• TStateType = DefaultValues

• TUpdateType = TStateType

• TCustomEventType = unknown

new Client\<TStateType, TUpdateType, TCustomEventType>(config?): Client\<TStateType, TUpdateType, TCustomEventType>

Defined in: client.ts:1484

Client\<TStateType, TUpdateType, TCustomEventType>

Defined in: client.ts:1482

The client for interacting with the UI. Used by LoadExternalComponent and the API might change in the future.

assistants: AssistantsClient

Defined in: client.ts:1456

The client for interacting with assistants.

Defined in: client.ts:1471

The client for interacting with cron runs.

runs: RunsClient\<TStateType, TUpdateType, TCustomEventType>

Defined in: client.ts:1466

The client for interacting with runs.

Defined in: client.ts:1476

The client for interacting with the KV store.

threads: ThreadsClient\<TStateType, TUpdateType>

Defined in: client.ts:1461

The client for interacting with threads.

@langchain/langgraph-sdk

@langchain/langgraph-sdk / CronsClient

Defined in: client.ts:197

new CronsClient(config?): CronsClient

Defined in: client.ts:88

BaseClient.constructor

create(assistantId, payload?): Promise\<CronCreateResponse>

Defined in: client.ts:238

Assistant ID to use for this cron job.

Payload for creating a cron job.

Promise\<CronCreateResponse>

createForThread(threadId, assistantId, payload?): Promise\<CronCreateForThreadResponse>

Defined in: client.ts:205

The ID of the thread.

Assistant ID to use for this cron job.

Payload for creating a cron job.

Promise\<CronCreateForThreadResponse>

The created background run.

delete(cronId): Promise\<void>

Defined in: client.ts:265

Cron ID of Cron job to delete.

search(query?): Promise\<Cron[]>

Defined in: client.ts:276

@langchain/langgraph-sdk

@langchain/langgraph-sdk / RunsClient

Defined in: client.ts:776

• TStateType = DefaultValues

• TUpdateType = TStateType

• TCustomEventType = unknown

new RunsClient\<TStateType, TUpdateType, TCustomEventType>(config?): RunsClient\<TStateType, TUpdateType, TCustomEventType>

Defined in: client.ts:88

RunsClient\<TStateType, TUpdateType, TCustomEventType>

BaseClient.constructor

cancel(threadId, runId, wait, action): Promise\<void>

Defined in: client.ts:1063

The ID of the thread.

Whether to block when canceling

CancelAction = "interrupt"

Action to take when cancelling the run. Possible values are interrupt or rollback. Default is interrupt.

create(threadId, assistantId, payload?): Promise\<Run>

Defined in: client.ts:885

The ID of the thread.

Assistant ID to use for this run.

Payload for creating a run.

createBatch(payloads): Promise\<Run[]>

Defined in: client.ts:921

Create a batch of stateless background runs.

RunsCreatePayload & object[]

An array of payloads for creating runs.

An array of created runs.

delete(threadId, runId): Promise\<void>

Defined in: client.ts:1157

The ID of the thread.

get(threadId, runId): Promise\<Run>

Defined in: client.ts:1050

The ID of the thread.

join(threadId, runId, options?): Promise\<void>

Defined in: client.ts:1085

Block until a run is done.

The ID of the thread.

joinStream(threadId, runId, options?): AsyncGenerator\<{ data: any; event: StreamEvent; }>

Defined in: client.ts:1111

Stream output from a run in real-time, until the run is done. Output is not buffered, so any output produced before this call will not be received here.

The ID of the thread.

Additional options for controlling the stream behavior: - signal: An AbortSignal that can be used to cancel the stream request - cancelOnDisconnect: When true, automatically cancels the run if the client disconnects from the stream - streamMode: Controls what types of events to receive from the stream (can be a single mode or array of modes) Must be a subset of the stream modes passed when creating the run. Background runs default to having the union of all stream modes enabled.

AbortSignal | { cancelOnDisconnect: boolean; signal: AbortSignal; streamMode: StreamMode | StreamMode[]; }

AsyncGenerator\<{ data: any; event: StreamEvent; }>

An async generator yielding stream parts.

list(threadId, options?): Promise\<Run[]>

Defined in: client.ts:1013

List all runs for a thread.

The ID of the thread.

Filtering and pagination options.

Maximum number of runs to return. Defaults to 10

Offset to start from. Defaults to 0.

Status of the run to filter by.

Create a run and stream the results.

The ID of the thread.

Assistant ID to use for this run.

Payload for creating a run.

stream\<TStreamMode, TSubgraphs>(threadId, assistantId, payload?): TypedAsyncGenerator\<TStreamMode, TSubgraphs, TStateType, TUpdateType, TCustomEventType>

Defined in: client.ts:781

• TStreamMode extends StreamMode | StreamMode[] = StreamMode

• TSubgraphs extends boolean = false

Omit\<RunsStreamPayload\<TStreamMode, TSubgraphs>, "multitaskStrategy" | "onCompletion">

TypedAsyncGenerator\<TStreamMode, TSubgraphs, TStateType, TUpdateType, TCustomEventType>

stream\<TStreamMode, TSubgraphs>(threadId, assistantId, payload?): TypedAsyncGenerator\<TStreamMode, TSubgraphs, TStateType, TUpdateType, TCustomEventType>

Defined in: client.ts:799

• TStreamMode extends StreamMode | StreamMode[] = StreamMode

• TSubgraphs extends boolean = false

RunsStreamPayload\<TStreamMode, TSubgraphs>

TypedAsyncGenerator\<TStreamMode, TSubgraphs, TStateType, TUpdateType, TCustomEventType>

Create a run and wait for it to complete.

The ID of the thread.

Assistant ID to use for this run.

Payload for creating a run.

wait(threadId, assistantId, payload?): Promise\<DefaultValues>

Defined in: client.ts:938

Omit\<RunsWaitPayload, "multitaskStrategy" | "onCompletion">

Promise\<DefaultValues>

wait(threadId, assistantId, payload?): Promise\<DefaultValues>

Defined in: client.ts:944

Promise\<DefaultValues>

@langchain/langgraph-sdk

@langchain/langgraph-sdk / StoreClient

Defined in: client.ts:1175

new StoreClient(config?): StoreClient

Defined in: client.ts:88

BaseClient.constructor

deleteItem(namespace, key): Promise\<void>

Defined in: client.ts:1296

A list of strings representing the namespace path.

The unique identifier for the item.

getItem(namespace, key, options?): Promise\<null | Item>

Defined in: client.ts:1252

Retrieve a single item.

A list of strings representing the namespace path.

The unique identifier for the item.

Whether to refresh the TTL on this read operation. If null, uses the store's default behavior.

Promise\<null | Item>

listNamespaces(options?): Promise\<ListNamespaceResponse>

Defined in: client.ts:1392

List namespaces with optional match conditions.

Maximum number of namespaces to return (default is 100).

Optional integer specifying the maximum depth of namespaces to return.

Number of namespaces to skip before returning results (default is 0).

Optional list of strings representing the prefix to filter namespaces.

Optional list of strings representing the suffix to filter namespaces.

Promise\<ListNamespaceResponse>

putItem(namespace, key, value, options?): Promise\<void>

Defined in: client.ts:1196

Store or update an item.

A list of strings representing the namespace path.

The unique identifier for the item within the namespace.

A dictionary containing the item's data.

null | false | string[]

Controls search indexing - null (use defaults), false (disable), or list of field paths to index.

Optional time-to-live in minutes for the item, or null for no expiration.

searchItems(namespacePrefix, options?): Promise\<SearchItemsResponse>

Defined in: client.ts:1347

Search for items within a namespace prefix.

List of strings representing the namespace prefix.

Optional dictionary of key-value pairs to filter results.

Maximum number of items to return (default is 10).

Number of items to skip before returning results (default is 0).

Optional search query.

Whether to refresh the TTL on items returned by this search. If null, uses the store's default behavior.

Promise\<SearchItemsResponse>

@langchain/langgraph-sdk

@langchain/langgraph-sdk / ThreadsClient

Defined in: client.ts:489

• TStateType = DefaultValues

• TUpdateType = TStateType

new ThreadsClient\<TStateType, TUpdateType>(config?): ThreadsClient\<TStateType, TUpdateType>

Defined in: client.ts:88

ThreadsClient\<TStateType, TUpdateType>

BaseClient.constructor

copy(threadId): Promise\<Thread\<TStateType>>

Defined in: client.ts:566

Copy an existing thread

ID of the thread to be copied

Promise\<Thread\<TStateType>>

create(payload?): Promise\<Thread\<TStateType>>

Defined in: client.ts:511

Payload for creating a thread.

Graph ID to associate with the thread.

How to handle duplicate creation.

Metadata for the thread.

Apply a list of supersteps when creating a thread, each containing a sequence of updates.

Used for copying a thread between deployments.

ID of the thread to create.

If not provided, a random UUID will be generated.

Promise\<Thread\<TStateType>>

delete(threadId): Promise\<void>

Defined in: client.ts:599

get\<ValuesType>(threadId): Promise\<Thread\<ValuesType>>

Defined in: client.ts:499

• ValuesType = TStateType

Promise\<Thread\<ValuesType>>

getHistory\<ValuesType>(threadId, options?): Promise\<ThreadState\<ValuesType>[]>

Defined in: client.ts:752

Get all past states for a thread.

• ValuesType = TStateType

Partial\<Omit\<Checkpoint, "thread_id">>

Promise\<ThreadState\<ValuesType>[]>

List of thread states.

getState\<ValuesType>(threadId, checkpoint?, options?): Promise\<ThreadState\<ValuesType>>

Defined in: client.ts:659

Get state for a thread.

• ValuesType = TStateType

Promise\<ThreadState\<ValuesType>>

patchState(threadIdOrConfig, metadata): Promise\<void>

Defined in: client.ts:722

Patch the metadata of a thread.

Thread ID or config to patch the state of.

Metadata to patch the state with.

search\<ValuesType>(query?): Promise\<Thread\<ValuesType>[]>

Defined in: client.ts:611

• ValuesType = TStateType

Maximum number of threads to return. Defaults to 10

Metadata to filter threads by.

Offset to start from.

Sort order. Must be one of 'asc' or 'desc'.

Thread status to filter on. Must be one of 'idle', 'busy', 'interrupted' or 'error'.

Promise\<Thread\<ValuesType>[]>

update(threadId, payload?): Promise\<Thread\<DefaultValues>>

Defined in: client.ts:579

Payload for updating the thread.

Metadata for the thread.

Promise\<Thread\<DefaultValues>>

updateState\<ValuesType>(threadId, options): Promise\<Pick\<Config, "configurable">>

Defined in: client.ts:693

Add state to a thread.

• ValuesType = TUpdateType

The ID of the thread.

Promise\<Pick\<Config, "configurable">>

@langchain/langgraph-sdk

@langchain/langgraph-sdk / getApiKey

getApiKey(apiKey?): undefined | string

Defined in: client.ts:53

Get the API key from the environment. Precedence: 1. explicit argument 2. LANGGRAPH_API_KEY 3. LANGSMITH_API_KEY 4. LANGCHAIN_API_KEY

Optional API key provided as an argument

The API key if found, otherwise undefined

@langchain/langgraph-sdk

@langchain/langgraph-sdk / ClientConfig

Defined in: client.ts:71

optional apiKey: string

Defined in: client.ts:73

optional apiUrl: string

Defined in: client.ts:72

optional callerOptions: AsyncCallerParams

Defined in: client.ts:74

optional defaultHeaders: Record\<string, undefined | null | string>

Defined in: client.ts:76

optional timeoutMs: number

Defined in: client.ts:75

langchain/langgraph-sdk

@langchain/langgraph-sdk

@langchain/langgraph-sdk / useStream

useStream\<StateType, Bag>(options): UseStream\<StateType, Bag>

Defined in: react/stream.tsx:618

• StateType extends Record\<string, unknown> = Record\<string, unknown>

• Bag extends object = BagTemplate

UseStreamOptions\<StateType, Bag>

UseStream\<StateType, Bag>

@langchain/langgraph-sdk

@langchain/langgraph-sdk / UseStream

Defined in: react/stream.tsx:507

• StateType extends Record\<string, unknown> = Record\<string, unknown>

• Bag extends BagTemplate = BagTemplate

Defined in: react/stream.tsx:592

The ID of the assistant to use.

Defined in: react/stream.tsx:542

The current branch of the thread.

Defined in: react/stream.tsx:587

LangGraph SDK client used to send request and receive responses.

Defined in: react/stream.tsx:519

Last seen error from the thread or during streaming.

experimental_branchTree: Sequence\<StateType>

Defined in: react/stream.tsx:558

Tree of all branches for the thread.

getMessagesMetadata: (message, index?) => undefined | MessageMetadata\<StateType>

Defined in: react/stream.tsx:579

Get the metadata for a message, such as first thread state the message was seen in and branch information.

The message to get the metadata for.

The index of the message in the thread.

undefined | MessageMetadata\<StateType>

The metadata for the message.

history: ThreadState\<StateType>[]

Defined in: react/stream.tsx:552

Flattened history of thread states of a thread.

interrupt: undefined | Interrupt\<GetInterruptType\<Bag>>

Defined in: react/stream.tsx:563

Get the interrupt value for the stream if interrupted.

Defined in: react/stream.tsx:524

Whether the stream is currently running.

Defined in: react/stream.tsx:569

Messages inferred from the thread. Will automatically update with incoming message chunks.

setBranch: (branch) => void

Defined in: react/stream.tsx:547

Set the branch of the thread.

Defined in: react/stream.tsx:529

submit: (values, options?) => void

Defined in: react/stream.tsx:534

Create and stream a run to the thread.

undefined | null | GetUpdateType\<Bag, StateType>

SubmitOptions\<StateType, GetConfigurableType\<Bag>>

Defined in: react/stream.tsx:514

The current values of the thread.

@langchain/langgraph-sdk

@langchain/langgraph-sdk / UseStreamOptions

Defined in: react/stream.tsx:408

• StateType extends Record\<string, unknown> = Record\<string, unknown>

• Bag extends BagTemplate = BagTemplate

optional apiKey: string

Defined in: react/stream.tsx:430

optional apiUrl: string

Defined in: react/stream.tsx:425

The URL of the API to use.

Defined in: react/stream.tsx:415

The ID of the assistant to use.

optional callerOptions: AsyncCallerParams

Defined in: react/stream.tsx:435

Custom call options, such as custom fetch implementation.

optional client: Client\<DefaultValues, DefaultValues, unknown>

Defined in: react/stream.tsx:420

Client used to send requests.

optional defaultHeaders: Record\<string, undefined | null | string>

Defined in: react/stream.tsx:440

Default headers to send with requests.

optional messagesKey: string

Defined in: react/stream.tsx:448

Specify the key within the state that contains messages. Defaults to "messages".

optional onCustomEvent: (data, options) => void

Defined in: react/stream.tsx:470

Callback that is called when a custom event is received.

GetCustomEventType\<Bag>

optional onDebugEvent: (data) => void

Defined in: react/stream.tsx:494

Callback that is called when a debug event is received. This API is experimental and subject to change.

optional onError: (error) => void

Defined in: react/stream.tsx:453

Callback that is called when an error occurs.

optional onFinish: (state) => void

Defined in: react/stream.tsx:458

Callback that is called when the stream is finished.

ThreadState\<StateType>

optional onLangChainEvent: (data) => void

Defined in: react/stream.tsx:488

Callback that is called when a LangChain event is received.

string & object | "on_tool_start" | "on_tool_stream" | "on_tool_end" | "on_chat_model_start" | "on_chat_model_stream" | "on_chat_model_end" | "on_llm_start" | "on_llm_stream" | "on_llm_end" | "on_chain_start" | "on_chain_stream" | "on_chain_end" | "on_retriever_start" | "on_retriever_stream" | "on_retriever_end" | "on_prompt_start" | "on_prompt_stream" | "on_prompt_end"

Record\<string, unknown>

https://langchain-ai.github.io/langgraph/cloud/how-tos/stream_events/#stream-graph-in-events-mode for more details.

optional onMetadataEvent: (data) => void

Defined in: react/stream.tsx:482

Callback that is called when a metadata event is received.

optional onThreadId: (threadId) => void

Defined in: react/stream.tsx:504

Callback that is called when the thread ID is updated (ie when a new thread is created).

optional onUpdateEvent: (data) => void

Defined in: react/stream.tsx:463

Callback that is called when an update event is received.

optional threadId: null | string

Defined in: react/stream.tsx:499

The ID of the thread to fetch history and current values from.

@langchain/langgraph-sdk

@langchain/langgraph-sdk / MessageMetadata

MessageMetadata\<StateType>: object

Defined in: react/stream.tsx:169

• StateType extends Record\<string, unknown>

branch: string | undefined

The branch of the message.

branchOptions: string[] | undefined

The list of branches this message is part of. This is useful for displaying branching controls.

firstSeenState: ThreadState\<StateType> | undefined

The first thread state the message was seen in.

The ID of the message used.

**Examples:**

Example 1 (javascript):
```javascript
const item = await client.store.getItem(
  ["documents", "user123"],
  "item456",
  { refreshTtl: true }
);
console.log(item);
// {
//   namespace: ["documents", "user123"],
//   key: "item456",
//   value: { title: "My Document", content: "Hello World" },
//   createdAt: "2024-07-30T12:00:00Z",
//   updatedAt: "2024-07-30T12:00:00Z"
// }
```

Example 2 (unknown):
```unknown
await client.store.putItem(
  ["documents", "user123"],
  "item456",
  { title: "My Document", content: "Hello World" },
  { ttl: 60 } // expires in 60 minutes
);
```

Example 3 (javascript):
```javascript
const results = await client.store.searchItems(
  ["documents"],
  {
    filter: { author: "John Doe" },
    limit: 5,
    refreshTtl: true
  }
);
console.log(results);
// {
//   items: [
//     {
//       namespace: ["documents", "user123"],
//       key: "item789",
//       value: { title: "Another Document", author: "John Doe" },
//       createdAt: "2024-07-30T12:00:00Z",
//       updatedAt: "2024-07-30T12:00:00Z"
//     },
//     // ... additional items ...
//   ]
// }
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/cloud/reference/api/api_ref.html

---

## How to use the graph API¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/graph-api/

**Contents:**
- How to use the graph API¶
- Setup¶
- Define and update state¶
  - Define state¶
  - Update state¶
  - Process state updates with reducers¶
    - MessagesState¶
  - Define input and output schemas¶
  - Pass private state between nodes¶
  - Use Pydantic models for graph state¶

This guide demonstrates the basics of LangGraph's Graph API. It walks through state, as well as composing common graph structures such as sequences, branches, and loops. It also covers LangGraph's control features, including the Send API for map-reduce workflows and the Command API for combining state updates with "hops" across nodes.

Set up LangSmith for better debugging

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started in the docs.

Here we show how to define and update state in LangGraph. We will demonstrate:

State in LangGraph can be a TypedDict, Pydantic model, or dataclass. Below we will use TypedDict. See this section for detail on using Pydantic.

By default, graphs will have the same input and output schema, and the state determines that schema. See this section for how to define distinct input and output schemas.

Let's consider a simple example using messages. This represents a versatile formulation of state for many LLM applications. See our concepts page for more detail.

API Reference: AnyMessage

This state tracks a list of message objects, as well as an extra integer field.

Let's build an example graph with a single node. Our node is just a Python function that reads our graph's state and makes updates to it. The first argument to this function will always be the state:

API Reference: AIMessage

This node simply appends a message to our message list, and populates an extra field.

Nodes should return updates to the state directly, instead of mutating the state.

Let's next define a simple graph containing this node. We use StateGraph to define a graph that operates on this state. We then use add_node populate our graph.

API Reference: StateGraph

LangGraph provides built-in utilities for visualizing your graph. Let's inspect our graph. See this section for detail on visualization.

In this case, our graph just executes a single node. Let's proceed with a simple invocation:

API Reference: HumanMessage

For convenience, we frequently inspect the content of message objects via pretty-print:

Each key in the state can have its own independent reducer function, which controls how updates from nodes are applied. If no reducer function is explicitly specified then it is assumed that all updates to the key should override it.

For TypedDict state schemas, we can define reducers by annotating the corresponding field of the state with a reducer function.

In the earlier example, our node updated the "messages" key in the state by appending a message to it. Below, we add a reducer to this key, such that updates are automatically appended:

Now our node can be simplified:

In practice, there are additional considerations for updating lists of messages:

LangGraph includes a built-in reducer add_messages that handles these considerations:

API Reference: add_messages

This is a versatile representation of state for applications involving chat models. LangGraph includes a pre-built MessagesState for convenience, so that we can have:

By default, StateGraph operates with a single schema, and all nodes are expected to communicate using that schema. However, it's also possible to define distinct input and output schemas for a graph.

When distinct schemas are specified, an internal schema will still be used for communication between nodes. The input schema ensures that the provided input matches the expected structure, while the output schema filters the internal data to return only the relevant information according to the defined output schema.

Below, we'll see how to define distinct input and output schema.

API Reference: StateGraph | START | END

Notice that the output of invoke only includes the output schema.

In some cases, you may want nodes to exchange information that is crucial for intermediate logic but doesn't need to be part of the main schema of the graph. This private data is not relevant to the overall input/output of the graph and should only be shared between certain nodes.

Below, we'll create an example sequential graph consisting of three nodes (node_1, node_2 and node_3), where private data is passed between the first two steps (node_1 and node_2), while the third step (node_3) only has access to the public overall state.

API Reference: StateGraph | START | END

A StateGraph accepts a state_schema argument on initialization that specifies the "shape" of the state that the nodes in the graph can access and update.

In our examples, we typically use a python-native TypedDict or dataclass for state_schema, but state_schema can be any type.

Here, we'll see how a Pydantic BaseModel can be used for state_schema to add run-time validation on inputs.

API Reference: StateGraph | START | END

Invoke the graph with an invalid input

See below for additional features of Pydantic model state:

When using Pydantic models as state schemas, it's important to understand how serialization works, especially when: - Passing Pydantic objects as inputs - Receiving outputs from the graph - Working with nested Pydantic models

Let's see these behaviors in action.

Pydantic performs runtime type coercion for certain data types. This can be helpful but also lead to unexpected behavior if you're not aware of it.

When working with LangChain message types in your state schema, there are important considerations for serialization. You should use AnyMessage (rather than BaseMessage) for proper serialization/deserialization when using message objects over the wire.

Sometimes you want to be able to configure your graph when calling it. For example, you might want to be able to specify what LLM or system prompt to use at runtime, without polluting the graph state with these parameters.

To add runtime configuration:

See below for a simple example:

API Reference: END | StateGraph | START

Below we demonstrate a practical example in which we configure what LLM to use at runtime. We will use both OpenAI and Anthropic models.

from dataclasses import dataclass from langchain.chat_models import init_chat_model from langgraph.graph import MessagesState, END, StateGraph, START from langgraph.runtime import Runtime from typing_extensions import TypedDict @dataclass class ContextSchema: model_provider: str = "anthropic" MODELS = { "anthropic": init_chat_model("anthropic:claude-3-5-haiku-latest"), "openai": init_chat_model("openai:gpt-4.1-mini"), } def call_model(state: MessagesState, runtime: Runtime[ContextSchema]): model = MODELS[runtime.context.model_provider] response = model.invoke(state["messages"]) return {"messages": [response]} builder = StateGraph(MessagesState, context_schema=ContextSchema) builder.add_node("model", call_model) builder.add_edge(START, "model") builder.add_edge("model", END) graph = builder.compile() # Usage input_message = {"role": "user", "content": "hi"} # With no configuration, uses default (Anthropic) response_1 = graph.invoke({"messages": [input_message]}, context=ContextSchema())["messages"][-1] # Or, can set OpenAI response_2 = graph.invoke({"messages": [input_message]}, context={"model_provider": "openai"})["messages"][-1] print(response_1.response_metadata["model_name"]) print(response_2.response_metadata["model_name"]) claude-3-5-haiku-20241022 gpt-4.1-mini-2025-04-14

Below we demonstrate a practical example in which we configure two parameters: the LLM and system message to use at runtime.

from dataclasses import dataclass from typing import Optional from langchain.chat_models import init_chat_model from langchain_core.messages import SystemMessage from langgraph.graph import END, MessagesState, StateGraph, START from langgraph.runtime import Runtime from typing_extensions import TypedDict @dataclass class ContextSchema: model_provider: str = "anthropic" system_message: str | None = None MODELS = { "anthropic": init_chat_model("anthropic:claude-3-5-haiku-latest"), "openai": init_chat_model("openai:gpt-4.1-mini"), } def call_model(state: MessagesState, runtime: Runtime[ContextSchema]): model = MODELS[runtime.context.model_provider] messages = state["messages"] if (system_message := runtime.context.system_message): messages = [SystemMessage(system_message)] + messages response = model.invoke(messages) return {"messages": [response]} builder = StateGraph(MessagesState, context_schema=ContextSchema) builder.add_node("model", call_model) builder.add_edge(START, "model") builder.add_edge("model", END) graph = builder.compile() # Usage input_message = {"role": "user", "content": "hi"} response = graph.invoke({"messages": [input_message]}, context={"model_provider": "openai", "system_message": "Respond in Italian."}) for message in response["messages"]: message.pretty_print() ================================ Human Message ================================ hi ================================== Ai Message ================================== Ciao! Come posso aiutarti oggi?

There are many use cases where you may wish for your node to have a custom retry policy, for example if you are calling an API, querying a database, or calling an LLM, etc. LangGraph lets you add retry policies to nodes.

To configure a retry policy, pass the retry_policy parameter to the add_node. The retry_policy parameter takes in a RetryPolicy named tuple object. Below we instantiate a RetryPolicy object with the default parameters and associate it with a node:

API Reference: RetryPolicy

By default, the retry_on parameter uses the default_retry_on function, which retries on any exception except for the following:

In addition, for exceptions from popular http request libraries such as requests and httpx it only retries on 5xx status codes.

Consider an example in which we are reading from a SQL database. Below we pass two different retry policies to nodes:

Node caching is useful in cases where you want to avoid repeating operations, like when doing something expensive (either in terms of time or cost). LangGraph lets you add individualized caching policies to nodes in a graph.

To configure a cache policy, pass the cache_policy parameter to the add_node function. In the following example, a CachePolicy object is instantiated with a time to live of 120 seconds and the default key_func generator. Then it is associated with a node:

Then, to enable node-level caching for a graph, set the cache argument when compiling the graph. The example below uses InMemoryCache to set up a graph with in-memory cache, but SqliteCache is also available.

This guide assumes familiarity with the above section on state.

Here we demonstrate how to construct a simple sequence of steps. We will show:

To add a sequence of nodes, we use the .add_node and .add_edge methods of our graph:

API Reference: START | StateGraph

We can also use the built-in shorthand .add_sequence:

LangGraph makes it easy to add an underlying persistence layer to your application. This allows state to be checkpointed in between the execution of nodes, so your LangGraph nodes govern:

They also determine how execution steps are streamed, and how your application is visualized and debugged using LangGraph Studio.

Let's demonstrate an end-to-end example. We will create a sequence of three steps:

Let's first define our state. This governs the schema of the graph, and can also specify how to apply updates. See this section for more detail.

In our case, we will just keep track of two values:

Our nodes are just Python functions that read our graph's state and make updates to it. The first argument to this function will always be the state:

Note that when issuing updates to the state, each node can just specify the value of the key it wishes to update.

By default, this will overwrite the value of the corresponding key. You can also use reducers to control how updates are processed— for example, you can append successive updates to a key instead. See this section for more detail.

Finally, we define the graph. We use StateGraph to define a graph that operates on this state.

We will then use add_node and add_edge to populate our graph and define its control flow.

API Reference: START | StateGraph

Specifying custom names

You can specify custom names for nodes using .add_node:

We next compile our graph. This provides a few basic checks on the structure of the graph (e.g., identifying orphaned nodes). If we were adding persistence to our application via a checkpointer, it would also be passed in here.

LangGraph provides built-in utilities for visualizing your graph. Let's inspect our sequence. See this guide for detail on visualization.

Let's proceed with a simple invocation:

langgraph>=0.2.46 includes a built-in short-hand add_sequence for adding node sequences. You can compile the same graph as follows:

Parallel execution of nodes is essential to speed up overall graph operation. LangGraph offers native support for parallel execution of nodes, which can significantly enhance the performance of graph-based workflows. This parallelization is achieved through fan-out and fan-in mechanisms, utilizing both standard edges and conditional_edges. Below are some examples showing how to add create branching dataflows that work for you.

In this example, we fan out from Node A to B and C and then fan in to D. With our state, we specify the reducer add operation. This will combine or accumulate values for the specific key in the State, rather than simply overwriting the existing value. For lists, this means concatenating the new list with the existing list. See the above section on state reducers for more detail on updating state with reducers.

API Reference: StateGraph | START | END

With the reducer, you can see that the values added in each node are accumulated.

In the above example, nodes "b" and "c" are executed concurrently in the same superstep. Because they are in the same step, node "d" executes after both "b" and "c" are finished.

Importantly, updates from a parallel superstep may not be ordered consistently. If you need a consistent, predetermined ordering of updates from a parallel superstep, you should write the outputs to a separate field in the state together with a value with which to order them.

LangGraph executes nodes within supersteps, meaning that while parallel branches are executed in parallel, the entire superstep is transactional. If any of these branches raises an exception, none of the updates are applied to the state (the entire superstep errors).

Importantly, when using a checkpointer, results from successful nodes within a superstep are saved, and don't repeat when resumed.

If you have error-prone (perhaps want to handle flakey API calls), LangGraph provides two ways to address this:

Together, these let you perform parallel execution and fully control exception handling.

Deferring node execution is useful when you want to delay the execution of a node until all other pending tasks are completed. This is particularly relevant when branches have different lengths, which is common in workflows like map-reduce flows.

The above example showed how to fan-out and fan-in when each path was only one step. But what if one branch had more than one step? Let's add a node "b_2" in the "b" branch:

API Reference: StateGraph | START | END

In the above example, nodes "b" and "c" are executed concurrently in the same superstep. We set defer=True on node d so it will not execute until all pending tasks are finished. In this case, this means that "d" waits to execute until the entire "b" branch is finished.

If your fan-out should vary at runtime based on the state, you can use add_conditional_edges to select one or more paths using the graph state. See example below, where node a generates a state update that determines the following node.

API Reference: StateGraph | START | END

Your conditional edges can route to multiple destination nodes. For example:

LangGraph supports map-reduce and other advanced branching patterns using the Send API. Here is an example of how to use it:

API Reference: StateGraph | START | END | Send

When creating a graph with a loop, we require a mechanism for terminating execution. This is most commonly done by adding a conditional edge that routes to the END node once we reach some termination condition.

You can also set the graph recursion limit when invoking or streaming the graph. The recursion limit sets the number of supersteps that the graph is allowed to execute before it raises an error. Read more about the concept of recursion limits here.

Let's consider a simple graph with a loop to better understand how these mechanisms work.

To return the last value of your state instead of receiving a recursion limit error, see the next section.

When creating a loop, you can include a conditional edge that specifies a termination condition:

To control the recursion limit, specify "recursionLimit" in the config. This will raise a GraphRecursionError, which you can catch and handle:

Let's define a graph with a simple loop. Note that we use a conditional edge to implement a termination condition.

API Reference: StateGraph | START | END

This architecture is similar to a React agent in which node "a" is a tool-calling model, and node "b" represents the tools.

In our route conditional edge, we specify that we should end after the "aggregate" list in the state passes a threshold length.

Invoking the graph, we see that we alternate between nodes "a" and "b" before terminating once we reach the termination condition.

In some applications, we may not have a guarantee that we will reach a given termination condition. In these cases, we can set the graph's recursion limit. This will raise a GraphRecursionError after a given number of supersteps. We can then catch and handle this exception:

Instead of raising GraphRecursionError, we can introduce a new key to the state that keeps track of the number of steps remaining until reaching the recursion limit. We can then use this key to determine if we should end the run.

LangGraph implements a special RemainingSteps annotation. Under the hood, it creates a ManagedValue channel -- a state channel that will exist for the duration of our graph run and no longer.

import operator from typing import Annotated, Literal from typing_extensions import TypedDict from langgraph.graph import StateGraph, START, END from langgraph.managed.is_last_step import RemainingSteps class State(TypedDict): aggregate: Annotated[list, operator.add] remaining_steps: RemainingSteps def a(state: State): print(f'Node A sees {state["aggregate"]}') return {"aggregate": ["A"]} def b(state: State): print(f'Node B sees {state["aggregate"]}') return {"aggregate": ["B"]} # Define nodes builder = StateGraph(State) builder.add_node(a) builder.add_node(b) # Define edges def route(state: State) -> Literal["b", END]: if state["remaining_steps"] <= 2: return END else: return "b" builder.add_edge(START, "a") builder.add_conditional_edges("a", route) builder.add_edge("b", "a") graph = builder.compile() # Test it out result = graph.invoke({"aggregate": []}, {"recursion_limit": 4}) print(result) Node A sees [] Node B sees ['A'] Node A sees ['A', 'B'] {'aggregate': ['A', 'B', 'A']}

To better understand how the recursion limit works, let's consider a more complex example. Below we implement a loop, but one step fans out into two nodes:

This graph looks complex, but can be conceptualized as loop of supersteps:

We have a loop of four supersteps, where nodes C and D are executed concurrently.

Invoking the graph as before, we see that we complete two full "laps" before hitting the termination condition:

result = graph.invoke({"aggregate": []}) Node A sees [] Node B sees ['A'] Node D sees ['A', 'B'] Node C sees ['A', 'B'] Node A sees ['A', 'B', 'C', 'D'] Node B sees ['A', 'B', 'C', 'D', 'A'] Node D sees ['A', 'B', 'C', 'D', 'A', 'B'] Node C sees ['A', 'B', 'C', 'D', 'A', 'B'] Node A sees ['A', 'B', 'C', 'D', 'A', 'B', 'C', 'D']

However, if we set the recursion limit to four, we only complete one lap because each lap is four supersteps:

from langgraph.errors import GraphRecursionError try: result = graph.invoke({"aggregate": []}, {"recursion_limit": 4}) except GraphRecursionError: print("Recursion Error") Node A sees [] Node B sees ['A'] Node C sees ['A', 'B'] Node D sees ['A', 'B'] Node A sees ['A', 'B', 'C', 'D'] Recursion Error

Using the async programming paradigm can produce significant performance improvements when running IO-bound code concurrently (e.g., making concurrent API requests to a chat model provider).

To convert a sync implementation of the graph to an async implementation, you will need to:

Because many LangChain objects implement the Runnable Protocol which has async variants of all the sync methods it's typically fairly quick to upgrade a sync graph to an async graph.

See example below. To demonstrate async invocations of underlying LLMs, we will include a chat model:

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["OPENAI_API_KEY"] = "sk-..." llm = init_chat_model("openai:gpt-4.1")

👉 Read the OpenAI integration docs

pip install -U "langchain[anthropic]" import os from langchain.chat_models import init_chat_model os.environ["ANTHROPIC_API_KEY"] = "sk-..." llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

👉 Read the Anthropic integration docs

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["AZURE_OPENAI_API_KEY"] = "..." os.environ["AZURE_OPENAI_ENDPOINT"] = "..." os.environ["OPENAI_API_VERSION"] = "2025-03-01-preview" llm = init_chat_model( "azure_openai:gpt-4.1", azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"], )

👉 Read the Azure integration docs

pip install -U "langchain[google-genai]" import os from langchain.chat_models import init_chat_model os.environ["GOOGLE_API_KEY"] = "..." llm = init_chat_model("google_genai:gemini-2.0-flash")

👉 Read the Google GenAI integration docs

pip install -U "langchain[aws]" from langchain.chat_models import init_chat_model # Follow the steps here to configure your credentials: # https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html llm = init_chat_model( "anthropic.claude-3-5-sonnet-20240620-v1:0", model_provider="bedrock_converse", )

👉 Read the AWS Bedrock integration docs

API Reference: init_chat_model | StateGraph

See the streaming guide for examples of streaming with async.

It can be useful to combine control flow (edges) and state updates (nodes). For example, you might want to BOTH perform state updates AND decide which node to go to next in the SAME node. LangGraph provides a way to do so by returning a Command object from node functions:

We show an end-to-end example below. Let's create a simple graph with 3 nodes: A, B and C. We will first execute node A, and then decide whether to go to Node B or Node C next based on the output of node A.

API Reference: StateGraph | START | Command

We can now create the StateGraph with the above nodes. Notice that the graph doesn't have conditional edges for routing! This is because control flow is defined with Command inside node_a.

You might have noticed that we used Command as a return type annotation, e.g. Command[Literal["node_b", "node_c"]]. This is necessary for the graph rendering and tells LangGraph that node_a can navigate to node_b and node_c.

If we run the graph multiple times, we'd see it take different paths (A -> B or A -> C) based on the random choice in node A.

If you are using subgraphs, you might want to navigate from a node within a subgraph to a different subgraph (i.e. a different node in the parent graph). To do so, you can specify graph=Command.PARENT in Command:

Let's demonstrate this using the above example. We'll do so by changing nodeA in the above example into a single-node graph that we'll add as a subgraph to our parent graph.

State updates with Command.PARENT

When you send updates from a subgraph node to a parent graph node for a key that's shared by both parent and subgraph state schemas, you must define a reducer for the key you're updating in the parent graph state. See the example below.

A common use case is updating graph state from inside a tool. For example, in a customer support application you might want to look up customer information based on their account number or ID in the beginning of the conversation. To update the graph state from the tool, you can return Command(update={"my_custom_key": "foo", "messages": [...]}) from the tool:

You MUST include messages (or any state key used for the message history) in Command.update when returning Command from a tool and the list of messages in messages MUST contain a ToolMessage. This is necessary for the resulting message history to be valid (LLM providers require AI messages with tool calls to be followed by the tool result messages).

If you are using tools that update state via Command, we recommend using prebuilt ToolNode which automatically handles tools returning Command objects and propagates them to the graph state. If you're writing a custom node that calls tools, you would need to manually propagate Command objects returned by the tools as the update from the node.

Here we demonstrate how to visualize the graphs you create.

You can visualize any arbitrary Graph, including StateGraph.

Let's have some fun by drawing fractals :).

API Reference: StateGraph | START | END | add_messages

We can also convert a graph class into Mermaid syntax.

If preferred, we could render the Graph into a .png. Here we could use three options:

By default, draw_mermaid_png() uses Mermaid.Ink's API to generate the diagram.

API Reference: CurveStyle | MermaidDrawMethod | NodeStyles

Using Mermaid + Pyppeteer

**Examples:**

Example 1 (unknown):
```unknown
pip install -U langgraph
```

Example 2 (python):
```python
from langchain_core.messages import AnyMessage
from typing_extensions import TypedDict

class State(TypedDict):
    messages: list[AnyMessage]
    extra_field: int
```

Example 3 (python):
```python
from langchain_core.messages import AIMessage

def node(state: State):
    messages = state["messages"]
    new_message = AIMessage("Hello!")
    return {"messages": messages + [new_message], "extra_field": 10}
```

Example 4 (python):
```python
from langgraph.graph import StateGraph

builder = StateGraph(State)
builder.add_node(node)
builder.set_entry_point("node")
graph = builder.compile()
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/how-tos/recursion-limit/

---

## RemoteGraph¶

**URL:** https://langchain-ai.github.io/langgraph/reference/remote_graph/

**Contents:**
- RemoteGraph¶
- RemoteGraph ¶
  - InputType property ¶
  - OutputType property ¶
  - input_schema property ¶
  - output_schema property ¶
  - config_specs property ¶
  - __init__ ¶
  - get_graph ¶
  - aget_graph async ¶

The RemoteGraph class is a client implementation for calling remote

Bases: PregelProtocol

The RemoteGraph class is a client implementation for calling remote APIs that implement the LangGraph Server API specification.

For example, the RemoteGraph class can be used to call APIs from deployments on LangSmith Deployment.

RemoteGraph behaves the same way as a Graph and can be used directly as a node in another Graph.

Specify url, api_key, and/or headers to create default sync and async clients.

Get graph by graph name.

Get graph by graph name.

Get the state of a thread.

Get the state of a thread.

Get the state history of a thread.

Get the state history of a thread.

Update the state of a thread.

Update the state of a thread.

Create a run and stream the results.

Create a run and stream the results.

Create a run, wait until it finishes and return the final state.

Create a run, wait until it finishes and return the final state.

Get the name of the Runnable.

Get a pydantic model that can be used to validate input to the Runnable.

Get a JSON schema that represents the input to the Runnable.

Get a pydantic model that can be used to validate output to the Runnable.

Get a JSON schema that represents the output of the Runnable.

The type of config this Runnable accepts specified as a pydantic model.

Get a JSON schema that represents the config of the Runnable.

Return a list of prompts used by this Runnable.

Compose this Runnable with another object to create a RunnableSequence.

Compose this Runnable with another object to create a RunnableSequence.

Compose this Runnable with Runnable-like objects to make a RunnableSequence.

Pick keys from the output dict of this Runnable.

Assigns new fields to the dict output of this Runnable.

Default implementation runs invoke in parallel using a thread pool executor.

Run invoke in parallel on a list of inputs.

Default implementation runs ainvoke in parallel using asyncio.gather.

Run ainvoke in parallel on a list of inputs.

Stream all output from a Runnable, as reported to the callback system.

Default implementation of transform, which buffers input and calls astream.

Default implementation of atransform, which buffers input and calls astream.

Bind arguments to a Runnable, returning a new Runnable.

Bind lifecycle listeners to a Runnable, returning a new Runnable.

Bind async lifecycle listeners to a Runnable, returning a new Runnable.

Bind input and output types to a Runnable, returning a new Runnable.

Create a new Runnable that retries the original Runnable on exceptions.

Return a new Runnable that maps a list of inputs to a list of outputs.

Add fallbacks to a Runnable, returning a new Runnable.

Create a BaseTool from a Runnable.

The type of input this Runnable accepts specified as a type annotation.

The type of output this Runnable produces specified as a type annotation.

The type of input this Runnable accepts specified as a pydantic model.

The type of output this Runnable produces specified as a pydantic model.

List configurable fields for this Runnable.

The type of input this Runnable accepts specified as a type annotation.

The type of output this Runnable produces specified as a type annotation.

The type of input this Runnable accepts specified as a pydantic model.

The type of output this Runnable produces specified as a pydantic model.

List configurable fields for this Runnable.

Specify url, api_key, and/or headers to create default sync and async clients.

If client or sync_client are provided, they will be used instead of the default clients. See LangGraphClient and SyncLangGraphClient for details on the default clients. At least one of url, client, or sync_client must be provided.

The assistant ID or graph name of the remote graph to use.

The URL of the remote API.

The API key to use for authentication. If not provided, it will be read from the environment (LANGGRAPH_API_KEY, LANGSMITH_API_KEY, or LANGCHAIN_API_KEY).

Additional headers to include in the requests.

A LangGraphClient instance to use instead of creating a default client.

A SyncLangGraphClient instance to use instead of creating a default client.

An optional RunnableConfig instance with additional configuration.

Human-readable name to attach to the RemoteGraph instance. This is useful for adding RemoteGraph as a subgraph via graph.add_node(remote_graph). If not provided, defaults to the assistant ID.

Whether to enable sending LangSmith distributed tracing headers.

Get graph by graph name.

This method calls GET /assistants/{assistant_id}/graph.

This parameter is not used.

Include graph representation of subgraphs. If an integer value is provided, only subgraphs with a depth less than or equal to the value will be included.

The graph information for the assistant in JSON format.

Get graph by graph name.

This method calls GET /assistants/{assistant_id}/graph.

This parameter is not used.

Include graph representation of subgraphs. If an integer value is provided, only subgraphs with a depth less than or equal to the value will be included.

The graph information for the assistant in JSON format.

Get the state of a thread.

This method calls POST /threads/{thread_id}/state/checkpoint if a checkpoint is specified in the config or GET /threads/{thread_id}/state if no checkpoint is specified.

A RunnableConfig that includes thread_id in the configurable field.

Include subgraphs in the state.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The latest state of the thread.

Get the state of a thread.

This method calls POST /threads/{thread_id}/state/checkpoint if a checkpoint is specified in the config or GET /threads/{thread_id}/state if no checkpoint is specified.

A RunnableConfig that includes thread_id in the configurable field.

Include subgraphs in the state.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

The latest state of the thread.

Get the state history of a thread.

This method calls POST /threads/{thread_id}/history.

A RunnableConfig that includes thread_id in the configurable field.

Metadata to filter on.

A RunnableConfig that includes checkpoint metadata.

Max number of states to return.

States of the thread.

Get the state history of a thread.

This method calls POST /threads/{thread_id}/history.

A RunnableConfig that includes thread_id in the configurable field.

Metadata to filter on.

A RunnableConfig that includes checkpoint metadata.

Max number of states to return.

Optional custom headers to include with the request.

Optional query parameters to include with the request.

States of the thread.

Update the state of a thread.

This method calls POST /threads/{thread_id}/state.

A RunnableConfig that includes thread_id in the configurable field.

Values to update to the state.

Update the state as if this node had just executed.

RunnableConfig for the updated thread.

Update the state of a thread.

This method calls POST /threads/{thread_id}/state.

A RunnableConfig that includes thread_id in the configurable field.

Values to update to the state.

Update the state as if this node had just executed.

RunnableConfig for the updated thread.

Create a run and stream the results.

This method calls POST /threads/{thread_id}/runs/stream if a thread_id is speciffed in the configurable field of the config or POST /runs/stream otherwise.

A RunnableConfig for graph invocation.

Stream mode(s) to use.

Interrupt the graph before these nodes.

Interrupt the graph after these nodes.

Stream from subgraphs.

Additional headers to pass to the request.

Additional params to pass to client.runs.stream.

The output of the graph.

Create a run and stream the results.

This method calls POST /threads/{thread_id}/runs/stream if a thread_id is speciffed in the configurable field of the config or POST /runs/stream otherwise.

A RunnableConfig for graph invocation.

Stream mode(s) to use.

Interrupt the graph before these nodes.

Interrupt the graph after these nodes.

Stream from subgraphs.

Additional headers to pass to the request.

Additional params to pass to client.runs.stream.

The output of the graph.

Create a run, wait until it finishes and return the final state.

A RunnableConfig for graph invocation.

Interrupt the graph before these nodes.

Interrupt the graph after these nodes.

Additional headers to pass to the request.

Additional params to pass to RemoteGraph.stream.

The output of the graph.

Create a run, wait until it finishes and return the final state.

A RunnableConfig for graph invocation.

Interrupt the graph before these nodes.

Interrupt the graph after these nodes.

Additional headers to pass to the request.

Additional params to pass to RemoteGraph.astream.

The output of the graph.

Get the name of the Runnable.

Get a pydantic model that can be used to validate input to the Runnable.

Runnables that leverage the configurable_fields and configurable_alternatives methods will have a dynamic input schema that depends on which configuration the Runnable is invoked with.

This method allows to get an input schema for a specific configuration.

A config to use when generating the schema.

A pydantic model that can be used to validate input.

Get a JSON schema that represents the input to the Runnable.

A config to use when generating the schema.

A JSON schema that represents the input to the Runnable.

.. versionadded:: 0.3.0

Get a pydantic model that can be used to validate output to the Runnable.

Runnables that leverage the configurable_fields and configurable_alternatives methods will have a dynamic output schema that depends on which configuration the Runnable is invoked with.

This method allows to get an output schema for a specific configuration.

A config to use when generating the schema.

A pydantic model that can be used to validate output.

Get a JSON schema that represents the output of the Runnable.

A config to use when generating the schema.

A JSON schema that represents the output of the Runnable.

.. versionadded:: 0.3.0

The type of config this Runnable accepts specified as a pydantic model.

To mark a field as configurable, see the configurable_fields and configurable_alternatives methods.

A list of fields to include in the config schema.

A pydantic model that can be used to validate config.

Get a JSON schema that represents the config of the Runnable.

A list of fields to include in the config schema.

A JSON schema that represents the config of the Runnable.

.. versionadded:: 0.3.0

Return a list of prompts used by this Runnable.

Compose this Runnable with another object to create a RunnableSequence.

Compose this Runnable with another object to create a RunnableSequence.

Compose this Runnable with Runnable-like objects to make a RunnableSequence.

Equivalent to RunnableSequence(self, *others) or self | others[0] | ...

.. code-block:: python

Pick keys from the output dict of this Runnable.

.. code-block:: python

.. code-block:: python

Assigns new fields to the dict output of this Runnable.

Returns a new Runnable.

.. code-block:: python

Default implementation runs invoke in parallel using a thread pool executor.

The default implementation of batch works well for IO bound runnables.

Subclasses should override this method if they can batch more efficiently; e.g., if the underlying Runnable uses an API which supports a batch mode.

Run invoke in parallel on a list of inputs.

Yields results as they complete.

Default implementation runs ainvoke in parallel using asyncio.gather.

The default implementation of batch works well for IO bound runnables.

Subclasses should override this method if they can batch more efficiently; e.g., if the underlying Runnable uses an API which supports a batch mode.

A list of inputs to the Runnable.

A config to use when invoking the Runnable. The config supports standard keys like 'tags', 'metadata' for tracing purposes, 'max_concurrency' for controlling how much work to do in parallel, and other keys. Please refer to the RunnableConfig for more details. Defaults to None.

Whether to return exceptions instead of raising them. Defaults to False.

Additional keyword arguments to pass to the Runnable.

A list of outputs from the Runnable.

Run ainvoke in parallel on a list of inputs.

Yields results as they complete.

A list of inputs to the Runnable.

A config to use when invoking the Runnable. The config supports standard keys like 'tags', 'metadata' for tracing purposes, 'max_concurrency' for controlling how much work to do in parallel, and other keys. Please refer to the RunnableConfig for more details. Defaults to None. Defaults to None.

Whether to return exceptions instead of raising them. Defaults to False.

Additional keyword arguments to pass to the Runnable.

A tuple of the index of the input and the output from the Runnable.

Stream all output from a Runnable, as reported to the callback system.

This includes all inner runs of LLMs, Retrievers, Tools, etc.

Output is streamed as Log objects, which include a list of Jsonpatch ops that describe how the state of the run has changed in each step, and the final state of the run.

The Jsonpatch ops can be applied in order to construct state.

The input to the Runnable.

The config to use for the Runnable.

Whether to yield diffs between each step or the current state.

Whether to yield the streamed_output list.

Only include logs with these names.

Only include logs with these types.

Only include logs with these tags.

Exclude logs with these names.

Exclude logs with these types.

Exclude logs with these tags.

Additional keyword arguments to pass to the Runnable.

A RunLogPatch or RunLog object.

Default implementation of transform, which buffers input and calls astream.

Subclasses should override this method if they can start producing output while input is still being generated.

An iterator of inputs to the Runnable.

The config to use for the Runnable. Defaults to None.

Additional keyword arguments to pass to the Runnable.

The output of the Runnable.

Default implementation of atransform, which buffers input and calls astream.

Subclasses should override this method if they can start producing output while input is still being generated.

An async iterator of inputs to the Runnable.

The config to use for the Runnable. Defaults to None.

Additional keyword arguments to pass to the Runnable.

The output of the Runnable.

Bind arguments to a Runnable, returning a new Runnable.

Useful when a Runnable in a chain requires an argument that is not in the output of the previous Runnable or included in the user input.

The arguments to bind to the Runnable.

A new Runnable with the arguments bound.

.. code-block:: python

Bind lifecycle listeners to a Runnable, returning a new Runnable.

on_start: Called before the Runnable starts running, with the Run object. on_end: Called after the Runnable finishes running, with the Run object. on_error: Called if the Runnable throws an error, with the Run object.

The Run object contains information about the run, including its id, type, input, output, error, start_time, end_time, and any tags or metadata added to the run.

Called before the Runnable starts running. Defaults to None.

Called after the Runnable finishes running. Defaults to None.

Called if the Runnable throws an error. Defaults to None.

A new Runnable with the listeners bound.

.. code-block:: python

Bind async lifecycle listeners to a Runnable, returning a new Runnable.

on_start: Asynchronously called before the Runnable starts running. on_end: Asynchronously called after the Runnable finishes running. on_error: Asynchronously called if the Runnable throws an error.

The Run object contains information about the run, including its id, type, input, output, error, start_time, end_time, and any tags or metadata added to the run.

Asynchronously called before the Runnable starts running. Defaults to None.

Asynchronously called after the Runnable finishes running. Defaults to None.

Asynchronously called if the Runnable throws an error. Defaults to None.

A new Runnable with the listeners bound.

.. code-block:: python

Bind input and output types to a Runnable, returning a new Runnable.

The input type to bind to the Runnable. Defaults to None.

The output type to bind to the Runnable. Defaults to None.

A new Runnable with the types bound.

Create a new Runnable that retries the original Runnable on exceptions.

A tuple of exception types to retry on. Defaults to (Exception,).

Whether to add jitter to the wait time between retries. Defaults to True.

The maximum number of attempts to make before giving up. Defaults to 3.

Parameters for tenacity.wait_exponential_jitter. Namely: initial, max, exp_base, and jitter (all float values).

A new Runnable that retries the original Runnable on exceptions.

.. code-block:: python

Return a new Runnable that maps a list of inputs to a list of outputs.

Calls invoke() with each input.

A new Runnable that maps a list of inputs to a list of outputs.

Add fallbacks to a Runnable, returning a new Runnable.

The new Runnable will try the original Runnable, and then each fallback in order, upon failures.

A sequence of runnables to try if the original Runnable fails.

A tuple of exception types to handle. Defaults to (Exception,).

If string is specified then handled exceptions will be passed to fallbacks as part of the input under the specified key. If None, exceptions will not be passed to fallbacks. If used, the base Runnable and its fallbacks must accept a dictionary as input. Defaults to None.

A new Runnable that will try the original Runnable, and then each

fallback in order, upon failures.

A sequence of runnables to try if the original Runnable fails.

A tuple of exception types to handle.

If string is specified then handled exceptions will be passed to fallbacks as part of the input under the specified key. If None, exceptions will not be passed to fallbacks. If used, the base Runnable and its fallbacks must accept a dictionary as input.

A new Runnable that will try the original Runnable, and then each

fallback in order, upon failures.

Create a BaseTool from a Runnable.

as_tool will instantiate a BaseTool with a name, description, and args_schema from a Runnable. Where possible, schemas are inferred from runnable.get_input_schema. Alternatively (e.g., if the Runnable takes a dict as input and the specific dict keys are not typed), the schema can be specified directly with args_schema. You can also pass arg_types to just specify the required arguments and their types.

The schema for the tool. Defaults to None.

The name of the tool. Defaults to None.

The description of the tool. Defaults to None.

A dictionary of argument names to types. Defaults to None.

.. code-block:: python

dict input, specifying schema via args_schema:

.. code-block:: python

dict input, specifying schema via arg_types:

.. code-block:: python

.. code-block:: python

.. versionadded:: 0.2.14

**Examples:**

Example 1 (unknown):
```unknown
InputType: type[Input]
```

Example 2 (unknown):
```unknown
OutputType: type[Output]
```

Example 3 (unknown):
```unknown
input_schema: type[BaseModel]
```

Example 4 (unknown):
```unknown
output_schema: type[BaseModel]
```

---

## Config

**URL:** https://langchain-ai.github.io/langgraph/reference/config/

**Contents:**
- Config
- get_store ¶
- get_stream_writer ¶

Access LangGraph store from inside a graph node or entrypoint task at runtime.

Access LangGraph StreamWriter from inside a graph node or entrypoint task at runtime.

Access LangGraph store from inside a graph node or entrypoint task at runtime.

Can be called from inside any StateGraph node or functional API task, as long as the StateGraph or the entrypoint was initialized with a store, e.g.:

Async with Python < 3.11

If you are using Python < 3.11 and are running LangGraph asynchronously, get_store() won't work since it uses contextvar propagation (only available in Python >= 3.11).

Access LangGraph StreamWriter from inside a graph node or entrypoint task at runtime.

Can be called from inside any StateGraph node or functional API task.

Async with Python < 3.11

If you are using Python < 3.11 and are running LangGraph asynchronously, get_stream_writer() won't work since it uses contextvar propagation (only available in Python >= 3.11).

**Examples:**

Example 1 (unknown):
```unknown
get_store() -> BaseStore
```

Example 2 (python):
```python
# with StateGraph
graph = (
    StateGraph(...)
    ...
    .compile(store=store)
)

# or with entrypoint
@entrypoint(store=store)
def workflow(inputs):
    ...
```

Example 3 (python):
```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.store.memory import InMemoryStore
from langgraph.config import get_store

store = InMemoryStore()
store.put(("values",), "foo", {"bar": 2})


class State(TypedDict):
    foo: int


def my_node(state: State):
    my_store = get_store()
    stored_value = my_store.get(("values",), "foo").value["bar"]
    return {"foo": stored_value + 1}


graph = (
    StateGraph(State)
    .add_node(my_node)
    .add_edge(START, "my_node")
    .compile(store=store)
)

graph.invoke({"foo": 1})
```

Example 4 (python):
```python
from langgraph.func import entrypoint, task
from langgraph.store.memory import InMemoryStore
from langgraph.config import get_store

store = InMemoryStore()
store.put(("values",), "foo", {"bar": 2})


@task
def my_task(value: int):
    my_store = get_store()
    stored_value = my_store.get(("values",), "foo").value["bar"]
    return stored_value + 1


@entrypoint(store=store)
def workflow(value: int):
    return my_task(value).result()


workflow.invoke(1)
```

---

## Run a local server¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/langgraph-platform/local-server/

**Contents:**
- Run a local server¶
- Prerequisites¶
- 1. Install the LangGraph CLI¶
- 2. Create a LangGraph app 🌱¶
- 3. Install dependencies¶
- 4. Create a .env file¶
- 5. Launch LangGraph Server 🚀¶
- 6. Test your application in LangGraph Studio¶
- 7. Test the API¶
- Next steps¶

This guide shows you how to run a LangGraph application locally.

Before you begin, ensure you have the following:

Create a new app from the new-langgraph-project-python template. This template demonstrates a single-node application you can extend with your own logic.

If you use langgraph new without specifying a template, you will be presented with an interactive menu that will allow you to choose from a list of available templates.

In the root of your new LangGraph app, install the dependencies in edit mode so your local changes are used by the server:

You will find a .env.example in the root of your new LangGraph app. Create a .env file in the root of your new LangGraph app and copy the contents of the .env.example file into it, filling in the necessary API keys:

Start the LangGraph API server locally:

The langgraph dev command starts LangGraph Server in an in-memory mode. This mode is suitable for development and testing purposes. For production use, deploy LangGraph Server with access to a persistent storage backend. For more information, see Deployment options.

LangGraph Studio is a specialized UI that you can connect to LangGraph API server to visualize, interact with, and debug your application locally. Test your graph in LangGraph Studio by visiting the URL provided in the output of the langgraph dev command:

For a LangGraph Server running on a custom host/port, update the baseURL parameter.

Use the --tunnel flag with your command to create a secure tunnel, as Safari has limitations when connecting to localhost servers:

Install the LangGraph Python SDK:

Send a message to the assistant (threadless run):

Install the LangGraph Python SDK:

Send a message to the assistant (threadless run):

Now that you have a LangGraph app running locally, take your journey further by exploring deployment and advanced features:

LangGraph Server API Reference: Explore the LangGraph Server API documentation.

Python SDK Reference: Explore the Python SDK API Reference.

**Examples:**

Example 1 (unknown):
```unknown
# Python >= 3.11 is required.

pip install --upgrade "langgraph-cli[inmem]"
```

Example 2 (unknown):
```unknown
langgraph new path/to/your/app --template new-langgraph-project-python
```

Example 3 (unknown):
```unknown
cd path/to/your/app
pip install -e .
```

Example 4 (unknown):
```unknown
LANGSMITH_API_KEY=lsv2...
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/how-tos/map-reduce/

---

## Constants

**URL:** https://langchain-ai.github.io/langgraph/reference/constants/

**Contents:**
- Constants
- TAG_HIDDEN module-attribute ¶
- TAG_NOSTREAM module-attribute ¶
- START module-attribute ¶
- END module-attribute ¶

Tag to hide a node/edge from certain tracing/streaming environments.

Tag to disable streaming for a chat model.

The first (maybe virtual) node in graph-style Pregel.

The last (maybe virtual) node in graph-style Pregel.

Tag to hide a node/edge from certain tracing/streaming environments.

Tag to disable streaming for a chat model.

The first (maybe virtual) node in graph-style Pregel.

The last (maybe virtual) node in graph-style Pregel.

**Examples:**

Example 1 (unknown):
```unknown
TAG_HIDDEN = intern('langsmith:hidden')
```

Example 2 (unknown):
```unknown
TAG_NOSTREAM = intern('nostream')
```

Example 3 (unknown):
```unknown
START = intern('__start__')
```

Example 4 (unknown):
```unknown
END = intern('__end__')
```

---

## Types¶

**URL:** https://langchain-ai.github.io/langgraph/reference/types/

**Contents:**
- Types¶
- All module-attribute ¶
- StreamMode module-attribute ¶
- StreamWriter module-attribute ¶
- RetryPolicy ¶
  - initial_interval class-attribute instance-attribute ¶
  - backoff_factor class-attribute instance-attribute ¶
  - max_interval class-attribute instance-attribute ¶
  - max_attempts class-attribute instance-attribute ¶
  - jitter class-attribute instance-attribute ¶

Configuration for retrying nodes.

Configuration for caching nodes.

Information about an interrupt that occurred in a node.

Snapshot of the state of the graph at the beginning of a step.

A message or packet to send to a specific node in the graph.

One or more commands to update the graph's state and send messages to nodes.

Interrupt the graph with a resumable exception from within a node.

Special value to indicate that graph should interrupt on all nodes.

How the stream method should emit outputs.

Callable that accepts a single argument and writes it to the output stream.

Special value to indicate that graph should interrupt on all nodes.

How the stream method should emit outputs.

Callable that accepts a single argument and writes it to the output stream. Always injected into nodes if requested as a keyword argument, but it's a no-op when not using stream_mode="custom".

Configuration for retrying nodes.

Added in version 0.2.24

Amount of time that must elapse before the first retry occurs. In seconds.

Multiplier by which the interval increases after each retry.

Maximum amount of time that may elapse between retries. In seconds.

Maximum number of attempts to make before giving up, including the first.

Whether to add random jitter to the interval between retries.

List of exception classes that should trigger a retry, or a callable that returns True for exceptions that should trigger a retry.

Amount of time that must elapse before the first retry occurs. In seconds.

Multiplier by which the interval increases after each retry.

Maximum amount of time that may elapse between retries. In seconds.

Maximum number of attempts to make before giving up, including the first.

Whether to add random jitter to the interval between retries.

List of exception classes that should trigger a retry, or a callable that returns True for exceptions that should trigger a retry.

Bases: Generic[KeyFuncT]

Configuration for caching nodes.

Function to generate a cache key from the node's input.

Time to live for the cache entry in seconds. If None, the entry never expires.

Function to generate a cache key from the node's input. Defaults to hashing the input with pickle.

Time to live for the cache entry in seconds. If None, the entry never expires.

Information about an interrupt that occurred in a node.

Added in version 0.2.24

Changed in version v0.4.0

Changed in version v0.6.0

The following attributes have been removed:

The ID of the interrupt. Can be used to resume the interrupt directly.

The value associated with the interrupt.

The ID of the interrupt. Can be used to resume the interrupt directly.

The value associated with the interrupt.

Snapshot of the state of the graph at the beginning of a step.

Current values of channels.

The name of the node to execute in each task for this step.

Config used to fetch this snapshot.

Metadata associated with this snapshot.

Timestamp of snapshot creation.

Config used to fetch the parent snapshot, if any.

Tasks to execute in this step. If already attempted, may contain an error.

Interrupts that occurred in this step that are pending resolution.

Current values of channels.

The name of the node to execute in each task for this step.

Config used to fetch this snapshot.

Metadata associated with this snapshot.

Timestamp of snapshot creation.

Config used to fetch the parent snapshot, if any.

Tasks to execute in this step. If already attempted, may contain an error.

Interrupts that occurred in this step that are pending resolution.

A message or packet to send to a specific node in the graph.

The Send class is used within a StateGraph's conditional edges to dynamically invoke a node with a custom state at the next step.

Importantly, the sent state can differ from the core graph's state, allowing for flexible and dynamic workflow management.

One such example is a "map-reduce" workflow where your graph invokes the same node multiple times in parallel with different states, before aggregating the results back into the main graph's state.

The name of the target node to send the message to.

The state or message to send to the target node.

Initialize a new instance of the Send class.

Initialize a new instance of the Send class.

The name of the target node to send the message to.

The state or message to send to the target node.

Bases: Generic[N], ToolOutputMixin

One or more commands to update the graph's state and send messages to nodes.

Added in version 0.2.24

graph to send the command to. Supported values are:

Update to apply to the graph's state.

Value to resume execution with. To be used together with interrupt(). Can be one of the following:

Can be one of the following:

Interrupt the graph with a resumable exception from within a node.

The interrupt function enables human-in-the-loop workflows by pausing graph execution and surfacing a value to the client. This value can communicate context or request input required to resume execution.

In a given node, the first invocation of this function raises a GraphInterrupt exception, halting execution. The provided value is included with the exception and sent to the client executing the graph.

A client resuming the graph must use the Command primitive to specify a value for the interrupt and continue execution. The graph resumes from the start of the node, re-executing all logic.

If a node contains multiple interrupt calls, LangGraph matches resume values to interrupts based on their order in the node. This list of resume values is scoped to the specific task executing the node and is not shared across tasks.

To use an interrupt, you must enable a checkpointer, as the feature relies on persisting the graph state.

The value to surface to the client when the graph is interrupted.

On subsequent invocations within the same node (same task to be precise), returns the value provided during the first invocation

On the first invocation within the node, halts execution and surfaces the provided value to the client.

**Examples:**

Example 1 (unknown):
```unknown
All = Literal['*']
```

Example 2 (unknown):
```unknown
StreamMode = Literal[
    "values",
    "updates",
    "checkpoints",
    "tasks",
    "debug",
    "messages",
    "custom",
]
```

Example 3 (unknown):
```unknown
StreamWriter = Callable[[Any], None]
```

Example 4 (unknown):
```unknown
initial_interval: float = 0.5
```

---

## Caching

**URL:** https://langchain-ai.github.io/langgraph/reference/cache/

**Contents:**
- Caching
- Caching¶
- BaseCache ¶
  - __init__ ¶
  - get abstractmethod ¶
  - aget abstractmethod async ¶
  - set abstractmethod ¶
  - aset abstractmethod async ¶
  - clear abstractmethod ¶
  - aclear abstractmethod async ¶

Base class for a cache.

Bases: ABC, Generic[ValueT]

Base class for a cache.

Initialize the cache with a serializer.

Get the cached values for the given keys.

Asynchronously get the cached values for the given keys.

Set the cached values for the given keys and TTLs.

Asynchronously set the cached values for the given keys and TTLs.

Delete the cached values for the given namespaces.

Asynchronously delete the cached values for the given namespaces.

Initialize the cache with a serializer.

Get the cached values for the given keys.

Asynchronously get the cached values for the given keys.

Set the cached values for the given keys and TTLs.

Asynchronously set the cached values for the given keys and TTLs.

Delete the cached values for the given namespaces. If no namespaces are provided, clear all cached values.

Asynchronously delete the cached values for the given namespaces. If no namespaces are provided, clear all cached values.

Bases: BaseCache[ValueT]

Get the cached values for the given keys.

Asynchronously get the cached values for the given keys.

Set the cached values for the given keys.

Asynchronously set the cached values for the given keys.

Delete the cached values for the given namespaces.

Asynchronously delete the cached values for the given namespaces.

Get the cached values for the given keys.

Asynchronously get the cached values for the given keys.

Set the cached values for the given keys.

Asynchronously set the cached values for the given keys.

Delete the cached values for the given namespaces. If no namespaces are provided, clear all cached values.

Asynchronously delete the cached values for the given namespaces. If no namespaces are provided, clear all cached values.

File-based cache using SQLite.

Bases: BaseCache[ValueT]

File-based cache using SQLite.

Initialize the cache with a file path.

Get the cached values for the given keys.

Asynchronously get the cached values for the given keys.

Set the cached values for the given keys and TTLs.

Asynchronously set the cached values for the given keys and TTLs.

Delete the cached values for the given namespaces.

Asynchronously delete the cached values for the given namespaces.

Initialize the cache with a file path.

Get the cached values for the given keys.

Asynchronously get the cached values for the given keys.

Set the cached values for the given keys and TTLs.

Asynchronously set the cached values for the given keys and TTLs.

Delete the cached values for the given namespaces. If no namespaces are provided, clear all cached values.

Asynchronously delete the cached values for the given namespaces. If no namespaces are provided, clear all cached values.

**Examples:**

Example 1 (unknown):
```unknown
__init__(
    *, serde: SerializerProtocol | None = None
) -> None
```

Example 2 (unknown):
```unknown
get(keys: Sequence[FullKey]) -> dict[FullKey, ValueT]
```

Example 3 (unknown):
```unknown
aget(keys: Sequence[FullKey]) -> dict[FullKey, ValueT]
```

Example 4 (unknown):
```unknown
set(
    pairs: Mapping[FullKey, tuple[ValueT, int | None]],
) -> None
```

---

## Errors¶

**URL:** https://langchain-ai.github.io/langgraph/reference/errors/

**Contents:**
- Errors¶
- EmptyChannelError ¶
- GraphRecursionError ¶
- InvalidUpdateError ¶
- GraphInterrupt ¶
- NodeInterrupt ¶
- EmptyInputError ¶
- TaskNotFound ¶

Raised when attempting to get the value of a channel that hasn't been updated

Raised when the graph has exhausted the maximum number of steps.

Raised when attempting to update a channel with an invalid set of updates.

Raised when a subgraph is interrupted, suppressed by the root graph.

Raised by a node to interrupt execution.

Raised when graph receives an empty input.

Raised when the executor is unable to find a task (for distributed mode).

Raised when attempting to get the value of a channel that hasn't been updated for the first time yet.

Bases: RecursionError

Raised when the graph has exhausted the maximum number of steps.

This prevents infinite loops. To increase the maximum number of steps, run your graph with a config specifying a higher recursion_limit.

Troubleshooting guides:

Raised when attempting to update a channel with an invalid set of updates.

Troubleshooting guides:

Raised when a subgraph is interrupted, suppressed by the root graph. Never raised directly, or surfaced to the user.

Bases: GraphInterrupt

Raised by a node to interrupt execution.

Raised when graph receives an empty input.

Raised when the executor is unable to find a task (for distributed mode).

**Examples:**

Example 1 (unknown):
```unknown
graph = builder.compile()
graph.invoke(
    {"messages": [("user", "Hello, world!")]},
    # The config is the second positional argument
    {"recursion_limit": 1000},
)
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/reference/prebuilt/

---

## Runtime¶

**URL:** https://langchain-ai.github.io/langgraph/reference/runtime/

**Contents:**
- Runtime¶
- Runtime dataclass ¶
  - context class-attribute instance-attribute ¶
  - store class-attribute instance-attribute ¶
  - stream_writer class-attribute instance-attribute ¶
  - previous class-attribute instance-attribute ¶
- get_runtime ¶

Bases: Generic[ContextT]

Convenience class that bundles run-scoped context and other runtime utilities.

Added in version v0.6.0

Static context for the graph run, like user_id, db_conn, etc.

Store for the graph run, enabling persistence and memory.

Function that writes to the custom stream.

The previous return value for the given thread.

Static context for the graph run, like user_id, db_conn, etc.

Can also be thought of as 'run dependencies'.

Store for the graph run, enabling persistence and memory.

Function that writes to the custom stream.

The previous return value for the given thread.

Only available with the functional API when a checkpointer is provided.

Get the runtime for the current graph run.

Get the runtime for the current graph run.

Optional schema used for type hinting the return type of the runtime.

The runtime for the current graph run.

**Examples:**

Example 1 (python):
```python
from typing import TypedDict
from langgraph.graph import StateGraph
from dataclasses import dataclass
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore


@dataclass
class Context:  # (1)!
    user_id: str


class State(TypedDict, total=False):
    response: str


store = InMemoryStore()  # (2)!
store.put(("users",), "user_123", {"name": "Alice"})


def personalized_greeting(state: State, runtime: Runtime[Context]) -> State:
    '''Generate personalized greeting using runtime context and store.'''
    user_id = runtime.context.user_id  # (3)!
    name = "unknown_user"
    if runtime.store:
        if memory := runtime.store.get(("users",), user_id):
            name = memory.value["name"]

    response = f"Hello {name}! Nice to see you again."
    return {"response": response}


graph = (
    StateGraph(state_schema=State, context_schema=Context)
    .add_node("personalized_greeting", personalized_greeting)
    .set_entry_point("personalized_greeting")
    .set_finish_point("personalized_greeting")
    .compile(store=store)
)

result = graph.invoke({}, context=Context(user_id="user_123"))
print(result)
# > {'response': 'Hello Alice! Nice to see you again.'}
```

Example 2 (unknown):
```unknown
context: ContextT = field(default=None)
```

Example 3 (unknown):
```unknown
store: BaseStore | None = field(default=None)
```

Example 4 (unknown):
```unknown
stream_writer: StreamWriter = field(
    default=_no_op_stream_writer
)
```

---

## Types¶

**URL:** https://langchain-ai.github.io/langgraph/reference/types/?h=cachepolicy

**Contents:**
- Types¶
- All module-attribute ¶
- StreamMode module-attribute ¶
- StreamWriter module-attribute ¶
- RetryPolicy ¶
  - initial_interval class-attribute instance-attribute ¶
  - backoff_factor class-attribute instance-attribute ¶
  - max_interval class-attribute instance-attribute ¶
  - max_attempts class-attribute instance-attribute ¶
  - jitter class-attribute instance-attribute ¶

Configuration for retrying nodes.

Configuration for caching nodes.

Information about an interrupt that occurred in a node.

Snapshot of the state of the graph at the beginning of a step.

A message or packet to send to a specific node in the graph.

One or more commands to update the graph's state and send messages to nodes.

Interrupt the graph with a resumable exception from within a node.

Special value to indicate that graph should interrupt on all nodes.

How the stream method should emit outputs.

Callable that accepts a single argument and writes it to the output stream.

Special value to indicate that graph should interrupt on all nodes.

How the stream method should emit outputs.

Callable that accepts a single argument and writes it to the output stream. Always injected into nodes if requested as a keyword argument, but it's a no-op when not using stream_mode="custom".

Configuration for retrying nodes.

Added in version 0.2.24

Amount of time that must elapse before the first retry occurs. In seconds.

Multiplier by which the interval increases after each retry.

Maximum amount of time that may elapse between retries. In seconds.

Maximum number of attempts to make before giving up, including the first.

Whether to add random jitter to the interval between retries.

List of exception classes that should trigger a retry, or a callable that returns True for exceptions that should trigger a retry.

Amount of time that must elapse before the first retry occurs. In seconds.

Multiplier by which the interval increases after each retry.

Maximum amount of time that may elapse between retries. In seconds.

Maximum number of attempts to make before giving up, including the first.

Whether to add random jitter to the interval between retries.

List of exception classes that should trigger a retry, or a callable that returns True for exceptions that should trigger a retry.

Bases: Generic[KeyFuncT]

Configuration for caching nodes.

Function to generate a cache key from the node's input.

Time to live for the cache entry in seconds. If None, the entry never expires.

Function to generate a cache key from the node's input. Defaults to hashing the input with pickle.

Time to live for the cache entry in seconds. If None, the entry never expires.

Information about an interrupt that occurred in a node.

Added in version 0.2.24

Changed in version v0.4.0

Changed in version v0.6.0

The following attributes have been removed:

The ID of the interrupt. Can be used to resume the interrupt directly.

The value associated with the interrupt.

The ID of the interrupt. Can be used to resume the interrupt directly.

The value associated with the interrupt.

Snapshot of the state of the graph at the beginning of a step.

Current values of channels.

The name of the node to execute in each task for this step.

Config used to fetch this snapshot.

Metadata associated with this snapshot.

Timestamp of snapshot creation.

Config used to fetch the parent snapshot, if any.

Tasks to execute in this step. If already attempted, may contain an error.

Interrupts that occurred in this step that are pending resolution.

Current values of channels.

The name of the node to execute in each task for this step.

Config used to fetch this snapshot.

Metadata associated with this snapshot.

Timestamp of snapshot creation.

Config used to fetch the parent snapshot, if any.

Tasks to execute in this step. If already attempted, may contain an error.

Interrupts that occurred in this step that are pending resolution.

A message or packet to send to a specific node in the graph.

The Send class is used within a StateGraph's conditional edges to dynamically invoke a node with a custom state at the next step.

Importantly, the sent state can differ from the core graph's state, allowing for flexible and dynamic workflow management.

One such example is a "map-reduce" workflow where your graph invokes the same node multiple times in parallel with different states, before aggregating the results back into the main graph's state.

The name of the target node to send the message to.

The state or message to send to the target node.

Initialize a new instance of the Send class.

Initialize a new instance of the Send class.

The name of the target node to send the message to.

The state or message to send to the target node.

Bases: Generic[N], ToolOutputMixin

One or more commands to update the graph's state and send messages to nodes.

Added in version 0.2.24

graph to send the command to. Supported values are:

Update to apply to the graph's state.

Value to resume execution with. To be used together with interrupt(). Can be one of the following:

Can be one of the following:

Interrupt the graph with a resumable exception from within a node.

The interrupt function enables human-in-the-loop workflows by pausing graph execution and surfacing a value to the client. This value can communicate context or request input required to resume execution.

In a given node, the first invocation of this function raises a GraphInterrupt exception, halting execution. The provided value is included with the exception and sent to the client executing the graph.

A client resuming the graph must use the Command primitive to specify a value for the interrupt and continue execution. The graph resumes from the start of the node, re-executing all logic.

If a node contains multiple interrupt calls, LangGraph matches resume values to interrupts based on their order in the node. This list of resume values is scoped to the specific task executing the node and is not shared across tasks.

To use an interrupt, you must enable a checkpointer, as the feature relies on persisting the graph state.

The value to surface to the client when the graph is interrupted.

On subsequent invocations within the same node (same task to be precise), returns the value provided during the first invocation

On the first invocation within the node, halts execution and surfaces the provided value to the client.

**Examples:**

Example 1 (unknown):
```unknown
All = Literal['*']
```

Example 2 (unknown):
```unknown
StreamMode = Literal[
    "values",
    "updates",
    "checkpoints",
    "tasks",
    "debug",
    "messages",
    "custom",
]
```

Example 3 (unknown):
```unknown
StreamWriter = Callable[[Any], None]
```

Example 4 (unknown):
```unknown
initial_interval: float = 0.5
```

---

## LangChain Model Context Protocol (MCP) Adapters¶

**URL:** https://langchain-ai.github.io/langgraph/reference/mcp/

**Contents:**
- LangChain Model Context Protocol (MCP) Adapters¶
- MultiServerMCPClient ¶
  - __init__ ¶
  - session async ¶
  - get_tools async ¶
  - get_prompt async ¶
  - get_resources async ¶
  - __aenter__ async ¶
  - __aexit__ ¶
- load_mcp_tools async ¶

Client for connecting to multiple MCP servers and loading LangChain-compatible resources.

This module provides the MultiServerMCPClient class for managing connections to multiple MCP servers and loading tools, prompts, and resources from them.

Client for connecting to multiple MCP servers and loading LangChain-compatible tools, prompts and resources from them.

Client for connecting to multiple MCP servers and loading LangChain-compatible tools, prompts and resources from them.

Initialize a MultiServerMCPClient with MCP servers connections.

Connect to an MCP server and initialize a session.

Get a list of all tools from all connected servers.

Get a prompt from a given MCP server.

Get resources from a given MCP server.

Async context manager entry point.

Async context manager exit point.

Initialize a MultiServerMCPClient with MCP servers connections.

A dictionary mapping server names to connection configurations. If None, no initial connections are established.

Example: basic usage (starting a new session on each tool call)

Example: explicitly starting a session

Connect to an MCP server and initialize a session.

Name to identify this server connection

Whether to automatically initialize the session

If the server name is not found in the connections

An initialized ClientSession

Get a list of all tools from all connected servers.

Optional name of the server to get tools from. If None, all tools from all servers will be returned (default).

NOTE: a new session will be created for each tool call

A list of LangChain tools

Get a prompt from a given MCP server.

Get resources from a given MCP server.

Name of the server to get resources from

Optional resource URI or list of URIs to load. If not provided, all resources will be loaded.

A list of LangChain Blobs

Async context manager entry point.

Context manager support has been removed.

Async context manager exit point.

Exception type if an exception occurred.

Exception value if an exception occurred.

Exception traceback if an exception occurred.

Context manager support has been removed.

Tools adapter for converting MCP tools to LangChain tools.

This module provides functionality to convert MCP tools into LangChain-compatible tools, handle tool execution, and manage tool conversion between the two formats.

Load all available MCP tools and convert them to LangChain tools.

Load all available MCP tools and convert them to LangChain tools.

The MCP client session. If None, connection must be provided.

Connection config to create a new session if session is None.

List of LangChain tools. Tool annotations are returned as part

of the tool metadata object.

If neither session nor connection is provided.

Prompts adapter for converting MCP prompts to LangChain messages.

This module provides functionality to convert MCP prompt messages into LangChain message objects, handling both user and assistant message types.

Load MCP prompt and convert to LangChain messages.

Load MCP prompt and convert to LangChain messages.

The MCP client session.

Name of the prompt to load.

Optional arguments to pass to the prompt.

A list of LangChain messages converted from the MCP prompt.

Resources adapter for converting MCP resources to LangChain Blobs.

This module provides functionality to convert MCP resources into LangChain Blob objects, handling both text and binary resource content types.

Load MCP resources and convert them to LangChain Blobs.

Load MCP resources and convert them to LangChain Blobs.

List of URIs to load. If None, all resources will be loaded. Note: Dynamic resources will NOT be loaded when None is specified, as they require parameters and are ignored by the MCP SDK's session.list_resources() method.

A list of LangChain Blobs.

If an error occurs while fetching a resource.

**Examples:**

Example 1 (unknown):
```unknown
__init__(
    connections: dict[str, Connection] | None = None,
) -> None
```

Example 2 (python):
```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    {
        "math": {
            "command": "python",
            # Make sure to update to the full absolute path to your math_server.py file
            "args": ["/path/to/math_server.py"],
            "transport": "stdio",
        },
        "weather": {
            # Make sure you start your weather server on port 8000
            "url": "http://localhost:8000/mcp",
            "transport": "streamable_http",
        }
    }
)
all_tools = await client.get_tools()
```

Example 3 (python):
```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

client = MultiServerMCPClient({...})
async with client.session("math") as session:
    tools = await load_mcp_tools(session)
```

Example 4 (unknown):
```unknown
session(
    server_name: str, *, auto_initialize: bool = True
) -> AsyncIterator[ClientSession]
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/cloud/how-tos/add-human-in-the-loop/

---

## Pregel¶

**URL:** https://langchain-ai.github.io/langgraph/reference/pregel/

**Contents:**
- Pregel¶
- NodeBuilder ¶
  - subscribe_only ¶
  - subscribe_to ¶
  - read_from ¶
  - do ¶
  - write_to ¶
  - meta ¶
  - build ¶
- Pregel ¶

Subscribe to a single channel.

Add channels to subscribe to. Node will be invoked when any of these

Adds the specified channels to read from, without subscribing to them.

Adds the specified node.

Add tags or metadata to the node.

Subscribe to a single channel.

Add channels to subscribe to. Node will be invoked when any of these channels are updated, with a dict of the channel values as input.

Channel name(s) to subscribe to

If True, the channels will be included in the input to the node. Otherwise, they will trigger the node without being sent in input.

Adds the specified channels to read from, without subscribing to them.

Adds the specified node.

Channel names to write to

Channel name and value mappings

Add tags or metadata to the node.

Bases: PregelProtocol[StateT, ContextT, InputT, OutputT], Generic[StateT, ContextT, InputT, OutputT]

Pregel manages the runtime behavior for LangGraph applications.

Pregel combines actors and channels into a single application. Actors read data from channels and write data to channels. Pregel organizes the execution of the application into multiple steps, following the Pregel Algorithm/Bulk Synchronous Parallel model.

Each step consists of three phases:

Repeat until no actors are selected for execution, or a maximum number of steps is reached.

An actor is a PregelNode. It subscribes to channels, reads data from them, and writes data to them. It can be thought of as an actor in the Pregel algorithm. PregelNodes implement LangChain's Runnable interface.

Channels are used to communicate between actors (PregelNodes). Each channel has a value type, an update type, and an update function – which takes a sequence of updates and modifies the stored value. Channels can be used to send data from one chain to another, or to send data from a chain to itself in a future step. LangGraph provides a number of built-in channels:

Most users will interact with Pregel via a StateGraph (Graph API) or via an entrypoint (Functional API).

However, for advanced use cases, Pregel can be used directly. If you're not sure whether you need to use Pregel directly, then the answer is probably no - you should use the Graph API or Functional API instead. These are higher-level interfaces that will compile down to Pregel under the hood.

Here are some examples to give you a sense of how it works:

This example demonstrates how to introduce a cycle in the graph, by having a chain write to a channel it subscribes to. Execution will continue until a None value is written to the channel.

Stream graph steps for a single input.

Asynchronously stream graph steps for a single input.

Run the graph with a single input and config.

Asynchronously invoke the graph on a single input.

Get the current state of the graph.

Get the current state of the graph.

Get the history of the state of the graph.

Asynchronously get the history of the state of the graph.

Update the state of the graph with the given values, as if they came from

Asynchronously update the state of the graph with the given values, as if they came from

Apply updates to the graph state in bulk. Requires a checkpointer to be set.

Asynchronously apply updates to the graph state in bulk. Requires a checkpointer to be set.

Return a drawable representation of the computation graph.

Return a drawable representation of the computation graph.

Get the subgraphs of the graph.

Get the subgraphs of the graph.

Create a copy of the Pregel object with an updated config.

Stream graph steps for a single input.

The input to the graph.

The configuration to use for the run.

The static context to use for the run.

Added in version 0.6.0

The mode to stream output, defaults to self.stream_mode. Options are:

You can pass a list as the stream_mode parameter to stream multiple modes at once. The streamed outputs will be tuples of (mode, data).

See LangGraph streaming guide for more details.

Accepts the same values as stream_mode, but only prints the output to the console, for debugging purposes. Does not affect the output of the graph in any way.

The keys to stream, defaults to all non-context channels.

Nodes to interrupt before, defaults to all nodes in the graph.

Nodes to interrupt after, defaults to all nodes in the graph.

The durability mode for the graph execution, defaults to "async". Options are:

Whether to stream events from inside subgraphs, defaults to False. If True, the events will be emitted as tuples (namespace, data), or (namespace, mode, data) if stream_mode is a list, where namespace is a tuple with the path to the node where a subgraph is invoked, e.g. ("parent_node:<task_id>", "child_node:<task_id>").

See LangGraph streaming guide for more details.

The output of each step in the graph. The output shape depends on the stream_mode.

Asynchronously stream graph steps for a single input.

The input to the graph.

The configuration to use for the run.

The static context to use for the run.

Added in version 0.6.0

The mode to stream output, defaults to self.stream_mode. Options are:

You can pass a list as the stream_mode parameter to stream multiple modes at once. The streamed outputs will be tuples of (mode, data).

See LangGraph streaming guide for more details.

Accepts the same values as stream_mode, but only prints the output to the console, for debugging purposes. Does not affect the output of the graph in any way.

The keys to stream, defaults to all non-context channels.

Nodes to interrupt before, defaults to all nodes in the graph.

Nodes to interrupt after, defaults to all nodes in the graph.

The durability mode for the graph execution, defaults to "async". Options are:

Whether to stream events from inside subgraphs, defaults to False. If True, the events will be emitted as tuples (namespace, data), or (namespace, mode, data) if stream_mode is a list, where namespace is a tuple with the path to the node where a subgraph is invoked, e.g. ("parent_node:<task_id>", "child_node:<task_id>").

See LangGraph streaming guide for more details.

The output of each step in the graph. The output shape depends on the stream_mode.

Run the graph with a single input and config.

The input data for the graph. It can be a dictionary or any other type.

The configuration for the graph run.

The static context to use for the run.

Added in version 0.6.0

The stream mode for the graph run.

Accepts the same values as stream_mode, but only prints the output to the console, for debugging purposes. Does not affect the output of the graph in any way.

The output keys to retrieve from the graph run.

The nodes to interrupt the graph run before.

The nodes to interrupt the graph run after.

The durability mode for the graph execution, defaults to "async". Options are:

Additional keyword arguments to pass to the graph run.

The output of the graph run. If stream_mode is "values", it returns the latest output.

If stream_mode is not "values", it returns a list of output chunks.

Asynchronously invoke the graph on a single input.

The input data for the computation. It can be a dictionary or any other type.

The configuration for the computation.

The static context to use for the run.

Added in version 0.6.0

The stream mode for the computation.

Accepts the same values as stream_mode, but only prints the output to the console, for debugging purposes. Does not affect the output of the graph in any way.

The output keys to include in the result.

The nodes to interrupt before.

The nodes to interrupt after.

The durability mode for the graph execution, defaults to "async". Options are:

Additional keyword arguments.

The result of the computation. If stream_mode is "values", it returns the latest value.

If stream_mode is "chunks", it returns a list of chunks.

Get the current state of the graph.

Get the current state of the graph.

Get the history of the state of the graph.

Asynchronously get the history of the state of the graph.

Update the state of the graph with the given values, as if they came from node as_node. If as_node is not provided, it will be set to the last node that updated the state, if not ambiguous.

Asynchronously update the state of the graph with the given values, as if they came from node as_node. If as_node is not provided, it will be set to the last node that updated the state, if not ambiguous.

Apply updates to the graph state in bulk. Requires a checkpointer to be set.

The config to apply the updates to.

A list of supersteps, each including a list of updates to apply sequentially to a graph state. Each update is a tuple of the form (values, as_node, task_id) where task_id is optional.

If no checkpointer is set or no updates are provided.

If an invalid update is provided.

Asynchronously apply updates to the graph state in bulk. Requires a checkpointer to be set.

The config to apply the updates to.

A list of supersteps, each including a list of updates to apply sequentially to a graph state. Each update is a tuple of the form (values, as_node, task_id) where task_id is optional.

If no checkpointer is set or no updates are provided.

If an invalid update is provided.

Return a drawable representation of the computation graph.

Return a drawable representation of the computation graph.

Get the subgraphs of the graph.

The namespace to filter the subgraphs by.

Whether to recurse into the subgraphs. If False, only the immediate subgraphs will be returned.

An iterator of the (namespace, subgraph) pairs.

Get the subgraphs of the graph.

The namespace to filter the subgraphs by.

Whether to recurse into the subgraphs. If False, only the immediate subgraphs will be returned.

An iterator of the (namespace, subgraph) pairs.

Create a copy of the Pregel object with an updated config.

**Examples:**

Example 1 (unknown):
```unknown
subscribe_only(channel: str) -> Self
```

Example 2 (unknown):
```unknown
subscribe_to(*channels: str, read: bool = True) -> Self
```

Example 3 (unknown):
```unknown
read_from(*channels: str) -> Self
```

Example 4 (unknown):
```unknown
do(node: RunnableLike) -> Self
```

---

## Storage¶

**URL:** https://langchain-ai.github.io/langgraph/reference/store/

**Contents:**
- Storage¶
- NamespacePath module-attribute ¶
- NamespaceMatchType module-attribute ¶
- Embeddings ¶
  - embed_documents abstractmethod ¶
  - embed_query abstractmethod ¶
  - aembed_documents async ¶
  - aembed_query async ¶
- NotProvided ¶
- Item ¶

Base classes and types for persistent key-value stores.

Stores provide long-term memory that persists across threads and conversations. Supports hierarchical namespaces, key-value storage, and optional vector search.

Utilities for batching operations in a background task.

Utilities for working with embedding functions and LangChain's Embeddings interface.

Interface for embedding models.

Represents a stored item with metadata.

Operation to retrieve a specific item by its namespace and key.

Operation to search for items within a specified namespace hierarchy.

Represents a pattern for matching namespaces in the store.

Operation to list and filter namespaces in the store.

Operation to store, update, or delete an item in the store.

Abstract base class for persistent key-value stores.

Ensure that an embedding function conforms to LangChain's Embeddings interface.

Extract text from an object using a path expression or pre-tokenized path.

Tokenize a path into components.

A tuple representing a namespace path that can include wildcards.

Specifies how to match namespace paths.

A tuple representing a namespace path that can include wildcards.

Specifies how to match namespace paths.

"prefix": Match from the start of the namespace "suffix": Match from the end of the namespace

Interface for embedding models.

This is an interface meant for implementing text embedding models.

Text embedding models are used to map text to a vector (a point in n-dimensional space).

Texts that are similar will usually be mapped to points that are close to each other in this space. The exact details of what's considered "similar" and how "distance" is measured in this space are dependent on the specific embedding model.

This abstraction contains a method for embedding a list of documents and a method for embedding a query text. The embedding of a query text is expected to be a single vector, while the embedding of a list of documents is expected to be a list of vectors.

Usually the query embedding is identical to the document embedding, but the abstraction allows treating them independently.

In addition to the synchronous methods, this interface also provides asynchronous versions of the methods.

By default, the asynchronous methods are implemented using the synchronous methods; however, implementations may choose to override the asynchronous methods with an async native implementation for performance reasons.

Asynchronous Embed search docs.

Asynchronous Embed query text.

List of text to embed.

Asynchronous Embed search docs.

List of text to embed.

Asynchronous Embed query text.

Represents a stored item with metadata.

The stored data as a dictionary. Keys are filterable.

Unique identifier within the namespace.

Hierarchical path defining the collection in which this document resides. Represented as a tuple of strings, allowing for nested categorization. For example: ("documents", 'user123')

Timestamp of item creation.

Timestamp of last update.

Represents an item returned from a search operation with additional metadata.

Initialize a result item.

Initialize a result item.

Hierarchical path to the item.

Unique identifier within the namespace.

When the item was first created.

When the item was last updated.

Relevance/similarity score if from a ranked operation.

Operation to retrieve a specific item by its namespace and key.

This operation allows precise retrieval of stored items using their full path (namespace) and unique identifier (key) combination.

Basic item retrieval:

Hierarchical path that uniquely identifies the item's location.

Unique identifier for the item within its specific namespace.

Whether to refresh TTLs for the returned item.

Hierarchical path that uniquely identifies the item's location.

Unique identifier for the item within its specific namespace.

Whether to refresh TTLs for the returned item.

If no TTL was specified for the original item(s), or if TTL support is not enabled for your adapter, this argument is ignored.

Operation to search for items within a specified namespace hierarchy.

This operation supports both structured filtering and natural language search within a given namespace prefix. It provides pagination through limit and offset parameters.

Natural language search support depends on your store implementation.

Search with filters and pagination:

Natural language search:

Hierarchical path prefix defining the search scope.

Key-value pairs for filtering results based on exact matches or comparison operators.

Maximum number of items to return in the search results.

Number of matching items to skip for pagination.

Natural language search query for semantic search capabilities.

Whether to refresh TTLs for the returned item.

Hierarchical path prefix defining the search scope.

Key-value pairs for filtering results based on exact matches or comparison operators.

The filter supports both exact matches and operator-based comparisons.

Comparison operators:

Maximum number of items to return in the search results.

Number of matching items to skip for pagination.

Natural language search query for semantic search capabilities.

Whether to refresh TTLs for the returned item.

If no TTL was specified for the original item(s), or if TTL support is not enabled for your adapter, this argument is ignored.

Represents a pattern for matching namespaces in the store.

This class combines a match type (prefix or suffix) with a namespace path pattern that can include wildcards to flexibly match different namespace hierarchies.

Suffix matching with wildcard:

Simple suffix matching:

Type of namespace matching to perform.

Namespace path pattern that can include wildcards.

Type of namespace matching to perform.

Namespace path pattern that can include wildcards.

Operation to list and filter namespaces in the store.

This operation allows exploring the organization of data, finding specific collections, and navigating the namespace hierarchy.

List all namespaces under the "documents" path:

List all namespaces that end with "v1":

Optional conditions for filtering namespaces.

Maximum depth of namespace hierarchy to return.

Maximum number of namespaces to return.

Number of namespaces to skip for pagination.

Optional conditions for filtering namespaces.

All namespaces that start with "docs" and end with "draft":

Maximum depth of namespace hierarchy to return.

Namespaces deeper than this level will be truncated.

Maximum number of namespaces to return.

Number of namespaces to skip for pagination.

Operation to store, update, or delete an item in the store.

This class represents a single operation to modify the store's contents, whether adding new items, updating existing ones, or removing them.

Hierarchical path that identifies the location of the item.

Unique identifier for the item within its namespace.

The data to store, or None to mark the item for deletion.

Controls how the item's fields are indexed for search operations.

Controls the TTL (time-to-live) for the item in minutes.

Hierarchical path that identifies the location of the item.

The namespace acts as a folder-like structure to organize items. Each element in the tuple represents one level in the hierarchy.

Root level documents:

User-specific documents:

Nested cache structure:

Unique identifier for the item within its namespace.

The key must be unique within the specific namespace to avoid conflicts. Together with the namespace, it forms a complete path to the item.

If namespace is ("documents", "user123") and key is "report1", the full path would effectively be "documents/user123/report1"

The data to store, or None to mark the item for deletion.

The value must be a dictionary with string keys and JSON-serializable values. Setting this to None signals that the item should be deleted.

{ "field1": "string value", "field2": 123, "nested": {"can": "contain", "any": "serializable data"} }

Controls how the item's fields are indexed for search operations.

The item remains accessible through direct get() operations regardless of indexing. When indexed, fields can be searched using natural language queries through vector similarity search (if supported by the store implementation).

Controls the TTL (time-to-live) for the item in minutes.

If provided, and if the store you are using supports this feature, the item will expire this many minutes after it was last accessed. The expiration timer refreshes on both read operations (get/search) and write operations (put/update). When the TTL expires, the item will be scheduled for deletion on a best-effort basis. Defaults to None (no expiration).

Provided namespace is invalid.

Configuration for TTL (time-to-live) behavior in the store.

Default behavior for refreshing TTLs on read operations (GET and SEARCH).

Default TTL (time-to-live) in minutes for new items.

Interval in minutes between TTL sweep operations.

Default behavior for refreshing TTLs on read operations (GET and SEARCH).

If True, TTLs will be refreshed on read operations (get/search) by default. This can be overridden per-operation by explicitly setting refresh_ttl. Defaults to True if not configured.

Default TTL (time-to-live) in minutes for new items.

If provided, new items will expire after this many minutes after their last access. The expiration timer refreshes on both read and write operations. Defaults to None (no expiration).

Interval in minutes between TTL sweep operations.

If provided, the store will periodically delete expired items based on TTL. Defaults to None (no sweeping).

Configuration for indexing documents for semantic search in the store.

If not provided to the store, the store will not support vector search. In that case, all index arguments to put() and aput() operations will be ignored.

Number of dimensions in the embedding vectors.

Optional function to generate embeddings from text.

Fields to extract text from for embedding generation.

Number of dimensions in the embedding vectors.

Optional function to generate embeddings from text.

Using LangChain's initialization with InMemoryStore:

Using a custom embedding function with InMemoryStore:

Using an asynchronous embedding function with InMemoryStore:

Fields to extract text from for embedding generation.

Controls which parts of stored items are embedded for semantic search. Follows JSON path syntax:

You can always override this behavior when storing an item using the index parameter in the put or aput operations.

Abstract base class for persistent key-value stores.

Stores enable persistence and memory that can be shared across threads, scoped to user IDs, assistant IDs, or other arbitrary namespaces. Some implementations may support semantic search capabilities through an optional index configuration.

Semantic search capabilities vary by implementation and are typically disabled by default. Stores that support this feature can be configured by providing an index configuration at creation time. Without this configuration, semantic search is disabled and any index arguments to storage operations will have no effect.

Similarly, TTL (time-to-live) support is disabled by default. Subclasses must explicitly set supports_ttl = True to enable this feature.

Execute multiple operations synchronously in a single batch.

Execute multiple operations asynchronously in a single batch.

Retrieve a single item.

Search for items within a namespace prefix.

Store or update an item in the store.

List and filter namespaces in the store.

Asynchronously retrieve a single item.

Asynchronously search for items within a namespace prefix.

Asynchronously store or update an item in the store.

Asynchronously delete an item.

List and filter namespaces in the store asynchronously.

Execute multiple operations synchronously in a single batch.

An iterable of operations to execute.

A list of results, where each result corresponds to an operation in the input.

The order of results matches the order of input operations.

Execute multiple operations asynchronously in a single batch.

An iterable of operations to execute.

A list of results, where each result corresponds to an operation in the input.

The order of results matches the order of input operations.

Retrieve a single item.

Hierarchical path for the item.

Unique identifier within the namespace.

Whether to refresh TTLs for the returned item. If None, uses the store's default refresh_ttl setting. If no TTL is specified, this argument is ignored.

The retrieved item or None if not found.

Search for items within a namespace prefix.

Hierarchical path prefix to search within.

Optional query for natural language search.

Key-value pairs to filter results.

Maximum number of items to return.

Number of items to skip before returning results.

Whether to refresh TTLs for the returned items. If no TTL is specified, this argument is ignored.

List of items matching the search criteria.

Natural language search (requires vector store implementation):

Natural language search support depends on your store implementation and requires proper embedding configuration.

Store or update an item in the store.

Hierarchical path for the item, represented as a tuple of strings. Example: ("documents", "user123")

Unique identifier within the namespace. Together with namespace forms the complete path to the item.

Dictionary containing the item's data. Must contain string keys and JSON-serializable values.

Controls how the item's fields are indexed for search:

Time to live in minutes. Support for this argument depends on your store adapter. If specified, the item will expire after this many minutes from when it was last accessed. None means no expiration. Expired runs will be deleted opportunistically. By default, the expiration timer refreshes on both read operations (get/search) and write operations (put/update), whenever the item is included in the operation.

Indexing support depends on your store implementation. If you do not initialize the store with indexing capabilities, the index parameter will be ignored.

Similarly, TTL support depends on the specific store implementation. Some implementations may not support expiration of items.

Store item. Indexing depends on how you configure the store:

Do not index item for semantic search. Still accessible through get() and search() operations but won't have a vector representation.

Index specific fields for search:

Hierarchical path for the item.

Unique identifier within the namespace.

List and filter namespaces in the store.

Used to explore the organization of data, find specific collections, or navigate the namespace hierarchy.

Filter namespaces that start with this path.

Filter namespaces that end with this path.

Return namespaces up to this depth in the hierarchy. Namespaces deeper than this level will be truncated.

Maximum number of namespaces to return.

Number of namespaces to skip for pagination.

A list of namespace tuples that match the criteria. Each tuple represents a full namespace path up to max_depth.

???+ example "Examples":

Asynchronously retrieve a single item.

Hierarchical path for the item.

Unique identifier within the namespace.

The retrieved item or None if not found.

Asynchronously search for items within a namespace prefix.

Hierarchical path prefix to search within.

Optional query for natural language search.

Key-value pairs to filter results.

Maximum number of items to return.

Number of items to skip before returning results.

Whether to refresh TTLs for the returned items. If None, uses the store's TTLConfig.refresh_default setting. If TTLConfig is not provided or no TTL is specified, this argument is ignored.

List of items matching the search criteria.

Natural language search (requires vector store implementation):

Natural language search support depends on your store implementation and requires proper embedding configuration.

Asynchronously store or update an item in the store.

Hierarchical path for the item, represented as a tuple of strings. Example: ("documents", "user123")

Unique identifier within the namespace. Together with namespace forms the complete path to the item.

Dictionary containing the item's data. Must contain string keys and JSON-serializable values.

Controls how the item's fields are indexed for search:

Time to live in minutes. Support for this argument depends on your store adapter. If specified, the item will expire after this many minutes from when it was last accessed. None means no expiration. Expired runs will be deleted opportunistically. By default, the expiration timer refreshes on both read operations (get/search) and write operations (put/update), whenever the item is included in the operation.

Indexing support depends on your store implementation. If you do not initialize the store with indexing capabilities, the index parameter will be ignored.

Similarly, TTL support depends on the specific store implementation. Some implementations may not support expiration of items.

Store item. Indexing depends on how you configure the store:

Do not index item for semantic search. Still accessible through get() and search() operations but won't have a vector representation.

Index specific fields for search (if store configured to index items):

Asynchronously delete an item.

Hierarchical path for the item.

Unique identifier within the namespace.

List and filter namespaces in the store asynchronously.

Used to explore the organization of data, find specific collections, or navigate the namespace hierarchy.

Filter namespaces that start with this path.

Filter namespaces that end with this path.

Return namespaces up to this depth in the hierarchy. Namespaces deeper than this level will be truncated to this depth.

Maximum number of namespaces to return.

Number of namespaces to skip for pagination.

A list of namespace tuples that match the criteria. Each tuple represents a full namespace path up to max_depth.

Setting max_depth=3 with existing namespaces: # Given the following namespaces: # ("a", "b", "c") # ("a", "b", "d", "e") # ("a", "b", "d", "i") # ("a", "b", "f") # ("a", "c", "f") await store.alist_namespaces(prefix=("a", "b"), max_depth=3) # Returns: [("a", "b", "c"), ("a", "b", "d"), ("a", "b", "f")]

Ensure that an embedding function conforms to LangChain's Embeddings interface.

This function wraps arbitrary embedding functions to make them compatible with LangChain's Embeddings interface. It handles both synchronous and asynchronous functions.

Either an existing Embeddings instance, or a function that converts text to embeddings. If the function is async, it will be used for both sync and async operations.

An Embeddings instance that wraps the provided function(s).

Wrap a synchronous embedding function:

Wrap an asynchronous embedding function:

Initialize embeddings using a provider string:

Extract text from an object using a path expression or pre-tokenized path.

The object to extract text from

Either a path string or pre-tokenized path list.

Tokenize a path into components.

Asynchronous Postgres-backed store with optional vector search using pgvector.

Connection pool settings for PostgreSQL connections.

Postgres-backed store with optional vector search using pgvector.

Bases: AsyncBatchedBaseStore, BasePostgresStore[Conn]

Asynchronous Postgres-backed store with optional vector search using pgvector.

Basic setup and usage: from langgraph.store.postgres import AsyncPostgresStore conn_string = "postgresql://user:pass@localhost:5432/dbname" async with AsyncPostgresStore.from_conn_string(conn_string) as store: await store.setup() # Run migrations. Done once # Store and retrieve data await store.aput(("users", "123"), "prefs", {"theme": "dark"}) item = await store.aget(("users", "123"), "prefs")

Vector search using LangChain embeddings: from langchain.embeddings import init_embeddings from langgraph.store.postgres import AsyncPostgresStore conn_string = "postgresql://user:pass@localhost:5432/dbname" async with AsyncPostgresStore.from_conn_string( conn_string, index={ "dims": 1536, "embed": init_embeddings("openai:text-embedding-3-small"), "fields": ["text"] # specify which fields to embed. Default is the whole serialized value } ) as store: await store.setup() # Run migrations. Done once # Store documents await store.aput(("docs",), "doc1", {"text": "Python tutorial"}) await store.aput(("docs",), "doc2", {"text": "TypeScript guide"}) await store.aput(("docs",), "doc3", {"text": "Other guide"}, index=False) # don't index # Search by similarity results = await store.asearch(("docs",), query="programming guides", limit=2)

Using connection pooling for better performance: from langgraph.store.postgres import AsyncPostgresStore, PoolConfig conn_string = "postgresql://user:pass@localhost:5432/dbname" async with AsyncPostgresStore.from_conn_string( conn_string, pool_config=PoolConfig( min_size=5, max_size=20 ) ) as store: await store.setup() # Run migrations. Done once # Use store with connection pooling...

Make sure to: 1. Call setup() before first use to create necessary tables and indexes 2. Have the pgvector extension available to use vector search 3. Use Python 3.10+ for async functionality

Semantic search is disabled by default. You can enable it by providing an index configuration when creating the store. Without this configuration, all index arguments passed to put or aput will have no effect.

If you provide a TTL configuration, you must explicitly call start_ttl_sweeper() to begin the background task that removes expired items. Call stop_ttl_sweeper() to properly clean up resources when you're done with the store.

Create a new AsyncPostgresStore instance from a connection string.

Set up the store database asynchronously.

Delete expired store items based on TTL.

Periodically delete expired store items based on TTL.

Stop the TTL sweeper task if it's running.

Create a new AsyncPostgresStore instance from a connection string.

The Postgres connection info string.

Whether to use AsyncPipeline (only for single connections)

Configuration for the connection pool. If provided, will create a connection pool and use it instead of a single connection. This overrides the pipeline argument.

The embedding config.

A new AsyncPostgresStore instance.

Set up the store database asynchronously.

This method creates the necessary tables in the Postgres database if they don't already exist and runs database migrations. It MUST be called directly by the user the first time the store is used.

Delete expired store items based on TTL.

The number of deleted items.

Periodically delete expired store items based on TTL.

Task that can be awaited or cancelled.

Stop the TTL sweeper task if it's running.

Maximum time to wait for the task to stop, in seconds. If None, wait indefinitely.

True if the task was successfully stopped or wasn't running, False if the timeout was reached before the task stopped.

Connection pool settings for PostgreSQL connections.

Controls connection lifecycle and resource utilization: - Small pools (1-5) suit low-concurrency workloads - Larger pools handle concurrent requests but consume more resources - Setting max_size prevents resource exhaustion under load

Minimum number of connections maintained in the pool. Defaults to 1.

Maximum number of connections allowed in the pool. None means unlimited.

Additional connection arguments passed to each connection in the pool.

Minimum number of connections maintained in the pool. Defaults to 1.

Maximum number of connections allowed in the pool. None means unlimited.

Additional connection arguments passed to each connection in the pool.

Default kwargs set automatically: - autocommit: True - prepare_threshold: 0 - row_factory: dict_row

Bases: BaseStore, BasePostgresStore[Conn]

Postgres-backed store with optional vector search using pgvector.

Basic setup and usage: from langgraph.store.postgres import PostgresStore from psycopg import Connection conn_string = "postgresql://user:pass@localhost:5432/dbname" # Using direct connection with Connection.connect(conn_string) as conn: store = PostgresStore(conn) store.setup() # Run migrations. Done once # Store and retrieve data store.put(("users", "123"), "prefs", {"theme": "dark"}) item = store.get(("users", "123"), "prefs")

Or using the convenient from_conn_string helper: from langgraph.store.postgres import PostgresStore conn_string = "postgresql://user:pass@localhost:5432/dbname" with PostgresStore.from_conn_string(conn_string) as store: store.setup() # Store and retrieve data store.put(("users", "123"), "prefs", {"theme": "dark"}) item = store.get(("users", "123"), "prefs")

Vector search using LangChain embeddings: from langchain.embeddings import init_embeddings from langgraph.store.postgres import PostgresStore conn_string = "postgresql://user:pass@localhost:5432/dbname" with PostgresStore.from_conn_string( conn_string, index={ "dims": 1536, "embed": init_embeddings("openai:text-embedding-3-small"), "fields": ["text"] # specify which fields to embed. Default is the whole serialized value } ) as store: store.setup() # Do this once to run migrations # Store documents store.put(("docs",), "doc1", {"text": "Python tutorial"}) store.put(("docs",), "doc2", {"text": "TypeScript guide"}) store.put(("docs",), "doc2", {"text": "Other guide"}, index=False) # don't index # Search by similarity results = store.search(("docs",), query="programming guides", limit=2)

Semantic search is disabled by default. You can enable it by providing an index configuration when creating the store. Without this configuration, all index arguments passed to put or aputwill have no effect.

Make sure to call setup() before first use to create necessary tables and indexes. The pgvector extension must be available to use vector search.

If you provide a TTL configuration, you must explicitly call start_ttl_sweeper() to begin the background thread that removes expired items. Call stop_ttl_sweeper() to properly clean up resources when you're done with the store.

Retrieve a single item.

Search for items within a namespace prefix.

Store or update an item in the store.

List and filter namespaces in the store.

Asynchronously retrieve a single item.

Asynchronously search for items within a namespace prefix.

Asynchronously store or update an item in the store.

Asynchronously delete an item.

List and filter namespaces in the store asynchronously.

Create a new PostgresStore instance from a connection string.

Delete expired store items based on TTL.

Periodically delete expired store items based on TTL.

Stop the TTL sweeper thread if it's running.

Ensure the TTL sweeper thread is stopped when the object is garbage collected.

Set up the store database.

Retrieve a single item.

Hierarchical path for the item.

Unique identifier within the namespace.

Whether to refresh TTLs for the returned item. If None, uses the store's default refresh_ttl setting. If no TTL is specified, this argument is ignored.

The retrieved item or None if not found.

Search for items within a namespace prefix.

Hierarchical path prefix to search within.

Optional query for natural language search.

Key-value pairs to filter results.

Maximum number of items to return.

Number of items to skip before returning results.

Whether to refresh TTLs for the returned items. If no TTL is specified, this argument is ignored.

List of items matching the search criteria.

Natural language search (requires vector store implementation):

Natural language search support depends on your store implementation and requires proper embedding configuration.

Store or update an item in the store.

Hierarchical path for the item, represented as a tuple of strings. Example: ("documents", "user123")

Unique identifier within the namespace. Together with namespace forms the complete path to the item.

Dictionary containing the item's data. Must contain string keys and JSON-serializable values.

Controls how the item's fields are indexed for search:

Time to live in minutes. Support for this argument depends on your store adapter. If specified, the item will expire after this many minutes from when it was last accessed. None means no expiration. Expired runs will be deleted opportunistically. By default, the expiration timer refreshes on both read operations (get/search) and write operations (put/update), whenever the item is included in the operation.

Indexing support depends on your store implementation. If you do not initialize the store with indexing capabilities, the index parameter will be ignored.

Similarly, TTL support depends on the specific store implementation. Some implementations may not support expiration of items.

Store item. Indexing depends on how you configure the store:

Do not index item for semantic search. Still accessible through get() and search() operations but won't have a vector representation.

Index specific fields for search:

Hierarchical path for the item.

Unique identifier within the namespace.

List and filter namespaces in the store.

Used to explore the organization of data, find specific collections, or navigate the namespace hierarchy.

Filter namespaces that start with this path.

Filter namespaces that end with this path.

Return namespaces up to this depth in the hierarchy. Namespaces deeper than this level will be truncated.

Maximum number of namespaces to return.

Number of namespaces to skip for pagination.

A list of namespace tuples that match the criteria. Each tuple represents a full namespace path up to max_depth.

???+ example "Examples":

Asynchronously retrieve a single item.

Hierarchical path for the item.

Unique identifier within the namespace.

The retrieved item or None if not found.

Asynchronously search for items within a namespace prefix.

Hierarchical path prefix to search within.

Optional query for natural language search.

Key-value pairs to filter results.

Maximum number of items to return.

Number of items to skip before returning results.

Whether to refresh TTLs for the returned items. If None, uses the store's TTLConfig.refresh_default setting. If TTLConfig is not provided or no TTL is specified, this argument is ignored.

List of items matching the search criteria.

Natural language search (requires vector store implementation):

Natural language search support depends on your store implementation and requires proper embedding configuration.

Asynchronously store or update an item in the store.

Hierarchical path for the item, represented as a tuple of strings. Example: ("documents", "user123")

Unique identifier within the namespace. Together with namespace forms the complete path to the item.

Dictionary containing the item's data. Must contain string keys and JSON-serializable values.

Controls how the item's fields are indexed for search:

Time to live in minutes. Support for this argument depends on your store adapter. If specified, the item will expire after this many minutes from when it was last accessed. None means no expiration. Expired runs will be deleted opportunistically. By default, the expiration timer refreshes on both read operations (get/search) and write operations (put/update), whenever the item is included in the operation.

Indexing support depends on your store implementation. If you do not initialize the store with indexing capabilities, the index parameter will be ignored.

Similarly, TTL support depends on the specific store implementation. Some implementations may not support expiration of items.

Store item. Indexing depends on how you configure the store:

Do not index item for semantic search. Still accessible through get() and search() operations but won't have a vector representation.

Index specific fields for search (if store configured to index items):

Asynchronously delete an item.

Hierarchical path for the item.

Unique identifier within the namespace.

List and filter namespaces in the store asynchronously.

Used to explore the organization of data, find specific collections, or navigate the namespace hierarchy.

Filter namespaces that start with this path.

Filter namespaces that end with this path.

Return namespaces up to this depth in the hierarchy. Namespaces deeper than this level will be truncated to this depth.

Maximum number of namespaces to return.

Number of namespaces to skip for pagination.

A list of namespace tuples that match the criteria. Each tuple represents a full namespace path up to max_depth.

Setting max_depth=3 with existing namespaces: # Given the following namespaces: # ("a", "b", "c") # ("a", "b", "d", "e") # ("a", "b", "d", "i") # ("a", "b", "f") # ("a", "c", "f") await store.alist_namespaces(prefix=("a", "b"), max_depth=3) # Returns: [("a", "b", "c"), ("a", "b", "d"), ("a", "b", "f")]

Create a new PostgresStore instance from a connection string.

The Postgres connection info string.

whether to use Pipeline

Configuration for the connection pool. If provided, will create a connection pool and use it instead of a single connection. This overrides the pipeline argument.

The index configuration for the store.

The TTL configuration for the store.

A new PostgresStore instance.

Delete expired store items based on TTL.

The number of deleted items.

Periodically delete expired store items based on TTL.

Future that can be waited on or cancelled.

Stop the TTL sweeper thread if it's running.

Maximum time to wait for the thread to stop, in seconds. If None, wait indefinitely.

True if the thread was successfully stopped or wasn't running, False if the timeout was reached before the thread stopped.

Ensure the TTL sweeper thread is stopped when the object is garbage collected.

Set up the store database.

This method creates the necessary tables in the Postgres database if they don't already exist and runs database migrations. It MUST be called directly by the user the first time the store is used.

**Examples:**

Example 1 (unknown):
```unknown
NamespacePath = tuple[str | Literal['*'], ...]
```

Example 2 (unknown):
```unknown
("users",)  # Exact users namespace
("documents", "*")  # Any sub-namespace under documents
("cache", "*", "v1")  # Any cache category with v1 version
```

Example 3 (unknown):
```unknown
NamespaceMatchType = Literal['prefix', 'suffix']
```

Example 4 (unknown):
```unknown
embed_documents(texts: list[str]) -> list[list[float]]
```

---

## Build a basic chatbot¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/get-started/1-build-basic-chatbot/

**Contents:**
- Build a basic chatbot¶
- Prerequisites¶
- 1. Install packages¶
- 2. Create a StateGraph¶
- 3. Add a node¶
- 4. Add an entry point¶
- 5. Add an exit point¶
- 6. Compile the graph¶
- 7. Visualize the graph (optional)¶
- 8. Run the chatbot¶

In this tutorial, you will build a basic chatbot. This chatbot is the basis for the following series of tutorials where you will progressively add more sophisticated capabilities, and be introduced to key LangGraph concepts along the way. Let's dive in! 🌟

Before you start this tutorial, ensure you have access to a LLM that supports tool-calling features, such as OpenAI, Anthropic, or Google Gemini.

Install the required packages:

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph. For more information on how to get started, see LangSmith docs.

Now you can create a basic chatbot using LangGraph. This chatbot will respond directly to user messages.

Start by creating a StateGraph. A StateGraph object defines the structure of our chatbot as a "state machine". We'll add nodes to represent the llm and functions our chatbot can call and edges to specify how the bot should transition between these functions.

API Reference: StateGraph | START | END | add_messages

Our graph can now handle two key tasks:

When defining a graph, the first step is to define its State. The State includes the graph's schema and reducer functions that handle state updates. In our example, State is a schema with one key: messages. The reducer function is used to append new messages to the list instead of overwriting it. Keys without a reducer annotation will overwrite previous values.

To learn more about state, reducers, and related concepts, see LangGraph reference docs.

Next, add a "chatbot" node. Nodes represent units of work and are typically regular functions.

Let's first select a chat model:

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["OPENAI_API_KEY"] = "sk-..." llm = init_chat_model("openai:gpt-4.1")

👉 Read the OpenAI integration docs

pip install -U "langchain[anthropic]" import os from langchain.chat_models import init_chat_model os.environ["ANTHROPIC_API_KEY"] = "sk-..." llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

👉 Read the Anthropic integration docs

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["AZURE_OPENAI_API_KEY"] = "..." os.environ["AZURE_OPENAI_ENDPOINT"] = "..." os.environ["OPENAI_API_VERSION"] = "2025-03-01-preview" llm = init_chat_model( "azure_openai:gpt-4.1", azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"], )

👉 Read the Azure integration docs

pip install -U "langchain[google-genai]" import os from langchain.chat_models import init_chat_model os.environ["GOOGLE_API_KEY"] = "..." llm = init_chat_model("google_genai:gemini-2.0-flash")

👉 Read the Google GenAI integration docs

pip install -U "langchain[aws]" from langchain.chat_models import init_chat_model # Follow the steps here to configure your credentials: # https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html llm = init_chat_model( "anthropic.claude-3-5-sonnet-20240620-v1:0", model_provider="bedrock_converse", )

👉 Read the AWS Bedrock integration docs

We can now incorporate the chat model into a simple node:

Notice how the chatbot node function takes the current State as input and returns a dictionary containing an updated messages list under the key "messages". This is the basic pattern for all LangGraph node functions.

The add_messages function in our State will append the LLM's response messages to whatever messages are already in the state.

Add an entry point to tell the graph where to start its work each time it is run:

Add an exit point to indicate where the graph should finish execution. This is helpful for more complex flows, but even in a simple graph like this, adding an end node improves clarity.

This tells the graph to terminate after running the chatbot node.

Before running the graph, we'll need to compile it. We can do so by calling compile() on the graph builder. This creates a CompiledGraph we can invoke on our state.

You can visualize the graph using the get_graph method and one of the "draw" methods, like draw_ascii or draw_png. The draw methods each require additional dependencies.

You can exit the chat loop at any time by typing quit, exit, or q.

Congratulations! You've built your first chatbot using LangGraph. This bot can engage in basic conversation by taking user input and generating responses using an LLM. You can inspect a LangSmith Trace for the call above.

Below is the full code for this tutorial:

API Reference: init_chat_model | StateGraph | START | END | add_messages

You may have noticed that the bot's knowledge is limited to what's in its training data. In the next part, we'll add a web search tool to expand the bot's knowledge and make it more capable.

**Examples:**

Example 1 (unknown):
```unknown
pip install -U langgraph langsmith
```

Example 2 (python):
```python
from typing import Annotated

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)
```

Example 3 (unknown):
```unknown
pip install -U "langchain[openai]"
```

Example 4 (python):
```python
import os
from langchain.chat_models import init_chat_model

os.environ["OPENAI_API_KEY"] = "sk-..."

llm = init_chat_model("openai:gpt-4.1")
```

---
