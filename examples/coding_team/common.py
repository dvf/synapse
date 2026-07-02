import os
from contextlib import nullcontext
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

SWARM = "team.electron.network"

# Set these to real models to run the demo live, e.g.
#   ARCHITECT_MODEL=anthropic:claude-fable-5 CODER_MODEL=openai:gpt-5.5
# Unset, the demo runs offline against pydantic-ai's TestModel.
ARCHITECT_MODEL = os.getenv("ARCHITECT_MODEL")
CODER_MODEL = os.getenv("CODER_MODEL")


def make_agent(
    model: str | None, instructions: str, fallback: str
) -> tuple[Agent, TestModel | None]:
    if model:
        return Agent(model, instructions=instructions), None
    test_model = TestModel(custom_output_text=fallback)
    return Agent(test_model, instructions=instructions), test_model


async def run_agent(agent: Agent, test_model: TestModel | None, prompt: str) -> Any:
    context = agent.override(model=test_model) if test_model is not None else nullcontext()
    with context:
        result = await agent.run(prompt)
    return result.output
