import asyncio
import os

from synapse_p2p import Client


async def main() -> None:
    host, port = os.getenv("SYNAPSE_BOOTSTRAP", "127.0.0.1:9000").rsplit(":", 1)
    peers = await Client(host, int(port)).peers()
    print("Discovered peers:")
    for peer in peers:
        print(
            f"- {peer.name} kind={peer.kind} "
            f"at {peer.address}:{peer.port} capabilities={peer.capabilities}"
        )


if __name__ == "__main__":
    asyncio.run(main())
