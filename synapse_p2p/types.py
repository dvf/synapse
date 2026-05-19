from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass(slots=True)
class Node:
    identifier: str
    ip: str
    port: int


@dataclass(slots=True)
class BackgroundTask:
    name: str
    callable: Callable[..., Awaitable[Any]]
    period: float


def build_node_from_peer_name(peer_name: tuple[str, int]) -> Node:
    ip, port = peer_name
    identifier = sha256(f"{ip}:{port}".encode()).hexdigest()[:8]
    return Node(identifier=identifier, ip=ip, port=port)
