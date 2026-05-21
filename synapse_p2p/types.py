from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
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
class BackgroundTask:
    name: str
    callable: Callable[..., Awaitable[Any]]
    period: float


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


def build_connection_from_peer_name(peer_name: tuple[str, int]) -> Connection:
    ip, port = peer_name
    identifier = sha256(f"{ip}:{port}".encode()).hexdigest()[:8]
    return Connection(identifier=identifier, ip=ip, port=port)
