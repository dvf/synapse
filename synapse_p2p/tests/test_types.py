import pytest

from synapse_p2p.types import NodeKind, Peer


def test_peer_kind_accepts_enum_and_serializes_to_wire_value():
    peer = Peer(id="bootstrap", address="127.0.0.1", port=9000, kind=NodeKind.BOOTSTRAP)

    assert peer.kind is NodeKind.BOOTSTRAP
    assert peer.to_dict()["kind"] == "bootstrap"


def test_peer_kind_accepts_string_from_wire():
    peer = Peer.from_dict({"id": "node", "address": "127.0.0.1", "port": 9001, "kind": "node"})

    assert peer.kind is NodeKind.NODE
    assert peer.is_kind(NodeKind.NODE)
    assert peer.is_kind("node")


def test_peer_kind_rejects_unknown_value():
    with pytest.raises(ValueError):
        Peer(id="weird", address="127.0.0.1", port=9002, kind="weird")
