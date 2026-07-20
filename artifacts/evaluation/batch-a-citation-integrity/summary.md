# IncidentCopilot Offline Evaluation

- Run: `evalrun_20260720T083338Z_b7eaa5a9`
- Dataset: `dataset_incident_copilot_offline` version `1.0.0`
- Samples: 3 (3 completed, 0 failed)
- Raw results: `raw-results.jsonl`

| Metric | Value |
| --- | ---: |
| Service localization accuracy | 1.0000 |
| Failure type accuracy | 1.0000 |
| Retrieval Recall@K | 1.0000 |
| Retrieval MRR | 1.0000 |
| Tool selection F1 | 0.9487 |
| Tool argument accuracy | 0.7857 |
| Evidence relevance F1 | 0.7852 |
| Citation reference consistency | 1.0000 |
| Citation locator resolvability | 1.0000 |
| Citation content integrity | 1.0000 |
| Root-cause accuracy | 1.0000 |
| Mean research rounds | 1.0000 |
| Mean tool calls | 7.0000 |
| Mean latency (ms) | 12.5324 |
| P95 latency (ms) | 15.7717 |
| Total tokens | 12512 |
| Mean tokens | 4170.6667 |
| Token usage estimated | True |
| Estimated cost | N/A (no pricing configured) |

## Limitations

- This is a fixture regression evaluation, not a production generalization claim.
- Latency is single-process wall-clock time on the current machine, not a benchmark.
- Fake Model token counts are deterministic character-based estimates.
- Root-cause accuracy uses versioned lexical indicators, not an LLM-as-judge.
- Citation reference and locator metrics use all report EvidenceRefs; content integrity uses only successfully resolved citations.
- The offline resolver covers immutable repository fixture and knowledge sources, not live HTTP citations.
- Cost is unavailable because no provider pricing was configured.
