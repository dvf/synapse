<img src="https://user-images.githubusercontent.com/1169974/54090956-6e63f500-4350-11e9-882a-c846420c22f2.png" width=700>

A rapid RPC Framework for building Python 3.7+ services using Asyncio + [MsgPack](https://msgpack.org/index.html)

# Installation

```
pip install synapse-p2p
```

# How does it work?

Synapse creates and discovers p2p nodes on common namespace, which can be whatever you choose. In the below example, we create a node on `cryptocurrencies.bitcoin` in the hope that we'd eventually implement a full Bitcoin node.

This example creates two public endpoints/functions (`get_peers`, `broadcast_message`) which anyone on the network may call. There's also a background task `do_stuff` which is a task running in the background.

```python
from synapse_p2p.server import Server

app = Server(namespace="cryptocurrencies.bitcoin")


@app.background(seconds=5)
async def do_stuff():
    print("I am doing stuff in the background")


@app.endpoint("get_nodes")
async def get_nodes(**kwargs):
    return f"Here are the nodes I know about..."


@app.endpoint("broadcast_message")
async def broadcast_message(message, **kwargs):
    return f"Sending your message to known nodes: {message}"


app.run()

```

```
███████╗██╗   ██╗███╗   ██╗ █████╗ ██████╗ ███████╗███████╗
██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝
███████╗ ╚████╔╝ ██╔██╗ ██║███████║██████╔╝███████╗█████╗  
╚════██║  ╚██╔╝  ██║╚██╗██║██╔══██║██╔═══╝ ╚════██║██╔══╝  
███████║   ██║   ██║ ╚████║██║  ██║██║     ███████║███████╗
╚══════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝
            
⚡ synapse v0.0.5                              

Publishing endpoints to namespace cryptocurrencies.bitcoin

Listening on 127.0.0.1:9999

Registered Endpoints:
- get_nodes
- broadcast_message

Background Tasks:
- do_stuff (5s)
```

## Calling an endpoint on a node from a Python client

Synapse uses MsgPack-RPC, so we craft a payload and send it over TCP:

```python
import socket

from synapse import RemoteProcedureCall

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to the node
sock.connect(("127.0.0.1", 9999))

sock.send(
    RemoteProcedureCall(endpoint="broadcast_message", args=["hello everyone"]).encode()
)

data = sock.recv(1024)
print(f"Received: \n{data.decode()}")
sock.close()
```
```
Received: 
Sending your message to known nodes: hello everyone
```
