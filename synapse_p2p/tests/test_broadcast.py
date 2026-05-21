import asyncio

import pytest

from synapse_p2p import Broadcast, BroadcastReply, Client, Node


@pytest.mark.asyncio
async def test_broadcast_delivers_typed_broadcast_and_collects_later_reply():
    origin = Node(
        name="origin",
        role="coordinator",
        swarm="foo.electron.network",
        team="foo",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    worker = Node(
        name="worker",
        role="worker",
        swarm="foo.electron.network",
        team="foo",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    reply_received = asyncio.Event()

    @origin.on("broadcast.reply")
    async def on_reply(reply: BroadcastReply) -> None:
        assert reply.peer.name == "worker"
        reply_received.set()

    @worker.endpoint("team.question")
    async def answer(question: str, broadcast: Broadcast) -> dict:
        await worker.reply(broadcast, {"answer": f"worker heard: {question}"})
        return {"accepted": True, "nonce": broadcast.nonce}

    await origin.start()
    await worker.start()
    origin.add_peer(worker.self_peer())

    try:
        broadcast = await origin.broadcast("team.question", "who can help?")
        await asyncio.wait_for(reply_received.wait(), 0.2)
        replies = origin.replies(broadcast)

        assert isinstance(broadcast, Broadcast)
        assert broadcast.origin.name == "origin"
        assert replies[0].nonce == broadcast.nonce
        assert replies[0].result == {"answer": "worker heard: who can help?"}
    finally:
        await worker.stop()
        await origin.stop()


@pytest.mark.asyncio
async def test_broadcast_received_event_fires_for_unknown_endpoint():
    watcher = Node(
        name="watcher",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    origin = Node(
        name="origin",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    received = asyncio.Queue()

    @watcher.on("broadcast.received")
    async def on_received(event: dict) -> None:
        await received.put(event)

    await watcher.start()
    await origin.start()
    origin.add_peer(watcher.self_peer())

    try:
        broadcast = await origin.broadcast("team.question", "who can help?")
        event = await asyncio.wait_for(received.get(), 0.2)

        assert event["endpoint"] == "team.question"
        assert event["args"] == ["who can help?"]
        assert event["broadcast"].nonce == broadcast.nonce
    finally:
        await origin.stop()
        await watcher.stop()


@pytest.mark.asyncio
async def test_broadcast_reply_is_shared_with_known_watchers():
    origin = Node(
        name="origin",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    worker = Node(
        name="worker",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    watcher = Node(
        name="watcher",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    watcher_reply = asyncio.Queue()

    @watcher.on("broadcast.reply")
    async def on_watcher_reply(reply: BroadcastReply) -> None:
        await watcher_reply.put(reply)

    @worker.endpoint("team.question")
    async def answer(question: str, broadcast: Broadcast) -> dict:
        await worker.reply(broadcast, {"answer": question})
        return {"accepted": True}

    await origin.start()
    await worker.start()
    await watcher.start()
    origin.add_peer(worker.self_peer())
    worker.add_peer(watcher.self_peer())

    try:
        broadcast = await origin.broadcast("team.question", "who can help?")
        reply = await asyncio.wait_for(watcher_reply.get(), 0.2)

        assert reply.nonce == broadcast.nonce
        assert reply.peer.name == "worker"
        assert reply.result == {"answer": "who can help?"}
    finally:
        await watcher.stop()
        await worker.stop()
        await origin.stop()


@pytest.mark.asyncio
async def test_broadcast_reply_endpoint_forwards_replies_to_known_watchers():
    origin = Node(
        name="origin",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    worker = Node(
        name="worker",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    watcher = Node(
        name="watcher",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    watcher_reply = asyncio.Queue()

    @watcher.on("broadcast.reply")
    async def on_watcher_reply(reply: BroadcastReply) -> None:
        await watcher_reply.put(reply)

    await origin.start()
    await worker.start()
    await watcher.start()
    origin.add_peer(watcher.self_peer())

    try:
        await Client.from_peer(origin.self_peer()).call(
            "_synapse.broadcast.reply",
            "nonce",
            worker.self_peer().to_dict(),
            result={"answer": "forwarded"},
        )
        reply = await asyncio.wait_for(watcher_reply.get(), 0.2)

        assert reply.nonce == "nonce"
        assert reply.peer.name == "worker"
        assert reply.result == {"answer": "forwarded"}
    finally:
        await watcher.stop()
        await worker.stop()
        await origin.stop()


@pytest.mark.asyncio
async def test_broadcast_reply_endpoint_deduplicates_forwarded_replies():
    node = Node(
        name="node",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    worker = Node(
        name="worker",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )

    await node.start()
    await worker.start()

    try:
        for _ in range(2):
            await Client.from_peer(node.self_peer()).call(
                "_synapse.broadcast.reply",
                "nonce",
                worker.self_peer().to_dict(),
                result={"answer": "once"},
            )

        assert len(node.replies("nonce")) == 1
    finally:
        await worker.stop()
        await node.stop()


@pytest.mark.asyncio
async def test_broadcast_reply_endpoint_validates_membership():
    origin = Node(
        swarm="foo.electron.network",
        team="foo",
        bind="127.0.0.1",
        heartbeat_interval=None,
    )
    tcp = await origin.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        with pytest.raises(RuntimeError, match="different swarm"):
            await Client(host, port).call(
                "_synapse.broadcast.reply",
                "nonce",
                {
                    "id": "bad",
                    "name": "bad",
                    "address": "127.0.0.1",
                    "port": 9999,
                    "swarm": "bar.electron.network",
                    "team": "foo",
                    "kind": "node",
                },
                result={"answer": "nope"},
            )
    finally:
        await origin.stop()
