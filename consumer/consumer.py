import json
import os

from kafka import KafkaConsumer


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
        print(json.dumps(message.value, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()