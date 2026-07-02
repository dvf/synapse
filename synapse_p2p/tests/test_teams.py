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


@pytest.mark.asyncio
async def test_dead_assignee_lease_expires_and_task_is_reoffered():
    architect_node = make_node("architect")
    dead_node = make_node("dead-coder", ["python"])
    live_node = make_node("live-coder", ["python"])
    team = Team(architect_node, lease=0.3)

    dead_worker = Worker(dead_node, renew_interval=999)
    live_worker = Worker(live_node)

    @dead_worker.task
    async def hang(assignment: Assignment) -> str:
        await asyncio.Event().wait()
        return "never"

    @live_worker.task
    async def implement(assignment: Assignment) -> str:
        return "rescued"

    await architect_node.start()
    await dead_node.start()
    await connect(architect_node, dead_node)

    try:
        task = await team.offer("long job", requires=["python"])
        for _ in range(100):
            if task.status == "claimed":
                break
            await asyncio.sleep(0.02)
        assert task.assignee is not None and task.assignee.name == "dead-coder"

        # The healthy worker joins while the first assignee hangs silently.
        await live_node.start()
        await connect(architect_node, live_node)

        result = await team.wait(task, timeout=5)
        assert result == "rescued"
        assert task.attempts >= 2
        assert task.assignee is not None and task.assignee.name == "live-coder"
    finally:
        await live_node.stop()
        await dead_node.stop()
        await architect_node.stop()


@pytest.mark.asyncio
async def test_unclaimed_task_reaches_late_joining_worker():
    architect_node = make_node("architect")
    coder_node = make_node("late-coder", ["python"])
    team = Team(architect_node, lease=0.2)
    worker = Worker(coder_node)

    @worker.task
    async def implement(assignment: Assignment) -> str:
        return "late but done"

    await architect_node.start()

    try:
        task = await team.offer("waiting job", requires=["python"])
        await asyncio.sleep(0.1)

        await coder_node.start()
        await connect(architect_node, coder_node)

        result = await team.wait(task, timeout=5)
        assert result == "late but done"
        assert task.attempts >= 2
    finally:
        await coder_node.stop()
        await architect_node.stop()


@pytest.mark.asyncio
async def test_task_fails_after_max_attempts_without_workers():
    architect_node = make_node("architect")
    team = Team(architect_node, lease=0.1, max_attempts=2)

    await architect_node.start()
    try:
        task = await team.offer("impossible", requires=["cobol"])
        with pytest.raises(TeamTaskError, match="after 2 attempts"):
            await team.wait(task, timeout=5)
    finally:
        await architect_node.stop()


@pytest.mark.asyncio
async def test_worker_heartbeat_keeps_lease_alive_during_long_task():
    architect_node = make_node("architect")
    coder_node = make_node("slow-coder", ["python"])
    team = Team(architect_node, lease=0.3)
    worker = Worker(coder_node, renew_interval=0.05)

    @worker.task
    async def implement(assignment: Assignment) -> str:
        await asyncio.sleep(1.0)  # much longer than the lease, no manual progress
        return "slow and steady"

    await architect_node.start()
    await coder_node.start()
    await connect(architect_node, coder_node)

    try:
        task = await team.offer("marathon", requires=["python"])
        result = await team.wait(task, timeout=5)

        assert result == "slow and steady"
        assert task.attempts == 1  # never re-offered
        # Heartbeats renewed the lease without polluting recorded progress.
        assert all(not entry.get("heartbeat") for entry in task.progress)
    finally:
        await coder_node.stop()
        await architect_node.stop()


@pytest.mark.asyncio
async def test_team_restores_task_table_from_durable_log(tmp_path):
    from synapse_p2p import SqliteConversationLog

    path = tmp_path / "architect.db"
    first_node = Node(
        name="architect",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
        conversation_log=SqliteConversationLog(path),
    )
    coder_node = make_node("coder", ["python"])
    team = Team(first_node)
    worker = Worker(coder_node)

    @worker.task
    async def implement(assignment: Assignment) -> str:
        return "persisted result"

    await first_node.start()
    await coder_node.start()
    await connect(first_node, coder_node)

    try:
        task = await team.offer("durable job", requires=["python"])
        await team.wait(task, timeout=5)
    finally:
        await coder_node.stop()
        await first_node.stop()
        first_node.conversation_log.close()

    # The architect restarts with a fresh process but the same log and name.
    second_node = Node(
        name="architect",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
        conversation_log=SqliteConversationLog(path),
    )
    restored_team = Team(second_node)

    assert restored_team.restore() == 1
    restored = restored_team.tasks[task.id]
    assert restored.status == "done"
    assert restored.result == "persisted result"
    assert await restored_team.wait(restored, timeout=1) == "persisted result"
    second_node.conversation_log.close()


@pytest.mark.asyncio
async def test_finished_tasks_are_pruned_after_retention():
    architect_node = make_node("architect")
    coder_node = make_node("coder", ["python"])
    team = Team(architect_node, lease=0.1, task_retention=0.2)
    worker = Worker(coder_node)

    @worker.task
    async def implement(assignment: Assignment) -> str:
        return "quick"

    await architect_node.start()
    await coder_node.start()
    await connect(architect_node, coder_node)

    try:
        task = await team.offer("small job", requires=["python"])
        await team.wait(task, timeout=5)
        for _ in range(100):
            if task.id not in team.tasks:
                break
            await asyncio.sleep(0.02)
        assert task.id not in team.tasks
    finally:
        await coder_node.stop()
        await architect_node.stop()
