import os
from contextlib import nullcontext
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

SWARM = "foo.electron.network"
MODEL = os.getenv("PYDANTIC_AI_MODEL")


def make_agent(instructions: str, fallback: str) -> tuple[Agent, TestModel | None]:
    agent = Agent(MODEL or "openai:gpt-5.2", instructions=instructions)
    if MODEL:
        return agent, None
    return agent, TestModel(custom_output_text=fallback)


async def run_agent(agent: Agent, test_model: TestModel | None, prompt: str) -> Any:
    context = agent.override(model=test_model) if test_model is not None else nullcontext()
    with context:
        result = await agent.run(prompt)
    return result.output
