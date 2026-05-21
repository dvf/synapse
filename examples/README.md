# Synapse examples

Small, clean examples for the core Synapse ideas.

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

After installing, the CLI is available as `sn`:

```bash
uv run sn --help
# or, inside an activated venv:
sn --help
```

Run examples with `uv run` if you are using uv:

```bash
uv run python local_mdns_swarm/reviewer.py
```

Notes:

- Nodes listen on all interfaces by default and advertise a reachable local IP.
- mDNS examples require devices/processes to be on the same local network and may need firewall permission.
- Seed examples default to same-machine seeds. For another machine, point the seed at its advertised address, for example `SYNAPSE_BOOTSTRAP=192.168.1.25:9000`.
- The Pydantic AI example uses `TestModel` by default, so it works without API keys.
- To use a real model, set `PYDANTIC_AI_MODEL` and the provider's API key, for example:

```bash
export PYDANTIC_AI_MODEL="openai:gpt-5.2"
export OPENAI_API_KEY="..."
```

## CLI quick look

```bash
sn watch foo.electron.network
sn broadcast foo.electron.network "hello swarm"
sn list-swarms
```

## 1. Basic node RPC

```bash
python example_node.py
python example_client.py
```

A node exposes `sum`. A client calls it.

## 2. Two isolated nodes communicate

```bash
python isolated_agents/agent_alpha.py
python isolated_agents/agent_beta.py
python isolated_agents/ask_alpha.py
```

Beta joins Alpha through a seed. Both also advertise with mDNS, so `sn list-swarms` can see the swarm. The client asks Alpha; Alpha delegates to Beta.

On one machine, run the commands as-is. Across two machines, start Alpha first, copy the address it prints, then run Beta and the asker with:

```bash
SYNAPSE_ALPHA=192.168.1.25:9999 python isolated_agents/agent_beta.py
SYNAPSE_ALPHA=192.168.1.25:9999 python isolated_agents/ask_alpha.py
```

## 3. Bootstrap team trio

```bash
python bootstrap_team_trio/bootstrap.py
python bootstrap_team_trio/planner.py
python bootstrap_team_trio/reviewer.py
python bootstrap_team_trio/coder.py
python bootstrap_team_trio/inspect_team.py
```

A bootstrap node helps planner, reviewer, and coder find each other.

On one machine, run the commands as-is. Across machines, start the bootstrap first, copy the address it prints, then run the others with:

```bash
SYNAPSE_BOOTSTRAP=192.168.1.25:9000 python bootstrap_team_trio/planner.py
SYNAPSE_BOOTSTRAP=192.168.1.25:9000 python bootstrap_team_trio/reviewer.py
SYNAPSE_BOOTSTRAP=192.168.1.25:9000 python bootstrap_team_trio/coder.py
SYNAPSE_BOOTSTRAP=192.168.1.25:9000 python bootstrap_team_trio/inspect_team.py
```

## 4. Local mDNS swarm

```bash
python local_mdns_swarm/reviewer.py
python local_mdns_swarm/coder.py
python local_mdns_swarm/ask.py
```

Nodes with `mdns=True` discover each other on the same LAN without seeds.

## 5. Pydantic AI team

```bash
python pydantic_ai_team/reviewer.py
python pydantic_ai_team/coder.py
python pydantic_ai_team/product.py
python pydantic_ai_team/ask.py
```

A reviewer, coder, and product node use Pydantic AI, discover each other with mDNS, and reply into one broadcast conversation. It runs without API keys via `TestModel`; set `PYDANTIC_AI_MODEL` to use a real model.
