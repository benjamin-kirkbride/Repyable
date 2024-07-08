"""Package for test modules."""

import logging
import logging.handlers
import multiprocessing as mp

log_queue = mp.Queue(-1)  # type: ignore[var-annotated]
queue_handler = logging.handlers.QueueHandler(log_queue)

logger = logging.getLogger()
logger.addHandler(queue_handler)
