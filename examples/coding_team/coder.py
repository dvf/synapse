"""A coder node: claims tasks it can do, implements them, narrates progress.

Run several of these (they race to claim, the architect grants one):

    CODER_NAME=coder-1 uv run python -m examples.coding_team.coder
    CODER_NAME=coder-2 uv run python -m examples.coding_team.coder
"""

import asyncio
import os

from examples.coding_team.common import CODER_MODEL, SWARM, make_agent, run_agent
from synapse_p2p import Node
from synapse_p2p.teams import Assignment, Worker

brain, test_model = make_agent(
    CODER_MODEL,
    "You are a senior implementation engineer on a distributed agent team. "
    "You receive one task with a spec. Reply with the implementation: code, "
    "tests, and a one-paragraph note for the reviewing architect.",
    "Coder: implemented the task with a small patch, added tests, all passing.",
)

node = Node(
    name=os.getenv("CODER_NAME", "coder-1"),
    role="implementation",
    swarm=SWARM,
    capabilities=["python", "implementation", "tests"],
    mdns=True,
)

node.artifact(
    "agent-card",
    {
        "name": node.name,
        "role": node.role,
        "model": CODER_MODEL or "test-model",
        "capabilities": ["python", "implementation", "tests"],
        "description": "Claims implementation tasks and returns patches with tests.",
    },
    mime_type="application/vnd.synapse.agent-card+json",
)

worker = Worker(node)


@worker.task
async def implement(assignment: Assignment) -> dict:
    await assignment.progress(f"{node.name} starting", title=assignment.title)
    prompt = f"Task: {assignment.title}\nSpec: {assignment.spec}"
    output = await run_agent(brain, test_model, prompt)
    await assignment.progress(f"{node.name} finished, submitting result")
    return {"implementation": output, "by": node.name}


async def main() -> None:
    await node.start()
    try:
        await node.join()
        print(f"{node.name} online at {node.address}:{node.port}, waiting for offers")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
