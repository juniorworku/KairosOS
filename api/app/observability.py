"""JSON logs with an explicit field allowlist; request queries and bodies are excluded."""

import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        value: dict[str, object] = {"event": record.getMessage(), "level": record.levelname.lower()}
        for key in ("request_id", "path", "method", "status", "duration_ms"):
            field = getattr(record, key, None)
            if field is not None:
                value[key] = field
        return json.dumps(value)


def configure_logging() -> None:
    logger = logging.getLogger("kairos")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
