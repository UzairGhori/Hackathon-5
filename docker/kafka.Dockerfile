# ============================================================
# Customer Success Digital FTE — Kafka Broker
#
# Based on Confluent Platform Kafka 7.6.0.
# Configuration is driven entirely via environment variables
# in docker-compose.yml.
#
# Topics are auto-created on first produce when
# KAFKA_AUTO_CREATE_TOPICS_ENABLE=true.
# ============================================================

FROM confluentinc/cp-kafka:7.6.0

# Default broker configuration (overridden in docker-compose)
ENV KAFKA_BROKER_ID=1 \
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
    KAFKA_AUTO_CREATE_TOPICS_ENABLE=true
