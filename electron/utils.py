import os
from hashlib import sha256
from typing import List
from uuid import uuid4

from electron.types import Node


def guid():
    return uuid4().hex


def random_hash():
    return sha256(os.urandom(16)).hexdigest()


def sort_nodes_by_xor_distance(source: int, nodes: List[Node], reverse=False):
    return sorted(nodes, key=lambda n: int(n.identifier, 16) ^ source, reverse=reverse)


def xor_distance(source: int, candidate: str):
    return source ^ int(candidate, 16)
