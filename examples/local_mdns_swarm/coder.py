import asyncio

from synapse_p2p import Broadcast, Node, Peer

node = Node(
    name="coder",
    role="coder",
    swarm="foo.electron.network",
    capabilities=["python", "implementation"],
    mdns=True,
)


@node.on("peer.joined")
async def joined(peer: Peer) -> None:
    print(f"joined: {peer.name} at {peer.address}:{peer.port}")


@node.endpoint("team.question")
async def answer(question: str, broadcast: Broadcast) -> dict:
    await node.reply(broadcast, {"from": node.name, "answer": "I can implement it."})
    return {"accepted": True}


async def main() -> None:
    await node.start()
    try:
        await node.join()
        print(f"coder online at {node.address}:{node.port}")
        print("waiting for local Synapse nodes...")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
