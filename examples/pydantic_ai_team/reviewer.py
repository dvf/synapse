import asyncio

from examples.pydantic_ai_team.common import SEED, SWARM, make_agent, run_agent
from synapse_p2p import Broadcast, Node

brain, test_model = make_agent(
    "You are a concise senior code reviewer. Reply with risks and suggested tests.",
    "Reviewer: I can review the diff. I would check edge cases, error handling, and tests.",
)

node = Node(
    name="reviewer",
    role="code reviewer",
    swarm=SWARM,
    capabilities=["code-review", "risk-analysis"],
    seeds=[SEED],
)


@node.endpoint("team.question")
async def answer(question: str, broadcast: Broadcast) -> dict[str, str]:
    output = await run_agent(brain, test_model, question)
    await node.reply(broadcast, {"role": node.role, "answer": output})
    return {"accepted": "true"}


async def main() -> None:
    await node.start()
    await node.join()
    print(f"reviewer online at {node.address}:{node.port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
