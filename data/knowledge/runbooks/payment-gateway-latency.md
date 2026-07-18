+++
document_id = "doc_runbook_payment_gateway_latency"
document_type = "runbook"
title = "External payment gateway latency runbook"
source_uri = "internal://knowledge/runbooks/payment-gateway-latency.md"
service_tags = ["payment-service", "payment-gateway"]
environment_tags = ["production"]
version = "2.1"
effective_at = "2026-05-15T01:00:00Z"
ingested_at = "2026-07-18T02:45:00Z"
metadata = { owner = "payments-platform", audience = "sre" }
+++
# Symptoms

Gateway authorization spans are slow or return elevated upstream errors across multiple callers.

# Diagnosis

Compare gateway p95 latency and error rate with the payment-service database acquisition span.
If gateway latency is healthy while database waits dominate the trace, do not identify the
gateway as the primary cause.

# Safe response

Use the provider status page and dependency metrics as evidence. Escalate to the gateway owner
before changing client timeout or retry configuration.
