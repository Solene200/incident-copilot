+++
document_id = "doc_incident_payment_pool_20260628"
document_type = "incident"
title = "Historical payment connection pool exhaustion incident"
source_uri = "internal://knowledge/incidents/payment-pool-2026-06-28.md"
service_tags = ["payment-service"]
environment_tags = ["production"]
version = "1.0"
effective_at = "2026-06-28T06:30:00Z"
ingested_at = "2026-07-18T02:45:00Z"
metadata = { incident_reference = "historical-fixture-2026-06-28", severity = "sev2" }
+++
# Impact

Checkout requests returned elevated errors and connection pool timeout messages. Gateway latency
remained within its normal range.

# Root cause

A configuration rollout reduced the payment-service database connection limit below the validated
production baseline. The pool saturated and repository operations waited for connection acquisition.

# Resolution and learning

After human review, the team restored the validated limit and confirmed database load remained
safe. The release checklist now requires a connection limit diff and a pending-request comparison.
