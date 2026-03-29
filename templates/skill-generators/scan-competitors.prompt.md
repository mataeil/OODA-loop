# Generator: scan-competitors

Instructions for generating a production-ready `scan-competitors` SKILL.md.
This generator is invoked by `/ooda-skill create scan-competitors` after the
user interview. Apply these instructions exactly when composing the skill.

---

## What This Skill Does

`scan-competitors` is an `observe`-phase skill that monitors competitor
activity and detects changes in pricing, features, and changelogs. It runs
as part of the OODA loop and produces a structured change-detection report
that feeds the `strategize` phase.

A well-generated scan-competitors skill:
- Reads the competitor list and tracking scope from `references/context.json`
- Applies any adaptive lens from `agent/state/competitors/lens.json`
- Scrapes or searches each competitor's relevant pages
- Compares current data against the previous snapshot stored in state
- Reports only changes — unchanged data is not noise
- Writes a structured state file with per-competitor snapshots

---

## Quality Standards

REJECT these patterns — they indicate a low-quality skill:
- Reporting a competitor's feature that was already in the previous snapshot
- Describing a pricing page without extracting actual prices
- "Competitor X may have changed their offering" (hedged, no evidence)
- Fetching a URL without comparing against the previous snapshot

REQUIRE these patterns:
- Per-competitor snapshot with exact extracted values (price points, plan names,
  feature list, changelog entries)
- Change detection: compare current vs. previous snapshot, report only diffs
- Source: URL and date for every data point
- Change severity: high (pricing change), medium (new feature/removal),
  low (copy change, new blog post)

---

## Required SKILL.md Sections

Generate the SKILL.md with these sections in order:

### 1. YAML Frontmatter (contract block)
```yaml
name: scan-competitors
ooda_phase: observe
version: "1.0.0"
description: >
  Competitor intelligence monitor. Tracks {track_what} changes for
  {competitors}. Scrapes configured URLs or uses web search to detect
  pricing, feature, and changelog updates. Writes diffs to
  agent/state/competitors.json.

input:
  files:
    - agent/state/competitors.json
    - agent/skills/observe/scan-competitors/references/context.json
  web_search: true
  config_keys: []

output:
  files:
    - agent/state/competitors.json

safety:
  halt_check: true
  read_only: true
  cost_limit_usd: 0.10

domains:
  - competitors
```

### 2. Skill Header
Brief description (2-3 sentences) mentioning the actual competitors and
tracking scope from user_context. No generic language.

### 3. Step 0.5: Adaptive Lens (REQUIRED)
Read `agent/state/competitors/lens.json`.
If the lens exists and is valid JSON with items of confidence >= 0.6:
- Load `focus_items` — specific competitors or signal types to prioritize
- Load `learned_thresholds` — change significance thresholds per competitor
  (e.g., price change > $5 = high, <= $5 = low for a given competitor)
- Load `discovered_signals` — URL patterns or page structures that have
  yielded reliable data in past cycles
If lens is missing or corrupt: proceed with base behavior (scan all competitors
uniformly).

Print: `Lens loaded: {N} focus items, {N} thresholds` or `No lens — uniform scan mode`.

### 4. Step 1: HALT + Context Load
HALT file check. Then read `references/context.json` — if missing, print
`references/context.json not found. Run /ooda-skill create scan-competitors` and exit.
Extract: competitors (list), track_what (pricing|features|changelog|all),
competitor_urls (map of competitor name → URL, may be empty).

Build scan targets list:
- For each competitor: use `competitor_urls[name]` if present, else use
  web search to discover the canonical URL.
- Determine which page types to scrape based on `track_what`:
  - `pricing` → /pricing page
  - `features` → /features or /product page
  - `changelog` → /changelog, /releases, or GitHub releases
  - `all` → all of the above

### 5. Step 2: State Load
Read `agent/state/competitors.json`. Create with initial structure if missing.
Initial structure: schema_version, last_run, run_count, status, alerts,
snapshots (object keyed by competitor name), change_log (array, newest first).

Each snapshot entry shape:
```json
{
  "competitor": "{name}",
  "last_fetched": "{ISO 8601}",
  "pricing": { "plans": [], "raw_text": "" },
  "features": { "items": [], "raw_text": "" },
  "changelog": { "entries": [], "latest_version": "" },
  "source_urls": []
}
```

### 6. Step 3: Scraping + Search

For each competitor in context.json:

**A. Direct URL scraping (if competitor_url is known)**
For each target page type:
```bash
curl -s --max-time 15 -A "Mozilla/5.0" "{url}" | python3 -c "
import sys, re
html = sys.stdin.read()
# Extract visible text (strip tags)
text = re.sub('<[^>]+>', ' ', html)
text = re.sub(r'\s+', ' ', text).strip()
print(text[:4000])
"
```
If curl fails (timeout, 4xx, 5xx): record `fetch_error: true`, continue.

**B. Web search fallback (if URL unknown or fetch failed)**
Search query pattern per page type:
- pricing: `"{competitor_name}" pricing plans site:{competitor_domain}`
- features: `"{competitor_name}" features OR product 2024 OR 2025`
- changelog: `"{competitor_name}" changelog OR release notes`
Record the top 3 search results as evidence.

Apply lens `discovered_signals` if loaded: prefer URL patterns that have
yielded good data in past cycles.

### 7. Step 4: Change Detection

For each competitor, compare freshly fetched data against the previous snapshot.

**Pricing diff:**
- Extract plan names and prices from current raw_text (regex: `\$\d+`, `€\d+`, plan name patterns)
- Compare against previous `pricing.plans` array
- Change detected if: new plan added, plan removed, price changed, or pricing page
  removed entirely

**Features diff:**
- Extract feature bullet points from current raw_text
- Compare against previous `features.items` list (fuzzy match: 80% similarity threshold)
- Change detected if: new feature added or feature removed from the list

**Changelog diff:**
- Extract version numbers and release dates from current raw_text
- Compare against previous `changelog.latest_version`
- Change detected if: new version present

Assign severity per change:
- high: pricing change (any price modified, plan added or removed)
- medium: new feature added or feature removed, new major/minor version
- low: patch release, copy change, new blog post

Apply lens `learned_thresholds` to adjust severity if loaded.

Build `change_log` entry for each detected change:
```json
{
  "competitor": "{name}",
  "change_type": "pricing | feature | changelog | other",
  "severity": "high | medium | low",
  "description": "{specific change in one sentence}",
  "previous_value": "{what it was}",
  "current_value": "{what it is now}",
  "source_url": "{URL}",
  "detected_at": "{ISO 8601}"
}
```

### 8. Step 5: State Write
Write to `agent/state/competitors.json`: schema_version, last_run (ISO 8601),
run_count (incremented), status (alert if any high or medium changes, stable
otherwise), alerts (high-severity changes as alerts), snapshots (updated per
competitor), change_log (prepend new entries, retain last 200 entries).

### 9. Step 6: Report

```
scan-competitors — {ISO timestamp}
Status: {alert|stable}
Competitors scanned: {N} | Changes detected: {N}

Changes this cycle:
  [high]   {competitor}: {description} [{source_url}]
  [medium] {competitor}: {description} [{source_url}]
  [low]    {N} low-severity changes (run with --verbose to list)

No changes:
  {competitor_name}, {competitor_name} — no changes detected

Comparison summary:
  Competitor    Pricing  Features  Changelog  Last fetched
  ─────────────────────────────────────────────────────────
  {name}        ✓        ✓         ✓          {ISO date}
  {name}        ✗ err    ✓         N/A        {ISO date}
```

If no changes: `All competitors stable since last cycle ({last_run}).`

### 10. Graceful Degradation Table
Cover: HALT, context.json missing, competitor URL unreachable (fall back to
search), web_search unavailable (skip that competitor + note), state file
missing (create defaults), all competitors unreachable (status = "error", report
and exit 0), cost limit hit (stop after current competitor, write partial state).

---

## References Files to Create

**references/context.json** — user interview answers as structured JSON.
The skill reads this on every run for: competitors list, track_what scope,
competitor_urls map. Update this file manually when competitor URLs change.

---

## Validation Checklist

Before finalizing the generated SKILL.md, verify:

- [ ] YAML frontmatter has all required fields
- [ ] `name` equals `scan-competitors`
- [ ] `ooda_phase` equals `observe`
- [ ] `safety.halt_check` is `true`
- [ ] `safety.read_only` is `true`
- [ ] `references/context.json` listed in `input.files`
- [ ] Step 0.5 (Adaptive Lens) section present and reads `agent/state/competitors/lens.json`
- [ ] Step 1 includes HALT file check before any other work
- [ ] No hardcoded competitor names — all read from context.json
- [ ] Change detection logic present (compares current vs. previous snapshot)
- [ ] Severity levels defined (high/medium/low) with explicit criteria
- [ ] `change_log` entry shape defined with all required fields
- [ ] State file structure includes `snapshots` (per-competitor) and `change_log`
- [ ] Comparison summary table in the Report section
- [ ] Graceful degradation covers: URL unreachable, search unavailable, all failed
- [ ] Cost limit reached → partial state write (not discard)
