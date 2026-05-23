# Pydantic AI team

A reviewer, coder, and product strategist use Pydantic AI behind Synapse nodes.

Run in four terminals:

```bash
uv run python examples/pydantic_ai_team/reviewer.py
uv run python examples/pydantic_ai_team/coder.py
uv run python examples/pydantic_ai_team/product.py
uv run python examples/pydantic_ai_team/ask.py
```

What it shows:

- Each role is a Synapse node with a Pydantic AI agent behind `@node.ask`.
- The lead broadcasts to `synapse.ask`.
- Agents ACK when they join the conversation.
- Replies are grouped by the shared conversation nonce.
- Each agent publishes an `agent-card` artifact.

By default this uses Pydantic AI's `TestModel`, so it runs without API keys.

To use a real model:

```bash
export PYDANTIC_AI_MODEL="openai:gpt-5.2"
export OPENAI_API_KEY="..."
```
