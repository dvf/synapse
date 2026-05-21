from synapse_p2p.network import advertised_address


def test_advertised_address_uses_explicit_advertise_value():
    assert advertised_address("0.0.0.0", "10.0.0.5") == "10.0.0.5"


def test_advertised_address_uses_bind_when_bind_is_specific():
    assert advertised_address("127.0.0.1", "auto") == "127.0.0.1"


def test_node_defaults_bind_to_all_interfaces_and_advertises_reachable_address():
    from synapse_p2p import Node

    node = Node()

    assert node.bind == "0.0.0.0"
    assert node.address != "0.0.0.0"
