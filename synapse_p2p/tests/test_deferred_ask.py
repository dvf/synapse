import asyncio

import pytest

from synapse_p2p import Client, ConversationEvent, Node


def make_node(name: str) -> Node:
    return Node(
        name=name,
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )


@pytest.mark.asyncio
async def test_swarm_ask_defers_slow_handlers_and_replies_later():
    origin = make_node("origin")
    worker = make_node("worker")
    started = asyncio.Event()
    release = asyncio.Event()

    @worker.ask
    async def handle(task: str, context: dict) -> dict:
        started.set()
        await release.wait()
        return {"task": task}

    await origin.start()
    await worker.start()
    origin.add_peer(worker.self_peer())

    try:
        broadcast = await origin.broadcast("synapse.ask", "long job")
        # The broadcast returns while the handler is still running.
        await asyncio.wait_for(started.wait(), 1)
        assert origin.replies(broadcast) == []

        release.set()
        for _ in range(50):
            if origin.replies(broadcast):
                break
            await asyncio.sleep(0.02)

        replies = origin.replies(broadcast)
        assert replies and replies[0].result == {"task": "long job"}
        assert any(event.kind == "ack" for event in origin.conversation(broadcast))
    finally:
        await worker.stop()
        await origin.stop()


@pytest.mark.asyncio
async def test_swarm_ask_handler_error_becomes_conversation_error_event():
    origin = make_node("origin")
    worker = make_node("worker")
    errored = asyncio.Queue()

    @origin.on("conversation.error")
    async def on_error(event: ConversationEvent) -> None:
        await errored.put(event)

    @worker.ask
    async def handle(task: str, context: dict) -> dict:
        raise RuntimeError("no can do")

    await origin.start()
    await worker.start()
    origin.add_peer(worker.self_peer())

    try:
        await origin.broadcast("synapse.ask", "doomed job")
        event = await asyncio.wait_for(errored.get(), 1)

        assert event.payload["error"] == "no can do"
        assert event.peer.name == "worker"
    finally:
        await worker.stop()
        await origin.stop()


@pytest.mark.asyncio
async def test_direct_synapse_ask_without_broadcast_stays_synchronous():
    worker = make_node("worker")

    @worker.ask
    async def handle(task: str, context: dict) -> dict:
        return {"task": task, "sync": True}

    server = await worker.start()
    host, port = server.sockets[0].getsockname()[:2]

    try:
        result = await Client(host, port).call("synapse.ask", "quick job")
        assert result == {"task": "quick job", "sync": True}
    finally:
        await worker.stop()
