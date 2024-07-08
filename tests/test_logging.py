import concurrent.futures as futures
import logging
import time
from logging import handlers
from multiprocessing import Queue

import pytest

# Need to set up a queue and a sentinel
msg_q = Queue()
sentinel = "foo"

logger = logging.getLogger()
logger.addHandler(handlers.QueueHandler(msg_q))
logger.setLevel(logging.INFO)


def worker(max_count):
    count = 0
    while count < max_count:
        logger.info("sleeping ...")
        time.sleep(0.1)
        count += 1
    logger.info(sentinel)


@pytest.mark.parametrize(
    "Executor_",
    (
        futures.ThreadPoolExecutor,
        futures.ProcessPoolExecutor,
    ),
)
def test_spam(caplog, Executor_):
    num_records = 5

    with Executor_() as pool:
        fut = pool.submit(worker, num_records)

        all_records = []
        running = True
        while running:
            time.sleep(2)
            while not msg_q.empty():
                all_records.append(msg_q.get().getMessage())
            if sentinel in all_records:  # check for sentinel
                all_records.remove(sentinel)
                running = False

        futures.wait((fut,), timeout=0)

    assert len(all_records) == num_records
