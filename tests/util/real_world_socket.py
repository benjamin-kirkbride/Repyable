"""Module for simulating real-world network conditions in socket communications."""

import random
import sched
import socket
from threading import Thread
from typing import Any


class SchedulerThread(Thread):
    """A thread that runs a scheduler."""

    def __init__(
        self,
        *args: Any,
        scheduler: sched.scheduler | None = None,
        **kwargs: Any,
    ) -> None:
        """Initializes a SchedulerThread object."""
        super().__init__(*args, **kwargs)
        self.scheduler = scheduler if scheduler is not None else sched.scheduler()
        self.running = True

    def run(self) -> None:
        """Runs the scheduler."""
        while self.running:
            self.scheduler.run(blocking=True)


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

    def __init__(self) -> None:
        """Initialize the RealWorldSocket with a UDP socket."""
        self._socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self._scheduler = sched.scheduler()
        self._scheduler_thread = SchedulerThread(scheduler=self._scheduler)

        self._packet_loss_rate: float = 0.0
        self._base_latency: float = 0.0

    def start(self) -> None:
        """Start."""
        self._scheduler_thread.start()

    def stop(self) -> None:
        """Stop."""
        self._scheduler_thread.running = False
        self._scheduler_thread.join()

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
        # Packet loss simulation
        if not random.random() < self._packet_loss_rate:  # noqa: S311
            self._scheduler.enter(
                delay=self._simulate_latency(),
                priority=1,
                action=self._socket.send,
                argument=(data,),
            )
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
        if not random.random() < self._packet_loss_rate:  # noqa: S311
            self._scheduler.enter(
                delay=self._simulate_latency(),
                priority=1,
                action=self._socket.sendto,
                argument=(data, address),
            )

        return len(data)

    def recv(self, buffer_size: int) -> bytes:
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

    def _simulate_latency(self) -> float:
        """Simulate latency by delaying the data."""
        jitter = random.uniform(*self._jitter_range)  # noqa: S311
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

        self._send_packet_loss_rate = packet_loss_rate

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
    def jitter_range(self) -> tuple[float, float]:
        """Get the jitter range for the socket."""
        return self._jitter_range

    @jitter_range.setter
    def jitter_range(self, jitter_range: tuple[float, float]) -> None:
        if (
            len(jitter_range) != 2  # noqa: PLR2004
            or jitter_range[0] > jitter_range[1]
            or jitter_range[0] < 0
        ):
            msg = (
                "Jitter range must be a tuple of two non-negative numbers"
                " ,with the first less than or equal to the second."
            )
            raise ValueError(msg)
        self._jitter_range = jitter_range
