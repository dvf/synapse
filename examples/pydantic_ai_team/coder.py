import asyncio

from examples.pydantic_ai_team.common import SWARM, make_agent, run_agent
from synapse_p2p import Node

brain, test_model = make_agent(
    "You are a concise implementation agent. Reply with a practical implementation plan.",
    "Coder: I can implement it. I would create a small patch, add tests, and verify behavior.",
)

node = Node(
    name="coder",
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
        "capabilities": ["python", "implementation", "tests"],
        "description": "Creates implementation plans, patches, and test ideas.",
    },
    mime_type="application/vnd.synapse.agent-card+json",
)


@node.ask
async def answer(task: str, context: dict) -> dict[str, str]:
    output = await run_agent(brain, test_model, task)
    return {"role": node.role, "answer": output, "context": str(context)}


async def main() -> None:
    await node.start()
    try:
        await node.join()
        print(f"coder online at {node.address}:{node.port}")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
