import logging
import multiprocessing as mp
import time
import traceback
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class SafeProcess(mp.Process):
    """A process that can be stopped and passes exceptions to the parent process."""

    use_stop_event = False

    def __init__(
        self,
        *args: Any,
        target: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initializes a SafeProcess object."""
        super().__init__(*args, **kwargs)

        self._stop_event = mp.Event() if self.use_stop_event else None

        if target is not None and not callable(target):
            msg = "target must be a callable object"
            raise ValueError(msg)
        self._target = target

        self._parent_exception_conn, self._child_exception_conn = mp.Pipe()
        self._exception: tuple[Exception, str] | None = None

        self._parent_result_conn, self._child_result_conn = mp.Pipe()
        self._result: Any | None = None

    def stop(self) -> None:
        """Stop the process."""
        if self._stop_event is None:
            msg = "The stop method is not available if use_stop_event is False."
            raise NotImplementedError(msg)

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
        logger.critical("Process started.")
        logger.info("Process started.")
        try:
            result = self._target() if self._target is not None else self.user_target()

            self._set_result(result)
        except Exception as e:
            logger.exception("An error occurred in the process.")
            tb = traceback.format_exc()
            self._child_exception_conn.send((e, tb))
            raise

    def user_target(self) -> Any:
        """The user-defined run method."""
        msg = "The user_target method must be implemented if no target supplied."
        raise NotImplementedError(msg)

    @property
    def exception(self) -> tuple[Exception, str] | None:
        """Return the exception raised in the process, or None."""
        if self._parent_exception_conn.poll():
            self._exception = self._parent_exception_conn.recv()
        assert self._exception is None or (
            isinstance(self._exception, tuple)
            and len(self._exception) == 2
            and isinstance(self._exception[0], Exception)
            and isinstance(self._exception[1], str)
        )
        return self._exception

    @property
    def result(self) -> Any:
        """Return the result of the process."""
        if self._parent_result_conn.poll():
            self._result = self._parent_result_conn.recv()
        return self._result

    @result.setter
    def result(self, value: Any) -> None:
        msg = (
            "Cannot set result attribute directly."
            " Use _set_result method from process instead."
        )
        raise AttributeError(msg)

    def _set_result(self, result: Any) -> None:
        self._result = result
        self._child_result_conn.send(result)
