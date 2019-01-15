from electron.messages import RemoteProcedureCall


def test_rpc_hydrate():
    payload = {
        "endpoint": "my_endpoint",
        "args": [1, 2],
    }

    new = RemoteProcedureCall.hydrate(payload)

    assert new.endpoint == payload["endpoint"]
    assert new.args == payload["args"]
