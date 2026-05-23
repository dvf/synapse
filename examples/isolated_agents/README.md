# Isolated agents

Two nodes communicate through a known seed address.

Run in three terminals:

```bash
uv run python examples/isolated_agents/agent_alpha.py
uv run python examples/isolated_agents/agent_beta.py
uv run python examples/isolated_agents/ask_alpha.py
```

What it shows:

- Alpha exposes a custom endpoint, `alpha.ask_beta`.
- Beta joins Alpha through a seed and exposes an `@node.ask` handler.
- The client calls Alpha; Alpha delegates to Beta with `_node.ask`.
- Alpha and Beta both publish `agent-card` artifacts.

Across machines, start Alpha first, copy its address, then run Beta and the asker with:

```bash
SYNAPSE_ALPHA=192.168.1.25:9999 uv run python examples/isolated_agents/agent_beta.py
SYNAPSE_ALPHA=192.168.1.25:9999 uv run python examples/isolated_agents/ask_alpha.py
```
