import asyncio
import contextlib
import inspect
import time
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import asdict, dataclass, field
from typing import Any

from loguru import logger

from synapse_p2p import __logo__
from synapse_p2p.background import BackgroundTaskHandler
from synapse_p2p.client import Client
from synapse_p2p.exceptions import InvalidMessageError
from synapse_p2p.framing import read_frame, write_frame
from synapse_p2p.mdns import MdnsDiscovery
from synapse_p2p.messages import RPCError, RPCRequest, RPCResponse
from synapse_p2p.network import advertised_address
from synapse_p2p.serializers import BaseRPCSerializer, MessagePackRPCSerializer
from synapse_p2p.types import (
    BackgroundTask,
    Broadcast,
    BroadcastReply,
    Connection,
    NodeKind,
    Peer,
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
        max_upload_size: int = 4096,
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
        self.lifecycle_handlers: dict[str, list[Callable[[Any], Coroutine[Any, Any, None]]]] = {}
        self.endpoint_directory: dict[str, Callable] = {}
        self.endpoint_metadata: dict[str, EndpointMetadata] = {}
        self.max_upload_size = max_upload_size
        self.background_executor = BackgroundTaskHandler()
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
            self._emit_lifecycle(
                "broadcast.received",
                {
                    "endpoint": rpc.endpoint,
                    "broadcast": kwargs["broadcast"],
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

        if self.background_executor.tasks:
            print("\nBackground Tasks:")
            for task in self.background_executor.tasks:
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
        self.background_executor.start()
        if self.mdns is not None:
            await self.mdns.start()
        return self._listener

    async def stop(self) -> None:
        """Stop accepting connections and cancel background tasks."""
        await self.background_executor.stop()
        if self.mdns is not None:
            await self.mdns.stop()
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

    def _emit_lifecycle(self, event: str, payload: Any) -> None:
        for handler in self.lifecycle_handlers.get(event, []):
            asyncio.create_task(handler(payload), name=event)

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
        self.background_executor.add_task(
            BackgroundTask(
                name="_synapse.heartbeat",
                callable=self._send_heartbeats,
                period=self.heartbeat_interval,
            )
        )
        self.background_executor.add_task(
            BackgroundTask(
                name="_synapse.reap_stale_peers",
                callable=self._reap_stale_peers,
                period=self.heartbeat_interval,
            )
        )

    async def broadcast(self, endpoint: str, *args, **kwargs) -> Broadcast:
        """Send a one-way message to every known peer.

        The returned :class:`Broadcast` is the shared conversation event. Any peer
        can reply later with ``await node.reply(broadcast, result)``.
        """

        broadcast = Broadcast(nonce=new_nonce(), origin=self.self_peer(), endpoint=endpoint)
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

    def background(self, period: float) -> Callable:
        """Decorator to schedule a coroutine as a periodic background task."""

        def decorator(wrapped: Callable) -> Callable:
            self.background_executor.add_task(
                BackgroundTask(name=wrapped.__name__, callable=wrapped, period=period)
            )
            return wrapped

        return decorator
