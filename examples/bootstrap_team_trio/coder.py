import asyncio
import os

from synapse_p2p import Node

coder = Node(
    name="coder",
    role="coder",
    swarm="foo.electron.network",
    capabilities=["python", "implementation"],
    seeds=[os.getenv("SYNAPSE_BOOTSTRAP", "127.0.0.1:9000")],
    heartbeat_interval=5,
    peer_timeout=20,
)


@coder.ask
async def handle_task(task: str, context: dict):
    return {
        "handled_by": "coder",
        "task": task,
        "patch": "# demo patch would go here",
        "context": context,
    }


async def main() -> None:
    await coder.start()
    await coder.join()
    print(f"coder joined foo.electron.network on {coder.address}:{coder.port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
