import time
from typing import Any

import pytest

from repyable.parallel import SafeProcess, SafeThread


@pytest.mark.parametrize(
    "worker_class",
    [SafeProcess, SafeThread],
)
def test_safe_process_exception_handling(
    caplog: pytest.LogCaptureFixture,
    worker_class: type[SafeProcess] | type[SafeThread],
) -> None:

    def raise_exception():
        msg = "Test exception"
        raise ValueError(msg)

    worker = worker_class(target=raise_exception)
    worker.start()
    time.sleep(0.1)
    assert worker.result_queue.empty() is True

    assert worker.exception is not None
    exception, traceback = worker.exception
    assert isinstance(exception, ValueError)
    assert str(exception) == "Test exception"
    assert "raise ValueError" in traceback
    assert "Test exception" in traceback
    assert "ValueError" in caplog.text


@pytest.mark.parametrize(
    "worker_class",
    [SafeProcess, SafeThread],
)
def test_safe_process_no_exception(
    worker_class: type[SafeProcess] | type[SafeThread],
) -> None:
    def no_exception():
        time.sleep(0.1)

    worker = worker_class(target=no_exception)
    worker.start()
    worker.join()

    assert worker.exception is None


@pytest.mark.parametrize(
    "worker_class",
    [SafeProcess, SafeThread],
)
def test_nonfunctional_stop(worker_class: type[SafeProcess] | type[SafeThread]) -> None:
    def long_running():
        for _ in range(10):
            time.sleep(0.01)

    worker = worker_class(target=long_running)
    worker.start()
    with pytest.raises(NotImplementedError):
        worker.stop()
    assert worker.is_alive()
    time.sleep(0.1)
    worker.join(timeout=1)
    assert not worker.is_alive()


class LongRunningSafeProcess(SafeProcess):  # noqa: D101
    use_stop_event = True

    def __init__(  # noqa: D107
        self,
        *args: Any,
        result: int | None = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._result = result

    def user_target(self):  # noqa: D102
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            time.sleep(0.01)
        self.result_queue.put(self._result)


class LongRunningSafeThread(SafeThread):  # noqa: D101
    use_stop_event = True

    def __init__(  # noqa: D107
        self,
        *args: Any,
        result: int | None = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._result = result

    def user_target(self):  # noqa: D102
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            time.sleep(0.01)
        self.result_queue.put(self._result)


@pytest.mark.parametrize(
    "worker_class",
    [LongRunningSafeProcess, LongRunningSafeThread],
)
def test_functional_stop(
    worker_class: type[LongRunningSafeProcess] | type[LongRunningSafeThread],
) -> None:
    process = worker_class()
    process.start()
    process.stop()
    process.join()
    assert not process.is_alive()


@pytest.mark.parametrize(
    "worker_class",
    [SafeProcess, SafeThread],
)
def test_result(worker_class: type[SafeProcess] | type[SafeThread]) -> None:
    result = 42

    def return_value():
        return result

    process = worker_class(target=return_value)
    process.start()
    time.sleep(0.1)

    if process.result_queue.empty():
        pytest.fail("Result queue is empty")
    assert process.result_queue.get() == result

    process.join()


@pytest.mark.parametrize(
    "worker_class",
    [LongRunningSafeProcess, LongRunningSafeThread],
)
def test_many_processes(
    worker_class: type[LongRunningSafeProcess] | type[LongRunningSafeThread],
) -> None:
    result = 42

    processes = [worker_class(result=result) for _ in range(100)]
    for process in processes:
        process.start()
    for process in processes:
        process.stop()
    time.sleep(0.1)
    for process in processes:
        assert not process.result_queue.empty()
        assert process.result_queue.get() is result
        assert process.exception is None
    for process in processes:
        process.join()
