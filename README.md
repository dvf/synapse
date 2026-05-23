<picture>
<img width="400" alt="Synapse Logo" src="https://github.com/user-attachments/assets/706d1ce2-ae49-4c34-aa51-a5f8f1f5f68e" />
</picture>

<br><br>
**A p2p substrate for building agent swarms that discover each other, share capabilities, delegate work, broadcast questions, and run jobs on human or solar time.**

[![PyPI](https://img.shields.io/pypi/v/synapse-p2p.svg)](https://pypi.python.org/pypi/synapse-p2p)
[![Tests](https://github.com/dvf/synapse/actions/workflows/test.yml/badge.svg)](https://github.com/dvf/synapse/actions/workflows/test.yml)
[![License](https://img.shields.io/github/license/dvf/synapse)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

<br>


```python
from synapse_p2p import Node, solar

node = Node(
    name="garden-agent",
    swarm="garden.example.com",
    capabilities=["sensors", "watering"],
    mdns=True,
)


@node.periodic(solar("sunrise", latitude=51.5, longitude=-0.1, tz="Europe/London"))
async def morning_check() -> None:
    await node.broadcast("garden.status")


await node.start()
await node.join()
```

Synapse gives you one primitive: **Node**.

A node can discover peers, publish capabilities, expose endpoints, receive work, broadcast questions, reply into shared conversations, run periodic jobs, heartbeat peers, and notice when peers disappear. Synapse isn't an agent framework, it's a library that gives you simple atomics to build on top of. 

It also ships with a CLI tool to monitor your swarms:

```bash
> sn watch foo.electron.network
```

<picture>
<img width="1268" alt="image" src="https://github.com/user-attachments/assets/3b08371b-2a1b-465f-8939-cbf0a0ba219c" />
</picture>

---

## Index

- [What can you build with Synapse?](#what-can-you-build-with-synapse)
- [Install](#install)
- [Why Synapse](#why)
- [30-second RPC](#30-second-rpc)
- [Swarms](#swarms)
- [Discovery](#local-discovery-mdns)
  - [Local discovery: mDNS](#local-discovery-mdns)
  - [Remote discovery: seeds](#remote-discovery-seeds)
- [Capabilities](#capabilities)
- [Advertised artifacts and agent cards](#advertised-artifacts-and-agent-cards)
- [Ask](#ask)
- [Broadcast conversations](#broadcast)
- [Periodic tasks](#periodic-tasks)
- [Heartbeats and liveness](#heartbeats)
- [CLI](#cli)
  - [`sn watch`](#sn-watch)
  - [`sn broadcast`](#sn-broadcast)
  - [`sn list-swarms`](#sn-list-swarms)
- [Typed peer API](#typed-peer-api)
- [Examples](#examples)
- [Built-in endpoints](#built-in-endpoints)
- [Wire protocol](#wire-protocol)
- [Logging](#logging)
- [What Synapse is not](#what-synapse-is-not)
- [Roadmap](#roadmap)

---

## What can you build with Synapse?

Synapse is for small, composable agent swarms that need to find each other and coordinate without a central orchestrator.

- **Research teams** — a planner broadcasts a question; specialist agents reply into the same conversation.
- **Code-review swarms** — reviewers advertise capabilities like `security`, `tests`, or `docs`; a coordinator delegates work to the right peer.
- **Local-first automations** — laptop, server, and Raspberry Pi agents discover each other over mDNS with no config.
- **Scheduled agents** — run checks every 30 seconds, every weekday at 9am, or at sunrise/civil twilight using solar schedules.
- **Live swarm dashboards** — use `sn watch` to see nodes join, heartbeat, message, and disappear in real time.
- **Cross-language protocols** — speak length-prefixed MsgPack over TCP from Python today and other runtimes tomorrow.

Synapse handles the swarm substrate: discovery, capabilities, RPC, broadcast conversations, liveness, and schedules. You bring the agent logic.

---

## Install

```bash
uv add synapse-p2p
```

or 

```
pip install synapse-p2p
```

Then use the CLI:

```bash
sn --help
```

---

## Why

Most agents are still isolated processes. Synapse gives them a shared substrate:

- **discovery** — find nodes in the same swarm
- **capabilities** — advertise what each node can do
- **RPC** — call a named endpoint on a peer
- **ask** — delegate a task to a capable node
- **broadcast** — ask the whole swarm and collect replies
- **periodic jobs** — run interval, cron, and solar schedules
- **heartbeats** — know who is still around
- **typed Python API** — avoid dictionary soup
- **simple wire protocol** — length-prefixed MsgPack over TCP

The goal is not to decide how agents think. The goal is to let them communicate.

---

## 30-second RPC

This is the smallest useful Synapse program: one node exposes an RPC endpoint, and one client calls it.

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

A swarm is a group of nodes with the same swarm name. Nodes only join and heartbeat peers in the same swarm.

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

Use mDNS for local, zero-config discovery on the same LAN.

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

Use seeds when mDNS is not enough: private networks, remote machines, explicit bootstrap nodes, or internet-reachable hosts.

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

A seed is just another Synapse node. It is a first contact point, not a coordinator. Once joined, nodes exchange known peers and can talk directly.

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

## Advertised artifacts and agent cards

Nodes can advertise small metadata documents or resources that peers can fetch over Synapse RPC.
Synapse does not interpret the document; it only serves the bytes/JSON plus a MIME type. Higher-level agents decide what they understand.

An A2A-style agent card can be published as just another artifact:

```python
from synapse_p2p import Node

node = Node(
    name="Tiny Review LLC",
    role="reviewer",
    swarm="code.review",
    capabilities=["code-review", "pytest"],
)

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
    description="Self-description for agents that understand agent cards.",
)
```

Peers discover and fetch advertised artifacts with system endpoints:

```python
from synapse_p2p import Client

client = Client.from_peer(peer)

artifacts = await client.call("_synapse.artifacts")
# [{"name": "agent-card", "mime_type": "application/vnd.synapse.agent-card+json", ...}]

agent_card = await client.call("_synapse.artifact.get", "agent-card")
print(agent_card["mime_type"])
print(agent_card["content"])
```

MIME types are conventions for consumers:

- `application/vnd.synapse.agent-card+json` — a Synapse/A2A-style self-description
- `application/vnd.synapse.capability-schema+json` — capability-specific input/output schema
- `text/markdown`, `application/pdf`, `image/png`, `text/x-diff` — normal document/file types

For now, artifacts are small inline documents served over RPC. Large artifacts can advertise external URIs in their content or metadata.

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

Broadcast starts a swarm conversation. It is the simplest way to ask the whole swarm a question and let any capable node reply.

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

## Periodic tasks

Agents do not only respond to messages. They also wake up: every few seconds, every weekday morning, or when the sun rises.

Use `@node.periodic(...)` to run an async function on an interval, cron expression, or solar event while the node is running. Periodic tasks start with `await node.start()` or `node.run()`, and `await node.stop()` cancels scheduled and in-flight runs.

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
async def sunrise_agent() -> None:
    print("the sun is up; time to work")


@node.periodic(solar("civil_twilight_begin", latitude=51.5, longitude=-0.1, tz="Europe/London"))
async def dawn_check() -> None:
    print("civil twilight has begun")


node.run()
```

For simple intervals, a number is shorthand for seconds:

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

- The decorated function must be `async def` and take no arguments.
- The first run starts immediately when the node starts; later runs follow the schedule.
- Long-running tasks can overlap if a previous run is still active when the next scheduled time arrives.
- Exceptions are logged and do not stop future runs.
- Tasks added after `await node.start()` are scheduled immediately.

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

The CLI is `sn`.

```bash
sn --help
```

`sn` uses mDNS by default, so local swarms work with zero configuration. Use `--seed host:port` for seed discovery, or `--no-mdns` to disable local discovery.

### `sn watch`

Watch a swarm live:

```bash
sn watch foo.electron.network
```

`sn watch` opens an in-place terminal dashboard:

- left pane: swarm name, this watcher, peers, online dots, addresses, capabilities
- right pane: chatter/debug log for joins, messages, replies, offline events, and optional heartbeats

Peer dots:

| Dot | Meaning |
| --- | --- |
| bright green | fresh join/heartbeat pulse |
| muted green | online |
| yellow | stale, waiting for timeout |
| red | offline |

Useful options:

```bash
sn watch foo.electron.network --show-heartbeats
sn watch foo.electron.network --seed 192.168.1.25:9000 --no-mdns
sn watch foo.electron.network --team backend
sn watch foo.electron.network --no-capabilities
```


### `sn broadcast`

Broadcast a message to known swarm peers and stream replies:

```bash
sn broadcast foo.electron.network "Who can review this diff?"
```

Keep listening for late replies:

```bash
sn broadcast foo.electron.network "Who can help?" --forever
```

Tune discovery and reply timeout:

```bash
sn broadcast foo.electron.network "Ship status?" --discover 2 --timeout 10
```

Broadcast replies are grouped by the broadcast nonce, so all agents can participate in one shared conversation.


### `sn list-swarms`

List local mDNS-visible swarms:

```bash
sn list-swarms
```

Scan for longer:

```bash
sn list-swarms --seconds 5
```


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

# periodic jobs: interval, cron, sunrise, and civil twilight
python examples/periodic_tasks.py
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
