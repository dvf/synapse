import asyncio
import os

from synapse_p2p import Client


async def main() -> None:
    host, port = os.getenv("SYNAPSE_ALPHA", "127.0.0.1:9999").rsplit(":", 1)
    result = await Client(host, int(port)).call(
        "alpha.ask_beta",
        "hello from an isolated agent",
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
