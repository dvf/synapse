import asyncio

from examples.pydantic_ai_team.common import SWARM, make_agent, run_agent
from synapse_p2p import Broadcast, Node

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


@node.endpoint("team.question")
async def answer(question: str, broadcast: Broadcast) -> dict[str, str]:
    output = await run_agent(brain, test_model, question)
    await node.reply(broadcast, {"role": node.role, "answer": output})
    return {"accepted": "true"}


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
