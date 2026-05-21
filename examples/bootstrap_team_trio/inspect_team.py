import asyncio

from synapse_p2p import Client


async def main() -> None:
    peers = await Client("127.0.0.1", 9000).peers()
    print("Discovered peers:")
    for peer in peers:
        print(
            f"- {peer.name} kind={peer.kind} "
            f"at {peer.address}:{peer.port} capabilities={peer.capabilities}"
        )


if __name__ == "__main__":
    asyncio.run(main())
