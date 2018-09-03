from dataclasses import asdict

from electron.dataclasses import Node
from electron.serialization import pack, unpack, hydrate


def test_pack_and_unpack(node):
    packed = pack(node)
    unpacked = unpack(packed)

    assert asdict(node) == unpacked


def test_hydrate(node):
    packed = pack(node)
    unpacked = unpack(packed)

    assert node == hydrate(Node, unpacked)


def test_pack_nested_object(version):
    packed = pack(version)

    assert isinstance(packed, bytes)
