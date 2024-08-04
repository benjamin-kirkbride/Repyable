import dataclasses
import logging
import socket
import time

from repyable import MAX_CLIENTS, TIMEOUT, Address, ClientStatus, packet

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Client:
    """Client class."""

    address: Address
    status: ClientStatus = ClientStatus.CONNECTED
    last_seen: float = dataclasses.field(default_factory=time.time)


class Server:
    """Server class."""

    def __init__(self, address: Address):
        """Init."""
        self.address = address
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(address)

        self.timeout = TIMEOUT
        self.max_clients = MAX_CLIENTS
        self._clients: dict[Address, Client] = {}
        self._connected_clients = 0

    def _reject(self, address: Address, reason: packet.RejectReasons) -> None:
        payload = packet.Payload(reason.encode())
        header = packet.Header(packet.PacketType.REJECT, payload.checksum)
        packet_ = packet.Packet(header, payload)
        self.socket.sendto(packet_.pack(), address)

    def _accept(self, address: Address, payload: packet.Payload) -> None:
        header = packet.Header(packet.PacketType.ACCEPT, payload.checksum)
        packet_ = packet.Packet(header, payload)
        self.socket.sendto(packet_.pack(), address)

    def connect_client(self, address: Address) -> None:
        """Connect client."""
        if self._connected_clients >= self.max_clients:
            self._reject(address, packet.RejectReasons.SERVER_FULL)
            return

        client = self._clients.get(address)
        if client is None or client.status != ClientStatus.CONNECTED:
            # Not connected
            self._clients[address] = Client(address)
            self._connected_clients += 1
            logger.info(f"Client connected: {address}")

        # send accept packet to client to confirm connection
        # we don't care whether the client was already connected
        # other response packets may not have gotten through due to packet loss
        self._accept(address, packet.Payload(b"Connected"))

    def disconnect_client(self, address: Address) -> None:
        """Disconnect client."""
        client = self._clients.get(address)
        if client is None or client.status == ClientStatus.DISCONNECTED:
            # Already disconnected
            return

        self._clients[address].status = ClientStatus.DISCONNECTED
        self._connected_clients -= 1
        logger.info(f"Client disconnected: {address}")

    def check_timeouts(self) -> None:
        """Check timeouts."""
        current_time = time.monotonic()

        for address, client in self._clients.items():
            if current_time - client.last_seen > self.timeout:
                self.disconnect_client(address)

    def update(self, delta_time: float) -> None:
        """Update."""
        try:
            data, address = self.socket.recvfrom(1024)
            self._process_packet(data, Address(*address))
        except TimeoutError:
            pass

        self.check_timeouts()

    def _process_packet(self, data: bytes, address: Address) -> None:
        """Process packet."""
        header, payload = packet.Packet.frombytes(data)

        client = self._clients.get(address)
        if client is not None:
            client.last_seen = time.monotonic()

        if header.packet_type == packet.PacketType.REQUEST_CONNECT:
            self.connect_client(address)
        elif header.packet_type == packet.PacketType.REQUEST_DISCONNECT:
            self.disconnect_client(address)
