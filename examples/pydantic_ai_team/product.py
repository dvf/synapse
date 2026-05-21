import asyncio

from examples.pydantic_ai_team.common import SWARM, make_agent, run_agent
from synapse_p2p import Broadcast, Node

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


@node.endpoint("team.question")
async def answer(question: str, broadcast: Broadcast) -> dict[str, str]:
    output = await run_agent(brain, test_model, question)
    await node.reply(broadcast, {"role": node.role, "answer": output})
    return {"accepted": "true"}


async def main() -> None:
    await node.start()
    await node.join()
    print(f"product online at {node.address}:{node.port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
