import asyncio

from synapse_p2p import Client, Node

node = Node(
    name="alpha",
    role="coordinator",
    swarm="foo.electron.network",
    capabilities=["delegate"],
    port=9999,
    mdns=True,
)

node.artifact(
    "agent-card",
    {
        "name": node.name,
        "role": node.role,
        "capabilities": ["delegate"],
        "description": "Coordinates work and delegates tasks to beta.",
    },
    mime_type="application/vnd.synapse.agent-card+json",
)


@node.endpoint("alpha.ask_beta", description="Ask beta to handle a task")
async def ask_beta(task: str):
    beta = next(peer for peer in node.peers.values() if peer.name == "beta")

    return await Client.from_peer(beta).call(
        "_node.ask",
        task,
        context={"from": "alpha"},
    )


async def main() -> None:
    await node.start()
    try:
        print(f"alpha listening on {node.address}:{node.port}")
        print("start beta, then run: python examples/isolated_agents/ask_alpha.py")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
