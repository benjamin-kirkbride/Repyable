import contextlib
import logging
import multiprocessing as mp
import multiprocessing.queues
import queue
import threading as td
import time
import traceback
from collections.abc import Callable
from multiprocessing.connection import Connection
from multiprocessing.synchronize import Event
from types import ModuleType
from typing import Any, Literal, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class ParallelProtocol(Protocol):
    """A protocol for parallel processing."""

    def _ojoin(self, timeout: float | None = None) -> None: ...

    def is_alive(self) -> bool: ...


class SafeParallelMixin(ParallelProtocol):
    """A base class for parallel processing."""

    use_stop_event: bool = False
    subclass_name: Literal["process", "thread"]
    name: str

    def __init__(
        self,
        name: str | None,
        simple_queue_type: type[mp.SimpleQueue] | type[queue.SimpleQueue],
        target: Callable[..., Any] | None = None,
    ) -> None:
        """Initializes a Parallel object."""
        if name is not None:
            self.name = name

        self._stop_event = mp.Event() if self.use_stop_event else None
        self._not_running = mp.Event()

        if target is not None and not callable(target):
            msg = "target must be a callable object"
            raise ValueError(msg)
        self._target = target

        self._parent_exception_conn, self._child_exception_conn = mp.Pipe()
        self._exception: tuple[Exception, str] | None = None

        self.result_queue = simple_queue_type()

    def join(self, timeout: float | None = None) -> None:
        """Join the process."""
        now = time.monotonic()
        # we have to wait for the process to stop running
        if not self._not_running.wait(timeout=timeout):
            msg = f"Process {self.name} is still running."
            raise TimeoutError(msg)
        # we have to clear the pipe before joining
        # this ensures that the LOCAL/PARENT objects attributes are set properly
        if self._parent_exception_conn.poll():
            self.exception  # noqa: B018

        if self.is_alive():
            remaining_timeout = (
                None if timeout is None else timeout - (time.monotonic() - now)
            )
            self._ojoin(timeout=remaining_timeout)
            self._clean_up()

    def stop(self) -> None:
        """Stop the process."""
        logger.info(f"{self.name}: Stopping {type(self)!s}.")
        if self._stop_event is None:
            msg = "The stop method is not available if use_stop_event is False."
            raise NotImplementedError(msg)

        # make sure the thread had a chance to start running
        for _ in range(10):
            if self.is_alive():
                break
            time.sleep(0.01)
        else:
            msg = "Process is not running."
            raise RuntimeError(msg)

        assert self._stop_event is not None
        self._stop_event.set()

    def run(self) -> None:
        """Run the process."""
        try:
            self._not_running.clear()
            if self._target is not None:
                self.result_queue.put(self._target())
            else:
                self.user_target()
        except Exception as e:
            logger.exception(f"{self.name}: An exception occurred.")
            tb = traceback.format_exc()
            self._child_exception_conn.send((e, tb))
        finally:
            self._not_running.set()
            logger.info(f"{self.name}: Process finished.")

    def _clean_up(self) -> None:
        """Clean up resources."""
        self._child_exception_conn.close()
        self._parent_exception_conn.close()
        # threading queues do not have close method
        if isinstance(self.result_queue, multiprocessing.queues.SimpleQueue):
            self.result_queue.close()
        else:
            # Is this necessary?
            del self.result_queue

    def user_target(self) -> Any:
        """The user-defined run method."""
        msg = "The user_target method must be implemented if no target supplied."
        raise NotImplementedError(msg)

    @property
    def exception(self) -> tuple[Exception, str] | None:
        """Return the exception raised in the process, or None."""
        with contextlib.suppress(OSError):
            if self._parent_exception_conn.poll():
                self._exception = self._parent_exception_conn.recv()
        assert self._exception is None or (
            isinstance(self._exception, tuple)
            and len(self._exception) == 2
            and isinstance(self._exception[0], Exception)
            and isinstance(self._exception[1], str)
        )
        return self._exception


class SafeProcess(SafeParallelMixin, mp.Process):
    """A process that can be stopped and passes exceptions to the parent process."""

    def __init__(
        self,
        *args: Any,
        target: Any = None,
        name: str | None = None,
        daemon: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initializes a SafeProcess object."""
        mp.Process.__init__(self, *args, daemon=daemon, **kwargs)
        SafeParallelMixin.__init__(
            self, target=target, name=name, simple_queue_type=mp.SimpleQueue
        )

    def run(self) -> None:
        SafeParallelMixin.run(self)

    def is_alive(self) -> bool:
        return mp.Process.is_alive(self)

    def join(self, timeout: float | None = None) -> None:
        SafeParallelMixin.join(self, timeout=timeout)

    def _ojoin(self, timeout: float | None = None) -> None:
        mp.Process.join(self, timeout=timeout)


class SafeThread(SafeParallelMixin, td.Thread):
    """A thread that can be stopped and passes exceptions to the parent thread."""

    def __init__(
        self,
        *args: Any,
        target: Any = None,
        name: str | None = None,
        daemon: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initializes a SafeProcess object."""
        td.Thread.__init__(self, *args, daemon=daemon, **kwargs)
        SafeParallelMixin.__init__(
            self, target=target, name=name, simple_queue_type=queue.SimpleQueue
        )

    def run(self) -> None:
        SafeParallelMixin.run(self)

    def is_alive(self) -> bool:
        return td.Thread.is_alive(self)

    def join(self, timeout: float | None = None) -> None:
        SafeParallelMixin.join(self, timeout=timeout)

    def _ojoin(self, timeout: float | None = None) -> None:
        td.Thread.join(self, timeout=timeout)
