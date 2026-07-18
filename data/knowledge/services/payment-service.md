+++
document_id = "doc_service_payment_service"
document_type = "service"
title = "payment-service architecture and ownership"
source_uri = "internal://knowledge/services/payment-service.md"
service_tags = ["payment-service"]
environment_tags = ["production", "staging", "development"]
version = "1.4"
effective_at = "2026-07-01T01:00:00Z"
ingested_at = "2026-07-18T02:45:00Z"
metadata = { owner = "payments-platform", tier = "critical" }
+++
# Responsibilities

payment-service validates checkout requests, persists payment state, and calls the external
payment gateway for authorization. It does not store real card data in application logs.

# Dependencies

The synchronous request path depends on postgres-primary and payment-gateway. Database connections
come from an application pool configured by `db.pool.max_connections`. The lightweight health
endpoint does not exercise the database pool and can remain healthy during repository saturation.

# Observability

Primary signals include HTTP error rate, request latency, database pool utilization, pending pool
requests, connection acquisition time, and gateway dependency latency.
