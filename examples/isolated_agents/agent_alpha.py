import asyncio

from synapse_p2p import Client, Node

node = Node(
    name="alpha",
    role="coordinator",
    swarm="foo.electron.network",
    capabilities=["delegate"],
    address="127.0.0.1",
    port=9999,
    mdns=True,
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
    print("alpha listening on 127.0.0.1:9999")
    print("start beta, then run: python examples/isolated_agents/ask_alpha.py")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
