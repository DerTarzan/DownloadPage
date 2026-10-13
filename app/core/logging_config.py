import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
        root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
