from __future__ import annotations

import contextlib
import logging
import multiprocessing as mp
import select
import socket
import time
from typing import TYPE_CHECKING, NamedTuple

from faster_fifo import Queue

from repyable.parallel import SafeProcess

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)

MAX_PACKET_SIZE = 1200
MAX_PACKET_PER_SECOND = 10_000


class ReceivedPacket(NamedTuple):
    """A packet that is received from a UDP socket."""

    source: tuple[str, int]
    time: float
    data: bytes


class _UDPReceiver(SafeProcess):
    use_stop_event = True

    def __init__(
        self,
        *,
        sock: socket.socket,
        receive_queue: Queue[list[ReceivedPacket]],
        name: str,
        queue_batch: int | None,
        queue_timeout: float,
    ) -> None:
        super().__init__(name=name)
        self._socket = sock
        self._queue_batch = queue_batch
        self._queue_timeout = queue_timeout
        self._receive_queue: Queue[list[ReceivedPacket]] = receive_queue

    def _put_in_queue(self) -> None:
        """Put packets in the receive queue."""
        if self.packets:
            self._receive_queue.put(self.packets, block=False)
            self.handled_packets += len(self.packets)
            self.packets: list[ReceivedPacket] = []
            self._reset_next_queue_time()

    def _reset_next_queue_time(self) -> None:
        """Reset the next queue time."""
        self.next_queue_time = time.monotonic() + self._queue_timeout

    def user_target(self) -> None:
        """Receive data from a UDP socket."""
        self.packets: list[ReceivedPacket] = []  # type:ignore[no-redef]
        self.handled_packets = 0
        self.next_queue_time = time.monotonic() + self._queue_timeout

        stop_check_counter = 0
        assert self._stop_event is not None
        while True:
            stop_check_counter += 1
            if stop_check_counter % 10 == 0 and self._stop_event.is_set():
                break

            if not self.packets:
                self._reset_next_queue_time()

            try:
                data, address = self._socket.recvfrom(MAX_PACKET_SIZE + 1)
            except BlockingIOError:
                continue

            received_time = time.monotonic()

            if len(data) > MAX_PACKET_SIZE:
                logger.warning(f"{self.name}: Packet from {address} is too large.")
                continue

            self.packets.append(ReceivedPacket(address, received_time, data))

            if self._queue_batch is not None and len(self.packets) >= self._queue_batch:
                self._put_in_queue()
                continue

            if time.monotonic() > self.next_queue_time:
                self._put_in_queue()
                continue

        self._put_in_queue()

        logger.info(f"{self.name}: handled {self.handled_packets} packets.")


class UDPReceiverServer:
    """A process that records packets from a UDP socket."""

    use_stop_event = True

    def __init__(
        self,
        *,
        sock: socket.socket | None = None,
        address: tuple[str, int] | None = None,
        name: str = "Receiver Process",
        queue_batch: int = 100_000,
        queue_timeout: float = 0.5,
        processes: int = 2,
    ) -> None:
        """Initializes a UDPReceiver object."""
        self.name = name

        if sock is not None:
            self._socket = sock
        else:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if address is None:
                self._socket.bind(("localhost", 0))

        self._socket.setblocking(False)  # noqa: FBT003

        if address is not None:
            self._socket.bind(address)

        self._poller = select.poll()
        self._poller.register(self._socket, select.POLLIN)

        self.name = name
        self.bound_address = self._socket.getsockname()
        self._queue_batch = queue_batch
        self._queue_timeout = queue_timeout
        self._processes = processes
        self._children: list[_UDPReceiver] = []

        self.receive_queue: Queue[list[ReceivedPacket]] = Queue(
            max_size_bytes=1000 * 1000 * 100
        )

        self.started = False

    def _create_receivers(self) -> None:
        """Start the receiver children."""
        for i in range(self._processes):
            logger.debug(f"{self.name}: Starting child {i}")
            receiver = _UDPReceiver(
                sock=self._socket,
                receive_queue=self.receive_queue,
                name=f"{self.name} child {i}",
                queue_batch=self._queue_batch,
                queue_timeout=self._queue_timeout,
            )
            self._children.append(receiver)
            receiver.start()

    def start(self) -> None:
        """Receive UDP packets on the specified port and count them."""
        if self.started:
            msg = "Receiver already started."
            raise RuntimeError(msg)

        self._create_receivers()
        self.started = True

    def stop(self, *, strict: bool = False) -> None:
        """Stop the receiver children."""
        living_children = [child for child in self._children if child.is_alive()]
        living_children_names = [child.name for child in living_children]
        logger.info(f"{self.name}: Stopping children: {living_children_names}")
        for child in living_children:
            child.stop()

    def is_alive(self) -> bool:
        """Check if the receiver children are alive."""
        return any(child.is_alive() for child in self._children)

    def join(self, timeout: int = 1) -> None:
        """Join the receiver children."""
        if timeout < 0:
            msg = "Timeout must be greater than or equal to 0."
            raise ValueError(msg)

        for child in self._children:
            child.join(timeout=timeout)


@contextlib.contextmanager
def get_udp_receivers(
    *names: str,
    start: bool = True,
    children: int = 2,
) -> Generator[dict[str, UDPReceiverServer], None, None]:
    """Get multiple UDPReceiver instances."""
    receivers = {
        name: UDPReceiverServer(name=name, processes=children) for name in names
    }
    for receiver_server in receivers.values():
        if start:
            receiver_server.start()
    # give time for the receiver to start
    time.sleep(0.1)
    try:
        yield receivers
    finally:
        # give time for the receiver to process all packets
        # this prevents us from having to sleep in every test
        time.sleep(0.01)
        for receiver_server in receivers.values():
            if receiver_server.is_alive():
                receiver_server.stop()

        for receiver_server in receivers.values():
            receiver_server.join(timeout=1)
            assert not receiver_server.is_alive()


class ProcessedPacket(NamedTuple):
    """Processed packets from a UDPReceiver."""

    source: tuple[str, int]
    idx: int
    scheduled_time: float
    received_time: float
    padding: bytes

    def latency(self) -> float:
        """Calculate the latency of the packet."""
        return self.received_time - self.scheduled_time


def process_packets(
    packets: list[ReceivedPacket],
) -> list[ProcessedPacket]:
    """Process packets received by a UDPReceiver.

    Supported packet format:
        [[{idx}:{scheduled_time}:{padding}]]
    """
    processed_packets = []
    for packet in packets:
        source, received_time, data = packet
        idx, scheduled_time, padding = data[2:-2].decode().split(":")
        processed_packet = ProcessedPacket(
            source=source,
            idx=int(idx),
            scheduled_time=float(scheduled_time),
            received_time=received_time,
            padding=padding.encode(),
        )
        processed_packets.append(processed_packet)

    return processed_packets
