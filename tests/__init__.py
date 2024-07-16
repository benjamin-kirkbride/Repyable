"""Package for test modules."""

from __future__ import annotations

import logging
import logging.handlers
import multiprocessing as mp
import os


class _NonMainProcessQueueHandler(logging.handlers.QueueHandler):
    def __init__(self, queue: mp.Queue[logging.LogRecord]):
        super().__init__(queue)
        self.main_pid = os.getpid()

    def emit(self, record):
        # Only emit logs from non-main processes
        if os.getpid() != self.main_pid:
            super().emit(record)


log_queue = mp.Queue(-1)  # type: ignore[var-annotated]
queue_handler = _NonMainProcessQueueHandler(log_queue)

logger = logging.getLogger()
logger.addHandler(queue_handler)
