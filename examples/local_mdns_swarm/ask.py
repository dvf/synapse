import asyncio

from synapse_p2p import Node

node = Node(
    name="asker",
    role="coordinator",
    swarm="foo.electron.network",
    mdns=True,
)


async def main() -> None:
    await node.start()
    await node.join(wait=1)

    broadcast = await node.broadcast("team.question", "Who can help ship this feature?")
    await asyncio.sleep(1)

    for reply in node.replies(broadcast):
        print(reply.result)

    await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
