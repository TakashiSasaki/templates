# Progressive-discovery evaluation corpus

Each fixture is a small repository layout used by
`tests/test_progressive_discovery_skill.py`. The fixtures are intentionally
different: an index is a semantic boundary, not a required file at every
physical level.

- `simple-docs` — a small authored documentation tree.
- `deep-nested` — one deep destination that should be linked directly.
- `meaningful-skipping` — a deliberate physical-level skip.
- `generated-docs` — a deterministic generated index with apply/idempotence.
- `closed-inventory` — a closed inventory that must not receive an index.
- `curated-shortcuts` — curated direct links that must not be rewritten.
- `stale-missing-links` — stale and incomplete discovery evidence.
- `provider-consumer` — provider-maintenance and consumer surfaces kept apart.
- `no-publication-consumer` — a consumer with no publication system.
- `consumer-unselected` — no progressive-discovery rule or Skill selection.
