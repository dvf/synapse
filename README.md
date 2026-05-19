<img width="1074" src="https://user-images.githubusercontent.com/1169974/55302502-60653980-540f-11e9-94d0-03229ceeac4e.png">

# Synapse P2P

**A network substrate for Python agents.**

Synapse P2P is a tiny async RPC, discovery, and capability-publishing layer for building agent-to-agent networks, local agent swarms, distributed tools, peer-to-peer services, and lightweight service meshes.

It is designed to be useful to both humans and LLM agents:

- Humans get a simple Python API.
- Agents get discoverable methods, published capabilities, structured request/response messages, and machine-readable metadata.

```python
@app.endpoint("sum")
async def sum_endpoint(a: int, b: int) -> int:
    return a + b
```

```python
result = await Client("127.0.0.1", 9999).call("sum", 1, 2)
```

## Why Synapse?

LLM agents need a way to find each other, ask what each other can do, and delegate work over a small, predictable protocol.

Synapse provides the substrate for that:

- **RPC**: call remote Python functions over TCP.
- **Discovery**: inspect published methods and agent capabilities.
- **Agent identity**: expose role, description, and capabilities.
- **Delegation**: send tasks to another agent through `_agent.ask`.
- **Structured protocol**: MsgPack request/response envelopes with request IDs and errors.

Think of it as a minimal network layer for agentic systems — not a framework that decides how agents think, but a substrate they can use to connect.

## Features

- **Async TCP RPC** built on `asyncio`
- **MsgPack serialization** for compact binary messages
- **Length-prefixed framing** for reliable message boundaries over TCP
- **Decorator-based endpoints** with `@app.endpoint(...)`
- **Built-in async client** with request/response handling
- **Structured responses and errors** via `RPCResponse` and `RPCError`
- **Positional and keyword arguments** for remote calls
- **Request IDs** for correlation and future persistent-connection support
- **Published method discovery** via `_synapse.methods`
- **Agent metadata discovery** via `_agent.info` and `_agent.capabilities`
- **Agent task delegation** via `_agent.ask`
- **Periodic background tasks** with `@app.background(...)`
- **Serializer abstraction** for custom protocols later
- **P2P-oriented primitives** such as node identity and XOR-distance helpers

## Installation

```bash
pip install synapse-p2p
```

For development with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run pyrefly check
```

## Quickstart: RPC server and client

Create a server:

```python
from synapse_p2p import Server

app = Server(address="127.0.0.1", port=9999)  # or Server() for defaults


@app.endpoint("sum", description="Add two numbers")
async def sum_endpoint(a: int, b: int) -> int:
    return a + b


if __name__ == "__main__":
    app.run()
```

Call it from a client:

```python
import asyncio

from synapse_p2p import Client


async def main() -> None:
    client = Client("127.0.0.1", 9999)
    result = await client.call("sum", 1, 2)
    print(result)


asyncio.run(main())
```

Output:

```text
3
```

## Quickstart: agent node

An `AgentNode` is a Synapse server that publishes agent metadata and accepts delegated work.

```python
from synapse_p2p import AgentNode

agent = AgentNode(
    name="Reviewer",
    role="reviewer",
    description="Reviews Python code and suggests tests.",
    capabilities=["python", "code-review", "pytest"],
)


@agent.task_handler
async def handle_task(task: str, context: dict):
    return {
        "status": "done",
        "result": f"Reviewed task: {task}",
        "context_keys": list(context),
    }


agent.run()
```

Another agent or client can inspect it:

```python
info = await client.call("_agent.info")
capabilities = await client.call("_agent.capabilities")
```

And delegate work:

```python
result = await client.call(
    "_agent.ask",
    "Review this pull request",
    context={"files": ["server.py", "client.py"]},
)
```

## Built-in discovery endpoints

Synapse reserves `_synapse.*` for substrate-level metadata.

### `_synapse.ping`

Health check:

```python
await client.call("_synapse.ping")
# "pong"
```

### `_synapse.methods`

Returns published RPC methods:

```python
await client.call("_synapse.methods")
```

Example response:

```python
[
    {
        "name": "sum",
        "publish": True,
        "description": "Add two numbers",
    }
]
```

Endpoints are published by default:

```python
@app.endpoint("image.resize", description="Resize an image")
async def resize_image(...):
    ...
```

Private endpoints can opt out:

```python
@app.endpoint("admin.restart", publish=False)
async def restart():
    ...
```

## Built-in agent endpoints

Synapse reserves `_agent.*` for agent-level metadata and task delegation.

### `_agent.info`

Returns agent identity:

```python
{
    "name": "Reviewer",
    "role": "reviewer",
    "description": "Reviews Python code and suggests tests.",
    "capabilities": ["python", "code-review", "pytest"],
}
```

### `_agent.capabilities`

Returns machine-readable capability descriptors:

```python
[
    {
        "name": "code-review",
        "description": "Review Python code for correctness and maintainability.",
        "input_schema": {},
        "output_schema": {},
    }
]
```

Capabilities can be strings or explicit descriptors:

```python
from synapse_p2p import AgentCapability, AgentNode

agent = AgentNode(
    name="Researcher",
    role="researcher",
    capabilities=[
        AgentCapability(
            name="web-research",
            description="Find and summarize evidence from the web.",
            input_schema={"query": "string"},
            output_schema={"summary": "string", "sources": "array"},
        )
    ],
)
```

### `_agent.ask`

Delegates a task to the agent's registered task handler:

```python
await client.call(
    "_agent.ask",
    "Find bugs in this module",
    context={"code": "..."},
)
```

The task handler receives:

```python
async def handle_task(task: str, context: dict):
    ...
```

## Patterns for LLM agents

### 1. Discover a peer

```python
info = await client.call("_agent.info")
methods = await client.call("_synapse.methods")
capabilities = await client.call("_agent.capabilities")
```

### 2. Select a peer by capability

```python
if "code-review" in info["capabilities"]:
    result = await client.call("_agent.ask", "Review this diff", context={"diff": diff})
```

### 3. Publish tools as RPC methods

```python
@app.endpoint("filesystem.search", description="Search files by regex")
async def search_files(pattern: str) -> list[str]:
    ...
```

### 4. Hide dangerous tools

```python
@app.endpoint("shell.exec", publish=False)
async def shell_exec(command: str) -> str:
    ...
```

Private methods are still callable if known, but they are not advertised by `_synapse.methods`.

## Server lifecycle

Use `app.run()` for simple scripts. In larger async applications or tests, use `start()` and `stop()`:

```python
server = await app.start()
try:
    ...
finally:
    await app.stop()
```

## Background tasks

Synapse can run recurring async background jobs alongside your RPC server:

```python
@app.background(5)
async def heartbeat():
    print("still alive")
```

The task above runs roughly every five seconds. Exceptions are logged and do not stop future runs.

## Structured protocol

Synapse sends length-prefixed MsgPack messages over TCP.

A request looks like:

```python
RPCRequest(
    id="request-id",
    endpoint="sum",
    args=[1, 2],
    kwargs={},
)
```

A successful response looks like:

```python
RPCResponse(
    id="request-id",
    ok=True,
    result=3,
)
```

An error response looks like:

```python
RPCResponse(
    id="request-id",
    ok=False,
    error=RPCError(code="bad_request", message="Unregistered endpoint called: nope"),
)
```

## Low-level access

Most users should use `Client`, but lower-level message types are exported if you want to build custom transports or tooling:

```python
from synapse_p2p import RPCError, RPCRequest, RPCResponse, RemoteProcedureCall
from synapse_p2p.framing import read_frame, write_frame
from synapse_p2p.serializers import MessagePackRPCSerializer
```

`RemoteProcedureCall` is kept as a backwards-compatible alias for `RPCRequest`.

## Project status

Synapse is intentionally small and evolving. The current focus is a clean async RPC and agent substrate. Future work may include:

- Peer discovery and bootstrap peer exchange
- Agent-to-agent network discovery
- Long-running jobs for agent tasks
- Persistent connections and streaming events
- Routing tables / Kademlia-style node lookup
- Handshakes and node capabilities
- Authenticated or encrypted messages
- Broadcast and gossip primitives

## Keywords

Python agent substrate, agent-to-agent networking, LLM agent RPC, multi-agent systems, agent discovery, capability discovery, Python RPC, asyncio RPC, peer-to-peer Python, P2P networking, MsgPack RPC, TCP RPC, async microservices, distributed agents, distributed workers, service-to-service communication.
