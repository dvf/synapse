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

Synapse is a small peer-to-peer substrate for agent infrastructure. Give each process a `Node` and it gets a name, peers, capabilities, RPC endpoints, shared conversations, and periodic tasks.

Synapse is not the agent brain. It's the swarm layer agents stand on. A node can wrap an LLM agent, a script, a service, or a sensor, and it doesn't matter what model (if any) is behind it.

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

## Install

```bash
uv add synapse-p2p     # or: pip install synapse-p2p
sn --help              # the CLI
```

## The mental model

| Word | Meaning |
| --- | --- |
| **Node** | A running Synapse participant. You create one with `Node(...)`. |
| **Swarm** | Nodes with the same `swarm` name. They find and heartbeat each other. |
| **Capability** | A short advertised skill like `code-review` or `watering`. |
| **Endpoint** | An async function peers can call over RPC. |
| **Conversation** | A shared, gossiped event log that any node can wade into. |
| **Agent** | Your higher-level logic: an LLM loop, workflow, script, or automation. |

## Discovery

On the same LAN, mDNS needs zero config:

```python
node = Node(name="reviewer", swarm="foo.electron.network", mdns=True)
await node.start()
await node.join()
```

Across networks, use a seed. A seed is just another Synapse node: a first contact point, not a coordinator. Once joined, nodes exchange known peers and talk directly.

```python
node = Node(name="planner", swarm="foo.electron.network", seeds=["bootstrap.foo.electron.network:9999"])
```

## RPC

Any async function can be an endpoint:

```python
node = Node(name="calculator", port=9999)


@node.endpoint("sum", description="Add two numbers")
async def sum(a: int, b: int) -> int:
    return a + b
```

```python
from synapse_p2p import Client

result = await Client("127.0.0.1", 9999).call("sum", 1, 2)  # 3
```

Peers are self-describing: `_node.info`, `_node.capabilities`, and `_synapse.methods` tell you what a node is and what it can do. Nodes can also publish agent cards and other metadata with `node.artifact(...)`.

## Ask: delegate work

Give a node a default task handler:

```python
node = Node(name="reviewer", capabilities=["code-review"])


@node.ask
async def handle(task: str, context: dict):
    return await my_agent.run(task, context)
```

Ask one known peer directly:

```python
result = await Client.from_peer(peer).call("_node.ask", "Review this diff", context={"diff": diff})
```

Or ask the whole swarm when you don't know who should answer:

```python
broadcast = await node.broadcast("synapse.ask", "Review this diff", context={"diff": diff})
```

Nodes that opt in will ACK the conversation, run their handler in the background, and reply when they're done. The RPC itself returns immediately, so a handler that spends ten minutes inside an LLM doesn't hold a socket open. Read whatever came back:

```python
for reply in node.replies(broadcast):
    print(reply.peer.name, reply.result)
```

The same flow from the terminal:

```bash
sn ask foo.electron.network "Review this diff"
```

## Conversations

A broadcast creates a shared conversation. Every receiver gets the same nonce, and any node can reply, ACK, or ignore it. Synapse never decides who should answer.

```python
broadcast = await node.broadcast("team.question", "Who can review this diff?")
```

```python
@node.endpoint("team.question")
async def answer(question: str, broadcast: Broadcast) -> dict:
    await node.ack(broadcast, {"seen": True})
    await node.reply(broadcast, {"answer": "I can help"})
    return {"accepted": True}
```

Watch events live, or read the log after the fact:

```python
@node.on("conversation.reply")
async def on_reply(event: ConversationEvent) -> None:
    print(event.peer.name, event.payload)


for event in node.conversation(broadcast):
    print(event.kind, event.peer.name, event.payload)
```

The built-in event kinds are small conventions: `message`, `ack`, and `reply`. Emit your own with `node.emit_conversation_event(...)`.

## Conversation history

The event log is in-memory by default. Swap in SQLite if it should survive restarts:

```python
from synapse_p2p import Node, SqliteConversationLog

node = Node(name="architect", conversation_log=SqliteConversationLog("conversations.db"))
```

A node that joined late (or rebooted) can pull a conversation it missed from any peer:

```python
await node.sync_conversation(peer, conversation_id)
```

Long conversations compact themselves. Past `conversation_max_events`, older events get folded into a single `summary` event; the opening message and the most recent events are kept as-is. The default summarizer is a plain digest, but you probably want your model to do it:

```python
node = Node(name="architect", conversation_max_events=100, conversation_keep_recent=25)


@node.summarizer
async def summarize(events: list[ConversationEvent]) -> str:
    return await my_llm_summarize(events)
```

Compaction is local. Each node compresses its own copy of the shared log, and gossip can't resurrect compacted events. There's also `node.compact_conversation(...)` if you'd rather do it by hand.

For nodes that run indefinitely, set `conversation_retention` (seconds) and whole conversations get pruned after going quiet for that long. Events older than the retention window are refused outright, so a pruned conversation can't leak back in through gossip. With retention, compaction, and a SQLite log, a node can run forever on bounded memory and disk.

## Teams

`synapse_p2p.teams` is an optional task layer built on conversation events. A `Team` offers work, `Worker`s claim tasks that match their capabilities, and the team grants each task to the first claimant. Exactly one worker runs each task.

```python
from synapse_p2p.teams import Assignment, Team, Worker

# architect process (say, Claude)
team = Team(node)
task = await team.offer("implement the parser", spec={"file": "parser.py"}, requires=["python"])
result = await team.wait(task, timeout=600)

# coder process (say, GPT)
worker = Worker(coder_node)


@worker.task
async def implement(assignment: Assignment) -> dict:
    await assignment.progress("starting")
    return {"diff": await my_agent.run(assignment.title, assignment.spec)}
```

Each task is one conversation: `task.offer`, `task.claim`, `task.grant`, `task.progress`, then `task.done` or `task.failed`. Every peer can watch it, late joiners can sync it, and long threads compact like anything else. See [`examples/coding_team`](./examples/coding_team) for an architect on one model reviewing work from coders on another.

The layer is built for long-running work:

- Progress events renew a task's **lease** (`Team(lease=300)`). Workers heartbeat automatically while a handler runs, so a task can take hours without any manual progress calls.
- If an assignee dies or goes quiet past its lease, the team re-offers the task. Unclaimed offers are re-announced too, so a worker that joins late still finds existing work. Cap retries with `max_attempts`.
- A team backed by a SQLite log can rebuild its task table after a restart with `team.restore()` — finished tasks come back with their results, unfinished ones get re-offered.
- Set `task_retention` to drop finished tasks after a while, so a team that offers work forever doesn't grow without bound.

Delivery is at-least-once: a partitioned-but-alive worker can mean a task runs twice. The first `task.done` wins.

## Periodic tasks

```python
from synapse_p2p import cron, every, solar


@node.periodic(every(seconds=30))
async def refresh_cache() -> None: ...


@node.periodic(cron("0 9 * * mon-fri", tz="Europe/London"))
async def weekday_digest() -> None: ...


@node.periodic(solar("sunrise", latitude=51.5, longitude=-0.1, tz="Europe/London"))
async def sunrise_job() -> None: ...
```

Handlers must be `async def`. A bare number means seconds. The first run fires at startup, and exceptions are logged without killing the schedule. Solar events go from `sunrise` all the way to `astronomical_twilight_end`.

## Heartbeats

Nodes heartbeat known peers and mark stale ones offline. Tune with `heartbeat_interval` and `peer_timeout`.

```python
@node.on("peer.joined")
async def joined(peer: Peer) -> None: ...


@node.on("peer.offline")
async def offline(peer: Peer) -> None: ...
```

## CLI

```bash
sn watch foo.electron.network        # live view of joins, heartbeats, conversations
sn ask foo.electron.network "Who can help?"
sn broadcast foo.electron.network "Ship status?"
sn list-swarms
```

<picture>
<img width="1268" alt="sn watch" src="https://github.com/user-attachments/assets/3b08371b-2a1b-465f-8939-cbf0a0ba219c" />
</picture>

## Examples

| Example | What it demonstrates |
| --- | --- |
| [`basic_rpc`](./examples/basic_rpc) | The smallest node/client pair. |
| [`isolated_agents`](./examples/isolated_agents) | Delegation through a known seed. |
| [`bootstrap_team_trio`](./examples/bootstrap_team_trio) | Bootstrap discovery, ask handlers, agent cards. |
| [`local_mdns_swarm`](./examples/local_mdns_swarm) | Zero-config discovery, ACKs and replies in one conversation. |
| [`pydantic_ai_team`](./examples/pydantic_ai_team) | Pydantic AI agents behind nodes. |
| [`periodic_tasks`](./examples/periodic_tasks) | Interval, cron, and solar jobs. |
| [`stock_trading_team`](./examples/stock_trading_team) | Analyst/news/trader swarm with a paper exchange. |
| [`coding_team`](./examples/coding_team) | An architect and coders on different models, via the teams layer. |

Each folder has a README with exact run commands.

## What Synapse is not

Synapse does not implement planning, memory, consensus, auth policy, NAT traversal, hosted registries, or UX. Those belong above Synapse.

Two exceptions are on the roadmap because they belong in the substrate itself: node identity with signed gossip for untrusted networks, and a relay mode so seeds can bridge peers that can't dial each other.

> nodes + discovery + capabilities + conversations + artifacts + heartbeats + schedules + a tiny protocol

<details>
<summary><b>Protocol details</b></summary>

Wire format: a 4-byte unsigned big-endian length header, then a MsgPack payload. Frames up to 4 MiB are accepted by default (`Node(max_upload_size=...)`, `Client(max_download_size=...)`), which is plenty for diffs and documents.

```python
# request
{"type": "request", "id": "request-id", "endpoint": "sum", "args": [1, 2], "kwargs": {}}
# response
{"type": "response", "id": "request-id", "ok": True, "result": 3, "error": None}
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

No required task state machine, no server/client ceremony inside a swarm, no hosted registry, no opinion about how agents think.

</details>
