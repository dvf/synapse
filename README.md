<img width="1074" src="https://user-images.githubusercontent.com/1169974/55302502-60653980-540f-11e9-94d0-03229ceeac4e.png">


A rapid RPC framework for building p2p networks.

## Installation

```
pip install synapse-p2p
```

Or, for development with [uv](https://docs.astral.sh/uv/):

```
uv sync --group dev
uv run pytest
```

## How does it work?

This example registers a public endpoint `sum` that anyone on the network may call, plus a `heartbeat` task running periodically in the background.

```python
from synapse_p2p import Server

app = Server()


@app.background(3)
async def heartbeat():
    print("Running background task every 3 seconds")


@app.endpoint("sum")
async def sum_endpoint(a, b, response, **kwargs):
    response.write(f"The sum is {a + b}".encode())


app.run()
```

## Calling an endpoint from a Python client

Synapse uses MsgPack over TCP, so we craft an `RemoteProcedureCall` payload and send it:

```python
import socket

from synapse_p2p import RemoteProcedureCall
from synapse_p2p.serializers import MessagePackRPCSerializer

with socket.create_connection(("127.0.0.1", 9999)) as sock:
    sock.sendall(
        MessagePackRPCSerializer.serialize(
            RemoteProcedureCall(endpoint="sum", args=[1, 2])
        )
    )
    data = sock.recv(1024)

print(f"Received:\n{data.decode()}")
```

```
Received:
The sum is 3
```
