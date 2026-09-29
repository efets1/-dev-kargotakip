import json
import os

from kafka import KafkaConsumer


def format_event(event):
    event_type = event["event"]
    cargo_id = event["cargo_id"]
    if event_type == "cargo.delivered":
        return f"Cargo {cargo_id} delivered."
    if event_type == "cargo.status_changed":
        return f"Cargo {cargo_id} status changed to {event['status']}."
    if event_type == "cargo.created":
        return f"Cargo {cargo_id} created."
    return json.dumps(event, ensure_ascii=False)


def main():
    consumer = KafkaConsumer(
        "cargo-events",
        bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(","),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="cargo-event-consumer",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
    print("Listening for cargo events...", flush=True)
    for message in consumer:
        print(format_event(message.value), flush=True)


if __name__ == "__main__":
    main()