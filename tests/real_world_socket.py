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
        """Initialize the RealWorldSocket with a UDP socket."""
        self._socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def connect(self, host: str, port: int) -> None:
        """Connect the socket to a remote address.

        Args:
            host (str): The hostname or IP address to connect to.
            port (int): The port number to connect to.
        """
        self._socket.connect((host, port))

    def send(self, data: bytes) -> int:
        """Send data to the connected address.

        Args:
            data (bytes): The data to send.

        Returns:
            int: The number of bytes sent.
        """
        return self._socket.send(data)

    def receive(self, buffer_size: int) -> bytes:
        """Receive data from the socket.

        Args:
            buffer_size (int): The maximum amount of data to be received at once.

        Returns:
            bytes: The received data.
        """
        return self._socket.recv(buffer_size)

    def close(self) -> None:
        """Close the socket."""
        self._socket.close()
