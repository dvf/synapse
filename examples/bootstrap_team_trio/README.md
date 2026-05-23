# Bootstrap team trio

A seed/bootstrap node helps a planner, reviewer, and coder find each other.

Run in separate terminals:

```bash
uv run python examples/bootstrap_team_trio/bootstrap.py
uv run python examples/bootstrap_team_trio/planner.py
uv run python examples/bootstrap_team_trio/reviewer.py
uv run python examples/bootstrap_team_trio/coder.py
uv run python examples/bootstrap_team_trio/inspect_team.py
```

What it shows:

- The bootstrap node is only first contact; it is not an orchestrator.
- Workers join through `SYNAPSE_BOOTSTRAP` / `127.0.0.1:9000`.
- Each worker exposes an `@node.ask` handler.
- Each worker publishes an `agent-card` artifact.
- `inspect_team.py` lists peers and fetches their agent cards.

Across machines, start the bootstrap first, copy its address, then run the others with:

```bash
SYNAPSE_BOOTSTRAP=192.168.1.25:9000 uv run python examples/bootstrap_team_trio/planner.py
SYNAPSE_BOOTSTRAP=192.168.1.25:9000 uv run python examples/bootstrap_team_trio/reviewer.py
SYNAPSE_BOOTSTRAP=192.168.1.25:9000 uv run python examples/bootstrap_team_trio/coder.py
SYNAPSE_BOOTSTRAP=192.168.1.25:9000 uv run python examples/bootstrap_team_trio/inspect_team.py
```
