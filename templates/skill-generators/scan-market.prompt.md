# Generator: scan-market

Instructions for generating a production-ready `scan-market` SKILL.md.
This generator is invoked by `/ooda-skill create scan-market` after the user
interview. Apply these instructions exactly when composing the skill.

---

## What This Skill Does

`scan-market` is an `observe`-phase skill that gathers external business signals
about the user's market position. It runs on a schedule as part of the OODA
loop and produces a structured snapshot of market conditions, feeding the
`strategize` phase with concrete, project-specific data.

A well-generated scan-market skill:
- Reads the user's product context from `references/context.json`
- Applies any adaptive lens from `agent/state/business_strategy/lens.json`
- Searches for signals relevant to THIS specific product and customer segment
- Outputs a structured state file with scored observations
- Never produces generic market platitudes — every finding must cite a source

---

## Quality Standards

REJECT these patterns — they indicate a low-quality skill:
- "The market is growing rapidly" (no source, no number)
- "Competitors are adding new features" (which competitors? which features?)
- "Customer needs are evolving" (no specifics)
- Generic advice like "focus on differentiation"

REQUIRE these patterns:
- Named competitors with specific observations (e.g., "Competitor X raised
  prices on Pro plan from $29 to $39 — source: their pricing page, date: ...")
- Concrete metrics where available (e.g., "GitHub stars +200 this month")
- Source attribution for every finding (URL, API, or search query used)
- Timestamps on all observations

---

## Required SKILL.md Sections

Generate the SKILL.md with these sections in order:

### 1. YAML Frontmatter (contract block)
```yaml
name: scan-market
ooda_phase: observe
version: "1.0.0"
description: >
  Market intelligence scanner. Reads {product_description} context from
  references/context.json, researches {competitors}, and tracks signals
  relevant to {target_customer}. Writes structured findings to
  agent/state/business_strategy.json.

input:
  files:
    - agent/state/business_strategy.json
    - agent/skills/observe/scan-market/references/context.json
  web_search: true
  config_keys: []

output:
  files:
    - agent/state/business_strategy.json

safety:
  halt_check: true
  read_only: true
  cost_limit_usd: 0.15

domains:
  - business_strategy
```

### 2. Skill Header
Brief description (2-3 sentences) mentioning the actual product and target market
from user_context. No generic language.

### 3. Step 0.5: Adaptive Lens (REQUIRED)
Read `agent/state/business_strategy/lens.json`.
If the lens exists and is valid JSON with items of confidence >= 0.6:
- Load `focus_items` — areas to investigate more deeply this cycle
- Load `learned_thresholds` — signal thresholds calibrated to this product
- Load `discovered_signals` — signal types that have proven useful
If lens is missing or corrupt: proceed with base behavior (search all areas).

Print: `Lens loaded: {N} focus items, {N} thresholds` or `No lens — full scan mode`.

### 4. Step 1: HALT + Context Load
HALT file check. Then read `references/context.json` — if missing, print
`references/context.json not found. Run /ooda-skill create scan-market` and exit.
Extract: product_description, target_customer, business_goals, data_sources,
competitors list.

### 5. Step 2: State Load
Read `agent/state/business_strategy.json`. Create with initial structure if missing.
Initial structure must include: schema_version, last_run, run_count, status,
alerts, observations (array), competitor_snapshots (object keyed by competitor name).

### 6. Step 3: Signal Gathering
Organize searches into 3 tracks. Use the competitors and data_sources from
context.json — never use placeholder competitor names.

**Track A — Competitor Signals**
For each competitor in context.json:
- Web search: `"{competitor_name}" pricing OR changelog OR "new feature" site:{competitor_url}`
- Record: name, finding, source_url, date_found, signal_type (pricing|feature|release|other)

**Track B — Market Category Signals**
Search for the product's category and target customer segment:
- Use the actual product_description and target_customer from context.json
- Search for news, trends, and analyst signals relevant to THIS category
- Record: signal_text, source_url, relevance_score (0.0–1.0), date_found

**Track C — Configured Data Sources**
If data_sources in context.json lists accessible APIs or dashboards:
- Attempt to read each source (graceful degradation if unavailable)
- Record: source_name, metric_name, value, delta_from_last_run, timestamp

Apply lens focus_items if loaded: prioritize those areas in search queries.

### 7. Step 4: Analysis
Compute:
- `competitor_change_count`: number of competitors with changes detected
- `market_alert_count`: number of Track B signals with relevance_score >= 0.7
- `status`: "active" if any alert, "stable" otherwise
- `top_insight`: single most actionable observation, max 2 sentences

Map each business_goal from context.json to relevant findings (at least one
finding per goal if data exists, else note "no data found for this goal").

### 8. Step 5: State Write
Write to `agent/state/business_strategy.json`. Include: schema_version, last_run
(ISO 8601), run_count (incremented), status, alerts, observations array,
competitor_snapshots with latest data per competitor, goal_coverage map.

### 9. Step 6: Report
Print a structured report:
```
scan-market — {ISO timestamp}
Status: {active|stable}

Competitor signals ({N} found):
  {competitor}: {finding} [{source}]

Market signals ({N} above threshold):
  {signal_text} [relevance: {score}] [{source}]

Goal coverage:
  {goal}: {finding or "no data"}

Top insight: {top_insight}
```

### 10. Graceful Degradation Table
Cover: HALT, context.json missing, web_search unavailable (fall back to note),
all competitors unreachable, state file missing (create defaults), cost limit hit.

---

## References Files to Create

The wizard creates these alongside the SKILL.md:

**references/context.json** — user interview answers as structured JSON.
This is the primary source of truth for all project-specific parameters.
The skill MUST read this file before any search.

**references/known-entities.md** — human-readable summary of product,
target customer, competitors, and data sources. Updated manually by the user
to keep the skill calibrated over time.

---

## Validation Checklist

Before finalizing the generated SKILL.md, verify:

- [ ] YAML frontmatter has all required fields (name, ooda_phase, version, description, input.files, output.files, safety.halt_check, safety.read_only)
- [ ] `name` equals `scan-market`
- [ ] `ooda_phase` equals `observe`
- [ ] `safety.halt_check` is `true`
- [ ] `safety.read_only` is `true`
- [ ] `references/context.json` listed in `input.files`
- [ ] Step 0.5 (Adaptive Lens) section present and reads `agent/state/business_strategy/lens.json`
- [ ] Step 1 includes HALT file check before any other work
- [ ] No hardcoded competitor names — all read from context.json
- [ ] All findings require source attribution (URL or search query)
- [ ] State file structure includes `competitor_snapshots` and `goal_coverage`
- [ ] Report section prints structured output (not prose)
- [ ] Graceful degradation table covers all failure modes
