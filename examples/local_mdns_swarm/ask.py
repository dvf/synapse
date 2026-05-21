import asyncio

from synapse_p2p import BroadcastReply, Node

node = Node(
    name="asker",
    role="coordinator",
    swarm="foo.electron.network",
    mdns=True,
)


@node.on("peer.joined")
async def joined(peer) -> None:
    print(f"found: {peer.name} at {peer.address}:{peer.port}")


async def wait_for_replies(broadcast, minimum: int = 1, timeout: float = 5) -> list[BroadcastReply]:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        replies = node.replies(broadcast)
        if len(replies) >= minimum:
            return replies
        await asyncio.sleep(0.1)
    return node.replies(broadcast)


async def main() -> None:
    await node.start()
    try:
        print(f"asker online at {node.address}:{node.port}")
        print("looking for local Synapse nodes...")
        await node.join(wait=2)

        peers = list(node.peers.values())
        if not peers:
            print("no peers found")
            print("start reviewer.py and coder.py, then run this again")
            return

        print("asking swarm: Who can help ship this feature?")
        broadcast = await node.broadcast("team.question", "Who can help ship this feature?")
        replies = await wait_for_replies(broadcast, minimum=len(peers), timeout=5)

        if not replies:
            print("no replies")
            return

        for reply in replies:
            print(f"{reply.peer.name}: {reply.result}")
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
