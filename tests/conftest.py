import logging
import logging.handlers

import pytest

from tests import log_queue, queue_handler


@pytest.fixture(autouse=True, scope="session")
def _setup_logging(pytestconfig):
    """Set up logging for the entire test session.

    Special attention to making sure that multiprocessing logging works. For both
    reporting and caplog.

    See: https://github.com/Delgan/loguru/issues/573
    """
    logging_plugin = pytestconfig.pluginmanager.getplugin("logging-plugin")

    _listener = logging.handlers.QueueListener(
        log_queue,
        logging_plugin.report_handler,
        logging_plugin.caplog_handler,
        respect_handler_level=True,
    )

    _listener.start()
    yield
    _listener.stop()
    queue_handler.close()
