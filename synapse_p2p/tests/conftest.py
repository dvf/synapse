import pytest

from synapse_p2p.node import Node


@pytest.fixture
def node() -> Node:
    return Node(address="127.0.0.1")
