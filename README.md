<img width="1074" src="https://user-images.githubusercontent.com/1169974/55302502-60653980-540f-11e9-94d0-03229ceeac4e.png">


A rapid RPC Framework for building p2p networks

# Installation

```
pip install synapse-p2p
```

# How does it work?

This example creates a public endpoints called `sum` which anyone on the network may call. There's also a background task `do_stuff` which is a task running in the background.

```python
from synapse_p2p.server import Server

app = Server()


@app.background(3)
async def do_stuff():
    print("Running background task every 3 seconds")


@app.endpoint("sum")
async def my_endpoint(a, b, response, **kwargs):
    response.write(f"The sum is {a + b}".encode())


app.run()
```

## Calling an endpoint on a node from a Python client

Synapse uses MsgPack-RPC, so we craft a payload and send it over TCP:

```python
import socket

from synapse_p2p.messages import RemoteProcedureCall
from synapse_p2p.serializers import MessagePackRPCSerializer

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

sock.connect(("127.0.0.1", 9999))
sock.send(
    MessagePackRPCSerializer.serialize(RemoteProcedureCall(endpoint="sum", args=[1, 2]))
)

data = sock.recv(1024)
print(f"Received: \n{data.decode()}")
sock.close()
```
```
Received:
Thanks, the solution is 3
```
