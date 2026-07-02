"""A task layer for agent teams, built on shared conversation events.

Synapse core stays neutral: it moves events and does not decide who works on
what. This module layers a small, explicit vocabulary on top:

- ``task.offer``    — a :class:`Team` announces work and its requirements
- ``task.claim``    — a :class:`Worker` volunteers for an offered task
- ``task.grant``    — the offering team assigns the task to one claimant
- ``task.progress`` — the assignee narrates progress (and proves liveness)
- ``task.done``     — the assignee delivers a result
- ``task.failed``   — the assignee reports an error

Each task is its own conversation (``conversation_id == task id``), so the full
history of a task — offer, claims, progress, result — is one gossiped, durable,
compactable thread that any swarm member can watch or sync later.

Built for long-running work:

- Progress events renew a task's **lease**. If an assignee goes quiet for
  longer than the lease, the team re-offers the task to the swarm. Workers
  renew automatically in the background, so a handler can run for hours
  without emitting progress by hand.
- Unclaimed offers are re-announced every lease interval, so a worker that
  joins the swarm late still finds existing work.
- A team backed by a durable conversation log can rebuild its task table
  after a restart with :meth:`Team.restore`.

Delivery is at-least-once: if an assignee is alive but partitioned past its
lease, the task can run twice. The first ``task.done`` wins.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from synapse_p2p.node import Node, new_nonce
from synapse_p2p.schedules import every
from synapse_p2p.types import ConversationEvent, Peer, PeriodicTask

TASK_OFFER = "task.offer"
TASK_CLAIM = "task.claim"
TASK_GRANT = "task.grant"
TASK_PROGRESS = "task.progress"
TASK_DONE = "task.done"
TASK_FAILED = "task.failed"

FINISHED = {"done", "failed"}


class TeamTaskError(RuntimeError):
    """Raised when a task fails or times out while waiting for its result."""


@dataclass(slots=True)
class TeamTask:
    """The offering side's view of one unit of work."""

    id: str
    title: str
    spec: dict[str, Any] = field(default_factory=dict)
    requires: list[str] = field(default_factory=list)
    status: str = "offered"
    assignee: Peer | None = None
    result: Any = None
    error: str | None = None
    progress: list[dict[str, Any]] = field(default_factory=list)
    attempts: int = 1
    last_activity: float = field(default_factory=time.time)
    finished_at: float | None = None


@dataclass(slots=True)
class Assignment:
    """The worker side's view of a granted task, with a progress channel."""

    id: str
    title: str
    spec: dict[str, Any]
    node: Node

    async def progress(self, message: str, **data: Any) -> None:
        await self.node.emit_conversation_event(
            self.id, TASK_PROGRESS, {"task_id": self.id, "message": message, **data}
        )


class Team:
    """Offer tasks to the swarm and collect results.

    The team grants each task to the first claimant, so exactly one worker
    runs it at a time. ``lease`` is how long a task may sit unclaimed, or an
    assignee may stay silent, before the task is offered again.
    """

    def __init__(
        self,
        node: Node,
        *,
        lease: float = 300,
        max_attempts: int | None = None,
        task_retention: float | None = None,
    ) -> None:
        self.node = node
        self.lease = lease
        self.max_attempts = max_attempts
        self.task_retention = task_retention
        self.tasks: dict[str, TeamTask] = {}
        self._finished: dict[str, asyncio.Event] = {}
        node.on(f"conversation.{TASK_CLAIM}")(self._on_claim)
        node.on(f"conversation.{TASK_PROGRESS}")(self._on_progress)
        node.on(f"conversation.{TASK_DONE}")(self._on_done)
        node.on(f"conversation.{TASK_FAILED}")(self._on_failed)
        node.periodic_executor.add_task(
            PeriodicTask(
                name="_teams.reaper",
                callable=self._reap,
                schedule=every(seconds=max(0.05, lease / 4)),
            )
        )

    def _offer_payload(self, task: TeamTask) -> dict[str, Any]:
        return {
            "task_id": task.id,
            "title": task.title,
            "spec": task.spec,
            "requires": task.requires,
            "attempt": task.attempts,
        }

    async def offer(
        self,
        title: str,
        *,
        spec: dict[str, Any] | None = None,
        requires: list[str] | None = None,
    ) -> TeamTask:
        task = TeamTask(id=new_nonce(), title=title, spec=spec or {}, requires=requires or [])
        self.tasks[task.id] = task
        self._finished[task.id] = asyncio.Event()
        await self.node.emit_conversation_event(task.id, TASK_OFFER, self._offer_payload(task))
        return task

    async def wait(self, task: TeamTask, *, timeout: float | None = None) -> Any:
        """Wait until a task finishes; return its result or raise TeamTaskError."""
        finished = self._finished[task.id]
        try:
            await asyncio.wait_for(finished.wait(), timeout)
        except TimeoutError as e:
            raise TeamTaskError(f"task {task.id} timed out: {task.title}") from e
        if task.status == "failed":
            raise TeamTaskError(task.error or f"task {task.id} failed")
        return task.result

    def restore(self) -> int:
        """Rebuild the task table from the node's conversation log.

        Use after a restart with a durable log (``SqliteConversationLog``) and
        a stable node name: only tasks originally offered by a peer matching
        this node's id or name are adopted. Unfinished tasks are re-offered by
        the reaper once their lease expires. Returns how many tasks were
        restored.
        """
        restored = 0
        for conversation_id in self.node.conversation_log.conversations():
            if conversation_id in self.tasks:
                continue
            events = self.node.conversation_log.events(conversation_id)
            offers = [event for event in events if event.kind == TASK_OFFER]
            if not offers:
                continue
            origin = offers[0].peer
            if origin.id != self.node.node_id and origin.name != self.node.name:
                continue

            payload = offers[0].payload
            task = TeamTask(
                id=conversation_id,
                title=str(payload.get("title", "")),
                spec=dict(payload.get("spec", {})),
                requires=list(payload.get("requires", [])),
                attempts=max(len(offers), 1),
                last_activity=max(event.created_at for event in events),
            )
            self.tasks[task.id] = task
            self._finished[task.id] = asyncio.Event()
            for event in events:
                if event.kind == TASK_GRANT:
                    task.status = "claimed"
                elif event.kind == TASK_PROGRESS:
                    task.progress.append(dict(event.payload))
                elif event.kind == TASK_DONE and task.status not in FINISHED:
                    task.status = "done"
                    task.result = event.payload.get("result")
                    task.finished_at = event.created_at
                    self._finished[task.id].set()
                elif event.kind == TASK_FAILED and task.status not in FINISHED:
                    task.status = "failed"
                    task.error = str(event.payload.get("error", "unknown error"))
                    task.finished_at = event.created_at
                    self._finished[task.id].set()
            restored += 1
        return restored

    async def _reap(self) -> None:
        now = time.time()
        for task in list(self.tasks.values()):
            if task.status in FINISHED:
                if (
                    self.task_retention is not None
                    and task.finished_at is not None
                    and now - task.finished_at > self.task_retention
                ):
                    self.tasks.pop(task.id, None)
                    self._finished.pop(task.id, None)
                continue

            if now - task.last_activity <= self.lease:
                continue

            # Stale: either nobody claimed the offer, or the assignee went
            # quiet past its lease. Offer it to the swarm again.
            if self.max_attempts is not None and task.attempts >= self.max_attempts:
                task.status = "failed"
                task.error = f"no worker completed the task after {task.attempts} attempts"
                task.finished_at = now
                self._finished[task.id].set()
                continue
            previous = task.assignee.name if task.assignee else None
            task.assignee = None
            task.status = "offered"
            task.attempts += 1
            task.last_activity = now
            logger.info(
                "Re-offering task {} (attempt {}, previous assignee {})",
                task.id,
                task.attempts,
                previous,
            )
            await self.node.emit_conversation_event(
                task.id, TASK_OFFER, self._offer_payload(task)
            )

    async def _on_claim(self, event: ConversationEvent) -> None:
        task = self.tasks.get(event.conversation_id)
        if task is None or task.assignee is not None or task.status != "offered":
            return
        if event.payload.get("attempt") not in (None, task.attempts):
            return  # a stale claim from an earlier attempt
        task.assignee = event.peer
        task.status = "claimed"
        task.last_activity = time.time()
        await self.node.emit_conversation_event(
            task.id,
            TASK_GRANT,
            {"task_id": task.id, "worker_id": event.peer.id, "worker_name": event.peer.name},
            parent_id=event.event_id,
        )

    async def _on_progress(self, event: ConversationEvent) -> None:
        task = self.tasks.get(event.conversation_id)
        if task is None:
            return
        task.last_activity = time.time()
        if not event.payload.get("heartbeat"):
            task.progress.append(dict(event.payload))

    async def _on_done(self, event: ConversationEvent) -> None:
        task = self.tasks.get(event.conversation_id)
        if task is None or task.status in FINISHED:
            return
        task.result = event.payload.get("result")
        task.status = "done"
        task.finished_at = time.time()
        self._finished[task.id].set()

    async def _on_failed(self, event: ConversationEvent) -> None:
        task = self.tasks.get(event.conversation_id)
        if task is None or task.status in FINISHED:
            return
        task.error = str(event.payload.get("error", "unknown error"))
        task.status = "failed"
        task.finished_at = time.time()
        self._finished[task.id].set()


TaskHandler = Callable[[Assignment], Awaitable[Any]]


class Worker:
    """Claim offered tasks the node is capable of, and run them when granted.

    While a handler runs, the worker emits heartbeat progress events every
    ``renew_interval`` seconds so the team's lease stays fresh — a task can
    run for hours without any explicit progress calls.
    """

    def __init__(
        self, node: Node, *, claim_timeout: float = 60, renew_interval: float = 60
    ) -> None:
        self.node = node
        self.claim_timeout = claim_timeout
        self.renew_interval = renew_interval
        self._handler: TaskHandler | None = None
        self._pending: dict[str, tuple[ConversationEvent, float]] = {}
        self._running: set[str] = set()
        node.on(f"conversation.{TASK_OFFER}")(self._on_offer)
        node.on(f"conversation.{TASK_GRANT}")(self._on_grant)

    def task(self, wrapped: TaskHandler) -> TaskHandler:
        """Decorator registering the coroutine that executes granted tasks."""
        self._handler = wrapped
        return wrapped

    def _can_do(self, requires: list[str]) -> bool:
        mine = {capability.name for capability in self.node.capabilities}
        return set(requires) <= mine

    def _prune_pending(self) -> None:
        deadline = time.time() - self.claim_timeout
        stale = [task_id for task_id, (_, at) in self._pending.items() if at < deadline]
        for task_id in stale:
            self._pending.pop(task_id, None)

    async def _on_offer(self, event: ConversationEvent) -> None:
        self._prune_pending()
        if self._handler is None:
            return
        if event.peer.id == self.node.node_id:
            return
        task_id = str(event.payload["task_id"])
        if task_id in self._running:
            return  # a re-offer for work this worker is already doing
        if not self._can_do(list(event.payload.get("requires", []))):
            return
        self._pending[task_id] = (event, time.time())
        await self.node.emit_conversation_event(
            task_id,
            TASK_CLAIM,
            {
                "task_id": task_id,
                "attempt": event.payload.get("attempt"),
                "capabilities": [capability.name for capability in self.node.capabilities],
            },
            parent_id=event.event_id,
        )

    async def _on_grant(self, event: ConversationEvent) -> None:
        task_id = str(event.payload.get("task_id", ""))
        pending = self._pending.pop(task_id, None)
        if pending is None:
            return
        if event.payload.get("worker_id") != self.node.node_id:
            return  # another worker was granted the task
        offer, _ = pending
        assignment = Assignment(
            id=task_id,
            title=str(offer.payload.get("title", "")),
            spec=dict(offer.payload.get("spec", {})),
            node=self.node,
        )
        self._running.add(task_id)
        self.node._spawn(self._run(assignment), name=f"task:{task_id}")

    async def _renew_lease(self, assignment: Assignment) -> None:
        while True:
            await asyncio.sleep(self.renew_interval)
            await self.node.emit_conversation_event(
                assignment.id,
                TASK_PROGRESS,
                {"task_id": assignment.id, "message": "working", "heartbeat": True},
            )

    async def _run(self, assignment: Assignment) -> None:
        assert self._handler is not None
        renewal = asyncio.create_task(
            self._renew_lease(assignment), name=f"task-lease:{assignment.id}"
        )
        try:
            result = await self._handler(assignment)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Task {} failed on {}", assignment.id, self.node.name)
            await self.node.emit_conversation_event(
                assignment.id, TASK_FAILED, {"task_id": assignment.id, "error": str(e)}
            )
            return
        finally:
            renewal.cancel()
            self._running.discard(assignment.id)
        await self.node.emit_conversation_event(
            assignment.id, TASK_DONE, {"task_id": assignment.id, "result": result}
        )
