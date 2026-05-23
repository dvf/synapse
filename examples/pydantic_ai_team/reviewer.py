import asyncio

from examples.pydantic_ai_team.common import SWARM, make_agent, run_agent
from synapse_p2p import Node

brain, test_model = make_agent(
    "You are a concise senior code reviewer. Reply with risks and suggested tests.",
    "Reviewer: I can review the diff. I would check edge cases, error handling, and tests.",
)

node = Node(
    name="reviewer",
    role="code reviewer",
    swarm=SWARM,
    capabilities=["code-review", "risk-analysis"],
    mdns=True,
)

node.artifact(
    "agent-card",
    {
        "name": node.name,
        "role": node.role,
        "capabilities": ["code-review", "risk-analysis"],
        "description": "Reviews code and points out risks and missing tests.",
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
        print(f"reviewer online at {node.address}:{node.port}")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
