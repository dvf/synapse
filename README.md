<br><picture>
<img width="400" alt="Synapse Logo" src="https://github.com/user-attachments/assets/706d1ce2-ae49-4c34-aa51-a5f8f1f5f68e" />
</picture>

<br>

**Build agent swarms: teams of nodes that discover each other, share abilities, join conversations, expose custom endpoints, and wake up on schedules like sunrise... across any network**

Synapse is a lightweight peer-to-peer substrate for agent infrastructure. Give each process a `Node` and Synapse gives that node a name, peers, capabilities, RPC endpoints, shared conversations, agent cards, heartbeats, and periodic tasks.

[![PyPI](https://img.shields.io/pypi/v/synapse-p2p.svg)](https://pypi.python.org/pypi/synapse-p2p)
[![Tests](https://github.com/dvf/synapse/actions/workflows/test.yml/badge.svg)](https://github.com/dvf/synapse/actions/workflows/test.yml)
[![License](https://img.shields.io/github/license/dvf/synapse)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
![PyPI - Downloads](https://img.shields.io/pypi/dw/synapse-p2p)

```python
from synapse_p2p import Node, solar

node = Node(
    name="garden-node",
    swarm="garden.example.com",
    capabilities=["sensors", "watering"],
    mdns=True,
)


@node.periodic(solar("sunrise", latitude=51.5, longitude=-0.1, tz="Europe/London"))
async def morning_check() -> None:
    await node.broadcast("garden.status")


node.run()
```

A node can wrap an LLM agent, a script, a service, a sensor, or a tool. Synapse is not the agent brain. It is the swarm layer agents stand on.

What makes it fun:

- **Swarms are teams**—nodes find teammates by swarm name.
- **Nodes have names and abilities**—advertise `code-review`, `weather`, `memory`, `watering`, anything.
- **Shared conversations**—broadcast once; many nodes can wade in, reply, leave, and come back later.
- **Custom endpoints**—expose any async function as swarm-callable RPC.
- **Agent cards**—publish metadata so peers can understand what you are.
- **Periodic tasks**—start work every minute, every weekday, or literally at sunrise.

---

## 🧭 Table of contents

- [Install](#install)
- [The mental model](#the-mental-model)
- [Why it feels different](#why-it-feels-different)
- [What can you build?](#what-can-you-build)
- [Synapse vs A2A](#synapse-vs-a2a)
- [Quickstart: RPC](#quickstart-rpc)
- [Swarms and discovery](#swarms-and-discovery)
- [Capabilities](#capabilities)
- [Ask: delegate work](#ask-delegate-work)
- [Broadcast: ask the swarm](#broadcast-ask-the-swarm)
- [Periodic tasks](#periodic-tasks)
- [Artifacts and agent cards](#artifacts-and-agent-cards)
- [Heartbeats](#heartbeats)
- [CLI](#cli)
- [Examples](#examples)
- [Protocol details](#protocol-details)
- [What Synapse is not](#what-synapse-is-not)

---

## 📦 Install

Using `uv` or `pip`:
```bash
uv add synapse-p2p
```
```bash
pip install synapse-p2p
```

Then:

```bash
sn --help
```

---

## 🧠 The mental model

Synapse uses these words carefully:

| Word | Meaning |
| --- | --- |
| **Node** | A running Synapse participant. You create one with `Node(...)`. |
| **Peer** | Another node this node knows about. |
| **Swarm** | Nodes with the same `swarm` name. |
| **Agent** | Your higher-level logic: an LLM loop, workflow, script, or automation. |
| **Capability** | A short advertised skill like `code-review`, `web-research`, or `watering`. |
| **Endpoint** | An async function peers can call over RPC. |

Use **node** for Synapse networking. Use **agent** for the logic you put behind a node.

Synapse gives nodes:

- a **name** and swarm identity
- **peer discovery** over mDNS or seeds
- advertised **capabilities / abilities**
- custom async **RPC endpoints**
- direct **task delegation**
- **shared broadcast conversations**
- **agent cards** and other advertised metadata
- **periodic tasks** on interval, cron, or solar time
- **heartbeats** and offline detection
- a simple MsgPack-over-TCP protocol

---

## ✨ Why it feels different

Most agent frameworks start with one agent loop. Synapse starts with the swarm.

```text
planner-node ── broadcasts "who can review this?"
      │
      ├── security-node replies now
      ├── tests-node replies now
      └── docs-node replies later using the same conversation nonce
```

A node can join a swarm, advertise what it can do, expose custom endpoints, publish an agent card, and participate in conversations without a central coordinator.

Periodic tasks make nodes feel alive:

```python
@node.periodic(solar("sunrise", latitude=51.5, longitude=-0.1, tz="Europe/London"))
async def wake_up() -> None:
    await node.broadcast("daily.start")
```

---

## 🛠️ What can you build?

- **Research swarms** — a planner node broadcasts a question; specialist nodes wade into the same conversation.
- **Code-review teams** — nodes advertise `security`, `tests`, or `docs`; a coordinator delegates to the right peer.
- **Local-first automations** — laptop, server, and Raspberry Pi nodes discover each other with mDNS.
- **Sunrise agents** — a node starts work at sunrise, sunset, or civil twilight.
- **Internal agent APIs** — put an LLM agent behind a custom endpoint so other nodes can discover and call it.
- **Self-describing tools** — publish an agent card with name, role, abilities, input modes, and output modes.
- **Live dashboards** — watch joins, heartbeats, messages, replies, and offline events with `sn watch`.

Synapse handles the substrate. You bring the behavior.

---

## ⚖️ Synapse vs A2A

A2A is a full agent interoperability protocol. Synapse is much smaller: a peer-to-peer substrate for nodes that need to find each other and talk.

Use **A2A** when you need a formal cross-vendor agent protocol with task lifecycle, message parts, artifacts, streaming, push notifications, and enterprise-style integration points.

Use **Synapse** when you want to build a swarm quickly:

| A2A | Synapse |
| --- | --- |
| Agent protocol | Swarm substrate |
| HTTP / JSON-RPC oriented | Length-prefixed MsgPack over TCP |
| Formal task lifecycle | Simple RPC, ask, and broadcast |
| Agent cards are central | Agent cards are optional artifacts |
| More concepts to implement | One main primitive: `Node` |
| Best for interoperability | Best for local-first swarms and fast experimentation |

Synapse is intentionally less bloated:

- no required task state machine
- no required message/part/artifact object model
- no server/client role ceremony inside a swarm
- no central coordinator
- no hosted registry requirement
- no opinion about how agents think

The core idea is simple: start nodes, advertise abilities, call endpoints, broadcast into shared conversations, and run periodic jobs.

---

## ⚡ Quickstart: RPC

Create a node with an endpoint:

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

## 🐝 Swarms and discovery

A **swarm** is a group of nodes with the same `swarm` name. Nodes only join and heartbeat peers in their own swarm.

```python
node = Node(
    name="coder",
    swarm="foo.electron.network",
    capabilities=["python", "tests"],
)
```

Use a domain-style swarm name to avoid collisions.

### 📡 Local discovery with mDNS

Use mDNS for zero-config discovery on a LAN:

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

### 🌍 Remote discovery with seeds

Use seeds when nodes are not on the same LAN:

```python
node = Node(
    name="planner",
    swarm="foo.electron.network",
    seeds=["bootstrap.foo.electron.network:9999"],
)

await node.start()
await node.join()
```

A seed is just another Synapse node. It is a first contact point, not a coordinator. Once joined, nodes exchange known peers and can talk directly.

---

## 🎯 Capabilities

Capabilities tell peers what a node can do.

```python
node = Node(capabilities=["python", "code-review"])
```

Use structured capabilities when you want descriptions and schemas:

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

Inspect a peer:

```python
info = await client.call("_node.info")
capabilities = await client.call("_node.capabilities")
methods = await client.call("_synapse.methods")
```

---

## 🤝 Ask: delegate work

Use `@node.ask` for the default task handler on a node.

```python
from synapse_p2p import Node

node = Node(name="reviewer", capabilities=["code-review"])


@node.ask
async def handle(task: str, context: dict):
    return {"status": "done", "task": task}
```

Ask a peer to do work:

```python
from synapse_p2p import Client

result = await Client.from_peer(peer).call(
    "_node.ask",
    "Review this diff",
    context={"diff": diff},
)
```

---

## 💬 Broadcast: ask the swarm

Use broadcast when you do not know which node should answer.

```python
broadcast = await node.broadcast("team.question", "Who can review this diff?")
```

Every receiver gets the same conversation nonce. Any node can reply:

```python
from synapse_p2p import Broadcast


@node.endpoint("team.question")
async def answer(question: str, broadcast: Broadcast) -> dict:
    await node.reply(broadcast, {"answer": "I can help"})
    return {"accepted": True}
```

The origin node can read all replies:

```python
for reply in node.replies(broadcast):
    print(reply.peer.name, reply.result)
```

Synapse also keeps a lightweight conversation event log. A broadcast creates a `message` event whose `conversation_id` is the broadcast nonce. Nodes may opt into the conversation with `ack` or other events; Synapse does not decide who should answer.

```python
@node.endpoint("team.question")
async def answer(question: str, broadcast: Broadcast) -> dict:
    # ACK means "I saw this and am choosing to wade in".
    # It does not mean Synapse assigned this node the work.
    await node.ack(broadcast, {"seen": True})
    await node.reply(broadcast, {"answer": "I can help"})
    return {"accepted": True}
```

Listen for conversation events:

```python
from synapse_p2p import ConversationEvent


@node.on("conversation.ack")
async def on_ack(event: ConversationEvent) -> None:
    print(event.peer.name, "acked", event.conversation_id)


for event in node.conversation(broadcast):
    print(event.kind, event.peer.name, event.payload)
```

Built-in conversation event kinds are intentionally small conventions:

- `message` — a broadcast or conversation message was seen
- `ack` — a node chose to acknowledge / enter the conversation
- `reply` — a node replied with a result

Higher-level agent frameworks can layer routing, claiming, status, artifacts, or task semantics on top by emitting their own event kinds with `node.emit_conversation_event(...)`.

Why this is useful:

- one broadcast creates one shared conversation
- every node sees the same nonce
- nodes can wade in or stay silent
- ACK is opt-in, not automatic assignment
- replies and events group without a central coordinator
- UUIDv7 nonces keep conversations roughly time-ordered when the runtime supports them

---

## 🌅 Periodic tasks

Nodes can wake up on a schedule: every few seconds, every weekday morning, or when the sun rises.

```python
from synapse_p2p import Node, cron, every, solar

node = Node(name="worker")


@node.periodic(every(seconds=30))
async def refresh_cache() -> None:
    print("refreshing cache")


@node.periodic(cron("0 9 * * mon-fri", tz="Europe/London"))
async def weekday_digest() -> None:
    print("weekday digest")


@node.periodic(solar("sunrise", latitude=51.5, longitude=-0.1, tz="Europe/London"))
async def sunrise_job() -> None:
    print("the sun is up; time to work")


node.run()
```

A number is shorthand for seconds:

```python
@node.periodic(30)  # equivalent to every(seconds=30)
async def refresh_cache() -> None:
    ...
```

Built-in schedules:

- `every(seconds=..., minutes=..., hours=..., days=...)`
- `cron("*/15 * * * *", tz="UTC")`
- `solar("sunrise", latitude=..., longitude=..., tz="UTC")`

Solar events include `sunrise`, `sunset`, `solar_noon`, `civil_twilight_begin`, `civil_twilight_end`, `nautical_twilight_begin`, `nautical_twilight_end`, `astronomical_twilight_begin`, and `astronomical_twilight_end`.

Notes:

- periodic handlers must be `async def`
- the first run starts immediately when the node starts
- later runs follow the schedule
- exceptions are logged and do not stop future runs
- long-running tasks can overlap if the next scheduled time arrives first

---

## 🪪 Artifacts and agent cards

Nodes can advertise small metadata documents that peers can fetch over RPC.

```python
node.artifact(
    "agent-card",
    {
        "name": node.name,
        "description": "Reviews Python PRs and returns concise feedback.",
        "capabilities": ["code-review", "pytest"],
        "input_modes": ["text", "git-diff", "url"],
        "output_modes": ["text/markdown", "text/x-diff"],
    },
    mime_type="application/vnd.synapse.agent-card+json",
    description="Self-description for peers that understand agent cards.",
)
```

Fetch artifacts from a peer:

```python
from synapse_p2p import Client

client = Client.from_peer(peer)

artifacts = await client.call("_synapse.artifacts")
agent_card = await client.call("_synapse.artifact.get", "agent-card")
```

Synapse does not interpret artifacts. It serves bytes/JSON plus a MIME type. Your application decides what the artifact means.

---

## 💓 Heartbeats

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

## 🖥️ CLI

The CLI is `sn`.

```bash
sn --help
```

### 👀 Watch a swarm

```bash
sn watch foo.electron.network
```

<picture>
<img width="1268" alt="image" src="https://github.com/user-attachments/assets/3b08371b-2a1b-465f-8939-cbf0a0ba219c" />
</picture>

Useful options:

```bash
sn watch foo.electron.network --show-heartbeats
sn watch foo.electron.network --seed 192.168.1.25:9000 --no-mdns
sn watch foo.electron.network --team backend
sn watch foo.electron.network --no-capabilities
```

### 📣 Broadcast from the terminal

```bash
sn broadcast foo.electron.network "Who can review this diff?"
sn broadcast foo.electron.network "Who can help?" --forever
sn broadcast foo.electron.network "Ship status?" --discover 2 --timeout 10
```

### 📋 List local swarms

```bash
sn list-swarms
sn list-swarms --seconds 5
```

---

## 📚 Examples

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

# Pydantic AI team that replies over mDNS
python examples/pydantic_ai_team/reviewer.py
python examples/pydantic_ai_team/coder.py
python examples/pydantic_ai_team/product.py
python examples/pydantic_ai_team/ask.py

# interval, cron, sunrise, and civil twilight jobs
python examples/periodic_tasks.py
```

The Pydantic AI example uses `TestModel` by default, so it runs without API keys. Set `PYDANTIC_AI_MODEL`, for example `openai:gpt-5.2`, to use a real model.

---

## 🔌 Protocol details

Built-in endpoints:

| Endpoint | Purpose |
| --- | --- |
| `_synapse.ping` | health check |
| `_synapse.info` | node identity and swarm metadata |
| `_synapse.methods` | published RPC methods |
| `_synapse.peers` | known peers |
| `_synapse.join` | join through a seed |
| `_synapse.heartbeat` | update peer liveness |
| `_synapse.broadcast.reply` | reply to a broadcast nonce |
| `_synapse.artifacts` | list advertised artifacts |
| `_synapse.artifact.get` | fetch one advertised artifact |
| `_node.info` | name, role, description, capabilities |
| `_node.capabilities` | machine-readable capabilities |
| `_node.ask` | delegate to the node ask handler |

Wire format:

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

Useful low-level exports:

```python
from synapse_p2p import Broadcast, BroadcastReply, Capability, Client, Node, Peer
from synapse_p2p import RPCError, RPCRequest, RPCResponse
```

Enable logs when debugging:

```python
from loguru import logger

logger.enable("synapse_p2p")
```

---

## 🚫 What Synapse is not

Synapse does **not** implement planning, memory, consensus, auth policy, NAT traversal, hosted registries, or UX.

Those belong above Synapse.

Synapse is the substrate:

> nodes + discovery + capabilities + heartbeats + broadcasts + schedules + a tiny protocol

---

## 🔎 Keywords

swarm substrate, agent substrate, node discovery, local mDNS discovery, agent-to-agent networking, LLM agent RPC, multi-agent systems, capability discovery, language-agnostic RPC, Python RPC, asyncio RPC, peer-to-peer Python, P2P networking, MsgPack RPC, TCP RPC, distributed agents.
