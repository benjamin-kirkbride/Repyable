"""Module for simulating real-world network conditions in socket communications."""

import contextlib
import heapq
import logging
import logging.config
import multiprocessing as mp
import multiprocessing.synchronize
import random
import socket
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from queue import Empty
from typing import Any, Literal, NamedTuple

from faster_fifo import Queue

from repyable.parallel import SafeProcess

logger = logging.getLogger(__name__)

MIN_LATENCY = 0.0015


@dataclass(order=True, frozen=True)
class PacketSendTask:
    """A packet to be sent by the scheduler."""

    method: Literal["send", "sendto"] = field(compare=False)
    scheduled_time: float
    data: bytes = field(compare=False)
    destination_address: tuple[str, int] | None = field(default=None, compare=False)


class PacketSender(SafeProcess):
    """A thread that executes functions with a given priority."""

    use_stop_event = True

    def __init__(self, socket: socket.socket, name: str) -> None:
        """Initializes a PriorityExecutor object."""
        super().__init__(name=name)
        self._socket = socket
        self.empty_send_queue = mp.Event()

        self._queue: Queue[PacketSendTask] = Queue()
        self._heap: list[PacketSendTask] = []

    def submit(self, item: Any) -> None:
        """Submit a function to be executed with a given priority."""
        self._queue.put(item)

    def _process_queue(self) -> None:
        """Process the queue of items."""
        packet_pushed = False
        try:
            items: list[PacketSendTask] = self._queue.get_many(
                max_messages_to_get=1000, block=False
            )
        except Empty:
            return

        for item in items:
            if item.scheduled_time <= time.monotonic():
                # execute the task immediately if it's ready
                self._execute(item)
                continue
            heapq.heappush(self._heap, item)
        packet_pushed = True

        if packet_pushed and self.empty_send_queue.is_set():
            self.empty_send_queue.clear()

    def user_target(self) -> None:
        """Process the queue of items."""
        stop_check_counter = 0

        assert self._stop_event is not None
        while True:
            stop_check_counter += 1
            if stop_check_counter % 100 == 0 and self._stop_event.is_set():
                logger.info(f"{self.name}: ack stop signal")
                break

            self._process_queue()
            try:
                while self._heap[0].scheduled_time <= time.monotonic():
                    task = heapq.heappop(self._heap)
                    self._execute(task)
            except IndexError:
                self.empty_send_queue.set()
                continue

    def _execute(self, task: PacketSendTask) -> None:
        if task.method == "send":
            self._send(task.data)
            return

        if task.method == "sendto":
            assert task.destination_address is not None
            self._sendto(task.data, task.destination_address)
            return

        msg = f"Invalid method: {task.method}"
        raise ValueError(msg)

    def _send(self, data: bytes) -> None:
        """Send data to the connected address."""
        self._socket.send(data)

    def _sendto(self, data: bytes, address: tuple[str, int]) -> None:
        """Send data to a specific address."""
        self._socket.sendto(data, address)


class RealWorldUDPSocket:
    """A wrapper around the real socket that emulates real world network conditions.

    Conditions:
        - Packet loss
        - Latency
        - Packet reordering
        - Packet duplication
        - Jitter
        - Bandwidth limitations
    """

    def __init__(self, name: str) -> None:
        """Initialize the RealWorldSocket with a UDP socket."""
        self.name = name

        self._socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self._packet_sender = PacketSender(
            socket=self._socket, name=f"{name} Packet Sender"
        )

        self._packet_loss_rate: float = 0.0
        self._base_latency: float = 0.0
        self._jitter: float = 0.0

    def start_sender(self) -> None:
        """Start."""
        self._packet_sender.start()

    def stop_sender(self) -> None:
        """Stop."""
        self._packet_sender.stop()
        self._packet_sender.join()

    def join_scheduler(self, timeout: float | None = None) -> None:
        """Join."""
        self._packet_sender.join(timeout=timeout)

    def scheduler_is_alive(self) -> bool:
        """Check if the scheduler is alive."""
        return self._packet_sender.is_alive()

    def connect(self, host: str, port: int) -> None:
        """Connect the socket to a remote address.

        Args:
            host (str): The hostname or IP address to connect to.
            port (int): The port number to connect to.
        """
        self._socket.connect((host, port))

    def bind(self, address: tuple[str, int]) -> None:
        """Bind the socket to a specific address.

        Args:
            address (tuple[str, int]): The address to bind to.
        """
        self._socket.bind(address)

    def getsockname(self) -> tuple[str, int]:
        """Get the socket's own address.

        Returns:
            tuple[str, int]: The address of the socket.
        """
        address = self._socket.getsockname()
        assert isinstance(address, tuple)
        assert len(address) == 2  # noqa: PLR2004
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        return address

    def settimeout(self, timeout: float) -> None:
        """Set the timeout for the socket.

        Args:
            timeout (float): The timeout value in seconds.
        """
        self._socket.settimeout(timeout)

    def send(self, data: bytes) -> int:
        """Send data to the connected address.

        Args:
            data (bytes): The data to send.

        Returns:
            int: The number of bytes sent.
        """
        # Packet loss simulation
        if not random.random() <= self._packet_loss_rate:  # noqa: S311
            # packet loss did occur
            logger.debug(f"{self.name}: Packet loss occurred for {data.decode()=}.")
            return len(data)

        # schedule the send action
        logger.debug(f"{self.name}: Scheduled `send` action for {data.decode()=}.")
        latency = self._simulate_latency()
        if latency < MIN_LATENCY:
            self._socket.send(data)
            return len(data)

        scheduled_time = time.monotonic() + latency
        task = PacketSendTask(method="send", scheduled_time=scheduled_time, data=data)
        self._packet_sender.submit(task)
        return len(data)

    def sendto(
        self,
        data: bytes,
        address: tuple[str, int],
        delay: float = 0,
    ) -> int:
        """Send data to a specific address.

        Returns:
            int: The number of bytes sent.
        """
        # Packet loss simulation
        if random.random() <= self._packet_loss_rate:  # noqa: S311
            # packet loss did occur
            logger.debug(f"{self.name}: Packet loss occurred for {data.decode()=}.")
            return len(data)

        # schedule the sendto action
        logger.debug(f"{self.name}: Scheduled `sendto` action for {data.decode()=}.")
        latency = self._simulate_latency() + delay
        if latency < MIN_LATENCY:
            self._socket.sendto(data, address)
            return len(data)

        scheduled_time = time.monotonic() + latency
        task = PacketSendTask(
            method="sendto",
            scheduled_time=scheduled_time,
            data=data,
            destination_address=address,
        )
        self._packet_sender.submit(task)
        return len(data)

    def recv(self, buffer_size: int) -> bytes:
        """Receive data from the socket.

        Args:
            buffer_size (int): The maximum amount of data to be received at once.

        Returns:
            bytes: The received data.
        """
        received = self._socket.recv(buffer_size)
        logger.debug(f"{self.name}: Received `{received.decode()=}`.")
        return received

    def recvfrom(self, buffer_size: int) -> tuple[bytes, tuple[str, int]]:
        """Receive data from the socket.

        Args:
            buffer_size (int): The maximum amount of data to be received at once.

        Returns:
            tuple[bytes, tuple[str, int]]: The received data and the sender's address.
        """
        received, address = self._socket.recvfrom(buffer_size)
        logger.debug(f"{self.name}: Received `{received.decode()=}` from {address=}.")
        return received, address

    def _simulate_latency(self) -> float:
        """Simulate latency by delaying the data."""
        jitter = random.random() * self._jitter  # noqa: S311
        assert 0 <= jitter <= self._jitter
        return self._base_latency + jitter

    @property
    def packet_loss_rate(self) -> float:
        """Set packet loss rate."""
        return self._packet_loss_rate

    @packet_loss_rate.setter
    def packet_loss_rate(self, packet_loss_rate: float) -> None:
        if not 0 <= packet_loss_rate <= 1:
            msg = "Packet loss rate must be between 0 and 1"
            raise ValueError(msg)

        self._packet_loss_rate = packet_loss_rate

    @property
    def base_latency(self) -> float:
        """The latency for the socket."""
        return self._base_latency

    @base_latency.setter
    def base_latency(self, latency: float) -> None:
        if latency < 0:
            msg = "Latency must be a non-negative number"
            raise ValueError(msg)

        self._base_latency = latency

    @property
    def jitter(self) -> float:
        """Get the jitter range for the socket."""
        return self._jitter

    @jitter.setter
    def jitter(self, value: float) -> None:
        if not isinstance(value, float | int):
            msg = f"Jitter must be a float, got {type(value)}"
            raise TypeError(msg)

        if value < 0:
            msg = "Jitter must be a non-negative number"
            raise ValueError(msg)
        self._jitter = value

    @property
    def empty_send_queue(self) -> multiprocessing.synchronize.Event:
        """Check if the packet sender queue is empty."""
        return self._packet_sender.empty_send_queue

    def ensure_empty_send_queue(self) -> None:
        """Wait until the send queue is empty.

        This is useful for ensuring that all packets have been sent.
        """
        empty_count = 0
        empty_goal = 3
        while True:
            if self.empty_send_queue.is_set():
                empty_count += 1
            else:
                empty_count = 0

            if empty_count >= empty_goal:
                break

            time.sleep(0.1)


@contextlib.contextmanager
def get_real_world_sockets(
    *names: str,
    start_scheduler: bool = True,
    bind: bool = False,
) -> Generator[dict[str, RealWorldUDPSocket], None, None]:
    """Get multiple RealWorldUDPSocket instances."""
    sockets = {name: RealWorldUDPSocket(name=name) for name in names}
    for rws in sockets.values():
        if start_scheduler:
            rws.start_sender()
        if bind:
            rws.bind(("localhost", 0))
    try:
        yield sockets
    finally:
        for rws in sockets.values():
            rws.stop_sender()

        for rws in sockets.values():
            rws.join_scheduler(timeout=1)
            assert not rws.scheduler_is_alive()


class PacketWithTime(NamedTuple):
    """A packet with the time it was sent and received."""

    source: tuple[str, int]
    number: int
    sent_time: float
    received_time: float
    payload: str

    def latency(self) -> float:
        """Calculate the latency of the packet."""
        return self.received_time - self.sent_time


RawPacket = tuple[float, tuple[str, int], bytes]


def _process_packets(raw_packets: list[RawPacket]) -> list[PacketWithTime]:
    """Process packets received by the server."""
    packets = []
    for raw_packet in raw_packets:
        received_time, source, raw_data = raw_packet
        data = raw_data.decode()
        assert data.startswith("[[")
        assert data.endswith("]]")
        assert data.count(":") == 2  # noqa: PLR2004

        packet_number, packet_time, payload = data[2:-2].split(":")
        packet = PacketWithTime(
            source=source,
            number=int(packet_number),
            sent_time=float(packet_time),
            received_time=received_time,
            payload=payload,
        )
        packets.append(packet)
    return packets
