# Coding team: an architect and coders on different models

A minimal heterogeneous agent team built on `synapse_p2p.teams`:

- **architect** — oversees the work. Offers tasks to the swarm, grants each to
  the first capable claimant, collects results, and reviews them with its own
  model (e.g. Claude).
- **coder-1 / coder-2** — claim tasks whose `requires` match their advertised
  capabilities, implement them with their own model (e.g. GPT), and narrate
  progress into the shared task conversation.

Every task is one shared conversation (`conversation_id == task id`) that all
peers gossip: offer → claim → grant → progress → done. The architect compacts
long task threads automatically (`conversation_max_events=30`), folding old
progress chatter into a `summary` event.

## Run it (offline)

Without model env vars the agents use pydantic-ai's `TestModel`, so the whole
flow runs with no API keys. From the repo root, in three terminals:

```bash
CODER_NAME=coder-1 uv run python -m examples.coding_team.coder
CODER_NAME=coder-2 uv run python -m examples.coding_team.coder
uv run python -m examples.coding_team.architect
```

Watch the swarm from a fourth terminal:

```bash
uv run sn watch team.electron.network
```

## Run it with real models

```bash
export ANTHROPIC_API_KEY=... OPENAI_API_KEY=...
ARCHITECT_MODEL=anthropic:claude-fable-5 uv run python -m examples.coding_team.architect
CODER_MODEL=openai:gpt-5.5 CODER_NAME=coder-1 uv run python -m examples.coding_team.coder
```

Any pydantic-ai model string works; the swarm doesn't care what model sits
behind a node. To push a coder's reasoning effort up, configure the agent's
`model_settings` in `common.py` (e.g. OpenAI's `reasoning_effort`).

## What to look at

- `synapse_p2p/teams.py` — the whole task vocabulary is ~200 lines of
  conversation events. Nothing here is special-cased in the substrate.
- Deferred results: coders return immediately at the RPC layer and deliver
  results as conversation events, so a task can take as long as the model needs.
- Late joiners can catch up on a task thread with
  `node.sync_conversation(peer, task_id)`.
