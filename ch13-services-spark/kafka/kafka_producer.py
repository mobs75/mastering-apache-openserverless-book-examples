"""
kafka_producer.py — OpenServerless action: Kafka producer.
Chapter 13 — Mastering Apache OpenServerless

Publishes messages to a Kafka topic inside the cluster.
kafka-python (v2.0.2) is pre-installed in the python:3.11 runtime.

Kafka broker: kafka.nuvolaris.svc.cluster.local:9092

IMPORTANT: Never use internal OpenWhisk topic names (e.g. _completed0, health).
Use application-specific topic names, e.g. myapp.events.

Deploy:
    ops action create kafka-producer kafka_producer.py --kind python:3.11

Test:
    ops action invoke kafka-producer --result \
      --param topic myapp.events \
      --param message '{"event": "user.signup", "user": "alice"}'
"""
from kafka import KafkaProducer
import json
import os


KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka.nuvolaris.svc.cluster.local:9092')


def main(args: dict) -> dict:
    topic   = args.get('topic', 'myapp.events')
    message = args.get('message', '{}')

    # Ensure message is always a JSON string
    if isinstance(message, dict):
        message = json.dumps(message)

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: v.encode('utf-8'),
        acks='all',               # Wait for all replicas to acknowledge
        retries=3,
        request_timeout_ms=10000
    )

    future          = producer.send(topic, value=message)
    record_metadata = future.get(timeout=10)
    producer.flush()
    producer.close()

    return {
        'result':    'sent',
        'topic':     record_metadata.topic,
        'partition': record_metadata.partition,
        'offset':    record_metadata.offset,
    }
