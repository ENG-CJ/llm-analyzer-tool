import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from llm_analyzer import __version__
from llm_analyzer.config.paths import log_path


def configure_logging(debug: bool = False, verbose: bool = False, path: Path | None = None) -> None:
    logger = logging.getLogger("llm_analyzer")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False
    destination = path or log_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(destination, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(f"%(asctime)s %(levelname)s %(name)s v{__version__} %(message)s")
    )
    logger.addHandler(handler)
    if verbose or debug:
        logger.addHandler(logging.StreamHandler())
    logger.info("Application initialized")
