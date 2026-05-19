<img width="1074" src="https://user-images.githubusercontent.com/1169974/55302502-60653980-540f-11e9-94d0-03229ceeac4e.png">

# Synapse P2P

**Synapse P2P** is a small async Python RPC framework for building peer-to-peer services, local network tools, distributed workers, and lightweight service-to-service APIs.

It gives you a simple decorator-based server API, a built-in async client, structured MsgPack request/response messages, and length-prefixed TCP framing.

```python
@app.endpoint("sum")
async def sum_endpoint(a, b):
    return a + b
```

```python
result = await Client("127.0.0.1", 9999).call("sum", 1, 2)
```

## Features

- **Async TCP RPC** built on `asyncio`
- **MsgPack serialization** for compact binary messages
- **Length-prefixed framing** for reliable message boundaries over TCP
- **Decorator-based endpoints** with `@app.endpoint(...)`
- **Built-in async client** with request/response handling
- **Structured responses and errors** via `RPCResponse` and `RPCError`
- **Positional and keyword arguments** for remote calls
- **Request IDs** for correlation and future persistent-connection support
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
```

## Quickstart

Create a server:

```python
from synapse_p2p import Server

app = Server(address="127.0.0.1", port=9999)  # or Server() for defaults


@app.endpoint("sum")
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

## Server endpoints

Endpoints are async Python callables registered by name:

```python
@app.endpoint("greet")
async def greet(name: str, excited: bool = False) -> str:
    message = f"Hello, {name}"
    return message.upper() if excited else message
```

Call with keyword arguments:

```python
result = await client.call("greet", "Ada", excited=True)
```

## Background tasks

Synapse can also run recurring async background jobs alongside your RPC server:

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

Synapse is intentionally small and evolving. The current focus is a clean async RPC foundation. Future P2P-oriented work may include:

- Peer discovery
- Persistent connections
- Routing tables / Kademlia-style node lookup
- Handshakes and node capabilities
- Authenticated or encrypted messages
- Broadcast and gossip primitives

## Keywords

Python RPC, asyncio RPC, peer-to-peer Python, P2P networking, MsgPack RPC, TCP RPC, async microservices, distributed workers, service-to-service communication.
