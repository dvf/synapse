from synapse_p2p.types import Connection
from synapse_p2p.utils import random_hash, sort_connections_by_xor_distance, xor_distance


def test_random_hash_is_hex_and_unique():
    a = random_hash()
    b = random_hash()
    assert len(a) == 64
    int(a, 16)
    assert a != b


def test_xor_distance_self_is_zero():
    ident = "deadbeef"
    assert xor_distance(int(ident, 16), ident) == 0


def test_sort_connections_by_xor_distance_orders_nearest_first():
    source = int("00000000", 16)
    connections = [
        Connection(identifier="000000ff", ip="1.1.1.1", port=1),
        Connection(identifier="00000001", ip="2.2.2.2", port=2),
        Connection(identifier="0000000f", ip="3.3.3.3", port=3),
    ]
    ordered = sort_connections_by_xor_distance(source, connections)
    assert [n.identifier for n in ordered] == ["00000001", "0000000f", "000000ff"]
