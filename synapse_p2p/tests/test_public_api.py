from synapse_p2p import (
    AdvertisedArtifact,
    BaseRPCSerializer,
    Broadcast,
    BroadcastReply,
    Capability,
    Client,
    MessagePackRPCSerializer,
    Node,
    NodeKind,
    Peer,
    RemoteProcedureCall,
    RPCError,
    RPCRequest,
    RPCResponse,
    ServedArtifact,
)


def test_substrate_types_are_exported_from_top_level_package():
    assert AdvertisedArtifact is not None
    assert BaseRPCSerializer is not None
    assert Broadcast is not None
    assert BroadcastReply is not None
    assert Capability is not None
    assert Client is not None
    assert MessagePackRPCSerializer is not None
    assert Node is not None
    assert NodeKind is not None
    assert Peer is not None
    assert RPCError is not None
    assert RPCRequest is not None
    assert RPCResponse is not None
    assert RemoteProcedureCall is RPCRequest
    assert ServedArtifact is not None
