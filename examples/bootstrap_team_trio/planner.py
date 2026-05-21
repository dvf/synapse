import asyncio
import os

from synapse_p2p import Node

planner = Node(
    name="planner",
    role="planner",
    swarm="foo.electron.network",
    capabilities=["planning", "delegation"],
    seeds=[os.getenv("SYNAPSE_BOOTSTRAP", "127.0.0.1:9000")],
    heartbeat_interval=5,
    peer_timeout=20,
)


@planner.ask
async def handle_task(task: str, context: dict):
    return {"handled_by": "planner", "plan": [task], "context": context}


@planner.endpoint("team.members", description="Return discovered team members")
async def team_members():
    return [peer.to_dict() for peer in planner.peers.values()]


async def main() -> None:
    await planner.start()
    await planner.join()
    print(f"planner joined foo.electron.network on {planner.address}:{planner.port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
