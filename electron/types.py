from dataclasses import dataclass
from hashlib import sha256


@dataclass
class Node:
    identifier: str
    ip: str
    port: int


def get_identifier(peer_name):
    return sha256(f"{peer_name[0]}:{peer_name[1]}".encode()).hexdigest()


def build_node_from_peer_name(peer_name):
    return Node(
        identifier=get_identifier(peer_name)[:8],
        ip=peer_name[0],
        port=peer_name[1],
    )
