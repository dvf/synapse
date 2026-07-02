<br><picture>
<img width="400" alt="Synapse Logo" src="https://github.com/user-attachments/assets/706d1ce2-ae49-4c34-aa51-a5f8f1f5f68e" />
</picture>

<br>

**Build agent swarms that discover each other, share abilities, join conversations, and wake up on schedules like sunrise... across any network.**

[![PyPI](https://img.shields.io/pypi/v/synapse-p2p.svg)](https://pypi.python.org/pypi/synapse-p2p)
[![Tests](https://github.com/dvf/synapse/actions/workflows/test.yml/badge.svg)](https://github.com/dvf/synapse/actions/workflows/test.yml)
[![License](https://img.shields.io/github/license/dvf/synapse)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
![PyPI - Downloads](https://img.shields.io/pypi/dw/synapse-p2p)

<br>
<hr>

Synapse is not an agent framework. It's the layer underneath: give each process a `Node` and it gets a name, peers, capabilities, RPC, and shared conversations. What sits behind the node — Claude, GPT, a script, a sensor — is your business.

```bash
uv add synapse-p2p     # or: pip install synapse-p2p
```

Let's build an agent team.

## 1. Give your agent a node

Here's a reviewer. The `@node.ask` handler is what it does when someone hands it work — yours probably calls an LLM.

```python
# reviewer.py
from synapse_p2p import Node

node = Node(
    name="reviewer",
    swarm="myteam.example.com",
    capabilities=["code-review"],
    mdns=True,
)


@node.ask
async def handle(task: str, context: dict):
    return await my_agent.run(task, context)


node.run()
```

A **swarm** is just a shared name. With `mdns=True`, every node on your LAN with the same swarm name finds the others automatically — nothing to configure, no server to run. (Different networks? Point nodes at a `seeds=["host:9999"]` — a seed is any other node, a first contact, not a coordinator.)

## 2. Ask it for something

```bash
$ sn ask myteam.example.com "Review this diff" --context url=https://github.com/org/repo/pull/1
ask: 019e4ab0-1d0d-709a-...
waiting for ACKs and replies... press Ctrl+C to stop
✓ reviewer acked
- reviewer: LGTM after fixing tests
```

Three things happened. The ask was **broadcast** to the swarm. The reviewer **ACKed** — "I saw this, I'm choosing to help" — nothing assigned it the work. Then it ran its handler in the background and **replied** when done. The RPC itself returned instantly, so a handler that spends ten minutes inside a model doesn't hold a socket open.

The same thing in code:

```python
broadcast = await node.broadcast("synapse.ask", "Review this diff")

for reply in node.replies(broadcast):
    print(reply.peer.name, reply.result)
```

## 3. Add teammates

Start more nodes with the same swarm name — a `tester`, a `security` reviewer. Each broadcast now creates one **shared conversation**: every receiver gets the same nonce, and each decides for itself whether to wade in, reply, or stay silent. You can watch the whole thing live:

```bash
sn watch myteam.example.com
```

<picture>
<img width="1268" alt="sn watch" src="https://github.com/user-attachments/assets/3b08371b-2a1b-465f-8939-cbf0a0ba219c" />
</picture>

Conversations are event logs. `message`, `ack`, and `reply` are built in; emit your own kinds with `node.emit_conversation_event(...)` and subscribe with `@node.on("conversation.reply")`.

## 4. Put an architect in charge

Broadcasts are democratic — sometimes you want exactly one node to do each piece of work. That's the teams layer:

```python
# architect.py
from synapse_p2p.teams import Team

team = Team(node)

task = await team.offer("implement the parser", spec={"file": "parser.py"}, requires=["python"])
result = await team.wait(task, timeout=600)
```

```python
# coder.py
from synapse_p2p.teams import Assignment, Worker

worker = Worker(node)  # a node with capabilities=["python"]


@worker.task
async def implement(assignment: Assignment) -> dict:
    await assignment.progress("starting")
    return {"diff": await my_agent.run(assignment.title, assignment.spec)}
```

Workers whose capabilities match the `requires` race to claim; the team grants each task to the first claimant, so exactly one runs it. Every task is its own conversation — offer, claim, grant, progress, done — that the whole swarm can watch.

And it's built for work that takes forever:

- While a handler runs, the worker heartbeats automatically. A task can take hours with no manual progress calls.
- If a coder dies or goes quiet past its **lease** (`Team(lease=300)`), the task is re-offered. Workers that join late pick up work that's still open. `max_attempts` caps the retries.
- Delivery is at-least-once; the first `task.done` wins.

The architect and the coders don't have to run the same model. An architect on Claude reviewing work from coders on GPT is just... two processes. See [`examples/coding_team`](./examples/coding_team) — it runs offline, no API keys.

## 5. Leave it running

For a team that lives for months, three settings on the node:

```python
from synapse_p2p import Node, SqliteConversationLog

node = Node(
    name="architect",
    swarm="myteam.example.com",
    conversation_log=SqliteConversationLog("architect.db"),  # survive restarts
    conversation_max_events=100,                             # compact long threads
    conversation_retention=7 * 86_400,                       # forget quiet conversations
)
```

When a conversation passes `conversation_max_events`, older events get folded into a single `summary` event — the opening message and the recent tail stay verbatim. The default summarizer is a plain digest; hand the job to your model instead:

```python
@node.summarizer
async def summarize(events):
    return await my_llm_summarize(events)
```

Conversations quiet for longer than `conversation_retention` are pruned entirely, and events older than the window are refused, so nothing leaks back in through gossip. Compaction + retention + SQLite = bounded memory and disk, forever.

A restarted node catches up on what it missed (`await node.sync_conversation(peer, conversation_id)`), and a restarted architect rebuilds its task table straight from the log (`team.restore()`) — finished tasks come back with results, unfinished ones get re-offered.

## Also in the box

**Schedules.** Nodes can wake up on an interval, a cron expression, or the actual sun:

```python
from synapse_p2p import cron, every, solar


@node.periodic(solar("sunrise", latitude=51.5, longitude=-0.1, tz="Europe/London"))
async def morning_check() -> None:
    await node.broadcast("garden.status")
```

**Agent cards.** Publish metadata peers can fetch — `node.artifact("agent-card", {...})` — and introspect any peer with `_node.info`, `_node.capabilities`, `_synapse.methods`.

**Liveness.** Nodes heartbeat their peers; hook `@node.on("peer.joined")` and `@node.on("peer.offline")`.

**Examples.** Each folder in [`examples/`](./examples) is runnable and has its own README — from [`basic_rpc`](./examples/basic_rpc) (two files) to [`stock_trading_team`](./examples/stock_trading_team) and [`coding_team`](./examples/coding_team).

## What Synapse is not

No planning, no memory, no consensus, no auth policy, no NAT traversal, no hosted registry, no opinion about how agents think. Those belong above Synapse. (Two exceptions are on the roadmap because they belong in the substrate: node identity with signed gossip, and a relay mode so seeds can bridge peers that can't dial each other. Until then, treat the swarm's network as the security boundary — a LAN or a tailnet, not the open internet.)

> nodes + discovery + capabilities + conversations + artifacts + heartbeats + schedules + a tiny protocol

<details>
<summary><b>Protocol details</b></summary>

Wire format: a 4-byte unsigned big-endian length header, then a MsgPack payload. Frames up to 4 MiB by default (`Node(max_upload_size=...)`, `Client(max_download_size=...)`).

```python
# request
{"type": "request", "id": "request-id", "endpoint": "sum", "args": [1, 2], "kwargs": {}}
# response
{"type": "response", "id": "request-id", "ok": True, "result": 3, "error": None}
```

Any async function is an endpoint:

```python
@node.endpoint("sum", description="Add two numbers")
async def sum(a: int, b: int) -> int:
    return a + b
```

```python
from synapse_p2p import Client

result = await Client("127.0.0.1", 9999).call("sum", 1, 2)  # 3
```

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
| `_synapse.conversation.event` | gossip a shared conversation event |
| `_synapse.conversation.sync` | serve a conversation's events to a late joiner |
| `_synapse.conversation.list` | list locally known conversation ids |
| `_synapse.artifacts` | list advertised artifacts |
| `_synapse.artifact.get` | fetch one advertised artifact |
| `_node.info` | name, role, description, capabilities |
| `_node.capabilities` | machine-readable capabilities |
| `_node.ask` | delegate directly to the node ask handler |
| `synapse.ask` | swarm-facing ask endpoint used by `sn ask` |

Debug logging:

```python
from loguru import logger

logger.enable("synapse_p2p")
```

</details>

<details>
<summary><b>Synapse vs A2A</b></summary>

A2A is a full agent interoperability protocol. Synapse is much smaller. Use A2A when you need a formal cross-vendor protocol with task lifecycles, message parts, and enterprise integration points. Use Synapse when you want to build a swarm quickly.

| A2A | Synapse |
| --- | --- |
| Agent protocol | Swarm substrate |
| HTTP / JSON-RPC oriented | Length-prefixed MsgPack over TCP |
| Formal task lifecycle | Simple RPC, ask, and broadcast |
| Agent cards are central | Agent cards are optional artifacts |
| More concepts to implement | One main primitive: `Node` |
| Best for interoperability | Best for local-first swarms and fast experimentation |

</details>
