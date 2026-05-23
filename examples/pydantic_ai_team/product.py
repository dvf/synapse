import asyncio

from examples.pydantic_ai_team.common import SWARM, make_agent, run_agent
from synapse_p2p import Node

brain, test_model = make_agent(
    "You are a concise product strategist. Reply with user value and launch framing.",
    "Product: I can frame it. Lead with the user benefit, reduce setup, and make the demo obvious.",
)

node = Node(
    name="product",
    role="product strategist",
    swarm=SWARM,
    capabilities=["positioning", "user-value", "launch"],
    mdns=True,
)

node.artifact(
    "agent-card",
    {
        "name": node.name,
        "role": node.role,
        "capabilities": ["positioning", "user-value", "launch"],
        "description": "Frames product value, positioning, and launch strategy.",
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
        print(f"product online at {node.address}:{node.port}")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
