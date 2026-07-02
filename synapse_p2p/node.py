import asyncio
import base64
import contextlib
import hashlib
import inspect
import json
import time
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import asdict, dataclass, field
from typing import Any

from loguru import logger

from synapse_p2p import __logo__
from synapse_p2p.client import Client
from synapse_p2p.conversations import (
    SUMMARY_KIND,
    BaseConversationLog,
    MemoryConversationLog,
    Summarizer,
    default_summarizer,
)
from synapse_p2p.exceptions import InvalidMessageError
from synapse_p2p.framing import read_frame, write_frame
from synapse_p2p.mdns import MdnsDiscovery
from synapse_p2p.messages import RPCError, RPCRequest, RPCResponse
from synapse_p2p.network import advertised_address
from synapse_p2p.periodic import PeriodicTaskHandler
from synapse_p2p.schedules import Schedule, every
from synapse_p2p.serializers import BaseRPCSerializer, MessagePackRPCSerializer
from synapse_p2p.types import (
    Broadcast,
    BroadcastReply,
    Connection,
    ConversationEvent,
    NodeKind,
    Peer,
    PeriodicTask,
    ServedArtifact,
    build_connection_from_peer_name,
)
from synapse_p2p.utils import random_hash


def new_nonce() -> str:
    """Create a time-sortable broadcast nonce when the runtime supports UUIDv7."""
    uuid7 = getattr(uuid, "uuid7", None)
    if uuid7 is not None:
        return str(uuid7())
    return str(uuid.uuid4())


@dataclass(slots=True)
class EndpointMetadata:
    name: str
    publish: bool = True
    description: str = ""


@dataclass(slots=True)
class Capability:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)


AskHandler = Callable[[str, dict[str, Any]], Awaitable[Any]]
Seed = str | tuple[str, int]


class Node:
    def __init__(
        self,
        bind: str = "0.0.0.0",
        port: int = 0,
        advertise: str | None = "auto",
        serializer_class: type[BaseRPCSerializer] = MessagePackRPCSerializer,
        max_upload_size: int = 4 * 1024 * 1024,
        node_id: str | None = None,
        name: str = "",
        role: str = "",
        description: str = "",
        capabilities: list[str | Capability] | None = None,
        kind: NodeKind | str = NodeKind.NODE,
        swarm: str | None = None,
        team: str | None = "default",
        seeds: list[Seed] | None = None,
        mdns: bool = False,
        heartbeat_interval: float | None = 5,
        peer_timeout: float = 20,
        conversation_log: BaseConversationLog | None = None,
        conversation_max_events: int | None = None,
        conversation_keep_recent: int = 25,
        summarizer: Summarizer | None = None,
    ) -> None:
        self.bind = bind
        self.advertise = advertise
        self.address = advertised_address(bind, advertise)
        self.port = port
        self.node_id = node_id or random_hash()
        self.name = name
        self.role = role
        self.description = description
        self.capabilities = [self._normalize_capability(c) for c in capabilities or []]
        self._ask_handler: AskHandler | None = None
        self.kind = NodeKind.from_value(kind)
        self.swarm = swarm
        self.team = team
        self.seeds = [self._normalize_seed(seed) for seed in seeds or []]
        self.mdns_enabled = mdns
        self.mdns = MdnsDiscovery(self) if mdns else None
        self.heartbeat_interval = heartbeat_interval
        self.peer_timeout = peer_timeout
        self.peers: dict[str, Peer] = {}
        self.broadcast_replies: dict[str, list[BroadcastReply]] = {}
        self.conversation_log = conversation_log or MemoryConversationLog()
        self.conversation_max_events = conversation_max_events
        self.conversation_keep_recent = conversation_keep_recent
        self._summarizer: Summarizer = summarizer or default_summarizer
        self._compacting: set[str] = set()
        self._background: set[asyncio.Task] = set()
        self.artifact_directory: dict[str, ServedArtifact] = {}
        self.lifecycle_handlers: dict[str, list[Callable[[Any], Coroutine[Any, Any, None]]]] = {}
        self.endpoint_directory: dict[str, Callable] = {}
        self.endpoint_metadata: dict[str, EndpointMetadata] = {}
        self.max_upload_size = max_upload_size
        self.periodic_executor = PeriodicTaskHandler()
        self.serializer_class = serializer_class
        self._listener: asyncio.Server | None = None
        self._register_system_endpoints()
        self._register_node_endpoints()
        self._register_lifecycle_tasks()

    def _normalize_capability(self, capability: str | Capability) -> Capability:
        if isinstance(capability, str):
            return Capability(name=capability)
        return capability

    def capability(
        self,
        name: str,
        *,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> Capability:
        capability = Capability(
            name=name,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
        )
        self.capabilities.append(capability)
        return capability

    def ask(self, wrapped: AskHandler) -> AskHandler:
        self._ask_handler = wrapped
        return wrapped

    def artifact(
        self,
        name: str,
        content: Any,
        *,
        mime_type: str = "application/json",
        kind: str = "metadata",
        description: str = "",
        encoding: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ServedArtifact:
        """Advertise a small inline artifact that peers can fetch over RPC.

        Synapse does not interpret the MIME type. It advertises and serves the
        document so higher-level agents can decide whether they understand it.
        """
        artifact = self._build_artifact(
            name=name,
            content=content,
            mime_type=mime_type,
            kind=kind,
            description=description,
            encoding=encoding,
            metadata=metadata or {},
        )
        self.artifact_directory[name] = artifact
        return artifact

    def _build_artifact(
        self,
        *,
        name: str,
        content: Any,
        mime_type: str,
        kind: str,
        description: str,
        encoding: str | None,
        metadata: dict[str, Any],
    ) -> ServedArtifact:
        if isinstance(content, bytes):
            raw = content
            served_content: Any = base64.b64encode(content).decode("ascii")
            artifact_encoding = encoding or "base64"
        elif isinstance(content, str):
            raw = content.encode()
            served_content = content
            artifact_encoding = encoding or "text"
        else:
            raw = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
            served_content = content
            artifact_encoding = encoding or "json"

        return ServedArtifact(
            name=name,
            mime_type=mime_type,
            content=served_content,
            kind=kind,
            description=description,
            encoding=artifact_encoding,
            size=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            metadata=dict(metadata),
        )

    def run(self) -> None:
        """Run the node."""
        print(__logo__)
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(self.serve())

    def _normalize_seed(self, seed: Seed) -> tuple[str, int]:
        if isinstance(seed, tuple):
            return seed
        if ":" not in seed:
            return seed, 9999
        address, port = seed.rsplit(":", 1)
        return address, int(port)

    async def _dispatch(self, rpc: RPCRequest, connection: Connection):
        kwargs = dict(rpc.kwargs)
        if "broadcast" in kwargs and isinstance(kwargs["broadcast"], dict):
            kwargs["broadcast"] = Broadcast.from_dict(kwargs["broadcast"])
            broadcast = kwargs["broadcast"]
            self._remember_conversation_event(
                ConversationEvent(
                    conversation_id=broadcast.nonce,
                    event_id=broadcast.nonce,
                    kind="message",
                    peer=broadcast.origin,
                    payload={
                        "endpoint": rpc.endpoint,
                        "args": list(rpc.args),
                        "kwargs": {
                            key: value
                            for key, value in kwargs.items()
                            if key != "broadcast"
                        },
                    },
                )
            )
            self._emit_lifecycle(
                "broadcast.received",
                {
                    "endpoint": rpc.endpoint,
                    "broadcast": broadcast,
                    "args": list(rpc.args),
                    "kwargs": {key: value for key, value in kwargs.items() if key != "broadcast"},
                },
            )

        endpoint = self.endpoint_directory.get(rpc.endpoint)
        if endpoint is None:
            raise InvalidMessageError(f"Unregistered endpoint called: {rpc.endpoint}")

        signature = inspect.signature(endpoint)
        injected = {"rpc": rpc, "connection": connection}
        for name, value in injected.items():
            if name in signature.parameters:
                kwargs[name] = value

        return await endpoint(*rpc.args, **kwargs)

    async def handle_data(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Receive a framed request, dispatch it, and write a framed response."""
        connection = build_connection_from_peer_name(writer.get_extra_info("peername"))
        logger.debug(
            "Talking to connection {} @ {}:{}",
            connection.identifier,
            connection.ip,
            connection.port,
        )
        request_id = ""

        try:
            data = await read_frame(reader, self.max_upload_size)
            rpc = self.serializer_class.deserialize(data)
            if not isinstance(rpc, RPCRequest):
                raise InvalidMessageError("expected request message")
            request_id = rpc.id

            result = await self._dispatch(rpc, connection)
            response = RPCResponse(id=request_id, ok=True, result=result)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            logger.debug(
                "Connection closed before a full request from {}:{}",
                connection.ip,
                connection.port,
            )
            writer.close()
            with contextlib.suppress(ConnectionError, OSError):
                await writer.wait_closed()
            return
        except InvalidMessageError as e:
            logger.debug("Invalid message from {}:{}: {}", connection.ip, connection.port, e)
            response = RPCResponse(
                id=request_id,
                ok=False,
                error=RPCError(code="bad_request", message=str(e)),
            )
        except Exception as e:
            logger.exception("Endpoint raised while handling {}:{}", connection.ip, connection.port)
            response = RPCResponse(
                id=request_id,
                ok=False,
                error=RPCError(code="internal_error", message=str(e)),
            )

        try:
            await write_frame(writer, self.serializer_class.serialize(response))
        except (ConnectionError, OSError):
            logger.debug(
                "Connection closed before response to {}:{}",
                connection.ip,
                connection.port,
            )
        finally:
            logger.debug("Closing connection to {}:{}", connection.ip, connection.port)
            writer.close()
            with contextlib.suppress(ConnectionError, OSError):
                await writer.wait_closed()

    def _print_startup(self) -> None:
        print(f"Listening on {self.bind}:{self.port} (advertising {self.address})\n")
        print("Registered Endpoints:")
        for endpoint in self.endpoint_directory:
            print(f"- {endpoint}")

        if self.periodic_executor.tasks:
            print("\nPeriodic Tasks:")
            for task in self.periodic_executor.tasks:
                print(f"- {task.name} ({task.period}s)")
        print()

    async def start(self) -> asyncio.Server:
        """Start accepting connections without blocking forever."""
        if self._listener is not None:
            return self._listener

        self._listener = await asyncio.start_server(self.handle_data, self.bind, self.port)
        socket = self._listener.sockets[0] if self._listener.sockets else None
        if socket is not None:
            _bound_address, self.port = socket.getsockname()[:2]
            self.address = advertised_address(self.bind, self.advertise)
        self.periodic_executor.start()
        if self.mdns is not None:
            await self.mdns.start()
        return self._listener

    async def stop(self) -> None:
        """Stop accepting connections and cancel periodic and background tasks."""
        await self.periodic_executor.stop()
        if self.mdns is not None:
            await self.mdns.stop()

        for task in list(self._background):
            task.cancel()
        if self._background:
            await asyncio.gather(*self._background, return_exceptions=True)
        self._background.clear()

        if self._listener is None:
            return

        self._listener.close()
        await self._listener.wait_closed()
        self._listener = None

    async def serve(self) -> None:
        """Attach TCP Stream handler to underlying socket interface."""
        listener = await self.start()
        self._print_startup()

        try:
            async with listener:
                await listener.serve_forever()
        finally:
            await self.stop()

    def node_info(self) -> dict:
        return {
            "id": self.node_id,
            "name": self.name,
            "kind": self.kind.value,
            "address": self.address,
            "port": self.port,
            "swarm": self.swarm,
            "team": self.team,
            "role": self.role,
            "description": self.description,
            "capabilities": [capability.name for capability in self.capabilities],
        }

    def self_peer(self) -> Peer:
        return Peer(
            id=self.node_id,
            name=self.name,
            kind=self.kind,
            address=self.address,
            port=self.port,
            swarm=self.swarm,
            team=self.team,
            capabilities=[capability.name for capability in self.capabilities],
        )

    def on(self, event: str) -> Callable:
        """Register a lifecycle event handler.

        Supported events are ``peer.joined``, ``peer.heartbeat``, ``peer.offline``,
        ``broadcast.received``, and ``broadcast.reply``.
        """

        def decorator(
            wrapped: Callable[[Any], Coroutine[Any, Any, None]],
        ) -> Callable[[Any], Coroutine[Any, Any, None]]:
            self.lifecycle_handlers.setdefault(event, []).append(wrapped)
            return wrapped

        return decorator

    def _spawn(self, coroutine: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task:
        """Run a coroutine in the background, keeping a strong reference until done."""
        task = asyncio.create_task(coroutine, name=name)
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task

    def _emit_lifecycle(self, event: str, payload: Any) -> None:
        for handler in self.lifecycle_handlers.get(event, []):
            self._spawn(handler(payload), name=event)

    def add_peer(self, peer: Peer, *, event: str = "peer.joined") -> None:
        if peer.id == self.node_id:
            return
        peer.last_seen = time.time()
        known = peer.id in self.peers
        self.peers[peer.id] = peer
        self._emit_lifecycle("peer.heartbeat" if known else event, peer)

    def _validate_peer_membership(self, peer: Peer) -> None:
        if self.swarm is not None and peer.swarm != self.swarm:
            raise InvalidMessageError("peer requested a different swarm")
        if self.team is not None and peer.team != self.team:
            raise InvalidMessageError("peer requested a different team")

    async def _send_heartbeats(self) -> None:
        for peer in list(self.peers.values()):
            try:
                await Client(peer.address, peer.port).call(
                    "_synapse.heartbeat", self.self_peer().to_dict()
                )
            except Exception:
                logger.debug(
                    "Could not heartbeat peer {} @ {}:{}",
                    peer.id,
                    peer.address,
                    peer.port,
                )

    async def _reap_stale_peers(self) -> None:
        now = time.time()
        stale = [
            peer
            for peer in self.peers.values()
            if now - peer.last_seen > self.peer_timeout
        ]
        for peer in stale:
            self.peers.pop(peer.id, None)
            self._emit_lifecycle("peer.offline", peer)

    def _register_lifecycle_tasks(self) -> None:
        if self.heartbeat_interval is None:
            return
        self.periodic_executor.add_task(
            PeriodicTask(
                name="_synapse.heartbeat",
                callable=self._send_heartbeats,
                schedule=every(seconds=self.heartbeat_interval),
            )
        )
        self.periodic_executor.add_task(
            PeriodicTask(
                name="_synapse.reap_stale_peers",
                callable=self._reap_stale_peers,
                schedule=every(seconds=self.heartbeat_interval),
            )
        )

    async def broadcast(self, endpoint: str, *args, **kwargs) -> Broadcast:
        """Send a one-way message to every known peer.

        The returned :class:`Broadcast` is the shared conversation event. Any peer
        can reply later with ``await node.reply(broadcast, result)``.
        """

        broadcast = Broadcast(nonce=new_nonce(), origin=self.self_peer(), endpoint=endpoint)
        self._remember_conversation_event(
            ConversationEvent(
                conversation_id=broadcast.nonce,
                event_id=broadcast.nonce,
                kind="message",
                peer=broadcast.origin,
                payload={"endpoint": endpoint, "args": list(args), "kwargs": dict(kwargs)},
            )
        )
        message = broadcast.to_dict()

        async def send(peer: Peer) -> None:
            await Client.from_peer(peer).call(endpoint, *args, broadcast=message, **kwargs)

        await asyncio.gather(
            *(send(peer) for peer in list(self.peers.values())),
            return_exceptions=True,
        )
        return broadcast

    async def reply(self, broadcast: Broadcast, result: Any) -> None:
        """Reply to a broadcast using its nonce and share the reply with known peers."""
        self._remember_conversation_event(
            ConversationEvent(
                conversation_id=broadcast.nonce,
                event_id=random_hash(),
                kind="reply",
                peer=self.self_peer(),
                payload={"result": result},
                parent_id=broadcast.nonce,
            )
        )
        recipients = {broadcast.origin.id: broadcast.origin}
        for peer in self.peers.values():
            recipients.setdefault(peer.id, peer)
        recipients.pop(self.node_id, None)

        async def send(peer: Peer) -> None:
            await Client.from_peer(peer).call(
                "_synapse.broadcast.reply",
                broadcast.nonce,
                self.self_peer().to_dict(),
                result=result,
            )

        await asyncio.gather(
            *(send(peer) for peer in recipients.values()),
            return_exceptions=True,
        )

    def replies(self, broadcast: Broadcast | str) -> list[BroadcastReply]:
        """Return replies received for a broadcast or nonce."""
        nonce = broadcast.nonce if isinstance(broadcast, Broadcast) else broadcast
        return list(self.broadcast_replies.get(nonce, []))

    def conversation(self, conversation: Broadcast | str) -> list[ConversationEvent]:
        """Return locally known events for a conversation id or broadcast."""
        conversation_id = (
            conversation.nonce if isinstance(conversation, Broadcast) else conversation
        )
        return self.conversation_log.events(conversation_id)

    def conversations(self) -> list[str]:
        """Return ids of all locally known conversations."""
        return self.conversation_log.conversations()

    def _remember_conversation_event(self, event: ConversationEvent) -> bool:
        self._validate_peer_membership(event.peer)
        if not self.conversation_log.append(event):
            return False
        self.add_peer(event.peer)
        self._emit_lifecycle("conversation.event", event)
        self._emit_lifecycle(f"conversation.{event.kind}", event)
        self._maybe_compact(event.conversation_id)
        return True

    def summarizer(self, wrapped: Summarizer) -> Summarizer:
        """Register the coroutine used to summarize events during compaction."""
        self._summarizer = wrapped
        return wrapped

    def _maybe_compact(self, conversation_id: str) -> None:
        if self.conversation_max_events is None:
            return
        if conversation_id in self._compacting:
            return
        if self.conversation_log.count(conversation_id) <= self.conversation_max_events:
            return
        self._compacting.add(conversation_id)
        self._spawn(self._compact_and_release(conversation_id), name="conversation.compact")

    async def _compact_and_release(self, conversation_id: str) -> None:
        try:
            await self.compact_conversation(conversation_id)
        except Exception:
            logger.exception("Could not compact conversation {}", conversation_id)
        finally:
            self._compacting.discard(conversation_id)

    async def compact_conversation(
        self,
        conversation: Broadcast | str,
        *,
        keep_recent: int | None = None,
    ) -> ConversationEvent | None:
        """Fold older events into one local ``summary`` event.

        Compaction is local: each node compresses its own copy of the shared
        log. Gossip cannot resurrect compacted events because their ids stay
        remembered by the conversation log.
        """
        conversation_id = (
            conversation.nonce if isinstance(conversation, Broadcast) else conversation
        )
        keep = self.conversation_keep_recent if keep_recent is None else keep_recent
        events = self.conversation_log.events(conversation_id)
        head = events[0] if events and events[0].kind == "message" else None
        compactable = [event for event in events[: len(events) - keep] if event is not head]
        if not compactable:
            return None

        summary_text = await self._summarizer(compactable)
        summary = ConversationEvent(
            conversation_id=conversation_id,
            event_id=random_hash(),
            kind=SUMMARY_KIND,
            peer=self.self_peer(),
            payload={
                SUMMARY_KIND: summary_text,
                "compacted_events": len(compactable),
                "from": compactable[0].created_at,
                "until": compactable[-1].created_at,
            },
            parent_id=head.event_id if head is not None else None,
            # Take the newest compacted timestamp so the summary sorts where
            # the events it replaces used to sit.
            created_at=compactable[-1].created_at,
        )
        self.conversation_log.compact(
            conversation_id,
            [event.event_id for event in compactable],
            summary,
        )
        self._emit_lifecycle("conversation.compacted", summary)
        return summary

    async def sync_conversation(
        self,
        peer: Peer,
        conversation: Broadcast | str,
        *,
        since: float = 0.0,
    ) -> int:
        """Pull a conversation's events from a peer; return how many were new.

        Lets a late joiner (or a restarted node) catch up on a shared
        conversation it missed. Synced events are stored and emitted locally
        but not re-gossiped.
        """
        conversation_id = (
            conversation.nonce if isinstance(conversation, Broadcast) else conversation
        )
        response = await Client.from_peer(peer).call(
            "_synapse.conversation.sync", conversation_id, since=since
        )
        if not isinstance(response, dict):
            return 0
        added = 0
        for data in response.get("events", []):
            event = ConversationEvent.from_dict(data)
            with contextlib.suppress(InvalidMessageError):
                added += self._remember_conversation_event(event)
        return added

    async def emit_conversation_event(
        self,
        conversation: Broadcast | str,
        kind: str,
        payload: dict[str, Any] | None = None,
        *,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationEvent:
        """Append a lightweight event to a shared conversation and gossip it to peers."""
        conversation_id = (
            conversation.nonce if isinstance(conversation, Broadcast) else conversation
        )
        event = ConversationEvent(
            conversation_id=conversation_id,
            event_id=random_hash(),
            kind=kind,
            peer=self.self_peer(),
            payload=payload or {},
            parent_id=parent_id,
            metadata=metadata or {},
        )
        self._remember_conversation_event(event)
        await self._send_conversation_event(event)
        return event

    async def ack(
        self,
        conversation: Broadcast | str,
        payload: dict[str, Any] | None = None,
        *,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationEvent:
        """Emit an opt-in acknowledgement event for a conversation."""
        if isinstance(conversation, Broadcast) and parent_id is None:
            parent_id = conversation.nonce
        return await self.emit_conversation_event(
            conversation,
            "ack",
            payload,
            parent_id=parent_id,
            metadata=metadata,
        )

    async def _send_conversation_event(
        self,
        event: ConversationEvent,
        *,
        exclude: set[str] | None = None,
    ) -> None:
        excluded = {self.node_id, event.peer.id, *(exclude or set())}
        recipients = [peer for peer in self.peers.values() if peer.id not in excluded]

        async def send(peer: Peer) -> None:
            await Client.from_peer(peer).call("_synapse.conversation.event", event.to_dict())

        await asyncio.gather(*(send(peer) for peer in recipients), return_exceptions=True)

    async def _discover(self, *, wait: float = 0) -> None:
        if self.mdns is not None:
            await self.mdns.discover(wait=wait)

        for address, port in self.seeds:
            try:
                response = await Client(address, port).call(
                    "_synapse.join", self.self_peer().to_dict()
                )
            except Exception:
                logger.exception("Could not join seed {}:{}", address, port)
                continue

            if not isinstance(response, dict):
                continue
            for peer in response.get("peers", []):
                self.add_peer(Peer.from_dict(peer))
            self_peer = response.get("self")
            if self_peer:
                self.add_peer(Peer.from_dict(self_peer))

    async def join(self, *, wait: float = 0) -> None:
        await self._discover(wait=wait)

    def _register_node_endpoints(self) -> None:
        @self.endpoint("_node.info", publish=False)
        async def node_info() -> dict[str, Any]:
            return {
                "name": self.name,
                "role": self.role,
                "description": self.description,
                "capabilities": [capability.name for capability in self.capabilities],
            }

        @self.endpoint("_node.capabilities", publish=False)
        async def node_capabilities() -> list[dict[str, Any]]:
            return [asdict(capability) for capability in self.capabilities]

        @self.endpoint("_node.ask", publish=False)
        async def node_ask(task: str, context: dict[str, Any] | None = None) -> Any:
            if self._ask_handler is None:
                raise RuntimeError("node has no ask handler")
            return await self._ask_handler(task, context or {})

        @self.endpoint("synapse.ask", publish=False, description="Ask this node to perform work")
        async def swarm_ask(
            task: str,
            context: dict[str, Any] | None = None,
            broadcast: Broadcast | None = None,
        ) -> Any:
            if self._ask_handler is None:
                raise RuntimeError("node has no ask handler")
            if broadcast is None:
                return await self._ask_handler(task, context or {})
            # Defer: ACK now, run the handler in the background, and deliver
            # the result as a broadcast reply. Keeps the origin's RPC short no
            # matter how long the agent behind the handler takes.
            await self.ack(broadcast)
            self._spawn(self._run_deferred_ask(task, context or {}, broadcast), name="synapse.ask")
            return {"accepted": True, "deferred": True}

    async def _run_deferred_ask(
        self, task: str, context: dict[str, Any], broadcast: Broadcast
    ) -> None:
        assert self._ask_handler is not None
        try:
            result = await self._ask_handler(task, context)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Ask handler raised for broadcast {}", broadcast.nonce)
            await self.emit_conversation_event(
                broadcast, "error", {"task": task, "error": str(e)}
            )
            return
        await self.reply(broadcast, result)

    def _register_system_endpoints(self) -> None:
        @self.endpoint("_synapse.ping", publish=False)
        async def ping() -> str:
            return "pong"

        @self.endpoint("_synapse.info", publish=False)
        async def info() -> dict:
            return self.node_info()

        @self.endpoint("_synapse.methods", publish=False)
        async def methods() -> list[dict[str, str | bool]]:
            return [
                asdict(metadata)
                for metadata in self.endpoint_metadata.values()
                if metadata.publish
            ]

        @self.endpoint("_synapse.peers", publish=False)
        async def peers() -> list[dict]:
            return [peer.to_dict() for peer in self.peers.values()]

        @self.endpoint("_synapse.artifacts", publish=False)
        async def artifacts() -> list[dict[str, Any]]:
            return [
                artifact.descriptor().to_dict()
                for artifact in self.artifact_directory.values()
            ]

        @self.endpoint("_synapse.artifact.get", publish=False)
        async def artifact_get(name: str) -> dict[str, Any]:
            artifact = self.artifact_directory.get(name)
            if artifact is None:
                raise InvalidMessageError(f"unknown artifact: {name}")
            return artifact.to_dict()

        @self.endpoint("_synapse.conversation.event", publish=False)
        async def conversation_event(event: dict[str, Any]) -> dict[str, Any]:
            incoming = ConversationEvent.from_dict(event)
            remembered = self._remember_conversation_event(incoming)
            if remembered:
                await self._send_conversation_event(incoming)
            return {"ok": True, "stored": remembered}

        @self.endpoint("_synapse.conversation.sync", publish=False)
        async def conversation_sync(conversation_id: str, since: float = 0.0) -> dict[str, Any]:
            events = self.conversation_log.events(conversation_id, since=since)
            return {"events": [event.to_dict() for event in events]}

        @self.endpoint("_synapse.conversation.list", publish=False)
        async def conversation_list() -> list[str]:
            return self.conversation_log.conversations()

        @self.endpoint("_synapse.join", publish=False)
        async def join(peer: dict) -> dict:
            incoming = Peer.from_dict(peer)
            self._validate_peer_membership(incoming)
            self.add_peer(incoming)
            return {"accepted": True, "self": self.self_peer().to_dict(), "peers": await peers()}

        @self.endpoint("_synapse.heartbeat", publish=False)
        async def heartbeat(peer: dict) -> dict:
            incoming = Peer.from_dict(peer)
            self._validate_peer_membership(incoming)
            self.add_peer(incoming)
            return {"ok": True, "self": self.node_info()}

        @self.endpoint("_synapse.broadcast.reply", publish=False)
        async def broadcast_reply(nonce: str, peer: dict, result=None) -> dict:
            incoming = Peer.from_dict(peer)
            self._validate_peer_membership(incoming)

            replies = self.broadcast_replies.setdefault(nonce, [])
            if any(reply.peer.id == incoming.id for reply in replies):
                return {"ok": True}

            self.add_peer(incoming)
            self._remember_conversation_event(
                ConversationEvent(
                    conversation_id=nonce,
                    event_id=random_hash(),
                    kind="reply",
                    peer=incoming,
                    payload={"result": result},
                    parent_id=nonce,
                )
            )
            reply = BroadcastReply(nonce=nonce, peer=incoming, result=result)
            replies.append(reply)
            self._emit_lifecycle("broadcast.reply", reply)

            recipients = {
                known.id: known
                for known in self.peers.values()
                if known.id not in {self.node_id, incoming.id}
            }

            async def forward(known: Peer) -> None:
                await Client.from_peer(known).call(
                    "_synapse.broadcast.reply",
                    nonce,
                    incoming.to_dict(),
                    result=result,
                )

            await asyncio.gather(
                *(forward(known) for known in recipients.values()),
                return_exceptions=True,
            )
            return {"ok": True}

    def endpoint(
        self,
        name: str | None = None,
        *,
        publish: bool = True,
        description: str = "",
    ) -> Callable:
        """Decorator to register a coroutine as an RPC endpoint."""

        def decorator(wrapped: Callable) -> Callable:
            endpoint_name = name or wrapped.__name__
            self.endpoint_directory[endpoint_name] = wrapped
            self.endpoint_metadata[endpoint_name] = EndpointMetadata(
                name=endpoint_name,
                publish=publish,
                description=description or inspect.getdoc(wrapped) or "",
            )
            return wrapped

        return decorator

    def periodic(self, schedule: float | Schedule) -> Callable:
        """Decorator to schedule a coroutine as a periodic task."""
        task_schedule = every(seconds=schedule) if isinstance(schedule, int | float) else schedule

        def decorator(wrapped: Callable) -> Callable:
            if not inspect.iscoroutinefunction(wrapped):
                raise TypeError("periodic task must be an async function")
            self.periodic_executor.add_task(
                PeriodicTask(name=wrapped.__name__, callable=wrapped, schedule=task_schedule)
            )
            return wrapped

        return decorator
