"""Durable, compactable storage for shared conversation events.

A conversation log stores every :class:`ConversationEvent` a node has seen and
supports *compaction*: folding old events into a single ``summary`` event so a
long-running conversation stays small enough to hand to an LLM. Synapse ships a
naive extractive summarizer; agents can plug in an LLM summarizer instead.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Awaitable, Callable
from pathlib import Path

from synapse_p2p.types import ConversationEvent

Summarizer = Callable[[list[ConversationEvent]], Awaitable[str]]

SUMMARY_KIND = "summary"


async def default_summarizer(events: list[ConversationEvent]) -> str:
    """Summarize events without an LLM: keep a digest of who said what.

    Replace this with an LLM-backed callable via ``Node(summarizer=...)`` when a
    conversation carries real prose worth compressing semantically.
    """
    lines: list[str] = []
    counts: dict[str, int] = {}
    for event in events:
        counts[event.kind] = counts.get(event.kind, 0) + 1
        if event.kind == SUMMARY_KIND:
            previous = str(event.payload.get(SUMMARY_KIND, ""))
            if previous:
                lines.append(previous)
            continue
        preview = json.dumps(event.payload, default=str)
        if len(preview) > 200:
            preview = preview[:200] + "…"
        lines.append(f"{event.peer.name or event.peer.id} [{event.kind}]: {preview}")
    header = ", ".join(f"{count} {kind}" for kind, count in sorted(counts.items()))
    return f"({header})\n" + "\n".join(lines[-40:])


class BaseConversationLog:
    """Storage interface for conversation events.

    ``append`` must be idempotent by ``event_id`` and must keep remembering
    compacted event ids so gossip cannot resurrect events a summary replaced.
    """

    def append(self, event: ConversationEvent) -> bool:
        raise NotImplementedError

    def seen(self, event_id: str) -> bool:
        raise NotImplementedError

    def events(self, conversation_id: str, *, since: float = 0.0) -> list[ConversationEvent]:
        raise NotImplementedError

    def conversations(self) -> list[str]:
        raise NotImplementedError

    def count(self, conversation_id: str) -> int:
        raise NotImplementedError

    def compact(
        self,
        conversation_id: str,
        removed_event_ids: list[str],
        summary: ConversationEvent,
    ) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class MemoryConversationLog(BaseConversationLog):
    def __init__(self) -> None:
        self._events: dict[str, list[ConversationEvent]] = {}
        self._seen: set[str] = set()

    def append(self, event: ConversationEvent) -> bool:
        if event.event_id in self._seen:
            return False
        self._seen.add(event.event_id)
        self._events.setdefault(event.conversation_id, []).append(event)
        return True

    def seen(self, event_id: str) -> bool:
        return event_id in self._seen

    def events(self, conversation_id: str, *, since: float = 0.0) -> list[ConversationEvent]:
        events = self._events.get(conversation_id, [])
        if since:
            events = [event for event in events if event.created_at > since]
        return list(events)

    def conversations(self) -> list[str]:
        return list(self._events)

    def count(self, conversation_id: str) -> int:
        return len(self._events.get(conversation_id, []))

    def compact(
        self,
        conversation_id: str,
        removed_event_ids: list[str],
        summary: ConversationEvent,
    ) -> None:
        removed = set(removed_event_ids)
        kept = [
            event
            for event in self._events.get(conversation_id, [])
            if event.event_id not in removed
        ]
        self._seen.add(summary.event_id)
        merged = kept + [summary]
        merged.sort(key=lambda event: event.created_at)
        self._events[conversation_id] = merged


class SqliteConversationLog(BaseConversationLog):
    """Conversation log persisted to a single SQLite file.

    Survives restarts, so a node can serve ``_synapse.conversation.sync`` to
    late joiners even after it has been rebooted.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._db = sqlite3.connect(self.path)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                compacted INTEGER NOT NULL DEFAULT 0,
                data TEXT NOT NULL
            )
            """
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_conversation"
            " ON events (conversation_id, created_at)"
        )
        self._db.commit()

    def append(self, event: ConversationEvent) -> bool:
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO events (event_id, conversation_id, created_at, data)"
            " VALUES (?, ?, ?, ?)",
            (
                event.event_id,
                event.conversation_id,
                event.created_at,
                json.dumps(event.to_dict(), default=str),
            ),
        )
        self._db.commit()
        return cursor.rowcount > 0

    def seen(self, event_id: str) -> bool:
        row = self._db.execute("SELECT 1 FROM events WHERE event_id = ?", (event_id,)).fetchone()
        return row is not None

    def events(self, conversation_id: str, *, since: float = 0.0) -> list[ConversationEvent]:
        rows = self._db.execute(
            "SELECT data FROM events"
            " WHERE conversation_id = ? AND compacted = 0 AND created_at > ?"
            " ORDER BY created_at, rowid",
            (conversation_id, since),
        ).fetchall()
        return [ConversationEvent.from_dict(json.loads(row[0])) for row in rows]

    def conversations(self) -> list[str]:
        rows = self._db.execute(
            "SELECT DISTINCT conversation_id FROM events WHERE compacted = 0"
        ).fetchall()
        return [row[0] for row in rows]

    def count(self, conversation_id: str) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) FROM events WHERE conversation_id = ? AND compacted = 0",
            (conversation_id,),
        ).fetchone()
        return int(row[0])

    def compact(
        self,
        conversation_id: str,
        removed_event_ids: list[str],
        summary: ConversationEvent,
    ) -> None:
        self._db.executemany(
            "UPDATE events SET compacted = 1 WHERE event_id = ?",
            [(event_id,) for event_id in removed_event_ids],
        )
        self._db.execute(
            "INSERT OR REPLACE INTO events (event_id, conversation_id, created_at, data)"
            " VALUES (?, ?, ?, ?)",
            (
                summary.event_id,
                summary.conversation_id,
                summary.created_at,
                json.dumps(summary.to_dict(), default=str),
            ),
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()
