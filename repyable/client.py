import random
import socket
import struct
import time
from typing import Any

from repyable import TIMEOUT


class Client:
    """Client class."""

    def __init__(self, address: str, port: int):
        """Init."""
        self.address = address
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.timeout = TIMEOUT

    def send(self, data: bytes) -> None:
        """Send data."""
        self.socket.sendto(data, (self.address, self.port))

    def recv(self, size: int) -> bytes:
        """Receive data."""
        return self.socket.recv(size)

    def close(self) -> None:
        """Close."""
        self.socket.close()
