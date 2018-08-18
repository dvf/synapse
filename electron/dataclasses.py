from dataclasses import dataclass
from typing import List


@dataclass
class Node:
    identifier: str
    address: str
    port: int


@dataclass
class Version:
    identifier: str
    nodes: List[Node]
    version: str
    rpc: str = "version"
