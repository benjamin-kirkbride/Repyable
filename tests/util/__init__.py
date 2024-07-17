import time
from collections.abc import Callable
from typing import Any

from .udp_receiver import (
    MAX_PACKET_PER_SECOND,
    UDPReceiverServer,
    get_udp_receivers,
    process_packets,
)

__all__ = [
    "repeat_callable",
    "UDPReceiverServer",
    "Timer",
    "get_udp_receivers",
    "process_packets",
    "MAX_PACKET_PER_SECOND",
]


def repeat_callable(
    *,
    func: Callable[[], Any],
    num_times: int,
    delay: float = 0,
) -> Callable[..., None]:
    """Repeat a function multiple times with a delay in between."""

    def wrapper():
        for _ in range(num_times):
            func()
            time.sleep(delay)

    return wrapper


class Timer:
    """A context manager that times the execution of a block of code."""

    def __init__(self, name: str = "Timer") -> None:
        """Initializes a Timer object."""
        self.name = name

    def __enter__(self) -> "Timer":
        self.start_time = time.time()
        return self

    def __exit__(self, *_: object) -> None:

        self.end_time = time.time()
        self.elapsed_time = self.end_time - self.start_time
        print(f"{self.name} took {self.elapsed_time:.6f} seconds")

    @property
    def total_time(self) -> float:
        """Return the total time taken by the timer."""
        if self.elapsed_time is not None:
            return self.elapsed_time

        if self.start_time is not None:
            return time.time() - self.start_time

        msg = "Timer has not been started"
        raise ValueError(msg)
