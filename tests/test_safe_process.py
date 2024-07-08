import time

import pytest

from repyable.safe_process import SafeProcess


def test_safe_process_exception_handling(caplog):

    def raise_exception():
        msg = "Test exception"
        raise ValueError(msg)

    process = SafeProcess(target=raise_exception)
    process.start()
    process.join()
    assert not process.is_alive()

    assert process.result is None

    assert process.exception is not None
    exception, traceback = process.exception
    assert isinstance(exception, ValueError)
    assert str(exception) == "Test exception"
    assert "raise ValueError" in traceback
    assert "Test exception" in traceback
    assert "ValueError" in caplog.text


def test_safe_process_no_exception():
    def no_exception():
        time.sleep(0.1)

    process = SafeProcess(target=no_exception)
    process.start()
    process.join()

    assert process.exception is None


def test_nonfunctional_stop():
    def long_running():
        while True:
            time.sleep(0.1)

    process = SafeProcess(target=long_running)
    process.start()
    with pytest.raises(NotImplementedError):
        process.stop()
    assert process.is_alive()
    process.kill()
    process.join()
    assert not process.is_alive()


def test_functional_stop():
    class LongRunning(SafeProcess):
        use_stop_event = True

        def user_target(self):
            assert self._stop_event is not None
            while not self._stop_event.is_set():
                time.sleep(0.1)

    process = LongRunning()
    process.start()
    process.stop()
    process.join()
    assert not process.is_alive()


def test_result():
    result = 42

    def return_value():
        return result

    process = SafeProcess(target=return_value)
    process.start()
    process.join()

    assert process.result == result


def test_many_processes():
    result = 42

    class LongRunning(SafeProcess):
        use_stop_event = True

        def user_target(self):
            assert self._stop_event is not None
            while not self._stop_event.is_set():
                time.sleep(0.1)
            return result

    processes = [LongRunning() for _ in range(100)]
    for process in processes:
        process.start()
    for process in processes:
        process.stop()
    for process in processes:
        process.join()
    for process in processes:
        assert not process.is_alive()
        assert process.result is result
        assert process.exception is None
