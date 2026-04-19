# Fixture: principles-extraction

## Purpose

Verify that evolve's Tier 2b principle extraction produces principles when
episodes carry partially overlapping lessons, with v1.2.0's relaxed
thresholds (Jaccard 0.5, min_occurrences 2) and cluster fallback.

Production deployments (Lynceus 119 cycles, 2 valid episodes) extracted 0
principles because the v1.1.0 thresholds (0.8 Jaccard, occurrences >= 3)
were too strict for short lesson strings.

## Setup

The `seed/agent/state/evolve/` directory contains pre-populated `episodes.json`
with two cases:

**Case A — primary Jaccard match (2 episodes with overlapping lessons):**
- W15 lessons: `["service_health dominated scoring under logarithmic", "ux_evolution neglected for 5 cycles"]`
- W16 lessons: `["service_health dominated under logarithmic staleness", "backlog was neglected"]`
- Expected: at least one principle extracted referring to "service_health dominated".

**Case B — cluster fallback (10 lessons, low lexical overlap):**
- Included in W17: 10 one-off lessons, no two sharing 50% tokens.
- Expected: cluster fallback fires, emits top-3 `kind: "candidate"` principles
  at confidence 0.15.

## Expected dry-run output

```
[Reflect] New principle extracted: 'service_health dominated ...' (confidence 0.3, from 2 episodes)
[Reflect] Candidate principle (cluster fallback): '...' (confidence 0.15, N lessons)
```

Resulting `principles.json` should have >= 1 entry at confidence 0.3 AND
up to 3 entries at confidence 0.15 with `kind: "candidate"`.

## Config

Defaults — no tuning needed. `config.memory.principle_similarity_threshold`
and `config.memory.principle_min_occurrences` are absent (engine uses 0.5
and 2 respectively).
