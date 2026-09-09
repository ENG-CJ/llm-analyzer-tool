import logging

from llm_analyzer.logging_config import configure_logging


def test_rotating_logs_created_and_handlers_not_duplicated(tmp_path):
    path = tmp_path / "logs" / "diagnostics.log"
    configure_logging(path=path)
    configure_logging(debug=True, path=path)
    logger = logging.getLogger("llm_analyzer")
    try:
        logger.info("Fixture probe completed")
        for handler in logger.handlers:
            handler.flush()
        text = path.read_text(encoding="utf-8")
        assert "Fixture probe completed" in text
        assert "INFO" in text
        assert (
            sum(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers) == 1
        )
    finally:
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
