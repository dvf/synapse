from random import randint

import pytest
from faker import Faker

from synapse_p2p.server import Server
from synapse_p2p.utils import random_hash

fake = Faker()


@pytest.fixture
def identifier() -> str:
    return random_hash()


@pytest.fixture
def ipv4() -> str:
    return fake.ipv4_public()


@pytest.fixture
def port() -> int:
    return randint(2000, 10000)


@pytest.fixture
def server() -> Server:
    return Server(address="127.0.0.1", port=9999)
