# Langgraph - State Management

**Pages:** 13

---

## Channels¶

**URL:** https://langchain-ai.github.io/langgraph/reference/channels/

**Contents:**
- Channels¶
- BaseChannel ¶
  - ValueType abstractmethod property ¶
  - UpdateType abstractmethod property ¶
  - copy ¶
  - checkpoint ¶
  - from_checkpoint abstractmethod ¶
  - get abstractmethod ¶
  - is_available ¶
  - update abstractmethod ¶

Base class for all channels.

Bases: Generic[Value, Update, Checkpoint], ABC

Base class for all channels.

Return a copy of the channel.

Return a serializable representation of the channel's current state.

Return a new identical channel, optionally initialized from a checkpoint.

Return the current value of the channel.

Return True if the channel is available (not empty), False otherwise.

Update the channel's value with the given sequence of updates.

Notify the channel that a subscribed task ran. By default, no-op.

Notify the channel that the Pregel run is finishing. By default, no-op.

The type of the value stored in the channel.

The type of the update received by the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

Return a copy of the channel. By default, delegates to checkpoint() and from_checkpoint(). Subclasses can override this method with a more efficient implementation.

Return a serializable representation of the channel's current state. Raises EmptyChannelError if the channel is empty (never updated yet), or doesn't support checkpoints.

Return a new identical channel, optionally initialized from a checkpoint. If the checkpoint contains complex data structures, they should be copied.

Return the current value of the channel.

Raises EmptyChannelError if the channel is empty (never updated yet).

Return True if the channel is available (not empty), False otherwise. Subclasses should override this method to provide a more efficient implementation than calling get() and catching EmptyChannelError.

Update the channel's value with the given sequence of updates. The order of the updates in the sequence is arbitrary. This method is called by Pregel for all channels at the end of each step. If there are no updates, it is called with an empty sequence. Raises InvalidUpdateError if the sequence of updates is invalid. Returns True if the channel was updated, False otherwise.

Notify the channel that a subscribed task ran. By default, no-op. A channel can use this method to modify its state, preventing the value from being consumed again.

Returns True if the channel was updated, False otherwise.

Notify the channel that the Pregel run is finishing. By default, no-op. A channel can use this method to modify its state, preventing finish.

Returns True if the channel was updated, False otherwise.

A configurable PubSub Topic.

Stores the last value received, can receive at most one value per step.

Stores the value received in the step immediately preceding, clears after.

Stores the result of applying a binary operator to the current value and each new value.

Stores the last value received, assumes that if multiple values are

Bases: Generic[Value], BaseChannel[Sequence[Value], Value | list[Value], list[Value]]

A configurable PubSub Topic.

The type of the value stored in the channel.

Whether to accumulate values across steps. If False, the channel will be emptied after each step.

Notify the channel that a subscribed task ran. By default, no-op.

Notify the channel that the Pregel run is finishing. By default, no-op.

Return a copy of the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

Notify the channel that a subscribed task ran. By default, no-op. A channel can use this method to modify its state, preventing the value from being consumed again.

Returns True if the channel was updated, False otherwise.

Notify the channel that the Pregel run is finishing. By default, no-op. A channel can use this method to modify its state, preventing finish.

Returns True if the channel was updated, False otherwise.

Return a copy of the channel.

Bases: Generic[Value], BaseChannel[Value, Value, Value]

Stores the last value received, can receive at most one value per step.

Notify the channel that a subscribed task ran. By default, no-op.

Notify the channel that the Pregel run is finishing. By default, no-op.

Return a copy of the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

Notify the channel that a subscribed task ran. By default, no-op. A channel can use this method to modify its state, preventing the value from being consumed again.

Returns True if the channel was updated, False otherwise.

Notify the channel that the Pregel run is finishing. By default, no-op. A channel can use this method to modify its state, preventing finish.

Returns True if the channel was updated, False otherwise.

Return a copy of the channel.

Bases: Generic[Value], BaseChannel[Value, Value, Value]

Stores the value received in the step immediately preceding, clears after.

Notify the channel that a subscribed task ran. By default, no-op.

Notify the channel that the Pregel run is finishing. By default, no-op.

Return a copy of the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

Notify the channel that a subscribed task ran. By default, no-op. A channel can use this method to modify its state, preventing the value from being consumed again.

Returns True if the channel was updated, False otherwise.

Notify the channel that the Pregel run is finishing. By default, no-op. A channel can use this method to modify its state, preventing finish.

Returns True if the channel was updated, False otherwise.

Return a copy of the channel.

Bases: Generic[Value], BaseChannel[Value, Value, Value]

Stores the result of applying a binary operator to the current value and each new value.

Notify the channel that a subscribed task ran. By default, no-op.

Notify the channel that the Pregel run is finishing. By default, no-op.

Return a copy of the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

Notify the channel that a subscribed task ran. By default, no-op. A channel can use this method to modify its state, preventing the value from being consumed again.

Returns True if the channel was updated, False otherwise.

Notify the channel that the Pregel run is finishing. By default, no-op. A channel can use this method to modify its state, preventing finish.

Returns True if the channel was updated, False otherwise.

Return a copy of the channel.

Bases: Generic[Value], BaseChannel[Value, Value, Value]

Stores the last value received, assumes that if multiple values are received, they are all equal.

Notify the channel that a subscribed task ran. By default, no-op.

Notify the channel that the Pregel run is finishing. By default, no-op.

Return a copy of the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

The type of the value stored in the channel.

The type of the update received by the channel.

Notify the channel that a subscribed task ran. By default, no-op. A channel can use this method to modify its state, preventing the value from being consumed again.

Returns True if the channel was updated, False otherwise.

Notify the channel that the Pregel run is finishing. By default, no-op. A channel can use this method to modify its state, preventing finish.

Returns True if the channel was updated, False otherwise.

Return a copy of the channel.

**Examples:**

Example 1 (unknown):
```unknown
ValueType: Any
```

Example 2 (unknown):
```unknown
UpdateType: Any
```

Example 3 (unknown):
```unknown
copy() -> Self
```

Example 4 (unknown):
```unknown
checkpoint() -> Checkpoint | Any
```

---

## Time travel¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/get-started/6-time-travel/

**Contents:**
- Time travel¶
- 1. Rewind your graph¶
- 2. Add steps¶
- 3. Replay the full state history¶
- Resume from a checkpoint¶
- 4. Load a state from a moment-in-time¶
- Learn more¶

In a typical chatbot workflow, the user interacts with the bot one or more times to accomplish a task. Memory and a human-in-the-loop enable checkpoints in the graph state and control future responses.

What if you want a user to be able to start from a previous response and explore a different outcome? Or what if you want users to be able to rewind your chatbot's work to fix mistakes or try a different strategy, something that is common in applications like autonomous software engineers?

You can create these types of experiences using LangGraph's built-in time travel functionality.

This tutorial builds on Customize state.

Rewind your graph by fetching a checkpoint using the graph's get_state_history method. You can then resume execution at this previous point in time.

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

API Reference: TavilySearch | BaseMessage | InMemorySaver | StateGraph | START | END | add_messages | ToolNode | tools_condition

Add steps to your graph. Every step will be checkpointed in its state history:

Now that you have added steps to the chatbot, you can replay the full state history to see everything that occurred.

Checkpoints are saved for every step of the graph. This spans invocations so you can rewind across a full thread's history.

Resume from the to_replay state, which is after the chatbot node in the second graph invocation. Resuming from this point will call the action node next.

The checkpoint's to_replay.config contains a checkpoint_id timestamp. Providing this checkpoint_id value tells LangGraph's checkpointer to load the state from that moment in time.

The graph resumed execution from the tools node. You can tell this is the case since the first value printed above is the response from our search engine tool.

Congratulations! You've now used time-travel checkpoint traversal in LangGraph. Being able to rewind and explore alternative paths opens up a world of possibilities for debugging, experimentation, and interactive applications.

Take your LangGraph journey further by exploring deployment and advanced features:

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

## Add and manage memory¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/memory/add-memory/

**Contents:**
- Add and manage memory¶
- Add short-term memory¶
  - Use in production¶
  - Use in subgraphs¶
  - Read short-term memory in tools¶
  - Write short-term memory from tools¶
- Add long-term memory¶
  - Use in production¶
  - Read long-term memory in tools¶
  - Write long-term memory from tools¶

AI applications need memory to share context across multiple interactions. In LangGraph, you can add two types of memory:

Short-term memory (thread-level persistence) enables agents to track multi-turn conversations. To add short-term memory:

API Reference: InMemorySaver | StateGraph

In production, use a checkpointer backed by a database:

API Reference: PostgresSaver

You need to call checkpointer.setup() the first time you're using Postgres checkpointer

To use the MongoDB checkpointer, you will need a MongoDB cluster. Follow this guide to create a cluster if you don't already have one.

You need to call checkpointer.setup() the first time you're using Redis checkpointer

If your graph contains subgraphs, you only need to provide the checkpointer when compiling the parent graph. LangGraph will automatically propagate the checkpointer to the child subgraphs.

API Reference: START | StateGraph | InMemorySaver

If you want the subgraph to have its own memory, you can compile it with the appropriate checkpointer option. This is useful in multi-agent systems, if you want agents to keep track of their internal message histories.

LangGraph allows agents to access their short-term memory (state) inside the tools.

API Reference: InjectedState | create_react_agent

See the Context guide for more information.

To modify the agent's short-term memory (state) during execution, you can return state updates directly from the tools. This is useful for persisting intermediate results or making information accessible to subsequent tools or prompts.

API Reference: InjectedToolCallId | RunnableConfig | ToolMessage | InjectedState | create_react_agent | AgentState | Command

Use long-term memory to store user-specific or application-specific data across conversations.

API Reference: StateGraph

In production, use a store backed by a database:

You need to call store.setup() the first time you're using Postgres store

You need to call store.setup() the first time you're using Redis store

Enable semantic search in your graph's memory store to let graph agents search for items in the store by semantic similarity.

API Reference: init_embeddings

See this guide for more information on how to use semantic search with LangGraph memory store.

With short-term memory enabled, long conversations can exceed the LLM's context window. Common solutions are:

This allows the agent to keep track of the conversation without exceeding the LLM's context window.

Most LLMs have a maximum supported context window (denominated in tokens). One way to decide when to truncate messages is to count the tokens in the message history and truncate whenever it approaches that limit. If you're using LangChain, you can use the trim messages utility and specify the number of tokens to keep from the list, as well as the strategy (e.g., keep the last maxTokens) to use for handling the boundary.

To trim message history in an agent, use pre_model_hook with the trim_messages function:

To trim message history, use the trim_messages function:

You can delete messages from the graph state to manage the message history. This is useful when you want to remove specific messages or clear the entire message history.

To delete messages from the graph state, you can use the RemoveMessage. For RemoveMessage to work, you need to use a state key with add_messages reducer, like MessagesState.

To remove specific messages:

API Reference: RemoveMessage

To remove all messages:

When deleting messages, make sure that the resulting message history is valid. Check the limitations of the LLM provider you're using. For example:

The problem with trimming or removing messages, as shown above, is that you may lose information from culling of the message queue. Because of this, some applications benefit from a more sophisticated approach of summarizing the message history using a chat model.

To summarize message history in an agent, use pre_model_hook with a prebuilt SummarizationNode abstraction:

Prompting and orchestration logic can be used to summarize the message history. For example, in LangGraph you can extend the MessagesState to include a summary key:

Then, you can generate a summary of the chat history, using any existing summary as context for the next summary. This summarize_conversation node can be called after some number of messages have accumulated in the messages state key.

You can view and delete the information stored by the checkpointer.

LangMem is a LangChain-maintained library that offers tools for managing long-term memories in your agent. See the LangMem documentation for usage examples.

**Examples:**

Example 1 (python):
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph

checkpointer = InMemorySaver()

builder = StateGraph(...)
graph = builder.compile(checkpointer=checkpointer)

graph.invoke(
    {"messages": [{"role": "user", "content": "hi! i am Bob"}]},
    {"configurable": {"thread_id": "1"}},
)
```

Example 2 (python):
```python
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://postgres:postgres@localhost:5442/postgres?sslmode=disable"
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    builder = StateGraph(...)
    graph = builder.compile(checkpointer=checkpointer)
```

Example 3 (unknown):
```unknown
pip install -U "psycopg[binary,pool]" langgraph langgraph-checkpoint-postgres
```

Example 4 (python):
```python
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.checkpoint.postgres import PostgresSaver

model = init_chat_model(model="anthropic:claude-3-5-haiku-latest")

DB_URI = "postgresql://postgres:postgres@localhost:5442/postgres?sslmode=disable"
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    # checkpointer.setup()

    def call_model(state: MessagesState):
        response = model.invoke(state["messages"])
        return {"messages": response}

    builder = StateGraph(MessagesState)
    builder.add_node(call_model)
    builder.add_edge(START, "call_model")

    graph = builder.compile(checkpointer=checkpointer)

    config = {
        "configurable": {
            "thread_id": "1"
        }
    }

    for chunk in graph.stream(
        {"messages": [{"role": "user", "content": "hi! I'm bob"}]},
        config,
        stream_mode="values"
    ):
        chunk["messages"][-1].pretty_print()

    for chunk in graph.stream(
        {"messages": [{"role": "user", "content": "what's my name?"}]},
        config,
        stream_mode="values"
    ):
        chunk["messages"][-1].pretty_print()
```

---

## Checkpointers¶

**URL:** https://langchain-ai.github.io/langgraph/reference/checkpoints/

**Contents:**
- Checkpointers¶
- CheckpointMetadata ¶
  - source instance-attribute ¶
  - step instance-attribute ¶
  - parents instance-attribute ¶
- Checkpoint ¶
  - v instance-attribute ¶
  - id instance-attribute ¶
  - ts instance-attribute ¶
  - channel_values instance-attribute ¶

Metadata associated with a checkpoint.

State snapshot at a given point in time.

Base class for creating a graph checkpointer.

Create a checkpoint for the given channels.

Metadata associated with a checkpoint.

The source of the checkpoint.

The step number of the checkpoint.

The IDs of the parent checkpoints.

The source of the checkpoint.

The step number of the checkpoint.

-1 for the first "input" checkpoint. 0 for the first "loop" checkpoint. ... for the nth checkpoint afterwards.

The IDs of the parent checkpoints.

Mapping from checkpoint namespace to checkpoint ID.

State snapshot at a given point in time.

The version of the checkpoint format. Currently 1.

The ID of the checkpoint. This is both unique and monotonically

The timestamp of the checkpoint in ISO 8601 format.

The values of the channels at the time of the checkpoint.

The versions of the channels at the time of the checkpoint.

Map from node ID to map from channel name to version seen.

The channels that were updated in this checkpoint.

The version of the checkpoint format. Currently 1.

The ID of the checkpoint. This is both unique and monotonically increasing, so can be used for sorting checkpoints from first to last.

The timestamp of the checkpoint in ISO 8601 format.

The values of the channels at the time of the checkpoint. Mapping from channel name to deserialized channel snapshot value.

The versions of the channels at the time of the checkpoint. The keys are channel names and the values are monotonically increasing version strings for each channel.

Map from node ID to map from channel name to version seen. This keeps track of the versions of the channels that each node has seen. Used to determine which nodes to execute next.

The channels that were updated in this checkpoint.

Base class for creating a graph checkpointer.

Checkpointers allow LangGraph agents to persist their state within and across multiple interactions.

Serializer for encoding/decoding checkpoints.

When creating a custom checkpoint saver, consider implementing async versions to avoid blocking the main thread.

Fetch a checkpoint using the given configuration.

Fetch a checkpoint tuple using the given configuration.

List checkpoints that match the given criteria.

Store a checkpoint with its configuration and metadata.

Store intermediate writes linked to a checkpoint.

Delete all checkpoints and writes associated with a specific thread ID.

Asynchronously fetch a checkpoint using the given configuration.

Asynchronously fetch a checkpoint tuple using the given configuration.

Asynchronously list checkpoints that match the given criteria.

Asynchronously store a checkpoint with its configuration and metadata.

Asynchronously store intermediate writes linked to a checkpoint.

Delete all checkpoints and writes associated with a specific thread ID.

Generate the next version ID for a channel.

Define the configuration options for the checkpoint saver.

List of configuration field specs.

Fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Fetch a checkpoint tuple using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint tuple, or None if not found.

Implement this method in your custom checkpoint saver.

List checkpoints that match the given criteria.

Base configuration for filtering checkpoints.

Additional filtering criteria.

List checkpoints created before this configuration.

Maximum number of checkpoints to return.

Iterator of matching checkpoint tuples.

Implement this method in your custom checkpoint saver.

Store a checkpoint with its configuration and metadata.

Configuration for the checkpoint.

The checkpoint to store.

Additional metadata for the checkpoint.

New channel versions as of this write.

Updated configuration after storing the checkpoint.

Implement this method in your custom checkpoint saver.

Store intermediate writes linked to a checkpoint.

Configuration of the related checkpoint.

List of writes to store.

Identifier for the task creating the writes.

Path of the task creating the writes.

Implement this method in your custom checkpoint saver.

Delete all checkpoints and writes associated with a specific thread ID.

The thread ID whose checkpoints should be deleted.

Asynchronously fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Asynchronously fetch a checkpoint tuple using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint tuple, or None if not found.

Implement this method in your custom checkpoint saver.

Asynchronously list checkpoints that match the given criteria.

Base configuration for filtering checkpoints.

Additional filtering criteria for metadata.

List checkpoints created before this configuration.

Maximum number of checkpoints to return.

Async iterator of matching checkpoint tuples.

Implement this method in your custom checkpoint saver.

Asynchronously store a checkpoint with its configuration and metadata.

Configuration for the checkpoint.

The checkpoint to store.

Additional metadata for the checkpoint.

New channel versions as of this write.

Updated configuration after storing the checkpoint.

Implement this method in your custom checkpoint saver.

Asynchronously store intermediate writes linked to a checkpoint.

Configuration of the related checkpoint.

List of writes to store.

Identifier for the task creating the writes.

Path of the task creating the writes.

Implement this method in your custom checkpoint saver.

Delete all checkpoints and writes associated with a specific thread ID.

The thread ID whose checkpoints should be deleted.

Generate the next version ID for a channel.

Default is to use integer versions, incrementing by 1. If you override, you can use str/int/float versions, as long as they are monotonically increasing.

The current version identifier (int, float, or str).

Deprecated argument, kept for backwards compatibility.

The next version identifier, which must be increasing.

Create a checkpoint for the given channels.

Protocol for serialization and deserialization of objects.

Protocol for encryption and decryption of data.

Protocol for serialization and deserialization of objects.

Valid implementations include the pickle, json and orjson modules.

Protocol for encryption and decryption of data. - encrypt: Encrypt plaintext. - decrypt: Decrypt ciphertext.

Encrypt plaintext. Returns a tuple (cipher name, ciphertext).

Decrypt ciphertext. Returns the plaintext.

Encrypt plaintext. Returns a tuple (cipher name, ciphertext).

Decrypt ciphertext. Returns the plaintext.

Serializer that uses ormsgpack, with optional fallbacks.

Bases: SerializerProtocol

Serializer that uses ormsgpack, with optional fallbacks.

Security note: this serializer is intended for use within the BaseCheckpointSaver class and called within the Pregel loop. It should not be used on untrusted python objects. If an attacker can write directly to your checkpoint database, they may be able to trigger code execution when data is deserialized.

Serializer that encrypts and decrypts data using an encryption protocol.

Bases: SerializerProtocol

Serializer that encrypts and decrypts data using an encryption protocol.

Serialize an object to a tuple (type, bytes) and encrypt the bytes.

Create an EncryptedSerializer using AES encryption.

Serialize an object to a tuple (type, bytes) and encrypt the bytes.

Create an EncryptedSerializer using AES encryption.

An in-memory checkpoint saver.

Persistent dictionary with an API compatible with shelve and anydbm.

Bases: BaseCheckpointSaver[str], AbstractContextManager, AbstractAsyncContextManager

An in-memory checkpoint saver.

This checkpoint saver stores checkpoints in memory using a defaultdict.

Only use InMemorySaver for debugging or testing purposes. For production use cases we recommend installing langgraph-checkpoint-postgres and using PostgresSaver / AsyncPostgresSaver.

If you are using LangSmith Deployment, no checkpointer needs to be specified. The correct managed checkpointer will be used automatically.

The serializer to use for serializing and deserializing checkpoints.

Get a checkpoint tuple from the in-memory storage.

List checkpoints from the in-memory storage.

Save a checkpoint to the in-memory storage.

Save a list of writes to the in-memory storage.

Delete all checkpoints and writes associated with a thread ID.

Asynchronous version of get_tuple.

Asynchronous version of list.

Asynchronous version of put.

Asynchronous version of put_writes.

Delete all checkpoints and writes associated with a thread ID.

Fetch a checkpoint using the given configuration.

Asynchronously fetch a checkpoint using the given configuration.

Define the configuration options for the checkpoint saver.

Define the configuration options for the checkpoint saver.

List of configuration field specs.

Get a checkpoint tuple from the in-memory storage.

This method retrieves a checkpoint tuple from the in-memory storage based on the provided config. If the config contains a checkpoint_id key, the checkpoint with the matching thread ID and timestamp is retrieved. Otherwise, the latest checkpoint for the given thread ID is retrieved.

The config to use for retrieving the checkpoint.

The retrieved checkpoint tuple, or None if no matching checkpoint was found.

List checkpoints from the in-memory storage.

This method retrieves a list of checkpoint tuples from the in-memory storage based on the provided criteria.

Base configuration for filtering checkpoints.

Additional filtering criteria for metadata.

List checkpoints created before this configuration.

Maximum number of checkpoints to return.

An iterator of matching checkpoint tuples.

Save a checkpoint to the in-memory storage.

This method saves a checkpoint to the in-memory storage. The checkpoint is associated with the provided config.

The config to associate with the checkpoint.

The checkpoint to save.

Additional metadata to save with the checkpoint.

New versions as of this write

The updated config containing the saved checkpoint's timestamp.

Save a list of writes to the in-memory storage.

This method saves a list of writes to the in-memory storage. The writes are associated with the provided config.

The config to associate with the writes.

Identifier for the task creating the writes.

Path of the task creating the writes.

The updated config containing the saved writes' timestamp.

Delete all checkpoints and writes associated with a thread ID.

The thread ID to delete.

Asynchronous version of get_tuple.

This method is an asynchronous wrapper around get_tuple that runs the synchronous method in a separate thread using asyncio.

The config to use for retrieving the checkpoint.

The retrieved checkpoint tuple, or None if no matching checkpoint was found.

Asynchronous version of list.

This method is an asynchronous wrapper around list that runs the synchronous method in a separate thread using asyncio.

The config to use for listing the checkpoints.

An asynchronous iterator of checkpoint tuples.

Asynchronous version of put.

The config to associate with the checkpoint.

The checkpoint to save.

Additional metadata to save with the checkpoint.

New versions as of this write

The updated config containing the saved checkpoint's timestamp.

Asynchronous version of put_writes.

This method is an asynchronous wrapper around put_writes that runs the synchronous method in a separate thread using asyncio.

The config to associate with the writes.

The writes to save, each as a (channel, value) pair.

Identifier for the task creating the writes.

Path of the task creating the writes.

Delete all checkpoints and writes associated with a thread ID.

The thread ID to delete.

Fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Asynchronously fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Persistent dictionary with an API compatible with shelve and anydbm.

The dict is kept in memory, so the dictionary operations run as fast as a regular dictionary.

Write to disk is delayed until close or sync (similar to gdbm's fast mode).

Input file format is automatically discovered. Output file format is selectable between pickle, json, and csv. All three serialization formats are backed by fast C implementations.

Adapted from https://code.activestate.com/recipes/576642-persistent-dict-with-multiple-standard-file-format/

A checkpoint saver that stores checkpoints in a SQLite database.

Bases: BaseCheckpointSaver[str]

A checkpoint saver that stores checkpoints in a SQLite database.

This class is meant for lightweight, synchronous use cases (demos and small projects) and does not scale to multiple threads. For a similar sqlite saver with async support, consider using AsyncSqliteSaver.

The SQLite database connection.

The serializer to use for serializing and deserializing checkpoints. Defaults to JsonPlusSerializerCompat.

Create a new SqliteSaver instance from a connection string.

Set up the checkpoint database.

Get a cursor for the SQLite database.

Get a checkpoint tuple from the database.

List checkpoints from the database.

Save a checkpoint to the database.

Store intermediate writes linked to a checkpoint.

Delete all checkpoints and writes associated with a thread ID.

Get a checkpoint tuple from the database asynchronously.

List checkpoints from the database asynchronously.

Save a checkpoint to the database asynchronously.

Generate the next version ID for a channel.

Fetch a checkpoint using the given configuration.

Asynchronously fetch a checkpoint using the given configuration.

Asynchronously store intermediate writes linked to a checkpoint.

Delete all checkpoints and writes associated with a specific thread ID.

Define the configuration options for the checkpoint saver.

Define the configuration options for the checkpoint saver.

List of configuration field specs.

Create a new SqliteSaver instance from a connection string.

The SQLite connection string.

A new SqliteSaver instance.

Set up the checkpoint database.

This method creates the necessary tables in the SQLite database if they don't already exist. It is called automatically when needed and should not be called directly by the user.

Get a cursor for the SQLite database.

This method returns a cursor for the SQLite database. It is used internally by the SqliteSaver and should not be called directly by the user.

Whether to commit the transaction when the cursor is closed. Defaults to True.

sqlite3.Cursor: A cursor for the SQLite database.

Get a checkpoint tuple from the database.

This method retrieves a checkpoint tuple from the SQLite database based on the provided config. If the config contains a checkpoint_id key, the checkpoint with the matching thread ID and checkpoint ID is retrieved. Otherwise, the latest checkpoint for the given thread ID is retrieved.

The config to use for retrieving the checkpoint.

The retrieved checkpoint tuple, or None if no matching checkpoint was found.

List checkpoints from the database.

This method retrieves a list of checkpoint tuples from the SQLite database based on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

The config to use for listing the checkpoints.

Additional filtering criteria for metadata.

If provided, only checkpoints before the specified checkpoint ID are returned.

The maximum number of checkpoints to return.

An iterator of checkpoint tuples.

Save a checkpoint to the database.

This method saves a checkpoint to the SQLite database. The checkpoint is associated with the provided config and its parent config (if any).

The config to associate with the checkpoint.

The checkpoint to save.

Additional metadata to save with the checkpoint.

New channel versions as of this write.

Updated configuration after storing the checkpoint.

Store intermediate writes linked to a checkpoint.

This method saves intermediate writes associated with a checkpoint to the SQLite database.

Configuration of the related checkpoint.

List of writes to store, each as (channel, value) pair.

Identifier for the task creating the writes.

Path of the task creating the writes.

Delete all checkpoints and writes associated with a thread ID.

The thread ID to delete.

Get a checkpoint tuple from the database asynchronously.

This async method is not supported by the SqliteSaver class. Use get_tuple() instead, or consider using AsyncSqliteSaver.

List checkpoints from the database asynchronously.

This async method is not supported by the SqliteSaver class. Use list() instead, or consider using AsyncSqliteSaver.

Save a checkpoint to the database asynchronously.

This async method is not supported by the SqliteSaver class. Use put() instead, or consider using AsyncSqliteSaver.

Generate the next version ID for a channel.

This method creates a new version identifier for a channel based on its current version.

The current version identifier of the channel.

The next version identifier, which is guaranteed to be monotonically increasing.

Fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Asynchronously fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Asynchronously store intermediate writes linked to a checkpoint.

Configuration of the related checkpoint.

List of writes to store.

Identifier for the task creating the writes.

Path of the task creating the writes.

Implement this method in your custom checkpoint saver.

Delete all checkpoints and writes associated with a specific thread ID.

The thread ID whose checkpoints should be deleted.

An asynchronous checkpoint saver that stores checkpoints in a SQLite database.

Bases: BaseCheckpointSaver[str]

An asynchronous checkpoint saver that stores checkpoints in a SQLite database.

This class provides an asynchronous interface for saving and retrieving checkpoints using a SQLite database. It's designed for use in asynchronous environments and offers better performance for I/O-bound operations compared to synchronous alternatives.

The asynchronous SQLite database connection.

The serializer used for encoding/decoding checkpoints.

Requires the aiosqlite package. Install it with pip install aiosqlite.

While this class supports asynchronous checkpointing, it is not recommended for production workloads due to limitations in SQLite's write performance. For production use, consider a more robust database like PostgreSQL.

Remember to close the database connection after executing your code, otherwise, you may see the graph "hang" after execution (since the program will not exit until the connection is closed).

The easiest way is to use the async with statement as shown in the examples.

Usage within StateGraph:

>>> import asyncio >>> >>> from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver >>> from langgraph.graph import StateGraph >>> >>> async def main(): >>> builder = StateGraph(int) >>> builder.add_node("add_one", lambda x: x + 1) >>> builder.set_entry_point("add_one") >>> builder.set_finish_point("add_one") >>> async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as memory: >>> graph = builder.compile(checkpointer=memory) >>> coro = graph.ainvoke(1, {"configurable": {"thread_id": "thread-1"}}) >>> print(await asyncio.gather(coro)) >>> >>> asyncio.run(main()) Output: [2] Raw usage:

Create a new AsyncSqliteSaver instance from a connection string.

Get a checkpoint tuple from the database.

List checkpoints from the database asynchronously.

Save a checkpoint to the database.

Delete all checkpoints and writes associated with a thread ID.

Set up the checkpoint database asynchronously.

Get a checkpoint tuple from the database asynchronously.

List checkpoints from the database asynchronously.

Save a checkpoint to the database asynchronously.

Store intermediate writes linked to a checkpoint asynchronously.

Delete all checkpoints and writes associated with a thread ID.

Generate the next version ID for a channel.

Fetch a checkpoint using the given configuration.

Asynchronously fetch a checkpoint using the given configuration.

Define the configuration options for the checkpoint saver.

List of configuration field specs.

Create a new AsyncSqliteSaver instance from a connection string.

The SQLite connection string.

A new AsyncSqliteSaver instance.

Get a checkpoint tuple from the database.

This method retrieves a checkpoint tuple from the SQLite database based on the provided config. If the config contains a checkpoint_id key, the checkpoint with the matching thread ID and checkpoint ID is retrieved. Otherwise, the latest checkpoint for the given thread ID is retrieved.

The config to use for retrieving the checkpoint.

The retrieved checkpoint tuple, or None if no matching checkpoint was found.

List checkpoints from the database asynchronously.

This method retrieves a list of checkpoint tuples from the SQLite database based on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

Base configuration for filtering checkpoints.

Additional filtering criteria for metadata.

If provided, only checkpoints before the specified checkpoint ID are returned.

Maximum number of checkpoints to return.

An iterator of matching checkpoint tuples.

Save a checkpoint to the database.

This method saves a checkpoint to the SQLite database. The checkpoint is associated with the provided config and its parent config (if any).

The config to associate with the checkpoint.

The checkpoint to save.

Additional metadata to save with the checkpoint.

New channel versions as of this write.

Updated configuration after storing the checkpoint.

Delete all checkpoints and writes associated with a thread ID.

The thread ID to delete.

Set up the checkpoint database asynchronously.

This method creates the necessary tables in the SQLite database if they don't already exist. It is called automatically when needed and should not be called directly by the user.

Get a checkpoint tuple from the database asynchronously.

This method retrieves a checkpoint tuple from the SQLite database based on the provided config. If the config contains a checkpoint_id key, the checkpoint with the matching thread ID and checkpoint ID is retrieved. Otherwise, the latest checkpoint for the given thread ID is retrieved.

The config to use for retrieving the checkpoint.

The retrieved checkpoint tuple, or None if no matching checkpoint was found.

List checkpoints from the database asynchronously.

This method retrieves a list of checkpoint tuples from the SQLite database based on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

Base configuration for filtering checkpoints.

Additional filtering criteria for metadata.

If provided, only checkpoints before the specified checkpoint ID are returned.

Maximum number of checkpoints to return.

An asynchronous iterator of matching checkpoint tuples.

Save a checkpoint to the database asynchronously.

This method saves a checkpoint to the SQLite database. The checkpoint is associated with the provided config and its parent config (if any).

The config to associate with the checkpoint.

The checkpoint to save.

Additional metadata to save with the checkpoint.

New channel versions as of this write.

Updated configuration after storing the checkpoint.

Store intermediate writes linked to a checkpoint asynchronously.

This method saves intermediate writes associated with a checkpoint to the database.

Configuration of the related checkpoint.

List of writes to store, each as (channel, value) pair.

Identifier for the task creating the writes.

Path of the task creating the writes.

Delete all checkpoints and writes associated with a thread ID.

The thread ID to delete.

Generate the next version ID for a channel.

This method creates a new version identifier for a channel based on its current version.

The current version identifier of the channel.

The next version identifier, which is guaranteed to be monotonically increasing.

Fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Asynchronously fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Checkpointer that stores checkpoints in a Postgres database.

Bases: BasePostgresSaver

Checkpointer that stores checkpoints in a Postgres database.

Create a new PostgresSaver instance from a connection string.

Set up the checkpoint database asynchronously.

List checkpoints from the database.

Get a checkpoint tuple from the database.

Save a checkpoint to the database.

Store intermediate writes linked to a checkpoint.

Delete all checkpoints and writes associated with a thread ID.

Fetch a checkpoint using the given configuration.

Asynchronously fetch a checkpoint using the given configuration.

Asynchronously fetch a checkpoint tuple using the given configuration.

Asynchronously list checkpoints that match the given criteria.

Asynchronously store a checkpoint with its configuration and metadata.

Asynchronously store intermediate writes linked to a checkpoint.

Delete all checkpoints and writes associated with a specific thread ID.

Define the configuration options for the checkpoint saver.

Define the configuration options for the checkpoint saver.

List of configuration field specs.

Create a new PostgresSaver instance from a connection string.

The Postgres connection info string.

whether to use Pipeline

A new PostgresSaver instance.

Set up the checkpoint database asynchronously.

This method creates the necessary tables in the Postgres database if they don't already exist and runs database migrations. It MUST be called directly by the user the first time checkpointer is used.

List checkpoints from the database.

This method retrieves a list of checkpoint tuples from the Postgres database based on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

The config to use for listing the checkpoints.

Additional filtering criteria for metadata.

If provided, only checkpoints before the specified checkpoint ID are returned.

The maximum number of checkpoints to return.

An iterator of checkpoint tuples.

Get a checkpoint tuple from the database.

This method retrieves a checkpoint tuple from the Postgres database based on the provided config. If the config contains a checkpoint_id key, the checkpoint with the matching thread ID and timestamp is retrieved. Otherwise, the latest checkpoint for the given thread ID is retrieved.

The config to use for retrieving the checkpoint.

The retrieved checkpoint tuple, or None if no matching checkpoint was found.

Save a checkpoint to the database.

This method saves a checkpoint to the Postgres database. The checkpoint is associated with the provided config and its parent config (if any).

The config to associate with the checkpoint.

The checkpoint to save.

Additional metadata to save with the checkpoint.

New channel versions as of this write.

Updated configuration after storing the checkpoint.

Store intermediate writes linked to a checkpoint.

This method saves intermediate writes associated with a checkpoint to the Postgres database.

Configuration of the related checkpoint.

List of writes to store.

Identifier for the task creating the writes.

Delete all checkpoints and writes associated with a thread ID.

The thread ID to delete.

Fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Asynchronously fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Asynchronously fetch a checkpoint tuple using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint tuple, or None if not found.

Implement this method in your custom checkpoint saver.

Asynchronously list checkpoints that match the given criteria.

Base configuration for filtering checkpoints.

Additional filtering criteria for metadata.

List checkpoints created before this configuration.

Maximum number of checkpoints to return.

Async iterator of matching checkpoint tuples.

Implement this method in your custom checkpoint saver.

Asynchronously store a checkpoint with its configuration and metadata.

Configuration for the checkpoint.

The checkpoint to store.

Additional metadata for the checkpoint.

New channel versions as of this write.

Updated configuration after storing the checkpoint.

Implement this method in your custom checkpoint saver.

Asynchronously store intermediate writes linked to a checkpoint.

Configuration of the related checkpoint.

List of writes to store.

Identifier for the task creating the writes.

Path of the task creating the writes.

Implement this method in your custom checkpoint saver.

Delete all checkpoints and writes associated with a specific thread ID.

The thread ID whose checkpoints should be deleted.

Asynchronous checkpointer that stores checkpoints in a Postgres database.

Bases: BasePostgresSaver

Asynchronous checkpointer that stores checkpoints in a Postgres database.

Create a new AsyncPostgresSaver instance from a connection string.

Set up the checkpoint database asynchronously.

List checkpoints from the database asynchronously.

Get a checkpoint tuple from the database asynchronously.

Save a checkpoint to the database asynchronously.

Store intermediate writes linked to a checkpoint asynchronously.

Delete all checkpoints and writes associated with a thread ID.

List checkpoints from the database.

Get a checkpoint tuple from the database.

Save a checkpoint to the database.

Store intermediate writes linked to a checkpoint.

Delete all checkpoints and writes associated with a thread ID.

Fetch a checkpoint using the given configuration.

Asynchronously fetch a checkpoint using the given configuration.

Define the configuration options for the checkpoint saver.

Define the configuration options for the checkpoint saver.

List of configuration field specs.

Create a new AsyncPostgresSaver instance from a connection string.

The Postgres connection info string.

whether to use AsyncPipeline

A new AsyncPostgresSaver instance.

Set up the checkpoint database asynchronously.

This method creates the necessary tables in the Postgres database if they don't already exist and runs database migrations. It MUST be called directly by the user the first time checkpointer is used.

List checkpoints from the database asynchronously.

This method retrieves a list of checkpoint tuples from the Postgres database based on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

Base configuration for filtering checkpoints.

Additional filtering criteria for metadata.

If provided, only checkpoints before the specified checkpoint ID are returned.

Maximum number of checkpoints to return.

An asynchronous iterator of matching checkpoint tuples.

Get a checkpoint tuple from the database asynchronously.

This method retrieves a checkpoint tuple from the Postgres database based on the provided config. If the config contains a checkpoint_id key, the checkpoint with the matching thread ID and "checkpoint_id" is retrieved. Otherwise, the latest checkpoint for the given thread ID is retrieved.

The config to use for retrieving the checkpoint.

The retrieved checkpoint tuple, or None if no matching checkpoint was found.

Save a checkpoint to the database asynchronously.

This method saves a checkpoint to the Postgres database. The checkpoint is associated with the provided config and its parent config (if any).

The config to associate with the checkpoint.

The checkpoint to save.

Additional metadata to save with the checkpoint.

New channel versions as of this write.

Updated configuration after storing the checkpoint.

Store intermediate writes linked to a checkpoint asynchronously.

This method saves intermediate writes associated with a checkpoint to the database.

Configuration of the related checkpoint.

List of writes to store, each as (channel, value) pair.

Identifier for the task creating the writes.

Delete all checkpoints and writes associated with a thread ID.

The thread ID to delete.

List checkpoints from the database.

This method retrieves a list of checkpoint tuples from the Postgres database based on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

Base configuration for filtering checkpoints.

Additional filtering criteria for metadata.

If provided, only checkpoints before the specified checkpoint ID are returned.

Maximum number of checkpoints to return.

An iterator of matching checkpoint tuples.

Get a checkpoint tuple from the database.

This method retrieves a checkpoint tuple from the Postgres database based on the provided config. If the config contains a checkpoint_id key, the checkpoint with the matching thread ID and "checkpoint_id" is retrieved. Otherwise, the latest checkpoint for the given thread ID is retrieved.

The config to use for retrieving the checkpoint.

The retrieved checkpoint tuple, or None if no matching checkpoint was found.

Save a checkpoint to the database.

This method saves a checkpoint to the Postgres database. The checkpoint is associated with the provided config and its parent config (if any).

The config to associate with the checkpoint.

The checkpoint to save.

Additional metadata to save with the checkpoint.

New channel versions as of this write.

Updated configuration after storing the checkpoint.

Store intermediate writes linked to a checkpoint.

This method saves intermediate writes associated with a checkpoint to the database.

Configuration of the related checkpoint.

List of writes to store, each as (channel, value) pair.

Identifier for the task creating the writes.

Path of the task creating the writes.

Delete all checkpoints and writes associated with a thread ID.

The thread ID to delete.

Fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

Asynchronously fetch a checkpoint using the given configuration.

Configuration specifying which checkpoint to retrieve.

The requested checkpoint, or None if not found.

**Examples:**

Example 1 (unknown):
```unknown
source: Literal['input', 'loop', 'update', 'fork']
```

Example 2 (unknown):
```unknown
parents: dict[str, str]
```

Example 3 (unknown):
```unknown
channel_values: dict[str, Any]
```

Example 4 (unknown):
```unknown
channel_versions: ChannelVersions
```

---

## How to add cross-thread persistence (functional API)¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/cross-thread-persistence-functional

**Contents:**
- How to add cross-thread persistence (functional API)¶
- Setup¶
- Example: simple chatbot with long-term memory¶
  - Define store¶
  - Create workflow¶
  - Run the workflow!¶

This guide assumes familiarity with the following:

LangGraph allows you to persist data across different threads. For instance, you can store information about users (their names or preferences) in a shared (cross-thread) memory and reuse them in the new threads (e.g., new conversations).

When using the functional API, you can set it up to store and retrieve memories by using the Store interface:

Create an instance of a Store

Pass the store instance to the entrypoint() decorator and expose store parameter in the function signature:

In this guide, we will show how to construct and use a workflow that has a shared memory implemented using the Store interface.

Support for the Store API that is used in this guide was added in LangGraph v0.2.32.

Support for index and query arguments of the Store API that is used in this guide was added in LangGraph v0.2.54.

If you need to add cross-thread persistence to a StateGraph, check out this how-to guide.

First, let's install the required packages and set our API keys

Set up LangSmith for LangGraph development

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started here

In this example we will create a workflow that will be able to retrieve information about a user's preferences. We will do so by defining an InMemoryStore - an object that can store data in memory and query that data.

When storing objects using the Store interface you define two things:

In our example, we'll be using ("memories", <user_id>) as namespace and random UUID as key for each new memory.

Importantly, to determine the user, we will be passing user_id via the config keyword argument of the node function.

Let's first define our store!

API Reference: OpenAIEmbeddings

API Reference: ChatAnthropic | RunnableConfig | BaseMessage | entrypoint | task | add_messages | InMemorySaver

If you're using LangGraph Cloud or LangGraph Studio, you don't need to pass store to the entrypoint decorator, since it's done automatically.

Now let's specify a user ID in the config and tell the model our name:

config = {"configurable": {"thread_id": "1", "user_id": "1"}} input_message = {"role": "user", "content": "Hi! Remember: my name is Bob"} for chunk in workflow.stream([input_message], config, stream_mode="values"): chunk.pretty_print() ================================== Ai Message ================================== Hello Bob! Nice to meet you. I'll remember that your name is Bob. How can I help you today?

config = {"configurable": {"thread_id": "2", "user_id": "1"}} input_message = {"role": "user", "content": "what is my name?"} for chunk in workflow.stream([input_message], config, stream_mode="values"): chunk.pretty_print() ================================== Ai Message ================================== Your name is Bob. We can now inspect our in-memory store and verify that we have in fact saved the memories for the user:

for memory in in_memory_store.search(("memories", "1")): print(memory.value) {'data': 'User name is Bob'} Let's now run the workflow for another user to verify that the memories about the first user are self contained:

config = {"configurable": {"thread_id": "3", "user_id": "2"}} input_message = {"role": "user", "content": "what is my name?"} for chunk in workflow.stream([input_message], config, stream_mode="values"): chunk.pretty_print() ================================== Ai Message ================================== I don't have any information about your name. I can only see our current conversation without any prior context or personal details about you. If you'd like me to know your name, feel free to tell me!

**Examples:**

Example 1 (python):
```python
from langgraph.store.memory import InMemoryStore, BaseStore

store = InMemoryStore()
```

Example 2 (python):
```python
from langgraph.func import entrypoint

@entrypoint(store=store)
def workflow(inputs: dict, store: BaseStore):
    my_task(inputs).result()
    ...
```

Example 3 (unknown):
```unknown
pip install -U langchain_anthropic langchain_openai langgraph
```

Example 4 (python):
```python
import getpass
import os


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("ANTHROPIC_API_KEY")
_set_env("OPENAI_API_KEY")
```

---

## Enable human intervention¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/add-human-in-the-loop/

**Contents:**
- Enable human intervention¶
- Pause using interrupt¶
- Resume using the Command primitive¶
  - Resume multiple interrupts with one invocation¶
- Common patterns¶
  - Approve or reject¶
  - Review and edit state¶
  - Review tool calls¶
  - Add interrupts to any tool¶
  - Validate human input¶

To review, edit, and approve tool calls in an agent or workflow, use interrupts to pause a graph and wait for human input. Interrupts use LangGraph's persistence layer, which saves the graph state, to indefinitely pause graph execution until you resume.

For more information about human-in-the-loop workflows, see the Human-in-the-Loop conceptual guide.

Dynamic interrupts (also known as dynamic breakpoints) are triggered based on the current state of the graph. You can set dynamic interrupts by calling interrupt function in the appropriate place. The graph will pause, which allows for human intervention, and then resumes the graph with their input. It's useful for tasks like approvals, edits, or gathering additional context.

As of v1.0, interrupt is the recommended way to pause a graph. NodeInterrupt is deprecated and will be removed in v2.0.

To use interrupt in your graph, you need to:

API Reference: interrupt | Command

__interrupt__ is a special key that will be returned when running the graph if the graph is interrupted. Support for __interrupt__ in invoke and ainvoke has been added in version 0.4.0. If you're on an older version, you will only see __interrupt__ in the result if you use stream or astream. You can also use graph.get_state(thread_id) to get the interrupt value(s).

Interrupts resemble Python's input() function in terms of developer experience, but they do not automatically resume execution from the interruption point. Instead, they rerun the entire node where the interrupt was used. For this reason, interrupts are typically best placed at the start of a node or in a dedicated node.

Resuming from an interrupt is different from Python's input() function, where execution resumes from the exact point where the input() function was called.

When the interrupt function is used within a graph, execution pauses at that point and awaits user input.

To resume execution, use the Command primitive, which can be supplied via the invoke or stream methods. The graph resumes execution from the beginning of the node where interrupt(...) was initially called. This time, the interrupt function will return the value provided in Command(resume=value) rather than pausing again. All code from the beginning of the node to the interrupt will be re-executed.

When nodes with interrupt conditions are run in parallel, it's possible to have multiple interrupts in the task queue. For example, the following graph has two nodes run in parallel that require human input:

Once your graph has been interrupted and is stalled, you can resume all the interrupts at once with Command.resume, passing a dictionary mapping of interrupt ids to resume values.

API Reference: RunnableConfig | InMemorySaver | START | StateGraph | interrupt | Command

Below we show different design patterns that can be implemented using interrupt and Command.

Pause the graph before a critical step, such as an API call, to review and approve the action. If the action is rejected, you can prevent the graph from executing the step, and potentially take an alternative action.

API Reference: interrupt | Command

API Reference: interrupt

To add a human approval step to a tool:

API Reference: InMemorySaver | interrupt | create_react_agent

Run the agent with the stream() method, passing the config object to specify the thread ID. This allows the agent to resume the same conversation on future invocations.

You should see that the agent runs until it reaches the interrupt() call, at which point it pauses and waits for human input.

Resume the agent with a Command to continue based on human input.

API Reference: Command

You can create a wrapper to add interrupts to any tool. The example below provides a reference implementation compatible with Agent Inbox UI and Agent Chat UI.

You can use the wrapper to add interrupt() to any tool without having to add it inside the tool:

API Reference: InMemorySaver | create_react_agent

You should see that the agent runs until it reaches the interrupt() call, at which point it pauses and waits for human input.

Resume the agent with a Command to continue based on human input.

API Reference: Command

If you need to validate the input provided by the human within the graph itself (rather than on the client side), you can achieve this by using multiple interrupt calls within a single node.

API Reference: interrupt

To debug and test a graph, use static interrupts (also known as static breakpoints) to step through the graph execution one node at a time or to pause the graph execution at specific nodes. Static interrupts are triggered at defined points either before or after a node executes. You can set static interrupts by specifying interrupt_before and interrupt_after at compile time or run time.

Static interrupts are not recommended for human-in-the-loop workflows. Use dynamic interrupts instead.

You cannot set static breakpoints at runtime for sub-graphs. If you have a sub-graph, you must set the breakpoints at compilation time.

You can use LangGraph Studio to debug your graph. You can set static breakpoints in the UI and then run the graph. You can also use the UI to inspect the graph state at any point in the execution.

LangGraph Studio is free with locally deployed applications using langgraph dev.

To debug and test a graph, use static interrupts (also known as static breakpoints) to step through the graph execution one node at a time or to pause the graph execution at specific nodes. Static interrupts are triggered at defined points either before or after a node executes. You can set static interrupts by specifying interrupt_before and interrupt_after at compile time or run time.

Static interrupts are not recommended for human-in-the-loop workflows. Use dynamic interrupts instead.

You cannot set static breakpoints at runtime for sub-graphs. If you have a sub-graph, you must set the breakpoints at compilation time.

You can use LangGraph Studio to debug your graph. You can set static breakpoints in the UI and then run the graph. You can also use the UI to inspect the graph state at any point in the execution.

LangGraph Studio is free with locally deployed applications using langgraph dev.

When using human-in-the-loop, there are some considerations to keep in mind.

Place code with side effects, such as API calls, after the interrupt or in a separate node to avoid duplication, as these are re-triggered every time the node is resumed.

When invoking a subgraph as a function, the parent graph will resume execution from the beginning of the node where the subgraph was invoked where the interrupt was triggered. Similarly, the subgraph will resume from the beginning of the node where the interrupt() function was called.

Say we have a parent graph with 3 nodes:

Parent Graph: node_1 → node_2 (subgraph call) → node_3

And the subgraph has 3 nodes, where the second node contains an interrupt:

Subgraph: sub_node_1 → sub_node_2 (interrupt) → sub_node_3

When resuming the graph, the execution will proceed as follows:

Here is abbreviated example code that you can use to understand how subgraphs work with interrupts. It counts the number of times each node is entered and prints the count.

Using multiple interrupts within a single node can be helpful for patterns like validating human input. However, using multiple interrupts in the same node can lead to unexpected behavior if not handled carefully.

When a node contains multiple interrupt calls, LangGraph keeps a list of resume values specific to the task executing the node. Whenever execution resumes, it starts at the beginning of the node. For each interrupt encountered, LangGraph checks if a matching value exists in the task's resume list. Matching is strictly index-based, so the order of interrupt calls within the node is critical.

To avoid issues, refrain from dynamically changing the node's structure between executions. This includes adding, removing, or reordering interrupt calls, as such changes can result in mismatched indices. These problems often arise from unconventional patterns, such as mutating state via Command(resume=..., update=SOME_STATE_MUTATION) or relying on global variables to modify the node's structure dynamically.

**Examples:**

Example 1 (python):
```python
from langgraph.types import interrupt, Command

def human_node(state: State):
    value = interrupt( # (1)!
        {
            "text_to_revise": state["some_text"] # (2)!
        }
    )
    return {
        "some_text": value # (3)!
    }


graph = graph_builder.compile(checkpointer=checkpointer) # (4)!

# Run the graph until the interrupt is hit.
config = {"configurable": {"thread_id": "some_id"}}
result = graph.invoke({"some_text": "original text"}, config=config) # (5)!
print(result['__interrupt__']) # (6)!
# > [
# >    Interrupt(
# >       value={'text_to_revise': 'original text'},
# >       resumable=True,
# >       ns=['human_node:6ce9e64f-edef-fe5d-f7dc-511fa9526960']
# >    )
# > ]

print(graph.invoke(Command(resume="Edited text"), config=config)) # (7)!
# > {'some_text': 'Edited text'}
```

Example 2 (python):
```python
from typing import TypedDict
import uuid
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import START
from langgraph.graph import StateGraph

from langgraph.types import interrupt, Command


class State(TypedDict):
    some_text: str


def human_node(state: State):
    value = interrupt(  # (1)!
        {
            "text_to_revise": state["some_text"]  # (2)!
        }
    )
    return {
        "some_text": value  # (3)!
    }


# Build the graph
graph_builder = StateGraph(State)
graph_builder.add_node("human_node", human_node)
graph_builder.add_edge(START, "human_node")
checkpointer = InMemorySaver()  # (4)!
graph = graph_builder.compile(checkpointer=checkpointer)
# Pass a thread ID to the graph to run it.
config = {"configurable": {"thread_id": uuid.uuid4()}}
# Run the graph until the interrupt is hit.
result = graph.invoke({"some_text": "original text"}, config=config)  # (5)!

print(result['__interrupt__']) # (6)!
# > [
# >    Interrupt(
# >       value={'text_to_revise': 'original text'},
# >       resumable=True,
# >       ns=['human_node:6ce9e64f-edef-fe5d-f7dc-511fa9526960']
# >    )
# > ]
print(result["__interrupt__"])  # (6)!
# > [Interrupt(value={'text_to_revise': 'original text'}, id='6d7c4048049254c83195429a3659661d')]

print(graph.invoke(Command(resume="Edited text"), config=config)) # (7)!
# > {'some_text': 'Edited text'}
```

Example 3 (unknown):
```unknown
# Resume graph execution by providing the user's input.
graph.invoke(Command(resume={"age": "25"}), thread_config)
```

Example 4 (python):
```python
from typing import TypedDict
import uuid
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import START
from langgraph.graph import StateGraph
from langgraph.types import interrupt, Command


class State(TypedDict):
    text_1: str
    text_2: str


def human_node_1(state: State):
    value = interrupt({"text_to_revise": state["text_1"]})
    return {"text_1": value}


def human_node_2(state: State):
    value = interrupt({"text_to_revise": state["text_2"]})
    return {"text_2": value}


graph_builder = StateGraph(State)
graph_builder.add_node("human_node_1", human_node_1)
graph_builder.add_node("human_node_2", human_node_2)

# Add both nodes in parallel from START
graph_builder.add_edge(START, "human_node_1")
graph_builder.add_edge(START, "human_node_2")

checkpointer = InMemorySaver()
graph = graph_builder.compile(checkpointer=checkpointer)

thread_id = str(uuid.uuid4())
config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
result = graph.invoke(
    {"text_1": "original text 1", "text_2": "original text 2"}, config=config
)

# Resume with mapping of interrupt IDs to values
resume_map = {
    i.id: f"edited text for {i.value['text_to_revise']}"
    for i in graph.get_state(config).interrupts
}
print(graph.invoke(Command(resume=resume_map), config=config))
# > {'text_1': 'edited text for original text 1', 'text_2': 'edited text for original text 2'}
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/how-tos/persistence

---

## Graph Definitions¶

**URL:** https://langchain-ai.github.io/langgraph/reference/graphs/

**Contents:**
- Graph Definitions¶
- StateGraph ¶
  - add_node ¶
  - add_edge ¶
  - add_conditional_edges ¶
  - add_sequence ¶
  - compile ¶
- CompiledStateGraph ¶
  - stream ¶
  - astream async ¶

Bases: Generic[StateT, ContextT, InputT, OutputT]

A graph whose nodes communicate by reading and writing to a shared state. The signature of each node is State -> Partial.

Each state key can optionally be annotated with a reducer function that will be used to aggregate the values of that key received from multiple nodes. The signature of a reducer function is (Value, Value) -> Value.

The schema class that defines the state.

The schema class that defines the runtime context. Use this to expose immutable context data to your nodes, like user_id, db_conn, etc.

The schema class that defines the input to the graph.

The schema class that defines the output from the graph.

config_schema Deprecated

The config_schema parameter is deprecated in v0.6.0 and support will be removed in v2.0.0. Please use context_schema instead to specify the schema for run-scoped context.

Add a new node to the state graph.

Add a directed edge from the start node (or list of start nodes) to the end node.

Add a conditional edge from the starting node to any number of destination nodes.

Add a sequence of nodes that will be executed in the provided order.

Compiles the state graph into a CompiledStateGraph object.

Add a new node to the state graph.

The function or runnable this node will run. If a string is provided, it will be used as the node name, and action will be used as the function or runnable.

The action associated with the node. Will be used as the node function or runnable if node is a string (node name).

Whether to defer the execution of the node until the run is about to end.

The metadata associated with the node.

The input schema for the node. (default: the graph's state schema)

The retry policy for the node. If a sequence is provided, the first matching policy will be applied.

The cache policy for the node.

Destinations that indicate where a node can route to. This is useful for edgeless graphs with nodes that return Command objects. If a dict is provided, the keys will be used as the target node names and the values will be used as the labels for the edges. If a tuple is provided, the values will be used as the target node names.

This is only used for graph rendering and doesn't have any effect on the graph execution.

The instance of the state graph, allowing for method chaining.

Add a directed edge from the start node (or list of start nodes) to the end node.

When a single start node is provided, the graph will wait for that node to complete before executing the end node. When multiple start nodes are provided, the graph will wait for ALL of the start nodes to complete before executing the end node.

The key(s) of the start node(s) of the edge.

The key of the end node of the edge.

If the start key is 'END' or if the start key or end key is not present in the graph.

The instance of the state graph, allowing for method chaining.

Add a conditional edge from the starting node to any number of destination nodes.

The starting node. This conditional edge will run when exiting this node.

The callable that determines the next node or nodes. If not specifying path_map it should return one or more nodes. If it returns 'END', the graph will stop execution.

Optional mapping of paths to node names. If omitted the paths returned by path should be node names.

The instance of the graph, allowing for method chaining.

Without type hints on the path function's return value (e.g., -> Literal["foo", "__end__"]:) or a path_map, the graph visualization assumes the edge could transition to any node in the graph.

Add a sequence of nodes that will be executed in the provided order.

A sequence of StateNode (callables that accept a state arg) or (name, StateNode) tuples. If no names are provided, the name will be inferred from the node object (e.g. a Runnable or a Callable name). Each node will be executed in the order provided.

If the sequence is empty.

If the sequence contains duplicate node names.

The instance of the state graph, allowing for method chaining.

Compiles the state graph into a CompiledStateGraph object.

The compiled graph implements the Runnable interface and can be invoked, streamed, batched, and run asynchronously.

A checkpoint saver object or flag. If provided, this Checkpointer serves as a fully versioned "short-term memory" for the graph, allowing it to be paused, resumed, and replayed from any point. If None, it may inherit the parent graph's checkpointer when used as a subgraph. If False, it will not use or inherit any checkpointer.

An optional list of node names to interrupt before.

An optional list of node names to interrupt after.

A flag indicating whether to enable debug mode.

The name to use for the compiled graph.

The compiled state graph.

Bases: Pregel[StateT, ContextT, InputT, OutputT], Generic[StateT, ContextT, InputT, OutputT]

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

Merges two lists of messages, updating existing messages by ID.

Merges two lists of messages, updating existing messages by ID.

By default, this ensures the state is "append-only", unless the new message has the same ID as an existing message.

The base list of Messages.

The list of Messages (or single Message) to merge into the base list.

The format to return messages in. If None then Messages will be returned as is. If langchain-openai then Messages will be returned as BaseMessage objects with their contents formatted to match OpenAI message format, meaning contents can be string, 'text' blocks, or 'image_url' blocks and tool responses are returned as their own ToolMessage objects.

Must have langchain-core>=0.3.11 installed to use this feature.

A new list of messages with the messages from right merged into left.

If a message in right has the same ID as a message in left, the message from right will replace the message from left.

**Examples:**

Example 1 (python):
```python
from langchain_core.runnables import RunnableConfig
from typing_extensions import Annotated, TypedDict
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime


def reducer(a: list, b: int | None) -> list:
    if b is not None:
        return a + [b]
    return a


class State(TypedDict):
    x: Annotated[list, reducer]


class Context(TypedDict):
    r: float


graph = StateGraph(state_schema=State, context_schema=Context)


def node(state: State, runtime: Runtime[Context]) -> dict:
    r = runtime.context.get("r", 1.0)
    x = state["x"][-1]
    next_value = x * r * (1 - x)
    return {"x": next_value}


graph.add_node("A", node)
graph.set_entry_point("A")
graph.set_finish_point("A")
compiled = graph.compile()

step1 = compiled.invoke({"x": 0.5}, context={"r": 3.0})
# {'x': [0.5, 0.75]}
```

Example 2 (unknown):
```unknown
add_node(
    node: str | StateNode[NodeInputT, ContextT],
    action: StateNode[NodeInputT, ContextT] | None = None,
    *,
    defer: bool = False,
    metadata: dict[str, Any] | None = None,
    input_schema: type[NodeInputT] | None = None,
    retry_policy: (
        RetryPolicy | Sequence[RetryPolicy] | None
    ) = None,
    cache_policy: CachePolicy | None = None,
    destinations: (
        dict[str, str] | tuple[str, ...] | None
    ) = None,
    **kwargs: Unpack[DeprecatedKwargs]
) -> Self
```

Example 3 (python):
```python
from typing_extensions import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, StateGraph


class State(TypedDict):
    x: int


def my_node(state: State, config: RunnableConfig) -> State:
    return {"x": state["x"] + 1}


builder = StateGraph(State)
builder.add_node(my_node)  # node name will be 'my_node'
builder.add_edge(START, "my_node")
graph = builder.compile()
graph.invoke({"x": 1})
# {'x': 2}
```

Example 4 (unknown):
```unknown
builder = StateGraph(State)
builder.add_node("my_fair_node", my_node)
builder.add_edge(START, "my_fair_node")
graph = builder.compile()
graph.invoke({"x": 1})
# {'x': 2}
```

---

## 

**URL:** https://langchain-ai.github.io/langgraph/how-tos/cross-thread-persistence

---

## How to add thread-level persistence (functional API)¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/persistence-functional/

**Contents:**
- How to add thread-level persistence (functional API)¶
- Setup¶
- Example: simple chatbot with short-term memory¶

This guide assumes familiarity with the following:

Not needed for LangGraph API users

If you're using the LangGraph API, you needn't manually implement a checkpointer. The API automatically handles checkpointing for you. This guide is relevant when implementing LangGraph in your own custom server.

Many AI applications need memory to share context across multiple interactions on the same thread (e.g., multiple turns of a conversation). In LangGraph functional API, this kind of memory can be added to any entrypoint() workflow using thread-level persistence.

When creating a LangGraph workflow, you can set it up to persist its results by using a checkpointer:

Create an instance of a checkpointer:

Pass checkpointer instance to the entrypoint() decorator:

Optionally expose previous parameter in the workflow function signature:

Optionally choose which values will be returned from the workflow and which will be saved by the checkpointer as previous:

This guide shows how you can add thread-level persistence to your workflow.

If you need memory that is shared across multiple conversations or users (cross-thread persistence), check out this how-to guide.

If you need to add thread-level persistence to a StateGraph, check out this how-to guide.

First we need to install the packages required

Next, we need to set API key for Anthropic (the LLM we will use).

Set up LangSmith for LangGraph development

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started here.

We will be using a workflow with a single task that calls a chat model.

Let's first define the model we'll be using:

API Reference: ChatAnthropic

Now we can define our task and workflow. To add in persistence, we need to pass in a Checkpointer to the entrypoint() decorator.

API Reference: BaseMessage | add_messages | entrypoint | task | InMemorySaver

If we try to use this workflow, the context of the conversation will be persisted across interactions:

If you're using LangGraph Platform or LangGraph Studio, you don't need to pass checkpointer to the entrypoint decorator, since it's done automatically.

We can now interact with the agent and see that it remembers previous messages!

config = {"configurable": {"thread_id": "1"}} input_message = {"role": "user", "content": "hi! I'm bob"} for chunk in workflow.stream([input_message], config, stream_mode="values"): chunk.pretty_print() ================================== Ai Message ================================== Hi Bob! I'm Claude. Nice to meet you! How are you today? You can always resume previous threads:

input_message = {"role": "user", "content": "what's my name?"} for chunk in workflow.stream([input_message], config, stream_mode="values"): chunk.pretty_print() ================================== Ai Message ================================== Your name is Bob. If we want to start a new conversation, we can pass in a different thread_id. Poof! All the memories are gone!

input_message = {"role": "user", "content": "what's my name?"} for chunk in workflow.stream( [input_message], {"configurable": {"thread_id": "2"}}, stream_mode="values", ): chunk.pretty_print() ================================== Ai Message ================================== I don't know your name unless you tell me. Each conversation I have starts fresh, so I don't have access to any previous interactions or personal information unless you share it with me.

If you would like to stream LLM tokens from your chatbot, you can use stream_mode="messages". Check out this how-to guide to learn more.

**Examples:**

Example 1 (python):
```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
```

Example 2 (python):
```python
from langgraph.func import entrypoint

@entrypoint(checkpointer=checkpointer)
def workflow(inputs)
    ...
```

Example 3 (python):
```python
@entrypoint(checkpointer=checkpointer)
def workflow(
    inputs,
    *,
    # you can optionally specify `previous` in the workflow function signature
    # to access the return value from the workflow as of the last execution
    previous
):
    previous = previous or []
    combined_inputs = previous + inputs
    result = do_something(combined_inputs)
    ...
```

Example 4 (python):
```python
@entrypoint(checkpointer=checkpointer)
def workflow(inputs, *, previous):
    ...
    result = do_something(...)
    return entrypoint.final(value=result, save=combine(inputs, result))
```

---

## Customize state¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/get-started/5-customize-state/

**Contents:**
- Customize state¶
- 1. Add keys to the state¶
- 2. Update the state inside the tool¶
- 3. Prompt the chatbot¶
- 4. Add human assistance¶
- 5. Manually update the state¶
- 6. View the new value¶
- Next steps¶

In this tutorial, you will add additional fields to the state to define complex behavior without relying on the message list. The chatbot will use its search tool to find specific information and forward them to a human for review.

This tutorial builds on Add human-in-the-loop controls.

Update the chatbot to research the birthday of an entity by adding name and birthday keys to the state:

API Reference: add_messages

Adding this information to the state makes it easily accessible by other graph nodes (like a downstream node that stores or processes the information), as well as the graph's persistence layer.

Now, populate the state keys inside of the human_assistance tool. This allows a human to review the information before it is stored in the state. Use Command to issue a state update from inside the tool.

API Reference: ToolMessage | InjectedToolCallId | tool | Command | interrupt

The rest of the graph stays the same.

Prompt the chatbot to look up the "birthday" of the LangGraph library and direct the chatbot to reach out to the human_assistance tool once it has the required information. By setting name and birthday in the arguments for the tool, you force the chatbot to generate proposals for these fields.

We've hit the interrupt in the human_assistance tool again.

The chatbot failed to identify the correct date, so supply it with information:

Note that these fields are now reflected in the state:

This makes them easily accessible to downstream nodes (e.g., a node that further processes or stores the information).

LangGraph gives a high degree of control over the application state. For instance, at any point (including when interrupted), you can manually override a key using graph.update_state:

If you call graph.get_state, you can see the new value is reflected:

Manual state updates will generate a trace in LangSmith. If desired, they can also be used to control human-in-the-loop workflows. Use of the interrupt function is generally recommended instead, as it allows data to be transmitted in a human-in-the-loop interaction independently of state updates.

Congratulations! You've added custom keys to the state to facilitate a more complex workflow, and learned how to generate state updates from inside tools.

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

API Reference: TavilySearch | ToolMessage | InjectedToolCallId | tool | InMemorySaver | StateGraph | START | END | add_messages | ToolNode | tools_condition | Command | interrupt

There's one more concept to review before finishing the LangGraph basics tutorials: connecting checkpointing and state updates to time travel.

**Examples:**

Example 1 (python):
```python
from typing import Annotated

from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]
    name: str
    birthday: str
```

Example 2 (python):
```python
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool

from langgraph.types import Command, interrupt

@tool
# Note that because we are generating a ToolMessage for a state update, we
# generally require the ID of the corresponding tool call. We can use
# LangChain's InjectedToolCallId to signal that this argument should not
# be revealed to the model in the tool's schema.
def human_assistance(
    name: str, birthday: str, tool_call_id: Annotated[str, InjectedToolCallId]
) -> str:
    """Request assistance from a human."""
    human_response = interrupt(
        {
            "question": "Is this correct?",
            "name": name,
            "birthday": birthday,
        },
    )
    # If the information is correct, update the state as-is.
    if human_response.get("correct", "").lower().startswith("y"):
        verified_name = name
        verified_birthday = birthday
        response = "Correct"
    # Otherwise, receive information from the human reviewer.
    else:
        verified_name = human_response.get("name", name)
        verified_birthday = human_response.get("birthday", birthday)
        response = f"Made a correction: {human_response}"

    # This time we explicitly update the state with a ToolMessage inside
    # the tool.
    state_update = {
        "name": verified_name,
        "birthday": verified_birthday,
        "messages": [ToolMessage(response, tool_call_id=tool_call_id)],
    }
    # We return a Command object in the tool to update our state.
    return Command(update=state_update)
```

Example 3 (unknown):
```unknown
user_input = (
    "Can you look up when LangGraph was released? "
    "When you have the answer, use the human_assistance tool for review."
)
config = {"configurable": {"thread_id": "1"}}

events = graph.stream(
    {"messages": [{"role": "user", "content": user_input}]},
    config,
    stream_mode="values",
)
for event in events:
    if "messages" in event:
        event["messages"][-1].pretty_print()
```

Example 4 (unknown):
```unknown
================================ Human Message =================================

Can you look up when LangGraph was released? When you have the answer, use the human_assistance tool for review.
================================== Ai Message ==================================

[{'text': "Certainly! I'll start by searching for information about LangGraph's release date using the Tavily search function. Then, I'll use the human_assistance tool for review.", 'type': 'text'}, {'id': 'toolu_01JoXQPgTVJXiuma8xMVwqAi', 'input': {'query': 'LangGraph release date'}, 'name': 'tavily_search_results_json', 'type': 'tool_use'}]
Tool Calls:
  tavily_search_results_json (toolu_01JoXQPgTVJXiuma8xMVwqAi)
 Call ID: toolu_01JoXQPgTVJXiuma8xMVwqAi
  Args:
    query: LangGraph release date
================================= Tool Message =================================
Name: tavily_search_results_json

[{"url": "https://blog.langchain.dev/langgraph-cloud/", "content": "We also have a new stable release of LangGraph. By LangChain 6 min read Jun 27, 2024 (Oct '24) Edit: Since the launch of LangGraph Platform, we now have multiple deployment options alongside LangGraph Studio - which now fall under LangGraph Platform. LangGraph Platform is synonymous with our Cloud SaaS deployment option."}, {"url": "https://changelog.langchain.com/announcements/langgraph-cloud-deploy-at-scale-monitor-carefully-iterate-boldly", "content": "LangChain - Changelog | ☁ 🚀 LangGraph Platform: Deploy at scale, monitor LangChain LangSmith LangGraph LangChain LangSmith LangGraph LangChain LangSmith LangGraph LangChain Changelog Sign up for our newsletter to stay up to date DATE: The LangChain Team LangGraph LangGraph Platform ☁ 🚀 LangGraph Platform: Deploy at scale, monitor carefully, iterate boldly DATE: June 27, 2024 AUTHOR: The LangChain Team LangGraph Platform is now in closed beta, offering scalable, fault-tolerant deployment for LangGraph agents. LangGraph Platform also includes a new playground-like studio for debugging agent failure modes and quick iteration: Join the waitlist today for LangGraph Platform. And to learn more, read our blog post announcement or check out our docs. Subscribe By clicking subscribe, you accept our privacy policy and terms and conditions."}]
================================== Ai Message ==================================

[{'text': "Based on the search results, it appears that LangGraph was already in existence before June 27, 2024, when LangGraph Platform was announced. However, the search results don't provide a specific release date for the original LangGraph. \n\nGiven this information, I'll use the human_assistance tool to review and potentially provide more accurate information about LangGraph's initial release date.", 'type': 'text'}, {'id': 'toolu_01JDQAV7nPqMkHHhNs3j3XoN', 'input': {'name': 'Assistant', 'birthday': '2023-01-01'}, 'name': 'human_assistance', 'type': 'tool_use'}]
Tool Calls:
  human_assistance (toolu_01JDQAV7nPqMkHHhNs3j3XoN)
 Call ID: toolu_01JDQAV7nPqMkHHhNs3j3XoN
  Args:
    name: Assistant
    birthday: 2023-01-01
```

---

## How to add cross-thread persistence (functional API)¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/cross-thread-persistence-functional/

**Contents:**
- How to add cross-thread persistence (functional API)¶
- Setup¶
- Example: simple chatbot with long-term memory¶
  - Define store¶
  - Create workflow¶
  - Run the workflow!¶

This guide assumes familiarity with the following:

LangGraph allows you to persist data across different threads. For instance, you can store information about users (their names or preferences) in a shared (cross-thread) memory and reuse them in the new threads (e.g., new conversations).

When using the functional API, you can set it up to store and retrieve memories by using the Store interface:

Create an instance of a Store

Pass the store instance to the entrypoint() decorator and expose store parameter in the function signature:

In this guide, we will show how to construct and use a workflow that has a shared memory implemented using the Store interface.

Support for the Store API that is used in this guide was added in LangGraph v0.2.32.

Support for index and query arguments of the Store API that is used in this guide was added in LangGraph v0.2.54.

If you need to add cross-thread persistence to a StateGraph, check out this how-to guide.

First, let's install the required packages and set our API keys

Set up LangSmith for LangGraph development

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started here

In this example we will create a workflow that will be able to retrieve information about a user's preferences. We will do so by defining an InMemoryStore - an object that can store data in memory and query that data.

When storing objects using the Store interface you define two things:

In our example, we'll be using ("memories", <user_id>) as namespace and random UUID as key for each new memory.

Importantly, to determine the user, we will be passing user_id via the config keyword argument of the node function.

Let's first define our store!

API Reference: OpenAIEmbeddings

API Reference: ChatAnthropic | RunnableConfig | BaseMessage | entrypoint | task | add_messages | InMemorySaver

If you're using LangGraph Cloud or LangGraph Studio, you don't need to pass store to the entrypoint decorator, since it's done automatically.

Now let's specify a user ID in the config and tell the model our name:

config = {"configurable": {"thread_id": "1", "user_id": "1"}} input_message = {"role": "user", "content": "Hi! Remember: my name is Bob"} for chunk in workflow.stream([input_message], config, stream_mode="values"): chunk.pretty_print() ================================== Ai Message ================================== Hello Bob! Nice to meet you. I'll remember that your name is Bob. How can I help you today?

config = {"configurable": {"thread_id": "2", "user_id": "1"}} input_message = {"role": "user", "content": "what is my name?"} for chunk in workflow.stream([input_message], config, stream_mode="values"): chunk.pretty_print() ================================== Ai Message ================================== Your name is Bob. We can now inspect our in-memory store and verify that we have in fact saved the memories for the user:

for memory in in_memory_store.search(("memories", "1")): print(memory.value) {'data': 'User name is Bob'} Let's now run the workflow for another user to verify that the memories about the first user are self contained:

config = {"configurable": {"thread_id": "3", "user_id": "2"}} input_message = {"role": "user", "content": "what is my name?"} for chunk in workflow.stream([input_message], config, stream_mode="values"): chunk.pretty_print() ================================== Ai Message ================================== I don't have any information about your name. I can only see our current conversation without any prior context or personal details about you. If you'd like me to know your name, feel free to tell me!

**Examples:**

Example 1 (python):
```python
from langgraph.store.memory import InMemoryStore, BaseStore

store = InMemoryStore()
```

Example 2 (python):
```python
from langgraph.func import entrypoint

@entrypoint(store=store)
def workflow(inputs: dict, store: BaseStore):
    my_task(inputs).result()
    ...
```

Example 3 (unknown):
```unknown
pip install -U langchain_anthropic langchain_openai langgraph
```

Example 4 (python):
```python
import getpass
import os


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("ANTHROPIC_API_KEY")
_set_env("OPENAI_API_KEY")
```

---

## Add memory¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/get-started/3-add-memory/

**Contents:**
- Add memory¶
- 1. Create a MemorySaver checkpointer¶
- 2. Compile the graph¶
- 3. Interact with your chatbot¶
- 4. Ask a follow up question¶
- 5. Inspect the state¶
- Next steps¶

The chatbot can now use tools to answer user questions, but it does not remember the context of previous interactions. This limits its ability to have coherent, multi-turn conversations.

LangGraph solves this problem through persistent checkpointing. If you provide a checkpointer when compiling the graph and a thread_id when calling your graph, LangGraph automatically saves the state after each step. When you invoke the graph again using the same thread_id, the graph loads its saved state, allowing the chatbot to pick up where it left off.

We will see later that checkpointing is much more powerful than simple chat memory - it lets you save and resume complex state at any time for error recovery, human-in-the-loop workflows, time travel interactions, and more. But first, let's add checkpointing to enable multi-turn conversations.

This tutorial builds on Add tools.

Create a MemorySaver checkpointer:

API Reference: InMemorySaver

This is in-memory checkpointer, which is convenient for the tutorial. However, in a production application, you would likely change this to use SqliteSaver or PostgresSaver and connect a database.

Compile the graph with the provided checkpointer, which will checkpoint the State as the graph works through each node:

Now you can interact with your bot!

Pick a thread to use as the key for this conversation.

The config was provided as the second positional argument when calling our graph. It importantly is not nested within the graph inputs ({'messages': []}).

Ask a follow up question:

Notice that we aren't using an external list for memory: it's all handled by the checkpointer! You can inspect the full execution in this LangSmith trace to see what's going on.

Don't believe me? Try this using a different config.

Notice that the only change we've made is to modify the thread_id in the config. See this call's LangSmith trace for comparison.

By now, we have made a few checkpoints across two different threads. But what goes into a checkpoint? To inspect a graph's state for a given config at any time, call get_state(config).

The snapshot above contains the current state values, corresponding config, and the next node to process. In our case, the graph has reached an END state, so next is empty.

Congratulations! Your chatbot can now maintain conversation state across sessions thanks to LangGraph's checkpointing system. This opens up exciting possibilities for more natural, contextual interactions. LangGraph's checkpointing even handles arbitrarily complex graph states, which is much more expressive and powerful than simple chat memory.

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

In the next tutorial, you will add human-in-the-loop to the chatbot to handle situations where it may need guidance or verification before proceeding.

**Examples:**

Example 1 (python):
```python
from langgraph.checkpoint.memory import InMemorySaver

memory = InMemorySaver()
```

Example 2 (unknown):
```unknown
graph = graph_builder.compile(checkpointer=memory)
```

Example 3 (unknown):
```unknown
config = {"configurable": {"thread_id": "1"}}
```

Example 4 (unknown):
```unknown
user_input = "Hi there! My name is Will."

# The config is the **second positional argument** to stream() or invoke()!
events = graph.stream(
    {"messages": [{"role": "user", "content": user_input}]},
    config,
    stream_mode="values",
)
for event in events:
    event["messages"][-1].pretty_print()
```

---
