# ch13-services-spark/kafka — Chapter 13

Kafka integration examples for OpenServerless.

## Architecture

Kafka runs inside the cluster with two distinct roles:

| Role | Usage | Accessible |
|------|-------|------------|
| Internal bus | Transports activation events between Controller and Invoker | NO — system only |
| Application topics | Producer/consumer for application messages | YES — use dedicated topic names |

**Connection string:** `kafka.nuvolaris.svc.cluster.local:9092`

## Files

| File | Description |
|------|-------------|
| `kafka_producer.py` | Action that publishes messages to a Kafka topic |
| `kafka_consumer.py` | Action that consumes messages — scheduled via cron annotation |

## Deploy

```bash
# Producer
ops action create kafka-producer kafka_producer.py --kind python:3.11

# Consumer — runs every minute via cron scheduler
ops action create kafka-consumer kafka_consumer.py \
    --kind python:3.11 \
    --timeout 30000 \
    -a cron '* * * * *'
```

## Test the full flow

```bash
# 1. Publish messages
ops action invoke kafka-producer --result \
  --param topic myapp.events \
  --param message '{"event": "user.signup", "user": "alice"}'

ops action invoke kafka-producer --result \
  --param topic myapp.events \
  --param message '{"event": "page.view", "page": "/home"}'

# 2. Consume manually (or wait for cron to fire)
ops action invoke kafka-consumer --result --param topic myapp.events

# 3. Verify cron is running automatically
ops activation list --limit 5
```

## Verify cron scheduler

```bash
kubectl get cronjob cron-init -n nuvolaris
# NAME        SCHEDULE    SUSPEND   ACTIVE   LAST SCHEDULE
# cron-init   * * * * *   False     0        15s
```

## Why NOT the official Kafka feed provider

The `openwhisk-package-kafka` feed provider is **not compatible** with OpenServerless:
the nodejs runtime requires `index.js` as fixed entry point, but the package uses
`kafkaFeed.js`. The cron-based pattern above is the recommended approach.
