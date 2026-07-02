"""A task layer for agent teams, built on shared conversation events.

Synapse core stays neutral: it moves events and does not decide who works on
what. This module layers a small, explicit vocabulary on top:

- ``task.offer``    — a :class:`Team` announces work and its requirements
- ``task.claim``    — a :class:`Worker` volunteers for an offered task
- ``task.grant``    — the offering team assigns the task to one claimant
- ``task.progress`` — the assignee narrates progress into the shared log
- ``task.done``     — the assignee delivers a result
- ``task.failed``   — the assignee reports an error

Each task is its own conversation (``conversation_id == task id``), so the full
history of a task — offer, claims, progress, result — is one gossiped, durable,
compactable thread that any swarm member can watch or sync later.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from synapse_p2p.node import Node, new_nonce
from synapse_p2p.types import ConversationEvent, Peer

TASK_OFFER = "task.offer"
TASK_CLAIM = "task.claim"
TASK_GRANT = "task.grant"
TASK_PROGRESS = "task.progress"
TASK_DONE = "task.done"
TASK_FAILED = "task.failed"


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
    runs it even when many volunteer.
    """

    def __init__(self, node: Node) -> None:
        self.node = node
        self.tasks: dict[str, TeamTask] = {}
        self._finished: dict[str, asyncio.Event] = {}
        node.on(f"conversation.{TASK_CLAIM}")(self._on_claim)
        node.on(f"conversation.{TASK_PROGRESS}")(self._on_progress)
        node.on(f"conversation.{TASK_DONE}")(self._on_done)
        node.on(f"conversation.{TASK_FAILED}")(self._on_failed)

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
        await self.node.emit_conversation_event(
            task.id,
            TASK_OFFER,
            {"task_id": task.id, "title": title, "spec": task.spec, "requires": task.requires},
        )
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

    async def _on_claim(self, event: ConversationEvent) -> None:
        task = self.tasks.get(event.conversation_id)
        if task is None or task.assignee is not None or task.status != "offered":
            return
        task.assignee = event.peer
        task.status = "claimed"
        await self.node.emit_conversation_event(
            task.id,
            TASK_GRANT,
            {"task_id": task.id, "worker_id": event.peer.id, "worker_name": event.peer.name},
            parent_id=event.event_id,
        )

    async def _on_progress(self, event: ConversationEvent) -> None:
        task = self.tasks.get(event.conversation_id)
        if task is not None:
            task.progress.append(dict(event.payload))

    async def _on_done(self, event: ConversationEvent) -> None:
        task = self.tasks.get(event.conversation_id)
        if task is None or task.status in {"done", "failed"}:
            return
        task.result = event.payload.get("result")
        task.status = "done"
        self._finished[task.id].set()

    async def _on_failed(self, event: ConversationEvent) -> None:
        task = self.tasks.get(event.conversation_id)
        if task is None or task.status in {"done", "failed"}:
            return
        task.error = str(event.payload.get("error", "unknown error"))
        task.status = "failed"
        self._finished[task.id].set()


TaskHandler = Callable[[Assignment], Awaitable[Any]]


class Worker:
    """Claim offered tasks the node is capable of, and run them when granted."""

    def __init__(self, node: Node, *, claim_timeout: float = 60) -> None:
        self.node = node
        self.claim_timeout = claim_timeout
        self._handler: TaskHandler | None = None
        self._pending: dict[str, tuple[ConversationEvent, float]] = {}
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
        if not self._can_do(list(event.payload.get("requires", []))):
            return
        task_id = str(event.payload["task_id"])
        self._pending[task_id] = (event, time.time())
        await self.node.emit_conversation_event(
            task_id,
            TASK_CLAIM,
            {
                "task_id": task_id,
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
        self.node._spawn(self._run(assignment), name=f"task:{task_id}")

    async def _run(self, assignment: Assignment) -> None:
        assert self._handler is not None
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
        await self.node.emit_conversation_event(
            assignment.id, TASK_DONE, {"task_id": assignment.id, "result": result}
        )
