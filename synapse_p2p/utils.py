import os
from hashlib import sha256
from uuid import uuid4

from synapse_p2p.types import Node


def guid() -> str:
    return uuid4().hex


def random_hash() -> str:
    return sha256(os.urandom(16)).hexdigest()


def xor_distance(source: int, candidate: str) -> int:
    return source ^ int(candidate, 16)


def sort_nodes_by_xor_distance(source: int, nodes: list[Node], reverse: bool = False) -> list[Node]:
    return sorted(nodes, key=lambda n: xor_distance(source, n.identifier), reverse=reverse)
