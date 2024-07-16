import logging
import logging.handlers

import pytest

from tests import log_queue, queue_handler

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True, scope="session")
def _setup_logging(pytestconfig):
    """Set up logging for the entire test session.

    Special attention to making sure that multiprocessing logging works. For both
    reporting and caplog.

    See:
    - https://github.com/Delgan/loguru/issues/573
    - https://stackoverflow.com/a/36807327/1342874
    - https://github.com/pytest-dev/pytest/blob/b9663fed6f9e19fe0c4ccbfbd4a79c35206aaaf8/src/_pytest/logging.py#L550-L552
    - https://github.com/pytest-dev/pytest/issues/3037

    """
    logging_plugin = pytestconfig.pluginmanager.getplugin("logging-plugin")

    original_handlers = logging.root.handlers.copy()
    logging.root.handlers.clear()

    _listener = logging.handlers.QueueListener(
        log_queue,
        logging_plugin.report_handler,
        logging_plugin.caplog_handler,
        respect_handler_level=True,
    )

    _listener.start()
    logging.root.addHandler(queue_handler)
    yield
    _listener.stop()
    queue_handler.close()

    logging.root.handlers = original_handlers
