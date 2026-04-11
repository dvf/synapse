from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass
class Node:
    identifier: str
    ip: str
    port: int


@dataclass
class BackgroundTask:
    name: str
    callable: Callable[..., Awaitable[Any]]
    period: float


def get_identifier(peer_name: tuple[str, int]) -> str:
    return sha256(f"{peer_name[0]}:{peer_name[1]}".encode()).hexdigest()


def build_node_from_peer_name(peer_name: tuple[str, int]) -> Node:
    return Node(
        identifier=get_identifier(peer_name)[:8],
        ip=peer_name[0],
        port=peer_name[1],
    )
