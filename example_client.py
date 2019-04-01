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
