import logging

FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"


def configure_logging(level: str) -> None:
    """One format for the app and uvicorn. Leaves handlers alone if logging is already set up (e.g. pytest)."""
    logging.basicConfig(level=level, format=FORMAT)
    logging.getLogger("app").setLevel(level)
    for name in ("uvicorn", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
