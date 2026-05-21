import os
from hashlib import sha256

from synapse_p2p.types import Connection


def random_hash() -> str:
    return sha256(os.urandom(16)).hexdigest()


def xor_distance(source: int, candidate: str) -> int:
    return source ^ int(candidate, 16)


def sort_connections_by_xor_distance(
    source: int,
    connections: list[Connection],
    reverse: bool = False,
) -> list[Connection]:
    return sorted(connections, key=lambda n: xor_distance(source, n.identifier), reverse=reverse)
