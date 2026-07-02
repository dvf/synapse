# Coding team

An architect and two coders, each free to run a different model. The architect offers tasks to the swarm, grants each one to the first coder that claims it, collects the results, and reviews them. Coders claim tasks whose `requires` match their advertised capabilities and narrate progress as they work.

Every task is a shared conversation (`conversation_id == task id`) that all peers gossip: offer, claim, grant, progress, done. The architect sets `conversation_max_events=30`, so long task threads get folded into summary events automatically.

## Run it offline

Without model env vars the agents fall back to pydantic-ai's `TestModel`, so no API keys are needed. From the repo root, in three terminals:

```bash
CODER_NAME=coder-1 uv run python -m examples.coding_team.coder
CODER_NAME=coder-2 uv run python -m examples.coding_team.coder
uv run python -m examples.coding_team.architect
```

Watch the swarm from a fourth:

```bash
uv run sn watch team.electron.network
```

## Run it with real models

```bash
export ANTHROPIC_API_KEY=... OPENAI_API_KEY=...
ARCHITECT_MODEL=anthropic:claude-fable-5 uv run python -m examples.coding_team.architect
CODER_MODEL=openai:gpt-5.5 CODER_NAME=coder-1 uv run python -m examples.coding_team.coder
```

Any pydantic-ai model string works; the swarm doesn't care what sits behind a node. To raise a coder's reasoning effort, set `model_settings` on the agent in `common.py`.

## Notes

The whole task vocabulary lives in `synapse_p2p/teams.py` and is just conversation events; nothing in the substrate is special-cased for it. Coders return from the RPC immediately and deliver results as events, so a task can take as long as the model needs. A node that joins mid-task can catch up with `node.sync_conversation(peer, task_id)`.
