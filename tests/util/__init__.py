import time
from collections.abc import Callable
from typing import Any


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
