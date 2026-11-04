"""
kafka_consumer.py — OpenServerless action: Kafka consumer with cron scheduling.
Chapter 6 — Mastering Apache OpenServerless

Reads messages from a Kafka topic using a consumer group.
Scheduled via the OpenServerless cron annotation (runs every minute).

Key design decisions:
  - consumer_timeout_ms=3000: exits after 3s of inactivity (prevents action timeout)
  - group_id: tracks committed offsets so each run reads only new messages
  - max_messages: caps messages per invocation to stay within action timeout

NOTE: The official Kafka feed provider (openwhisk-package-kafka) is NOT compatible
with OpenServerless because the nodejs runtime requires index.js as entry point
while the package uses kafkaFeed.js. The cron-based pattern is the recommended
approach for OpenServerless.

Deploy with cron annotation (every minute):
    ops action create kafka-consumer kafka_consumer.py \
        --kind python:3.11 \
        --timeout 30000 \
        -a cron '* * * * *'

Manual test:
    ops action invoke kafka-consumer --result --param topic myapp.events

Verify automatic execution:
    ops activation list --limit 5
"""
from kafka import KafkaConsumer
import json
import os


KAFKA_BROKER   = os.environ.get('KAFKA_BROKER', 'kafka.openserverless.svc.cluster.local:9092')
CONSUMER_GROUP = os.environ.get('KAFKA_CONSUMER_GROUP', 'myapp-consumer')


def main(args: dict) -> dict:
    topic        = args.get('topic', 'myapp.events')
    max_messages = int(args.get('max_messages', 10))

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BROKER,
        auto_offset_reset='earliest',     # Start from beginning if no committed offset
        enable_auto_commit=True,
        group_id=CONSUMER_GROUP,          # Tracks offsets between cron invocations
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        consumer_timeout_ms=3000          # CRITICAL: exit after 3s without messages
    )

    messages = []
    for msg in consumer:
        messages.append({
            'partition': msg.partition,
            'offset':    msg.offset,
            'key':       msg.key.decode('utf-8') if msg.key else None,
            'value':     msg.value
        })
        if len(messages) >= max_messages:
            break

    consumer.close()

    return {
        'result':        'ok',
        'topic':         topic,
        'messages_read': len(messages),
        'messages':      messages
    }
