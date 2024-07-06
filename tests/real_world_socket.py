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

    def __init__(self) -> None:
        self._socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def connect(self, host: str, port: int) -> None:
        self._socket.connect((host, port))

    def send(self, data: bytes) -> int:
        return self._socket.send(data)

    def receive(self, buffer_size: int) -> bytes:
        return self._socket.recv(buffer_size)

    def close(self) -> None:
        self._socket.close()
