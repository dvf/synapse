from synapse_p2p.messages import RemoteProcedureCall


def test_rpc_defaults():
    rpc = RemoteProcedureCall(endpoint="ping")
    assert rpc.endpoint == "ping"
    assert rpc.args == []


def test_rpc_with_args():
    rpc = RemoteProcedureCall(endpoint="sum", args=[1, 2])
    assert rpc.endpoint == "sum"
    assert rpc.args == [1, 2]


def test_distinct_instances_do_not_share_args():
    a = RemoteProcedureCall(endpoint="a")
    b = RemoteProcedureCall(endpoint="b")
    a.args.append(1)
    assert b.args == []
