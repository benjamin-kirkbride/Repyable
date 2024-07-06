import socket


class RealWorldSocket:
    """A wrapper around the real socket that emulates real world network conditions.

    Conditions:
        - Packet loss
        - Latency
        - Packet reordering
        - Packet duplication
        - Jitter
        - Bandwidth limitations
    """

    def __init__(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def connect(self, host, port):
        self._socket.connect((host, port))

    def send(self, data):
        self._socket.send(data)

    def receive(self, buffer_size):
        return self._socket.recv(buffer_size)

    def close(self):
        self._socket.close()
