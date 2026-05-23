import asyncio

from synapse_p2p import Node, Peer

node = Node(
    name="reviewer",
    role="reviewer",
    swarm="foo.electron.network",
    capabilities=["code-review"],
    mdns=True,
)

node.artifact(
    "agent-card",
    {
        "name": node.name,
        "role": node.role,
        "capabilities": ["code-review"],
        "description": "Reviews a task and returns concise feedback.",
    },
    mime_type="application/vnd.synapse.agent-card+json",
    description="Self-description for peers that understand agent cards.",
)


@node.on("peer.joined")
async def joined(peer: Peer) -> None:
    print(f"joined: {peer.name} at {peer.address}:{peer.port}")


@node.ask
async def answer(task: str, context: dict) -> dict:
    return {
        "from": node.name,
        "answer": "I can review it.",
        "task": task,
        "context": context,
    }


async def main() -> None:
    await node.start()
    try:
        await node.join()
        print(f"reviewer online at {node.address}:{node.port}")
        print("waiting for local Synapse nodes...")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
