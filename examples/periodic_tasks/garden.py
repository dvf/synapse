"""A tiny solar-powered garden swarm demo.

Run it with:

    uv run python examples/periodic_tasks/garden.py

It demonstrates interval, cron, and solar schedules on one Synapse node. The
handlers are intentionally lightweight: in a real deployment they would call
sensors, irrigation hardware, or an agent layered above Synapse.
"""

from synapse_p2p import Node, cron, every, solar

node = Node(
    name="garden-caretaker",
    swarm="garden.example.local",
    capabilities=["soil-monitoring", "watering", "solar-jobs"],
    mdns=True,
)

node.artifact(
    "agent-card",
    {
        "name": node.name,
        "role": "garden caretaker",
        "capabilities": ["soil-monitoring", "watering", "solar-jobs"],
        "description": "Runs garden checks on interval, cron, and solar schedules.",
    },
    mime_type="application/vnd.synapse.agent-card+json",
)


@node.periodic(every(seconds=10))
async def soil_sensor_poll() -> None:
    print("interval: checking soil moisture sensors")


@node.periodic(cron("0 7 * * *", tz="Europe/London"))
async def morning_plan() -> None:
    print("cron: building today's watering plan")


@node.periodic(solar("sunrise", latitude=51.5, longitude=-0.1, tz="Europe/London"))
async def sunrise_wakeup() -> None:
    print("solar: sunrise — wake up the garden swarm")


@node.periodic(solar("sunset", latitude=51.5, longitude=-0.1, tz="Europe/London"))
async def sunset_shutdown() -> None:
    print("solar: sunset — park watering jobs for the night")


if __name__ == "__main__":
    node.run()
