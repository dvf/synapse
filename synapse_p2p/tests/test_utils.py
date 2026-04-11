from synapse_p2p.types import Node
from synapse_p2p.utils import random_hash, sort_nodes_by_xor_distance, xor_distance


def test_random_hash_is_hex_and_unique():
    a = random_hash()
    b = random_hash()
    assert len(a) == 64
    int(a, 16)
    assert a != b


def test_xor_distance_self_is_zero():
    ident = "deadbeef"
    assert xor_distance(int(ident, 16), ident) == 0


def test_sort_nodes_by_xor_distance_orders_nearest_first():
    source = int("00000000", 16)
    nodes = [
        Node(identifier="000000ff", ip="1.1.1.1", port=1),
        Node(identifier="00000001", ip="2.2.2.2", port=2),
        Node(identifier="0000000f", ip="3.3.3.3", port=3),
    ]
    ordered = sort_nodes_by_xor_distance(source, nodes)
    assert [n.identifier for n in ordered] == ["00000001", "0000000f", "000000ff"]
