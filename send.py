import socket

UDP_IP = "0.0.0.0"
UDP_PORT = 9999

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((UDP_IP, UDP_PORT))
s.sendto("dan".encode(), ("seed.dvf.nyc", 9999))

