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

node.artifact(
    "agent-card",
    {
        "name": node.name,
        "role": node.role,
        "capabilities": ["answer", "echo"],
        "description": "Handles direct ask requests from alpha.",
    },
    mime_type="application/vnd.synapse.agent-card+json",
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
    try:
        await node.join()
        print(f"beta joined alpha's team on {node.address}:{node.port}")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
