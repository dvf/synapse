import asyncio

import pytest

from synapse_p2p import (
    Client,
    ConversationEvent,
    MemoryConversationLog,
    Node,
    Peer,
    SqliteConversationLog,
    default_summarizer,
)


def make_event(event_id: str, *, conversation_id: str = "conv", created_at: float = 0.0):
    return ConversationEvent(
        conversation_id=conversation_id,
        event_id=event_id,
        kind="reply",
        peer=Peer(id=f"peer-{event_id}", address="127.0.0.1", port=1, name=event_id),
        payload={"result": event_id},
        created_at=created_at or float(len(event_id)),
    )


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_log_appends_deduplicates_and_lists(backend, tmp_path):
    log = (
        MemoryConversationLog()
        if backend == "memory"
        else SqliteConversationLog(tmp_path / "log.db")
    )
    event = make_event("a")

    assert log.append(event) is True
    assert log.append(event) is False
    assert log.seen("a") is True
    assert log.seen("missing") is False
    assert log.count("conv") == 1
    assert log.conversations() == ["conv"]
    assert log.events("conv")[0].payload == {"result": "a"}
    log.close()


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_log_compaction_replaces_events_and_blocks_resurrection(backend, tmp_path):
    log = (
        MemoryConversationLog()
        if backend == "memory"
        else SqliteConversationLog(tmp_path / "log.db")
    )
    old = make_event("old", created_at=1.0)
    recent = make_event("recent", created_at=2.0)
    log.append(old)
    log.append(recent)

    summary = ConversationEvent(
        conversation_id="conv",
        event_id="summary-1",
        kind="summary",
        peer=old.peer,
        payload={"summary": "old stuff"},
        created_at=1.0,
    )
    log.compact("conv", ["old"], summary)

    remaining = {event.event_id for event in log.events("conv")}
    assert remaining == {"summary-1", "recent"}
    # Gossip re-delivering a compacted event must not resurrect it.
    assert log.append(old) is False
    assert log.seen("old") is True
    log.close()


def test_sqlite_log_survives_restart(tmp_path):
    path = tmp_path / "log.db"
    log = SqliteConversationLog(path)
    log.append(make_event("a"))
    log.close()

    reopened = SqliteConversationLog(path)
    assert reopened.count("conv") == 1
    assert reopened.seen("a") is True
    reopened.close()


@pytest.mark.asyncio
async def test_default_summarizer_mentions_peers_and_folds_prior_summaries():
    events = [make_event("a"), make_event("b")]
    events.append(
        ConversationEvent(
            conversation_id="conv",
            event_id="s",
            kind="summary",
            peer=events[0].peer,
            payload={"summary": "earlier: c replied"},
        )
    )
    text = await default_summarizer(events)
    assert "a [reply]" in text
    assert "earlier: c replied" in text


@pytest.mark.asyncio
async def test_node_auto_compacts_conversation_past_max_events():
    node = Node(
        name="compactor",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
        conversation_max_events=5,
        conversation_keep_recent=2,
    )
    compacted = asyncio.Event()

    @node.on("conversation.compacted")
    async def on_compacted(event: ConversationEvent) -> None:
        compacted.set()

    await node.start()
    try:
        for index in range(8):
            await node.emit_conversation_event("conv", "note", {"index": index})
        await asyncio.wait_for(compacted.wait(), 1)

        events = node.conversation("conv")
        assert len(events) <= 5
        summaries = [event for event in events if event.kind == "summary"]
        assert summaries
        assert summaries[0].payload["compacted_events"] >= 3
        # The most recent events are preserved verbatim.
        assert events[-1].payload == {"index": 7}
    finally:
        await node.stop()


@pytest.mark.asyncio
async def test_manual_compaction_uses_custom_summarizer_and_keeps_head_message():
    node = Node(
        name="compactor",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )

    @node.summarizer
    async def summarize(events: list[ConversationEvent]) -> str:
        return f"custom summary of {len(events)} events"

    await node.start()
    try:
        broadcast = await node.broadcast("team.question", "who can help?")
        for index in range(6):
            await node.emit_conversation_event(broadcast, "note", {"index": index})

        summary = await node.compact_conversation(broadcast, keep_recent=2)

        assert summary is not None
        assert summary.payload["summary"] == "custom summary of 4 events"
        events = node.conversation(broadcast)
        # Head message survives compaction so the conversation keeps its opening.
        assert events[0].kind == "message"
        assert [event.kind for event in events[1:]] == ["summary", "note", "note"]
    finally:
        await node.stop()


@pytest.mark.asyncio
async def test_late_joiner_syncs_conversation_from_peer():
    origin = Node(
        name="origin",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    late = Node(
        name="late",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    await origin.start()

    broadcast = await origin.broadcast("team.question", "who can help?")
    await origin.emit_conversation_event(broadcast, "note", {"index": 1})

    await late.start()
    try:
        added = await late.sync_conversation(origin.self_peer(), broadcast)

        assert added == 2
        events = late.conversation(broadcast)
        assert [event.kind for event in events] == ["message", "note"]
        # Syncing again is idempotent.
        assert await late.sync_conversation(origin.self_peer(), broadcast) == 0
        listed = await Client.from_peer(origin.self_peer()).call("_synapse.conversation.list")
        assert isinstance(listed, list) and broadcast.nonce in listed
    finally:
        await late.stop()
        await origin.stop()


@pytest.mark.asyncio
async def test_default_summarizer_output_stays_bounded():
    events = [
        ConversationEvent(
            conversation_id="conv",
            event_id=f"e{index}",
            kind="reply",
            peer=Peer(id=f"p{index}", address="127.0.0.1", port=1, name=f"peer-{index}"),
            payload={"result": "x" * 500},
        )
        for index in range(200)
    ]
    events.append(
        ConversationEvent(
            conversation_id="conv",
            event_id="old-summary",
            kind="summary",
            peer=events[0].peer,
            payload={"summary": "y" * 50_000},
        )
    )
    text = await default_summarizer(events)
    assert len(text) < 10_000


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_log_prune_removes_events_and_forgets_ids(backend, tmp_path):
    log = (
        MemoryConversationLog()
        if backend == "memory"
        else SqliteConversationLog(tmp_path / "log.db")
    )
    event = make_event("a", created_at=123.0)
    log.append(event)
    assert log.last_activity("conv") == 123.0

    log.prune("conv")

    assert log.count("conv") == 0
    assert log.conversations() == []
    assert log.seen("a") is False
    assert log.append(event) is True  # a pruned id can be stored again
    log.close()


@pytest.mark.asyncio
async def test_node_reaps_inactive_conversations_and_rejects_stale_events():
    import time as time_module

    node = Node(
        name="reaper",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
        conversation_retention=0.3,
    )
    await node.start()

    try:
        broadcast = await node.broadcast("team.question", "anyone?")
        node.broadcast_replies[broadcast.nonce] = []
        assert node.conversation(broadcast)

        for _ in range(100):
            if not node.conversation(broadcast):
                break
            await asyncio.sleep(0.02)

        assert node.conversation(broadcast) == []
        assert broadcast.nonce not in node.broadcast_replies

        # Events older than the retention window are refused outright, so
        # gossip cannot resurrect a pruned conversation.
        stale = make_event("stale", created_at=time_module.time() - 60)
        stale.peer.swarm = node.swarm
        stale.peer.team = node.team
        assert node._remember_conversation_event(stale) is False
    finally:
        await node.stop()
