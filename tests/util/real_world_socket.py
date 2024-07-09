"""Module for simulating real-world network conditions in socket communications."""

import contextlib
import logging
import logging.config
import multiprocessing as mp
import random
import sched
import socket
import time
from collections.abc import Generator
from typing import Any, Literal, NamedTuple, TypedDict

from repyable.safe_process import SafeProcess

logger = logging.getLogger(__name__)


class SchedulerEnterArgs(TypedDict):
    """Type definition for the arguments of the `enter` method of sched.scheduler."""

    delay: float
    priority: int
    action: Any
    argument: tuple[Any, ...]
    kwargs: dict[str, Any]


class ScheduledSenderProcessEnterArgs(TypedDict):
    """Type definition for the arguments of the `enter` method of sched.scheduler."""

    delay: float
    priority: int
    action: Literal["send", "sendto"]
    argument: tuple[Any, ...]
    kwargs: dict[str, Any]


class ScheduledSenderProcess(SafeProcess):
    """A process that runs a scheduler."""

    use_stop_event = True

    def __init__(
        self,
        *args: Any,
        socket: socket.socket,
        **kwargs: Any,
    ) -> None:
        """Initializes a SchedulerProcess object."""
        super().__init__(*args, **kwargs)
        self._socket = socket
        self.scheduler = sched.scheduler()

        self.queue: mp.Queue[SchedulerEnterArgs] = mp.Queue()

    def user_target(self) -> None:
        """Runs the scheduler."""
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            while not self.queue.empty():
                enter_args = self.queue.get()

                if enter_args["action"] == "send":
                    action: Any = self._socket.send
                elif enter_args["action"] == "sendto":
                    action = self._socket.sendto
                else:
                    msg = f"Invalid action: {enter_args['action']}"
                    raise ValueError(msg)

                new_enter_args = SchedulerEnterArgs(
                    delay=enter_args["delay"],
                    priority=enter_args["priority"],
                    action=action,
                    argument=enter_args["argument"],
                    kwargs=enter_args["kwargs"],
                )
                self.scheduler.enter(**new_enter_args)

            self.scheduler.run(blocking=False)

    def enter(  # noqa: PLR0913
        self,
        delay: float,
        priority: int,
        action: Any,
        argument: tuple[Any, ...] = (),
        kwargs: dict[str, Any] = {},  # noqa: B006
    ) -> None:
        """Schedule an action to be executed by the scheduler.

        Args:
            delay (float): The time in seconds to wait before executing the action.
            priority (int): The priority of the action.
            action (Any): The action to be executed.
            argument (tuple): The arguments to be passed to the action.
            kwargs (dict): The keyword arguments to be passed to the action.
        """
        enter_args = SchedulerEnterArgs(
            delay=delay,
            priority=priority,
            action=action,
            argument=argument,
            kwargs=kwargs,
        )
        self.queue.put(enter_args)


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

        self._scheduler_process = ScheduledSenderProcess(socket=self._socket)

        self._packet_loss_rate: float = 0.0
        self._base_latency: float = 0.0
        self._jitter: float = 0.0

    def start_scheduler(self) -> None:
        """Start."""
        self._scheduler_process.start()

    def stop_scheduler(self) -> None:
        """Stop."""
        self._scheduler_process.stop()
        self._scheduler_process.join()

    def join_scheduler(self, timeout: float | None = None) -> None:
        """Join."""
        self._scheduler_process.join(timeout=timeout)

    def scheduler_is_alive(self) -> bool:
        """Check if the scheduler is alive."""
        return self._scheduler_process.is_alive()

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
            # schedule the send action
            logger.debug(f"{self.name}: Scheduled `send` action for {data.decode()=}.")
            self._scheduler_process.enter(
                delay=self._simulate_latency(),
                priority=1,
                action="send",
                argument=(data,),
            )
        else:
            # packet loss did occur
            logger.debug(f"{self.name}: Packet loss occurred for {data.decode()=}.")
        return len(data)

    def sendto(self, data: bytes, address: tuple[str, int]) -> int:
        """Send data to a specific address.

        Args:
            data (bytes): The data to send.
            address (tuple[str, int]): The address to send the data to.

        Returns:
            int: The number of bytes sent.
        """
        # Packet loss simulation
        if not random.random() <= self._packet_loss_rate:  # noqa: S311
            # schedule the sendto action
            logger.debug(
                f"{self.name}: Scheduled `sendto` action for {data.decode()=}."
            )
            self._scheduler_process.enter(
                delay=self._simulate_latency(),
                priority=1,
                action="sendto",
                argument=(data, address),
            )
        else:
            # packet loss did occur
            logger.debug(f"{self.name}: Packet loss occurred for {data.decode()=}.")

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

    def close(self) -> None:
        """Close the socket."""
        self._socket.close()

    def _simulate_latency(self) -> float:
        """Simulate latency by delaying the data."""
        jitter = random.random() * self._jitter  # noqa: S311
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
        if not isinstance(value, float):
            msg = "Jitter must be a float"
            raise TypeError(msg)

        if value < 0:
            msg = "Jitter must be a non-negative number"
            raise ValueError(msg)
        self._jitter = value


@contextlib.contextmanager
def get_multiple_real_world_sockets(
    *names: str,
    start_scheduler: bool = True,
    bind: bool = False,
) -> Generator[dict[str, RealWorldUDPSocket], None, None]:
    """Get multiple RealWorldUDPSocket instances."""
    sockets = {name: RealWorldUDPSocket(name=name) for name in names}
    for rws in sockets.values():
        if start_scheduler:
            rws.start_scheduler()
        if bind:
            rws.bind(("localhost", 0))
    try:
        yield sockets
    finally:
        for rws in sockets.values():
            rws.close()
            if rws.scheduler_is_alive():
                rws.stop_scheduler()

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


class ReceiveProcess(SafeProcess):
    """Receives packets from a socket and measures the time it takes for each."""

    use_stop_event = True

    def __init__(
        self,
        *args: Any,
        sock: socket.socket | RealWorldUDPSocket,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Initializes a ReceiveProcess object."""
        super().__init__(*args, **kwargs)

        self.socket = sock
        if timeout is not None:
            self.socket.settimeout(timeout)

    def user_target(self) -> list[PacketWithTime]:
        """Receive packets from a socket and measure the time it takes for each."""
        packets = []

        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                raw_data, address = self.socket.recvfrom(1024)
                current_time = time.monotonic()

                packets.append((current_time, address, raw_data))

            except TimeoutError:
                break

        return _process_packets(packets)
