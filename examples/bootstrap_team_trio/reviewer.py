import asyncio

from synapse_p2p import Node

reviewer = Node(
    name="reviewer",
    role="reviewer",
    swarm="foo.electron.network",
    capabilities=["code-review", "risk-analysis"],
    seeds=["127.0.0.1:9000"],
    heartbeat_interval=5,
    peer_timeout=20,
)


@reviewer.ask
async def handle_task(task: str, context: dict):
    return {
        "handled_by": "reviewer",
        "task": task,
        "finding": "Looks good for this demo.",
        "context": context,
    }


async def main() -> None:
    await reviewer.start()
    await reviewer.join()
    print(f"reviewer joined foo.electron.network on {reviewer.address}:{reviewer.port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
