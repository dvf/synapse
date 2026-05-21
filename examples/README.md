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
uv run python examples/local_mdns_swarm/reviewer.py
```

Notes:

- mDNS examples require devices/processes to be on the same local network and may need firewall permission.
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
python examples/isolated_agents/agent_alpha.py
python examples/isolated_agents/agent_beta.py
python examples/isolated_agents/ask_alpha.py
```

Beta joins Alpha through a seed. Both also advertise with mDNS, so `sn list-swarms` can see the swarm. The client asks Alpha; Alpha delegates to Beta.

## 3. Bootstrap team trio

```bash
python examples/bootstrap_team_trio/bootstrap.py
python examples/bootstrap_team_trio/planner.py
python examples/bootstrap_team_trio/reviewer.py
python examples/bootstrap_team_trio/coder.py
python examples/bootstrap_team_trio/inspect_team.py
```

A bootstrap node helps planner, reviewer, and coder find each other.

## 4. Local mDNS swarm

```bash
python examples/local_mdns_swarm/reviewer.py
python examples/local_mdns_swarm/coder.py
python examples/local_mdns_swarm/ask.py
```

Nodes with `mdns=True` discover each other on the same LAN without seeds.

## 5. Pydantic AI team

```bash
python examples/pydantic_ai_team/bootstrap.py
python examples/pydantic_ai_team/reviewer.py
python examples/pydantic_ai_team/coder.py
python examples/pydantic_ai_team/product.py
python examples/pydantic_ai_team/ask.py
```

A reviewer, coder, and product node use Pydantic AI and reply into one broadcast conversation. It runs without API keys via `TestModel`; set `PYDANTIC_AI_MODEL` to use a real model.
