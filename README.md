<picture>
<img width="678" height="141" alt="Synapse Logo (3)" src="https://github.com/user-attachments/assets/213dfe30-58da-41c4-ba5d-5014647cd4d3" />
</picture>

<br><br>
**A p2p swarm substrate for nodes that find each other, talk to each other, and work together.**

[![PyPI](https://img.shields.io/pypi/v/synapse-p2p.svg)](https://pypi.python.org/pypi/synapse-p2p)
[![Tests](https://github.com/dvf/synapse/actions/workflows/test.yml/badge.svg)](https://github.com/dvf/synapse/actions/workflows/test.yml)
[![License](https://img.shields.io/github/license/dvf/synapse)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

<br>

```python
from synapse_p2p import Node

node = Node(
    name="reviewer",
    swarm="foo.electron.network",
    capabilities=["code-review"],
    mdns=True,
)

await node.start()
await node.join()
```

Synapse gives you one primitive: **Node**.

A node can discover peers, publish capabilities, expose endpoints, receive work, broadcast questions, reply into shared conversations, heartbeat peers, and notice when peers disappear.

Synapse is not an agent framework. It is the clean network layer underneath one.

---

## Install

```bash
pip install synapse-p2p
```

Then use the CLI:

```bash
sn --help
```

---

## Why

LLM agents are often isolated. Synapse gives them a small shared substrate:

- **discovery** — find nodes in the same swarm
- **capabilities** — know what each node can do
- **RPC** — call a named endpoint
- **ask** — delegate a task to a node
- **broadcast** — ask the whole swarm
- **heartbeats** — know who is still around
- **typed Python API** — no dictionary soup
- **simple wire protocol** — length-prefixed MsgPack over TCP

The goal is not to decide how agents think. The goal is to let them communicate.

---

## 30-second RPC

Create a node:

```python
from synapse_p2p import Node

node = Node(name="calculator", port=9999)


@node.endpoint("sum", description="Add two numbers")
async def sum(a: int, b: int) -> int:
    return a + b


node.run()
```

Call it:

```python
import asyncio

from synapse_p2p import Client


async def main() -> None:
    result = await Client("127.0.0.1", 9999).call("sum", 1, 2)
    print(result)


asyncio.run(main())
```

---

## Swarms

A swarm is a group of nodes with the same swarm name.

```python
node = Node(
    name="coder",
    role="implementation",
    swarm="foo.electron.network",
    capabilities=["python", "tests"],
)
```

Use a domain-style name to avoid collisions:

```text
foo.electron.network
```

Need subgroups? Use optional `team`. It defaults to `"default"`.

---

## Local discovery: mDNS

For local machines on the same network:

```python
node = Node(
    name="reviewer",
    swarm="foo.electron.network",
    capabilities=["code-review"],
    mdns=True,
)

await node.start()
await node.join()
```

Any node on the same LAN with the same `swarm` and `mdns=True` can discover it.

Synapse advertises:

```text
_synapse._tcp.local.
```

mDNS is local by design. It usually does not cross routers, VPN boundaries, or restrictive firewalls.

---

## Remote discovery: seeds

For private networks or internet-reachable hosts, use seeds:

```python
node = Node(
    name="planner",
    swarm="foo.electron.network",
    seeds=["bootstrap.foo.electron.network:9999"],
)

await node.start()
await node.join()
```

A seed is just another Synapse node. Once joined, nodes exchange known peers.

By default, nodes listen on `0.0.0.0` and advertise an auto-detected reachable local address. For same-machine-only experiments, use `bind="127.0.0.1"`.

---

## Capabilities

Simple:

```python
node = Node(capabilities=["python", "code-review"])
```

Structured:

```python
from synapse_p2p import Capability, Node

node = Node(
    name="researcher",
    capabilities=[
        Capability(
            name="web-research",
            description="Find and summarize sources.",
            input_schema={"query": "string"},
            output_schema={"summary": "string", "sources": "array"},
        )
    ],
)
```

Inspect a node:

```python
info = await client.call("_node.info")
capabilities = await client.call("_node.capabilities")
methods = await client.call("_synapse.methods")
```

---

## Ask

Register one ask handler:

```python
node = Node(name="reviewer", capabilities=["code-review"])


@node.ask
async def handle(task: str, context: dict):
    return {"status": "done", "task": task}
```

Ask another node:

```python
result = await Client.from_peer(peer).call(
    "_node.ask",
    "Review this diff",
    context={"diff": diff},
)
```

---

## Broadcast

Broadcast starts a swarm conversation.

```python
broadcast = await node.broadcast("team.question", "Who can review this diff?")
```

That returns a `Broadcast` object:

```python
broadcast.nonce   # conversation id
broadcast.origin  # peer that started it
broadcast.endpoint
```

The nonce is the conversation atom. Synapse creates UUIDv7 nonces when the Python runtime supports them, so conversations are unique and time-sortable. On older runtimes it falls back to UUIDv4.

Every receiver gets the same `Broadcast` object. Any node can reply into that conversation by reusing the nonce through `node.reply(...)`:

```python
from synapse_p2p import Broadcast


@node.endpoint("team.question")
async def answer(question: str, broadcast: Broadcast) -> dict:
    await node.reply(broadcast, {"answer": "I can help"})
    return {"accepted": True}
```

The origin node groups all replies by nonce:

```python
for reply in node.replies(broadcast):
    print(reply.peer.name, reply.result)
```

Why this matters:

- one broadcast creates one shared event
- the nonce is the conversation id
- every agent sees the same nonce
- any agent can participate by replying with that nonce
- replies group without a central coordinator
- UUIDv7 nonces keep conversation ids roughly ordered by creation time

---

## Heartbeats

Nodes heartbeat known peers and mark stale peers offline.

```python
from synapse_p2p import Node, Peer

node = Node(name="planner", heartbeat_interval=5, peer_timeout=20)


@node.on("peer.joined")
async def joined(peer: Peer) -> None:
    print(f"joined: {peer.name}")


@node.on("peer.offline")
async def offline(peer: Peer) -> None:
    print(f"offline: {peer.name}")
```

Offline means “not seen within `peer_timeout`.”

---

## CLI

Watch a swarm live:

```bash
sn watch foo.electron.network
```

Broadcast and stream replies:

```bash
sn broadcast foo.electron.network "Who can review this diff?"
```

Keep listening:

```bash
sn broadcast foo.electron.network "Who can help?" --forever
```

List local mDNS-visible swarms:

```bash
sn list-swarms
```

`sn` uses mDNS by default. Use `--seed host:port` for seed discovery, or `--no-mdns` to disable local discovery.

---

## Typed peer API

Use dataclasses, not dictionaries:

```python
peers = await Client("127.0.0.1", 9000).peers()
reviewer = next(peer for peer in peers if "code-review" in peer.capabilities)
result = await Client.from_peer(reviewer).call("_node.ask", "Review this")
```

Useful exports:

```python
from synapse_p2p import Broadcast, BroadcastReply, Capability, Client, Node, Peer
```

---

## Examples

See [`examples/`](./examples).

```bash
# two nodes, one delegates to the other
python examples/isolated_agents/agent_alpha.py
python examples/isolated_agents/agent_beta.py
python examples/isolated_agents/ask_alpha.py

# local zero-config mDNS swarm
python examples/local_mdns_swarm/reviewer.py
python examples/local_mdns_swarm/coder.py
python examples/local_mdns_swarm/ask.py

# Pydantic AI team that actually replies over mDNS
python examples/pydantic_ai_team/reviewer.py
python examples/pydantic_ai_team/coder.py
python examples/pydantic_ai_team/product.py
python examples/pydantic_ai_team/ask.py
```

The Pydantic AI example uses `TestModel` by default, so it runs without API keys. Set `PYDANTIC_AI_MODEL`, for example `openai:gpt-5.2`, to use a real model.

---

## Built-in endpoints

Substrate endpoints:

| Endpoint | Purpose |
| --- | --- |
| `_synapse.ping` | health check |
| `_synapse.info` | node identity and swarm metadata |
| `_synapse.methods` | published RPC methods |
| `_synapse.peers` | known peers |
| `_synapse.join` | join through a seed |
| `_synapse.heartbeat` | update peer liveness |
| `_synapse.broadcast.reply` | reply to a broadcast nonce |

Node endpoints:

| Endpoint | Purpose |
| --- | --- |
| `_node.info` | name, role, description, capabilities |
| `_node.capabilities` | machine-readable capabilities |
| `_node.ask` | delegate to the node ask handler |

---

## Wire protocol

Synapse speaks length-prefixed MsgPack over TCP.

Each frame is:

1. 4-byte unsigned big-endian payload length
2. MsgPack payload bytes

Request:

```python
{
    "type": "request",
    "id": "request-id",
    "endpoint": "sum",
    "args": [1, 2],
    "kwargs": {},
}
```

Response:

```python
{
    "type": "response",
    "id": "request-id",
    "ok": True,
    "result": 3,
    "error": None,
}
```

Low-level helpers:

```python
from synapse_p2p import RPCError, RPCRequest, RPCResponse
from synapse_p2p.framing import read_frame, write_frame
from synapse_p2p.serializers import MessagePackRPCSerializer
```

---

## Logging

Synapse is quiet by default.

Enable internal logs when debugging:

```python
from loguru import logger

logger.enable("synapse_p2p")
```

---

## What Synapse is not

Synapse does **not** implement planning, memory, consensus, auth policy, NAT traversal, hosted registries, or UX.

Those belong in packages above Synapse.

Synapse is the substrate:

> nodes + discovery + capabilities + heartbeats + broadcasts + a tiny protocol

---

## Roadmap

mDNS and seeds work today. Natural next providers:

- DNS SRV/TXT for domain-backed swarms
- registries and rendezvous servers
- relays for unreachable peers
- NAT traversal
- authenticated swarms

---

## Keywords

swarm substrate, agent substrate, node discovery, local mDNS discovery, agent-to-agent networking, LLM agent RPC, multi-agent systems, capability discovery, language-agnostic RPC, Python RPC, asyncio RPC, peer-to-peer Python, P2P networking, MsgPack RPC, TCP RPC, distributed agents.
