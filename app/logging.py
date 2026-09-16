import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "event": record.getMessage(),
                "level": record.levelname,
                **{
                    key: getattr(record, key)
                    for key in ("job_id", "correlation_id", "status", "code", "duration_ms")
                    if hasattr(record, key)
                },
            }
        )


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("folio")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
