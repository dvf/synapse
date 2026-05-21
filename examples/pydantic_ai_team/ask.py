import asyncio

from examples.pydantic_ai_team.common import SWARM
from synapse_p2p import Node

node = Node(
    name="lead",
    role="team lead",
    swarm=SWARM,
    capabilities=["broadcast"],
    mdns=True,
)


async def main() -> None:
    await node.start()
    await node.join()
    await asyncio.sleep(1)

    broadcast = await node.broadcast(
        "team.question",
        "We are adding a live swarm CLI. Who can help, and what should we watch out for?",
    )
    print(f"broadcast: {broadcast.nonce}")

    seen = 0
    while seen < 3:
        await asyncio.sleep(0.5)
        replies = node.replies(broadcast)
        for reply in replies[seen:]:
            print(f"{reply.peer.name}: {reply.result}")
        seen = len(replies)

    await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
