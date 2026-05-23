import asyncio
import os
from typing import Any, cast

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
        try:
            card = cast(
                dict[str, Any],
                await Client.from_peer(peer).call("_synapse.artifact.get", "agent-card"),
            )
        except RuntimeError:
            continue
        print(f"  agent-card: {card['content']}")


if __name__ == "__main__":
    asyncio.run(main())
