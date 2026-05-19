import asyncio

from synapse_p2p import Client


async def main() -> None:
    result = await Client("127.0.0.1", 9999).call("sum", 1, 2)
    print(f"Received: {result}")


if __name__ == "__main__":
    asyncio.run(main())
