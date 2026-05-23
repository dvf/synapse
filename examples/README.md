# Synapse examples

Small, tangible examples for the core Synapse ideas.

## Prerequisites

From the repository root, install Synapse and the example dependencies:

```bash
uv sync --extra examples
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[examples]"
```

Run examples with `uv run` if you are using uv:

```bash
uv run python examples/local_mdns_swarm/reviewer.py
```

Notes:

- Nodes listen on all interfaces by default and advertise a reachable local IP.
- mDNS examples require devices/processes to be on the same local network and may need firewall permission.
- Seed examples default to same-machine seeds. For another machine, point the seed at its advertised address, for example `SYNAPSE_BOOTSTRAP=192.168.1.25:9000`.
- The Pydantic AI example uses `TestModel` by default, so it works without API keys.

## CLI quick look

```bash
uv run sn watch foo.electron.network
uv run sn ask foo.electron.network "hello swarm"
uv run sn broadcast foo.electron.network "hello swarm"
uv run sn list-swarms
```

Most agent examples publish an `agent-card` artifact and use shared conversation atomics:

- `synapse.ask` starts a swarm ask.
- Interested nodes ACK when they wade in.
- Replies are grouped by the shared conversation nonce.
- Agent cards are advertised through `_synapse.artifacts` and fetched with `_synapse.artifact.get`.

## Examples

| Example | What it demonstrates |
| --- | --- |
| [`basic_rpc`](./basic_rpc) | Smallest direct RPC node/client pair. |
| [`isolated_agents`](./isolated_agents) | One node delegates to another through a known seed. |
| [`bootstrap_team_trio`](./bootstrap_team_trio) | Bootstrap discovery, ask handlers, and fetching agent cards. |
| [`local_mdns_swarm`](./local_mdns_swarm) | Zero-config local discovery plus ACKs/replies in one conversation. |
| [`pydantic_ai_team`](./pydantic_ai_team) | Pydantic AI agents behind Synapse nodes. |
| [`periodic_tasks`](./periodic_tasks) | Interval, cron, and solar jobs in a garden-caretaker node. |
| [`stock_trading_team`](./stock_trading_team) | Analyst/news/trader swarm with a dumb paper exchange API and market-hours periodic scans. |

Each folder has its own README with exact run commands.
