from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any


class NodeKind(StrEnum):
    NODE = "node"
    BOOTSTRAP = "bootstrap"

    @classmethod
    def from_value(cls, value: str | NodeKind) -> NodeKind:
        if isinstance(value, cls):
            return value
        return cls(value)


@dataclass(slots=True)
class Connection:
    identifier: str
    ip: str
    port: int


@dataclass(slots=True)
class PeriodicTask:
    name: str
    callable: Callable[..., Awaitable[Any]]
    schedule: Any
    next_run: datetime | None = None

    @property
    def period(self) -> float | None:
        return getattr(self.schedule, "seconds", None)


@dataclass(slots=True)
class Peer:
    id: str
    address: str
    port: int
    swarm: str | None = None
    team: str | None = None
    name: str = ""
    kind: NodeKind | str = NodeKind.NODE
    capabilities: list[str] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.kind = NodeKind.from_value(self.kind)

    @property
    def node_kind(self) -> NodeKind:
        return NodeKind.from_value(self.kind)

    def is_kind(self, kind: NodeKind | str) -> bool:
        return self.kind == NodeKind.from_value(kind)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Peer:
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.node_kind.value
        return data


@dataclass(slots=True)
class Broadcast:
    nonce: str
    origin: Peer
    endpoint: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Broadcast:
        return cls(
            nonce=data["nonce"],
            origin=Peer.from_dict(data["origin"]),
            endpoint=data["endpoint"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nonce": self.nonce,
            "origin": self.origin.to_dict(),
            "endpoint": self.endpoint,
        }


@dataclass(slots=True)
class BroadcastReply:
    nonce: str
    peer: Peer
    result: Any

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BroadcastReply:
        return cls(
            nonce=data["nonce"],
            peer=Peer.from_dict(data["peer"]),
            result=data.get("result"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"nonce": self.nonce, "peer": self.peer.to_dict(), "result": self.result}


@dataclass(slots=True)
class AdvertisedArtifact:
    """Descriptor for a small document or resource a node can serve to peers."""

    name: str
    mime_type: str
    kind: str = "metadata"
    description: str = ""
    encoding: str = "json"
    size: int | None = None
    sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdvertisedArtifact:
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ServedArtifact:
    """Artifact descriptor plus inline content returned by a node."""

    name: str
    mime_type: str
    content: Any
    kind: str = "metadata"
    description: str = ""
    encoding: str = "json"
    size: int | None = None
    sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServedArtifact:
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def descriptor(self) -> AdvertisedArtifact:
        return AdvertisedArtifact(
            name=self.name,
            mime_type=self.mime_type,
            kind=self.kind,
            description=self.description,
            encoding=self.encoding,
            size=self.size,
            sha256=self.sha256,
            metadata=dict(self.metadata),
        )


@dataclass(slots=True)
class ConversationEvent:
    """A small event appended to a shared swarm conversation."""

    conversation_id: str
    event_id: str
    kind: str
    peer: Peer
    payload: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationEvent:
        return cls(
            conversation_id=data["conversation_id"],
            event_id=data["event_id"],
            kind=data["kind"],
            peer=Peer.from_dict(data["peer"]),
            payload=dict(data.get("payload", {})),
            parent_id=data.get("parent_id"),
            created_at=float(data.get("created_at", time.time())),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "event_id": self.event_id,
            "kind": self.kind,
            "peer": self.peer.to_dict(),
            "payload": self.payload,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


def build_connection_from_peer_name(peer_name: tuple[str, int]) -> Connection:
    ip, port = peer_name
    identifier = sha256(f"{ip}:{port}".encode()).hexdigest()[:8]
    return Connection(identifier=identifier, ip=ip, port=port)
