import pytest

from synapse_p2p.server import Server


@pytest.fixture
def server() -> Server:
    return Server(address="127.0.0.1", port=9999)
