import asyncio
import os

from synapse_p2p import Node

node = Node(
    name="beta",
    role="worker",
    swarm="foo.electron.network",
    capabilities=["answer", "echo"],
    seeds=[os.getenv("SYNAPSE_ALPHA", "127.0.0.1:9999")],
    mdns=True,
)


@node.ask
async def handle_task(task: str, context: dict):
    return {
        "handled_by": "beta",
        "task": task,
        "context": context,
    }


async def main() -> None:
    await node.start()
    await node.join()
    print(f"beta joined alpha's team on {node.address}:{node.port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
