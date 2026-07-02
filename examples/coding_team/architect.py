"""The architect node: offers tasks to the swarm, reviews what comes back.

The architect and the coders can run different models entirely — the swarm
only sees offers, claims, progress, and results. Each task is one shared
conversation, and the architect compacts long task threads automatically.
"""

import asyncio

from examples.coding_team.common import ARCHITECT_MODEL, SWARM, make_agent, run_agent
from synapse_p2p import ConversationEvent, Node
from synapse_p2p.teams import Team

brain, test_model = make_agent(
    ARCHITECT_MODEL,
    "You are the software architect overseeing a team of coder agents. "
    "Review their submitted implementations and give a short verdict.",
    "Architect: both implementations look solid; ship it.",
)

node = Node(
    name="architect",
    role="architect",
    swarm=SWARM,
    capabilities=["architecture", "review", "coordination"],
    mdns=True,
    # Keep task conversations small: fold old progress chatter into summaries.
    conversation_max_events=30,
    conversation_keep_recent=10,
)

team = Team(node)

FEATURE = "Add a `sn swarm top`-style live dashboard to the CLI"
SUBTASKS = [
    ("Implement the dashboard rendering loop", {"module": "synapse_p2p/cli.py"}),
    ("Add tests for the dashboard event stream", {"module": "synapse_p2p/tests/"}),
]


@node.on("conversation.task.progress")
async def on_progress(event: ConversationEvent) -> None:
    print(f"  progress from {event.peer.name}: {event.payload.get('message')}")


async def main() -> None:
    await node.start()
    await node.join(wait=1)
    print(f"architect online, {len(node.peers)} peer(s) known")

    tasks = []
    for title, spec in SUBTASKS:
        task = await team.offer(title, spec=spec, requires=["python", "implementation"])
        print(f"offered: {title} ({task.id})")
        tasks.append(task)

    results = []
    for task in tasks:
        result = await team.wait(task, timeout=600)
        assignee = task.assignee.name if task.assignee else "?"
        print(f"done: {task.title} by {assignee}")
        results.append(result)

    verdict = await run_agent(
        brain,
        test_model,
        f"Feature: {FEATURE}\nSubmissions: {results}\nGive your review verdict.",
    )
    print(f"\narchitect verdict:\n{verdict}")

    for task in tasks:
        kinds = [event.kind for event in node.conversation(task.id)]
        print(f"conversation {task.id}: {kinds}")

    await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
