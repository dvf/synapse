"""Run interval, cron, and solar periodic tasks on a Synapse node.

Start it with:

    uv run python examples/periodic_tasks.py

The interval task runs every 10 seconds. The cron and solar tasks show how to
schedule work on wall-clock and sunrise/civil-twilight time.
"""

from synapse_p2p import Node, cron, every, solar

node = Node(
    name="scheduled-agent",
    swarm="examples.synapse.local",
    capabilities=["periodic-jobs", "cron", "solar"],
    mdns=True,
)


@node.periodic(every(seconds=10))
async def heartbeat_job() -> None:
    print("interval: still alive")


@node.periodic(cron("0 9 * * mon-fri", tz="Europe/London"))
async def weekday_morning_job() -> None:
    print("cron: weekday morning check")


@node.periodic(solar("sunrise", latitude=51.5, longitude=-0.1, tz="Europe/London"))
async def sunrise_job() -> None:
    print("solar: sunrise in London")


@node.periodic(
    solar("civil_twilight_begin", latitude=51.5, longitude=-0.1, tz="Europe/London")
)
async def civil_twilight_job() -> None:
    print("solar: civil twilight has begun in London")


if __name__ == "__main__":
    node.run()
