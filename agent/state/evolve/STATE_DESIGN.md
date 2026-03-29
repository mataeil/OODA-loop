# State File Design — ooda-harness evolve engine

This document specifies every state file under `agent/state/evolve/`, including full
schemas, retention policies, cascade rules, and the rationale behind each design decision.

---

## File Inventory

| File | Purpose | Retention | Cascade Target |
|------|---------|-----------|----------------|
| state.json | Cycle tracking + decision log (working memory) | 20 entries | episodes.json |
| confidence.json | Per-domain confidence scores | Permanent (overwritten) | principles.json |
| goals.json | User-defined project goals | Permanent (user-managed) | episodes.json |
| skill-gaps.json | Detected missing capabilities | Unlimited (user prunes) | principles.json |
| memos.json | Cross-cycle notes + score adjustments | 10 entries | episodes.json |
| action-queue.json | Implementation task queue | 20 pending, 30 completed | metrics.json |
| metrics.json | Long-term counters | Permanent (append-only counters) | None (terminal) |
| episodes.json | Weekly episode summaries (Tier 2) | 52 weeks | principles.json |
| principles.json | Permanent learned rules (Tier 3) | Permanent | None (terminal) |
| CHANGELOG.md | Human-readable activity log | 50 entries | None |

---

## 1. state.json — Cycle Tracking + Working Memory

### What it tracks

The central state file. Records how many cycles have run, when the last one happened,
whether a cycle is currently in progress (crash recovery WAL), and a rolling log of
the most recent decisions.

### Full schema

```json
{
  "schema_version": "1.0.0",
  "cycle_count": 0,
  "last_cycle": null,
  "cycle_in_progress": false,
  "decision_log": [
    {
      "cycle": 5,
      "timestamp": "2026-01-15T14:30:00Z",
      "orient_summary": "Service health degraded. 2 domains stale for 8+ hours.",
      "selected_domain": "service_health",
      "selected_skill": "/scan-health",
      "scores": {
        "service_health": 18.27,
        "test_coverage": 5.17,
        "backlog": 3.18
      },
      "confidence_at_decision": 0.9,
      "chain_executed": ["/scan-health"],
      "chain_stopped_at": null,
      "stop_reason": null,
      "result": "success",
      "prs_created": [],
      "prs_processed": [
        {
          "number": 12,
          "action": "confidence_update",
          "domain": "test_coverage",
          "type": "merged"
        }
      ],
      "skill_gaps_detected": [],
      "proposed_skills_generated": [],
      "memo_written": true,
      "contrarian_check": null
    }
  ]
}
```

### Field definitions

| Field | Type | Description |
|-------|------|-------------|
| schema_version | string | Semver. Evolve engine checks this on load. |
| cycle_count | integer | Monotonically increasing. Never resets. |
| last_cycle | string/null | ISO 8601 timestamp of last completed cycle. Null on fresh install. |
| cycle_in_progress | boolean | WAL flag. Set true at cycle start, false at cycle end. If engine starts and finds this true, it means the previous cycle crashed — enter recovery mode. |
| decision_log | array | Rolling window of the last N entries, where N = `config.memory.working_memory_size` (default 20). |

### decision_log entry fields

| Field | Type | Description |
|-------|------|-------------|
| cycle | integer | Which cycle number this entry represents. |
| timestamp | string | ISO 8601 when the cycle completed. |
| orient_summary | string | 1-3 sentence summary of the Orient phase findings. |
| selected_domain | string | The domain key that won the scoring round. |
| selected_skill | string | The primary skill invoked (e.g., "/scan-health"). |
| scores | object | Full score table: `{ domain_key: float }`. All scored domains included. |
| confidence_at_decision | float | The confidence score of the selected domain at decision time. |
| chain_executed | array | List of skill names that were actually executed (primary + chain). |
| chain_stopped_at | string/null | If the chain was interrupted, which skill was it stopped at. |
| stop_reason | string/null | Why the chain stopped. Values: `"confidence_below_threshold"`, `"open_pr_limit"`, `"halt_detected"`, `"error"`, `null`. |
| result | string | Outcome. Values: `"success"`, `"partial_success"`, `"failure"`, `"observe_only"`. |
| prs_created | array | PRs created during this cycle: `[{number, title, branch}]`. |
| prs_processed | array | PRs whose status changed: `[{number, action, domain, type}]`. Type: `"merged"`, `"rejected"`, `"closed"`. |
| skill_gaps_detected | array | Gap IDs detected during this cycle. |
| proposed_skills_generated | array | Any auto-generated skill proposals. |
| memo_written | boolean | Whether a memo was written in memos.json. |
| contrarian_check | object/null | If this cycle triggered a contrarian check: `{argument, affected_domain, score_adjustment}`. Null otherwise. |

### Retention policy

- Maximum entries: `config.memory.working_memory_size` (default 20).
- When a new entry is appended and the log exceeds max, the oldest entry is removed.
- Before removal, the evicted entry's data feeds into the episode cascade (see episodes.json).

### Crash recovery

`cycle_in_progress` acts as a Write-Ahead Log flag:
1. Engine sets `cycle_in_progress = true` at Step 0 (before HALT check).
2. Engine sets `cycle_in_progress = false` at the end of Step 5 (after all state writes).
3. If evolve starts and finds `cycle_in_progress = true`, it means the last cycle did not complete. The engine should:
   - Log a warning in CHANGELOG.md.
   - NOT increment cycle_count (incomplete cycle does not count).
   - Proceed with a fresh cycle.

---

## 2. confidence.json — Per-Domain Confidence Scores

### What it tracks

How well the engine's actions have been received in each domain. A domain where PRs
get merged has high confidence; a domain where PRs get rejected has low confidence.
Confidence feeds into the scoring formula and the chain continuation threshold.

### Full schema

```json
{
  "schema_version": "1.0.0",
  "domains": {
    "service_health": {
      "score": 0.5,
      "last_updated": null,
      "recent_outcomes": []
    }
  }
}
```

### Domain entry fields

| Field | Type | Description |
|-------|------|-------------|
| score | float | Current confidence. Range: `[config.confidence.min, config.confidence.max]` (default 0.1-1.0). |
| last_updated | string/null | ISO 8601 of last confidence change. |
| recent_outcomes | array | Last 10 outcomes that affected this score: `[{type, pr, date, delta}]`. |

### Confidence update rules

| Event | Delta | Source |
|-------|-------|--------|
| PR merged | `+config.confidence.merge_boost` (default +0.1) | prs_processed in decision_log |
| PR rejected/closed | `-config.confidence.reject_penalty` (default -0.2) | prs_processed in decision_log |
| Successful observation | No change | Observations do not affect confidence |
| Skill error | -0.1 | Chain execution failure |

Score is always clamped to `[min, max]`.

### Initialization

When a new domain appears in config.json that does not exist in confidence.json,
the engine adds it with `score = config.confidence.initial` (default 0.5).

### Retention policy

- The `domains` object is overwritten in place. No historical growth.
- `recent_outcomes` is capped at 10 entries per domain (FIFO).
- This file never grows unbounded.

### Cascade to principles

When a domain's confidence drops below 0.3 for 5+ consecutive cycles, the engine
should extract a principle: "Domain X actions are frequently rejected. Review skill
quality or reduce automation level."

---

## 3. goals.json — Project Goals

### What it tracks

User-defined goals with measurable targets. The scoring formula uses goal contribution
(`goal_weight` from config) to prioritize domains that advance active goals.

### Full schema

```json
{
  "schema_version": "1.0.0",
  "goals": [
    {
      "id": "G1",
      "name": "Reduce infrastructure cost",
      "description": "Bring monthly hosting cost below $20 through optimization",
      "target": 20,
      "current": 65,
      "unit": "USD/month",
      "direction": "decrease",
      "progress": 0.0,
      "status": "active",
      "related_domains": ["service_health"],
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

### Goal entry fields

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier. Convention: "G1", "G2", etc. |
| name | string | Short name for display. |
| description | string | What this goal means and why it matters. |
| target | number | Numeric target value. |
| current | number | Current measured value. |
| unit | string | Measurement unit (for display). |
| direction | string | `"increase"` or `"decrease"`. Determines how progress is calculated. |
| progress | float | 0.0-1.0. For "increase": `current/target`. For "decrease": `1 - (current - target) / (initial - target)`. Clamped to [0, 1]. |
| status | string | `"active"`, `"achieved"`, `"abandoned"`. |
| related_domains | array | Domain keys that contribute to this goal. Used in scoring: if a domain is related to an active goal, it gets the goal_weight bonus. |
| created_at | string | ISO 8601. |
| updated_at | string | ISO 8601. Last time `current` was updated. |

### Progress calculation

```
if direction == "increase":
    progress = min(1.0, current / target)

if direction == "decrease":
    // initial is captured as "current" at goal creation time
    progress = min(1.0, max(0.0, 1.0 - (current - target) / (initial - target)))
```

When progress reaches 1.0, the engine should set status to "achieved" and log it
in CHANGELOG.md.

### Retention policy

- Goals are user-managed. The engine updates `current` and `progress` but never
  deletes goals.
- Achieved goals remain in the file for reference.
- No cap on number of goals, but the wizard should warn if there are more than 10
  active goals (focus dilution).

### Cascade to episodes

Goal progress snapshots are included in weekly episode summaries.

---

## 4. skill-gaps.json — Detected Missing Capabilities

### What it tracks

Situations where the engine needed a capability it did not have. Tracks frequency
of occurrence so that recurring gaps can be elevated to domain suggestions.

### Full schema

```json
{
  "schema_version": "1.0.0",
  "gaps": [
    {
      "id": "gap-001",
      "description": "No skill to analyze user funnel drop-off rates",
      "detected_at": "2026-01-15T14:30:00Z",
      "detected_in_cycle": 5,
      "ooda_phase": "observe",
      "frequency": 3,
      "last_seen_cycle": 12,
      "related_domain": "ux_evolution",
      "proposed_skill": "scan-funnel",
      "resolved": false,
      "resolved_at": null,
      "resolution": null
    }
  ]
}
```

### Gap entry fields

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier. Convention: "gap-NNN". |
| description | string | What capability is missing. |
| detected_at | string | ISO 8601 when first detected. |
| detected_in_cycle | integer | Cycle number of first detection. |
| ooda_phase | string | Which phase hit the gap: `"observe"`, `"orient"`, `"decide"`, `"act"`. |
| frequency | integer | How many times this gap has been encountered. Incremented each time the same gap is detected again (fuzzy match by description similarity). |
| last_seen_cycle | integer | Most recent cycle where this gap was detected. |
| related_domain | string/null | Domain key this gap is most associated with. |
| proposed_skill | string/null | Engine's suggestion for a skill that could fill this gap. |
| resolved | boolean | Whether the gap has been addressed (skill added, or gap is no longer relevant). |
| resolved_at | string/null | ISO 8601 when resolved. |
| resolution | string/null | How it was resolved: `"skill_added"`, `"domain_added"`, `"no_longer_relevant"`, `"user_dismissed"`. |

### Automatic domain suggestion trigger

From the self-evolution review: when 3+ unresolved gaps reference the same unregistered
domain (or null domain), the engine should:
1. Log a suggestion in CHANGELOG.md: "3 skill gaps detected for unregistered domain. Consider adding a new domain."
2. Write a memo in memos.json with the suggestion.
3. Do NOT automatically add domains — that requires user action via `/ooda-config`.

### Retention policy

- No cap on unresolved gaps. They accumulate until resolved.
- Resolved gaps are retained for 30 days (or until the file exceeds 50 entries),
  then pruned oldest-first.
- Frequency is the key signal: a gap with frequency >= 5 is a strong candidate
  for a new skill.

### Cascade to principles

When a gap is resolved (skill_added), and the new skill runs successfully 3+ times,
extract a principle: "Capability X was a recurring gap, resolved by adding skill Y.
Monitor for similar patterns in domain Z."

---

## 5. memos.json — Cross-Cycle Notes + Score Adjustments

### What it tracks

The "inner monologue" of the engine. Each cycle writes a memo summarizing what happened
and optionally adjusting domain scores for the next cycle. Score adjustments are
one-shot: they are consumed (zeroed out) after being applied in the next Orient phase.

### Full schema

```json
{
  "schema_version": "1.0.0",
  "last_memo": null,
  "score_adjustments": {},
  "history": [
    {
      "cycle": 5,
      "memo": "Health stable. UX not run for 3 cycles. Boosting UX for balance.",
      "adjustments": {
        "ux_evolution": 1.0
      },
      "timestamp": "2026-01-15T14:30:00Z"
    }
  ]
}
```

### Field definitions

| Field | Type | Description |
|-------|------|-------------|
| last_memo | string/null | The most recent memo text. Quick access without scanning history. |
| score_adjustments | object | Active adjustments to apply in the next Orient phase. Keys are domain names, values are score deltas (positive or negative floats). Consumed after application: the engine zeros out this object after applying adjustments. |
| history | array | Rolling window of past memos. |

### History entry fields

| Field | Type | Description |
|-------|------|-------------|
| cycle | integer | Which cycle wrote this memo. |
| memo | string | The memo text. |
| adjustments | object | What score adjustments were written (for audit trail — these are the adjustments as they were at write time, not necessarily what was applied). |
| timestamp | string | ISO 8601. |

### Score adjustment lifecycle

1. At end of cycle N, evolve writes adjustments to `score_adjustments`.
2. At start of cycle N+1, Orient phase reads `score_adjustments` and adds them to domain scores.
3. After applying, Orient zeros out `score_adjustments: {}`.
4. The adjustment remains in `history[N].adjustments` for audit.

### When to write adjustments

The engine should write score adjustments when:
- A domain has been selected 3+ consecutive cycles (boost other domains for balance).
- A domain has not been selected for 10+ cycles (boost it to prevent neglect).
- A contrarian check produced a valid counter-argument (boost the counter-domain).
- Goal progress is stalling (boost related domains).

### Retention policy

- History: maximum `10` entries. FIFO eviction.
- Evicted history entries feed into the episode cascade.

---

## 6. action-queue.json — Implementation Task Queue

### What it tracks

Pending implementation tasks extracted from observation reports, scored by RICE
(Reach x Impact x Confidence / Effort). The implementation domain selects from
this queue when it wins a cycle.

### Full schema

```json
{
  "schema_version": "1.0.0",
  "pending": [
    {
      "id": "2026-01-15-001",
      "title": "Add rate limiting to API endpoints",
      "source_report": "reports/2026-01-15-scan-health.md",
      "source_domain": "service_health",
      "rice_score": 75.0,
      "estimated_hours": 8,
      "difficulty": "medium",
      "related_files": ["src/middleware/ratelimit.ts"],
      "prerequisites": [],
      "status": "pending",
      "extracted_at": "2026-01-15T14:30:00Z",
      "pr_number": null,
      "decay_applied": 0.0,
      "status_history": [
        {
          "status": "pending",
          "at": "2026-01-15T14:30:00Z",
          "reason": "Extracted from health report: 3 rate-limit incidents this week."
        }
      ]
    }
  ],
  "in_progress": [],
  "completed": []
}
```

### Action entry fields

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier. Convention: "YYYY-MM-DD-NNN". |
| title | string | Short summary of the action. |
| source_report | string/null | Path to the report that generated this action. |
| source_domain | string | Which domain's observation produced this action. |
| rice_score | float | RICE score at extraction time. Immutable base score. |
| estimated_hours | integer | Rough effort estimate. |
| difficulty | string | `"low"`, `"medium"`, `"high"`. Maps to safety levels: low = Level 1, medium = Level 2, high = Level 3. |
| related_files | array | File paths likely to be modified. |
| prerequisites | array | IDs of other actions that must complete first. |
| status | string | `"pending"`, `"in_progress"`, `"completed"`, `"merged"`, `"rejected"`, `"decayed"`. |
| extracted_at | string | ISO 8601 when the action was added to the queue. |
| pr_number | integer/null | PR number if a PR was created for this action. |
| decay_applied | float | Cumulative decay penalty applied to this item. |
| status_history | array | Audit trail of status transitions. |

### RICE score with decay — effective score calculation

The implementation domain uses **effective_score**, not raw rice_score, for prioritization:

```
age_days = (now - extracted_at).days
decay_periods = floor(age_days / config.memory.action_queue_decay_days)
cumulative_decay = decay_periods * config.memory.action_queue_decay_amount

effective_score = rice_score - (cumulative_decay * rice_score)
// i.e., each decay period reduces the score by decay_amount proportion of the original
// With defaults: every 14 days, the item loses 5% of its original RICE score
```

Design decision: Decay is proportional to the original RICE score, not the current
effective score. This prevents exponential decay (which would make items nearly
impossible to recover) and keeps the math simple. A RICE-75 item loses 3.75 points
per 14 days. After 280 days (20 decay periods), it has lost 100% and is auto-removed.

When `effective_score` drops below 10.0, the item is automatically moved to completed
with status `"decayed"` and a status_history entry.

### Retention policy

- Pending: max 20 items. If full and a new item arrives with higher effective_score,
  the lowest-scoring pending item is evicted to completed with status `"decayed"`.
- In-progress: max 1 item at a time (one PR per cycle rule).
- Completed: max 30 items. FIFO eviction — oldest completed items are dropped.

### Cascade to metrics

When items move to completed (merged or rejected), metrics.json counters are updated.

---

## 7. metrics.json — Long-Term Counters

### What it tracks

Permanent counters that never reset. Provides the data for `/ooda status` dashboard
and long-term trend analysis. This is the only file that grows monotonically
without eviction — but the growth is bounded because it only stores counters and
daily summaries, not raw logs.

### Full schema

```json
{
  "schema_version": "1.0.0",
  "counters": {
    "total_cycles": 0,
    "total_prs_created": 0,
    "total_prs_merged": 0,
    "total_prs_rejected": 0,
    "total_skill_executions": 0,
    "total_chain_executions": 0,
    "total_halts": 0,
    "total_dry_runs": 0
  },
  "domain_executions": {
    "service_health": 0,
    "test_coverage": 0
  },
  "cost": {
    "total_estimated_usd": 0.0,
    "daily_log": [
      {
        "date": "2026-01-15",
        "estimated_usd": 0.42,
        "cycles": 3
      }
    ]
  },
  "streaks": {
    "current_domain": null,
    "current_streak": 0,
    "longest_streak": 0,
    "longest_streak_domain": null
  },
  "first_cycle_at": null,
  "last_updated": null
}
```

### Counter definitions

| Counter | Incremented when |
|---------|-----------------|
| total_cycles | Every cycle completion (not dry runs). |
| total_prs_created | A PR is created during Act phase. |
| total_prs_merged | A processed PR has type "merged". |
| total_prs_rejected | A processed PR has type "rejected" or "closed". |
| total_skill_executions | Each individual skill invocation (primary + chain members). |
| total_chain_executions | Each chain that runs (not individual skills, but complete chains). |
| total_halts | Engine encounters HALT file. |
| total_dry_runs | `/evolve --dry-run` is executed. |

### domain_executions

Keys match config.json domain keys. Value is total number of times that domain was
selected as the winner. Automatically adds new domains as they appear in config.

### cost.daily_log

- One entry per day the engine runs.
- `estimated_usd`: rough cost estimate for the day (based on token counting if available,
  or a flat estimate per cycle from config).
- `daily_log` is capped at 90 entries (3 months). Older entries are summarized into
  `total_estimated_usd` before eviction.
- The cost hard gate from config (`cost.daily_limit_usd`) checks the current day's
  entry before allowing a new cycle.

### streaks

Tracks consecutive same-domain selections. Used by memo generation to detect
when balance adjustments are needed (3+ consecutive triggers a memo).

### Retention policy

- Counters: permanent, never reset.
- domain_executions: permanent, one integer per domain.
- cost.daily_log: 90 days rolling window. Evicted amounts added to total_estimated_usd.
- This file stays small because it only stores aggregates.

---

## 8. episodes.json — Weekly Episode Summaries (Tier 2 Memory)

### What it tracks

Compressed summaries of what happened each week. This is the bridge between
short-term working memory (decision_log, 20 entries) and permanent principles.
Episodes capture patterns that are too detailed for principles but too old for
working memory.

### Full schema

```json
{
  "schema_version": "1.0.0",
  "episodes": [
    {
      "id": "EP-2026-W03",
      "week_start": "2026-01-13",
      "week_end": "2026-01-19",
      "cycle_range": [8, 14],
      "total_cycles": 7,
      "summary": "Focused on service health and UX. First autonomous PR created and merged. Test coverage stagnant.",
      "domains_selected": {
        "service_health": 3,
        "ux_evolution": 2,
        "implementation": 2
      },
      "confidence_snapshot": {
        "service_health": 0.9,
        "ux_evolution": 0.6,
        "test_coverage": 0.7
      },
      "goal_progress_snapshot": [
        {
          "id": "G1",
          "progress_start": 0.0,
          "progress_end": 0.15
        }
      ],
      "prs_created": 2,
      "prs_merged": 1,
      "prs_rejected": 0,
      "key_decisions": [
        "Boosted UX domain after 3 consecutive health cycles",
        "First implementation cycle — PR #4 created for quota modal"
      ],
      "skill_gaps_found": 1,
      "contrarian_checks": 0,
      "patterns_detected": [
        "service_health dominates early cycles due to 2.0 weight",
        "Implementation domain needs open-PR penalty to prevent queue flooding"
      ],
      "created_at": "2026-01-19T23:59:00Z"
    }
  ]
}
```

### Episode entry fields

| Field | Type | Description |
|-------|------|-------------|
| id | string | "EP-YYYY-WNN" format. ISO week number. |
| week_start / week_end | string | ISO date range. |
| cycle_range | array | [first_cycle, last_cycle] in this episode. |
| total_cycles | integer | How many cycles ran this week. |
| summary | string | 2-3 sentence natural language summary. |
| domains_selected | object | Count of how many times each domain won. |
| confidence_snapshot | object | End-of-week confidence scores per domain. |
| goal_progress_snapshot | array | Progress delta for each active goal. |
| prs_created / merged / rejected | integer | PR counts for the week. |
| key_decisions | array | 2-5 most significant decisions or events. |
| skill_gaps_found | integer | New gaps detected this week. |
| contrarian_checks | integer | How many contrarian checks ran. |
| patterns_detected | array | Patterns the engine noticed across the week. |
| created_at | string | ISO 8601. |

### Episode generation trigger

Episodes are generated **on the first cycle of a new ISO week** (Monday).
The engine checks: is the current ISO week different from the last episode's week?
If yes, generate an episode for the previous week.

This is simpler than "every N cycles" because:
- It aligns with human time perception (weekly cadence).
- It works regardless of cycle frequency (1 cycle/week or 20 cycles/week).
- The ISO week boundary is unambiguous.

### Episode generation process

1. Collect all decision_log entries from the previous week (by timestamp, not cycle number).
2. Aggregate domain selections, PR counts, confidence changes, goal deltas.
3. Ask the LLM to summarize key_decisions and patterns_detected based on the raw data.
4. Write the episode entry.
5. Prune old episodes beyond retention limit.

### Retention policy

- Maximum: `config.memory.episode_retention_weeks` (default 52) entries.
- FIFO eviction. Before evicting, feed the episode into principle extraction.

### Cascade to principles

When an episode is evicted (52 weeks old), or when a pattern appears in 4+ consecutive
episodes, the engine should evaluate whether to extract a principle. The extraction
criteria are detailed in the principles.json section.

---

## 9. principles.json — Permanent Learned Rules (Tier 3 Memory)

### What it tracks

Hard-won lessons that should persist indefinitely. These are the most compressed,
highest-value learnings from the entire history of the engine's operation.

### Full schema

```json
{
  "schema_version": "1.0.0",
  "principles": [
    {
      "id": "P001",
      "principle": "Service health domain should always run at least once per 12 hours due to 2.0 weight being insufficient during active implementation periods.",
      "source": "episode",
      "source_ids": ["EP-2026-W03", "EP-2026-W04", "EP-2026-W05"],
      "confidence": 0.8,
      "category": "scheduling",
      "created_at": "2026-02-03T00:00:00Z",
      "last_validated": "2026-03-15T00:00:00Z",
      "validation_count": 5,
      "invalidation_count": 0,
      "active": true
    }
  ]
}
```

### Principle entry fields

| Field | Type | Description |
|-------|------|-------------|
| id | string | "PNNN" format. Monotonically increasing. |
| principle | string | The rule, stated as a clear directive. |
| source | string | Where this principle was extracted from: `"episode"`, `"confidence_pattern"`, `"contrarian"`, `"user"`, `"gap_resolution"`. |
| source_ids | array | IDs of the episodes, gaps, or other entities that led to this principle. |
| confidence | float | 0.0-1.0. How confident the engine is that this principle is correct. |
| category | string | Grouping for the principle. Values: `"scheduling"`, `"safety"`, `"scoring"`, `"domain_balance"`, `"implementation"`, `"meta"`. |
| created_at | string | ISO 8601. |
| last_validated | string | ISO 8601. Last time evidence supporting this principle was observed. |
| validation_count | integer | How many times the principle has been confirmed. |
| invalidation_count | integer | How many times evidence contradicted the principle. |
| active | boolean | Whether this principle is currently applied during Orient. |

### Principle extraction triggers

A principle is extracted when any of these conditions are met:

1. **Recurring episode pattern**: The same pattern_detected string (fuzzy match)
   appears in 4+ episodes. The engine synthesizes a principle from the pattern.

2. **Confidence floor**: A domain's confidence stays below 0.3 for 5+ consecutive
   cycles. Principle: reduce automation for that domain.

3. **Contrarian validation**: A contrarian check's counter-argument is confirmed
   by subsequent cycle outcomes. Principle: the original strategy had a blind spot.

4. **Gap resolution success**: A skill gap is resolved and the new skill runs
   successfully 3+ times. Principle: document what the gap was and how it was solved.

5. **Episode eviction**: When a 52-week-old episode is about to be evicted, the
   engine scans it for any novel patterns not already captured in principles.

6. **User input**: Users can manually add principles via `/ooda-config principle add`.

### Principle lifecycle

- **Active**: Applied during Orient phase. The engine reads all active principles
  and uses them as additional context when building the world model.
- **Deactivated**: If `invalidation_count > validation_count` AND the principle
  has been tested 5+ times, it is deactivated (active = false). It remains in the
  file for reference but is no longer applied.
- **Reactivation**: If a deactivated principle's pattern re-emerges (3+ new validations
  with 0 new invalidations), it can be reactivated.

### How principles affect Orient

During Orient, the engine:
1. Loads all active principles.
2. Groups them by category.
3. Passes them as structured context to the LLM along with the current signals.
4. The LLM uses principles as "rules of thumb" when writing the orient_summary
   and deciding score adjustments.

This is intentionally soft integration — principles inform the LLM's reasoning
rather than being hard-coded scoring rules. This allows nuance and context-sensitivity.

### Retention policy

- Permanent. Principles are never automatically deleted.
- Deactivated principles are kept for reference.
- If the file exceeds 50 principles, the engine should warn the user to review
  and consolidate. Manual curation is required at this scale.

---

## 10. CHANGELOG.md — Human-Readable Activity Log

### What it tracks

A Markdown log of cycle activities, designed for human reading. This is the first
thing a user checks to understand what the engine has been doing.

### Template

```markdown
# Evolve Activity Log

Most recent 50 cycle entries. Newest first.

---

## Cycle #N — YYYY-MM-DD HH:MM TZ

- **Domain**: selected_domain (score: X.XX)
- **Orient**: orient_summary
- **Executed**: /skill-name [+ chain]
- **Result**: outcome summary
- **PR**: link or "none"
- **Memo**: memo text (if written)
- **Next**: prediction for next cycle

---
```

### Retention policy

- Maximum 50 entries. When exceeded, the oldest entry is removed.
- Entries are never cascaded — they exist purely for human consumption.
- The same information exists in structured form in state.json decision_log.

---

## 11. Contrarian Check System

The contrarian check is not a separate file — it is stored within the decision_log
entry (as `contrarian_check`) and in memos.json (as an adjustment).

### Trigger

Every `config.memory.contrarian_check_interval` cycles (default 10), the engine
must generate a counter-argument.

### Process

1. Identify the **dominant strategy**: the domain selected most frequently in the
   last 10 cycles.
2. Generate a counter-argument: "What if we are over-investing in X? What would
   happen if we redirected attention to Y?"
3. Evaluate the argument. If valid (the LLM rates it as plausible), apply a score
   adjustment: boost the counter-domain by +1.0 and reduce the dominant domain
   by -0.5 in the next cycle's memos.
4. Record the check in the decision_log entry's `contrarian_check` field.

### Storage

```json
"contrarian_check": {
  "dominant_domain": "service_health",
  "dominant_frequency": 6,
  "counter_domain": "test_coverage",
  "argument": "6/10 cycles were health checks with all-green results. Test coverage has not been checked in 2 weeks and may have regressed.",
  "validity": "plausible",
  "adjustment_applied": {
    "test_coverage": 1.0,
    "service_health": -0.5
  }
}
```

If the argument is rated "not_plausible", no adjustment is applied but the check
is still recorded (for audit and pattern detection).

---

## 12. Memory Cascade Architecture

### 3-Tier Overview

```
Tier 1: Working Memory
  ├── decision_log (state.json) — 20 entries, raw cycle data
  ├── memos.json — 10 entries, cross-cycle notes
  └── action-queue.json — 20 pending items

        ↓ (weekly trigger)

Tier 2: Episodes
  └── episodes.json — 52 weekly summaries, compressed

        ↓ (eviction trigger OR pattern detection)

Tier 3: Principles
  └── principles.json — permanent rules, validated over time
```

### Cascade flow

1. **Working → Episodes**: Triggered at the start of each new ISO week. The engine
   reads all Tier 1 data from the previous week and compresses it into one episode.
   Data in Tier 1 is not deleted by this cascade — it is evicted naturally by its
   own retention policy (FIFO at max size).

2. **Episodes → Principles**: Triggered when:
   - An episode is about to be evicted from the 52-week window.
   - A pattern is detected across 4+ consecutive episodes.
   - A domain shows persistent confidence problems.
   The engine evaluates whether the information warrants a permanent principle.

3. **Metrics (parallel track)**: metrics.json receives counters from all tiers
   but never feeds back into them. It is a one-way accumulator.

### Information compression at each tier

| Tier | Record size | Content |
|------|------------|---------|
| Working (T1) | ~300 bytes/entry | Full scores, chains, PRs, reasons |
| Episode (T2) | ~500 bytes/entry | Aggregated counts, key decisions, patterns |
| Principle (T3) | ~200 bytes/entry | Single rule statement + metadata |

Total steady-state storage: approximately 20KB for Tier 1, 26KB for Tier 2
(52 episodes), and <10KB for Tier 3. This means the entire memory system fits
in under 60KB — well within Claude's context window for full-state reads.

---

## KEY DESIGN DECISIONS

### D1: Keep 10 separate files, do not consolidate

**Decision**: 10 files, not 1 monolith.

**Reasoning**: Each file has a different update frequency and retention policy.
state.json updates every cycle. goals.json updates rarely. principles.json may not
change for weeks. Separate files mean:
- Git diffs are clean: one file changes per concern.
- Concurrent safety: if the engine crashes mid-write, only one file is corrupted.
- Selective reads: the Orient phase can read only what it needs (confidence + memos + principles) without loading the full action queue.
- Schema evolution: each file can evolve its schema independently.

The fwd.page reference used 8 files and it worked well for 15 cycles. Adding
episodes.json, principles.json, and metrics.json brings us to 10, but each one
has a clear single responsibility.

### D2: Decay is proportional to original RICE score, not compounding

**Decision**: `effective_score = rice_score - (decay_periods * decay_amount * rice_score)`

**Reasoning**: Compounding decay (multiply by 0.95 each period) creates exponential
curves where items become nearly worthless very quickly but never actually reach
zero. Proportional decay is linear, predictable, and has a clear endpoint
(20 periods = 100% decay = auto-removal). This makes the system behavior
easy to reason about and explain to users.

### D3: Episode generation is weekly (ISO week boundary), not cycle-count-based

**Decision**: Generate episodes when the ISO week changes.

**Reasoning**: Cycle frequency varies wildly — a user might run 1 cycle/day or
20 cycles/day. "Every 10 cycles" would mean "every 10 days" for one user and
"every 12 hours" for another. Weekly episodes:
- Align with human mental models of time.
- Produce consistent-sized summaries regardless of cycle frequency.
- Are trivially simple to implement (compare week numbers).
- Are easy to browse ("what happened in week 12?").

### D4: Principles affect Orient softly (LLM context), not as hard scoring rules

**Decision**: Active principles are passed as structured context to the LLM during
Orient, not as arithmetic modifiers to the scoring formula.

**Reasoning**: Hard rules are brittle. A principle like "health should run every
12 hours" might be correct 95% of the time but catastrophically wrong during a
deploy. By passing principles as context, the LLM can weigh them against current
signals and apply judgment. This preserves the adaptive nature of the OODA loop.

If we ever need hard rules, they belong in config.json safety settings, not in
the learning system.

### D5: Contrarian checks use the existing memo system, not a separate file

**Decision**: Contrarian arguments are stored in decision_log entries and their
score adjustments flow through memos.json.

**Reasoning**: The contrarian check is a special case of "orient insight leads
to score adjustment" — which is exactly what memos do. Creating a separate file
would duplicate the adjustment mechanism. By routing through memos, the contrarian
system gets cascade (memo → episode → principle) for free.

### D6: cycle_in_progress boolean instead of full WAL journal

**Decision**: A single boolean flag in state.json, not a separate WAL file.

**Reasoning**: The architect review suggested `cycle_in_progress.json` as a separate
WAL file. I simplified this to a boolean inside state.json because:
- The engine is single-threaded (one cycle at a time, enforced by lock file).
- If the cycle crashes, we do not need to replay it — we just skip it and start fresh.
- A boolean is atomic to read/write (versus a separate file that could also be corrupted).
- The lock file (`agent/state/evolve/.lock`) handles concurrency; the WAL flag handles crash detection.

### D7: Empty arrays for initial state, not seeded defaults

**Decision**: All template files start with empty arrays and zero counters.

**Reasoning**: The wizard (/ooda-setup) is responsible for populating initial state
based on project auto-detection. Pre-seeded defaults would conflict with the
wizard's output. Empty state means:
- The engine can detect "this is a fresh install" (cycle_count == 0).
- The first-cycle-observe-only mode works correctly (nothing to reference).
- No assumptions about which domains or goals the user will configure.

Confidence.json domains are auto-populated from config.json on first read —
any domain in config that is missing from confidence.json gets initialized
with `config.confidence.initial`.

### D8: metrics.json cost tracking uses daily_log capped at 90 days

**Decision**: Keep daily cost entries for 90 days, then roll up into the total.

**Reasoning**: Cost tracking serves two purposes:
1. The daily hard gate (stop if today's cost exceeds limit).
2. Long-term cost visibility.

Purpose 1 only needs today's entry. Purpose 2 needs trends. 90 days of daily
data is enough to show trends while keeping the file small. Older costs are
preserved in the `total_estimated_usd` counter.

### D9: Principle deactivation requires 5+ tests and more invalidations than validations

**Decision**: `invalidation_count > validation_count AND (validation_count + invalidation_count) >= 5`

**Reasoning**: Principles should be hard to kill. They represent distilled wisdom
from weeks of operation. A single contradictory data point should not deactivate
a principle — it might be an anomaly. Requiring 5+ total tests ensures statistical
significance. Requiring more invalidations than validations ensures we only
deactivate when the evidence genuinely tilts against the principle.

### D10: action-queue in_progress is a singleton (max 1), enforced by max_prs_per_cycle

**Decision**: `in_progress` is an array but functionally limited to 1 item.

**Reasoning**: The safety policy allows max 1 PR per cycle. Therefore, only 1
action can be in-progress at a time. Using an array (instead of a single object
or null) keeps the schema consistent with pending/completed and allows future
extension if the safety limit is relaxed.
