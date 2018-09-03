from hashlib import sha256
from random import randint
from uuid import uuid4

import pytest
from faker import Faker

from electron.dataclasses import Node, Version
from electron.hashing import hex_digest

fake = Faker()


@pytest.fixture
def node():
    return Node(
        identifier=hex_digest(uuid4().hex),
        address=fake.ipv4_public(),
        port=randint(2000, 9000),
    )


@pytest.fixture
def version():
    return Version(
        identifier=sha256(uuid4().bytes).hexdigest(),
        nodes=[node() for _ in range(0, randint(1, 20))],
        version="v1-0.1",
    )
