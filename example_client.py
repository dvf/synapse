import socket

from electron.messages import RemoteProcedureCall

REMOTE_IP = "127.0.0.1"
REMOTE_PORT = 9999

rpc_encoded = RemoteProcedureCall(endpoint="sum", args=[1, 2]).encode()

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

sock.connect((REMOTE_IP, REMOTE_PORT))
sock.send(rpc_encoded)

data = sock.recv(1024)
print(f"Received: \n{data.decode()}")
sock.close()
