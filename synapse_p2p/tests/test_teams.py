import asyncio

import pytest

from synapse_p2p import Capability, Node
from synapse_p2p.teams import Assignment, Team, TeamTaskError, Worker


def make_node(name: str, capabilities: list[str | Capability] | None = None) -> Node:
    return Node(
        name=name,
        swarm="foo.electron.network",
        capabilities=capabilities or [],
        bind="127.0.0.1",
        heartbeat_interval=None,
    )


async def connect(architect: Node, *workers: Node) -> None:
    for worker in workers:
        architect.add_peer(worker.self_peer())
        worker.add_peer(architect.self_peer())


@pytest.mark.asyncio
async def test_offer_claim_grant_and_done_flow():
    architect_node = make_node("architect")
    coder_node = make_node("coder", ["python"])
    team = Team(architect_node)
    worker = Worker(coder_node)

    @worker.task
    async def implement(assignment: Assignment) -> dict:
        await assignment.progress("starting", step=1)
        return {"diff": f"patch for {assignment.title}", "spec": assignment.spec}

    await architect_node.start()
    await coder_node.start()
    await connect(architect_node, coder_node)

    try:
        task = await team.offer(
            "implement the parser", spec={"file": "parser.py"}, requires=["python"]
        )
        result = await team.wait(task, timeout=2)

        assert result == {"diff": "patch for implement the parser", "spec": {"file": "parser.py"}}
        assert task.status == "done"
        assert task.assignee is not None and task.assignee.name == "coder"
        assert any(entry["message"] == "starting" for entry in task.progress)

        kinds = [event.kind for event in architect_node.conversation(task.id)]
        assert kinds[0] == "task.offer"
        assert {"task.claim", "task.grant", "task.progress", "task.done"} <= set(kinds)
    finally:
        await coder_node.stop()
        await architect_node.stop()


@pytest.mark.asyncio
async def test_only_one_worker_is_granted_the_task():
    architect_node = make_node("architect")
    coder_one = make_node("coder-1", ["python"])
    coder_two = make_node("coder-2", ["python"])
    team = Team(architect_node)
    ran: list[str] = []

    for node in (coder_one, coder_two):
        worker = Worker(node)

        def handler_for(name: str):
            async def implement(assignment: Assignment) -> str:
                ran.append(name)
                return f"done by {name}"

            return implement

        worker.task(handler_for(node.name))

    await architect_node.start()
    await coder_one.start()
    await coder_two.start()
    await connect(architect_node, coder_one, coder_two)

    try:
        task = await team.offer("small fix", requires=["python"])
        result = await team.wait(task, timeout=2)
        await asyncio.sleep(0.1)

        assert len(ran) == 1
        assert result == f"done by {ran[0]}"
    finally:
        await coder_two.stop()
        await coder_one.stop()
        await architect_node.stop()


@pytest.mark.asyncio
async def test_worker_without_required_capability_does_not_claim():
    architect_node = make_node("architect")
    coder_node = make_node("docs-only", ["docs"])
    team = Team(architect_node)
    worker = Worker(coder_node)

    @worker.task
    async def implement(assignment: Assignment) -> str:
        return "should never run"

    await architect_node.start()
    await coder_node.start()
    await connect(architect_node, coder_node)

    try:
        task = await team.offer("rust rewrite", requires=["rust"])
        with pytest.raises(TeamTaskError, match="timed out"):
            await team.wait(task, timeout=0.3)
        assert task.assignee is None
    finally:
        await coder_node.stop()
        await architect_node.stop()


@pytest.mark.asyncio
async def test_worker_failure_propagates_to_team_wait():
    architect_node = make_node("architect")
    coder_node = make_node("coder", ["python"])
    team = Team(architect_node)
    worker = Worker(coder_node)

    @worker.task
    async def implement(assignment: Assignment) -> str:
        raise ValueError("model refused")

    await architect_node.start()
    await coder_node.start()
    await connect(architect_node, coder_node)

    try:
        task = await team.offer("impossible task", requires=["python"])
        with pytest.raises(TeamTaskError, match="model refused"):
            await team.wait(task, timeout=2)
        assert task.status == "failed"
    finally:
        await coder_node.stop()
        await architect_node.stop()
