import logging
import tempfile
import unittest
from pathlib import Path

from proxy_forge.services.logging_service import configure_logging


class LoggingServiceTest(unittest.TestCase):
    def test_configure_logging_is_idempotent_per_logger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "runtime.log"
            logger_name = "proxy_forge_test_logging"

            logger = configure_logging(str(log_path), logger_name=logger_name)
            first_handlers = list(logger.handlers)
            second = configure_logging(str(log_path), logger_name=logger_name)

            self.assertIs(second, logger)
            self.assertEqual(logger.handlers, first_handlers)
            self.assertEqual(len(logger.handlers), 2)

            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()
            if hasattr(logger, "_proxy_forge_configured"):
                delattr(logger, "_proxy_forge_configured")
            logging.Logger.manager.loggerDict.pop(logger_name, None)


if __name__ == "__main__":
    unittest.main()
