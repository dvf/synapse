from random import randint

import msgpack
import pytest
from faker import Faker

from electron.types import Node
from electron.utils import random_hash

f = Faker()


@pytest.fixture
def address():
    return f.ipv4(), randint(2000, 60000)


def node_factory(identifier=None, ip=None, port=None):
    return {
        "identifier": identifier or random_hash(),
        "ip": ip or f.ipv4(),
        "port": port or randint(1000, 60000),
    }


@pytest.fixture
def valid_intro_message(node):
    return {
        "identifier": random_hash(),
        "nodes": [node() for _ in range(randint(0, 100))],
        "m": "intro",
    }


@pytest.fixture
def valid_ping_message(node):
    return {
        "identifier": random_hash(),
        "m": "ping",
    }


def test_parse_message_intro(server, valid_intro_message, address):
    new_intro, caller = server.parse_message(msgpack.packb(valid_intro_message), address)

    assert isinstance(caller, Node)
    assert isinstance(new_intro, Intro)
    assert new_intro.identifier is not None
    assert caller.distance > 0

