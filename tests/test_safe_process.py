import time

from repyable.safe_process import SafeProcess


def test_safe_process_exception_handling():
    def raise_exception():
        raise ValueError("Test exception")

    process = SafeProcess(target=raise_exception)
    process.start()
    process.join()

    assert process.exception is not None
    exception, traceback = process.exception
    assert isinstance(exception, ValueError)
    assert str(exception) == "Test exception"
    assert 'raise ValueError("Test exception")' in traceback

def test_safe_process_no_exception():
    def no_exception():
        time.sleep(0.1)

    process = SafeProcess(target=no_exception)
    process.start()
    process.join()

    assert process.exception is None

def test_safe_process_stop():
    def long_running():
        while True:
            time.sleep(0.1)

    process = SafeProcess(target=long_running)
    process.start()
    time.sleep(0.2)
    process.stop()
    process.join(timeout=1)

    assert not process.is_alive()
