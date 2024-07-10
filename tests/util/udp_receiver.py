import contextlib
import logging
import socket
import time
from collections.abc import Generator
from typing import NamedTuple

from repyable.parallel import SafeProcess

logger = logging.getLogger(__name__)


class ReceivedPacket(NamedTuple):
    """A packet that is received from a UDP socket."""

    source: tuple[str, int]
    time: float
    data: bytes


class UDPReceiver(SafeProcess):
    """A process that records packets from a UDP socket."""

    use_stop_event = True

    def __init__(
        self, bind_address: tuple[str, int], name: str = "Receiver Server"
    ) -> None:
        """Initializes a UDPReceiver object."""
        super().__init__(name=name)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(False)  # noqa: FBT003
        self._socket.bind(bind_address)

        self.name = name
        self.bound_address = self._socket.getsockname()

    def user_target(self) -> list[ReceivedPacket]:
        """Receive data from a UDP socket."""
        packets: list[ReceivedPacket] = []

        assert self._stop_event is not None
        while True:
            try:
                data, address = self._socket.recvfrom(1024)
                received_packet = ReceivedPacket(
                    source=address,
                    time=time.monotonic(),
                    data=data,
                )
                packets.append(received_packet)

            except BlockingIOError:
                if len(packets) == 10_000:
                    logger.critical(f"{self.name} received {len(packets)} packets.")
                if self._stop_event.is_set():
                    logger.info(f"{self.name}: ack stop signal.")
                    break
        logger.info(f"{self.name} received {len(packets)} packets.")

        return packets

    def clean_up(self) -> None:
        """Clean Up."""
        # access the result so the pipe is cleared
        self.result  # noqa: B018
        self._socket.close()
        super()._clean_up()


@contextlib.contextmanager
def get_udp_receivers(
    *names: str,
    start: bool = True,
) -> Generator[dict[str, UDPReceiver], None, None]:
    """Get multiple UDPReceiver instances."""
    receivers = {
        name: UDPReceiver(name=name, bind_address=("localhost", 0)) for name in names
    }
    for receiver in receivers.values():
        if start:
            receiver.start()
    # give time for the receiver to start
    time.sleep(0.1)
    try:
        yield receivers
    finally:
        # give time for the receiver to process all packets
        # this prevents us from having to sleep in every test
        time.sleep(0.01)
        for receiver in receivers.values():
            if receiver.is_alive():
                receiver.stop()

        for receiver in receivers.values():
            receiver.join(timeout=30)
            assert not receiver.is_alive()
            receiver.close()
