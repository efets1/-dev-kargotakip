import json
import logging
import threading

from flask import current_app


logger = logging.getLogger(__name__)
_producer = None
_producer_lock = threading.Lock()
TOPIC = "cargo-events"


def _get_producer():
    global _producer
    if _producer is None:
        with _producer_lock:
            if _producer is None:
                from kafka import KafkaProducer

                _producer = KafkaProducer(
                    bootstrap_servers=current_app.config["KAFKA_BOOTSTRAP_SERVERS"].split(","),
                    value_serializer=lambda value: json.dumps(value).encode("utf-8"),
                    api_version_auto_timeout_ms=3000,
                    request_timeout_ms=5000,
                )
    return _producer


def publish_cargo_event(event_type, cargo):
    event = {"event_type": event_type, "cargo": dict(cargo)}
    try:
        _get_producer().send(TOPIC, event)
        return True
    except Exception:
        logger.exception("Could not publish %s event to Kafka", event_type)
        return False