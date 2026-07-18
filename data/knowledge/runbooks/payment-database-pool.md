+++
document_id = "doc_runbook_payment_db_pool"
document_type = "runbook"
title = "Payment service database pool timeout runbook"
source_uri = "internal://knowledge/runbooks/payment-database-pool.md"
service_tags = ["payment-service", "postgres-primary"]
environment_tags = ["production", "staging"]
version = "3.0"
effective_at = "2026-06-01T01:00:00Z"
ingested_at = "2026-07-18T02:45:00Z"
metadata = { owner = "payments-platform", audience = "sre" }
+++
# Symptoms

Database connection acquisition timeout errors appear while HTTP requests remain queued. The
`db.pool.utilization` metric reaches the configured maximum and pending request count increases.

# Diagnosis

Compare active connections with the configured pool maximum. Check recent deployments and
configuration changes for `db.pool.max_connections`. Confirm database health and compare the
external payment gateway latency before assigning the root cause.

# Safe response

Restore a previously validated connection limit only after human review. Validate error rate,
pending requests, database load, and connection acquisition latency. Keep rollback instructions
available and do not automatically change production configuration.
