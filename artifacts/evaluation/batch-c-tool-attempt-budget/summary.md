# IncidentCopilot Offline Evaluation

- Run: `evalrun_20260720T093114Z_3cae6bad`
- Dataset: `dataset_incident_copilot_offline` version `1.0.0`
- Samples: 3 (3 completed, 0 failed)
- Raw results: `raw-results.jsonl`

| Metric | Value |
| --- | ---: |
| Service localization accuracy | 1.0000 |
| Failure type accuracy | 1.0000 |
| Retrieval Recall@K | 1.0000 |
| Retrieval MRR | 1.0000 |
| Tool selection F1 | 1.0000 |
| Tool argument accuracy | 1.0000 |
| Evidence relevance F1 | 0.5167 |
| Citation reference consistency | 1.0000 |
| Citation locator resolvability | 1.0000 |
| Citation content integrity | 1.0000 |
| Root-cause accuracy | 1.0000 |
| Mean research rounds | 1.0000 |
| Mean tool calls | 6.3333 |
| Mean latency (ms) | 11.2914 |
| P95 latency (ms) | 14.3827 |
| Total tokens | 15193 |
| Mean tokens | 5064.3333 |
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
