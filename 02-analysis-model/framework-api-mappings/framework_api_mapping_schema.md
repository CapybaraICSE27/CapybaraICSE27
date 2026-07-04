# Framework API Mapping Schema

| Column | Meaning |
|---|---|
| `rq` | `RQ1`, `RQ4`, or `RQ5`. |
| `framework` | Framework or assertion-library family. |
| `api_pattern` | Concrete method, namespace, or recognizable API family. |
| `receiver_or_namespace` | Receiver object or namespace, such as `page`, `locator`, `cy`, `browser`, `t`, or `expect`. |
| `emitted_feature_type` | Feature-event type emitted by the extractor before RQ aggregation. |
| `mapped_category` | Paper-facing category used by the RQ analysis. |
| `category_definition` | Short definition of the mapped category. |
| `scope_or_gate` | Eligibility rule, line-order gate, or scope rule. |
| `implementation_source` | Implementation file that emits or aggregates the mapping. |
| `notes` | Clarifying note for the API family. |
