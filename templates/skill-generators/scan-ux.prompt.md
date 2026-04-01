# Generator: scan-ux

Instructions for generating a production-ready `scan-ux` SKILL.md.
This generator is invoked by `/ooda-skill create scan-ux` after the user
interview. Apply these instructions exactly when composing the skill.

---

## What This Skill Does

`scan-ux` is an `observe`-phase skill that audits the product's UI for usability
issues, accessibility gaps, and UX friction. It runs as part of the OODA loop
and produces structured findings that feed the `strategize` phase with ranked,
actionable UX improvement opportunities.

A well-generated scan-ux skill:
- Reads the user's frontend stack and key flows from `references/context.json`
- Applies any adaptive lens from `agent/state/ux_evolution/lens.json`
- Uses Playwright to capture screenshots and evaluate real rendered UI
- Applies the user's chosen heuristic framework (or defaults to Nielsen's 10)
- Rotates through focus_areas across cycles so no area is perpetually ignored
- Outputs structured findings with severity, heuristic reference, and fix hints

---

## Quality Standards

REJECT these patterns — they indicate a low-quality skill:
- "The UI could be more intuitive" (no specific element, no heuristic cited)
- "Users may find this confusing" (no evidence, no screenshot reference)
- "Consider improving accessibility" (no specific WCAG criterion, no element)
- Auditing the same page every cycle without rotation

REQUIRE these patterns:
- Named UI element or component with specific finding
  (e.g., "CTA button on /pricing has insufficient contrast ratio: 2.8:1, WCAG AA requires 4.5:1")
- Heuristic reference for every finding
  (e.g., "Nielsen #4 — Consistency and Standards: button labels inconsistent across 3 pages")
- Screenshot evidence note (e.g., "Screenshot captured: /tmp/ux-scan/pricing-cta.png")
- Suggested fix (1 sentence, not a full solution)
- Severity: critical | high | medium | low

---

## Required SKILL.md Sections

Generate the SKILL.md with these sections in order:

### 1. YAML Frontmatter (contract block)
```yaml
contract_version: "1.0"
name: scan-ux
ooda_phase: observe
version: "1.0.0"
status: active
description: >
  UX audit skill for {frontend_stack}. Evaluates {key_flows} user flows
  using {ux_framework}. Uses Playwright to capture screenshots, applies
  heuristic evaluation, and writes findings to agent/state/ux_evolution.json.

input:
  files:
    - agent/state/ux_evolution.json
    - skills/scan-ux/references/context.json
  config_keys:
    - health_endpoints

output:
  files:
    - agent/state/ux_evolution.json
  prs: none

safety:
  halt_check: true
  read_only: true
  cost_limit_usd: 0.10

domains:
  - ux_evolution
```

### 2. Skill Header
Brief description (2-3 sentences) mentioning the actual frontend stack and key
flows from user_context. No generic language.

### 3. Step 0.5: Adaptive Lens (REQUIRED)
Read `agent/state/ux_evolution/lens.json`.
If the lens exists and is valid JSON with items of confidence >= 0.6:
- Load `focus_items` — specific UI areas or heuristics to prioritize this cycle
- Load `learned_thresholds` — severity calibration learned from past cycles
- Load `discovered_signals` — UI patterns that have repeatedly surfaced issues
If lens is missing: proceed with base behavior (audit all focus_areas in rotation).
If lens is corrupt (invalid JSON, missing schema_version):
  Log: `[WARN] Lens file corrupt, using base behavior.`
  Continue normally. Do NOT crash.

Print: `Lens loaded: {N} focus items, {N} thresholds` or `No lens — full rotation mode`.

### 4. Step 1: HALT + Context Load
HALT file check. Then read `references/context.json` — if missing, print
`references/context.json not found. Run /ooda-skill create scan-ux` and exit.
Extract: frontend_stack, key_flows (as list), ux_framework, focus_areas (as list).

Resolve heuristic framework:
- "Nielsen" or "use defaults" → Nielsen's 10 Usability Heuristics (list all 10 with short names)
- "WCAG" → WCAG 2.1 AA criteria (list most critical: 1.1.1, 1.4.3, 1.4.4, 2.1.1, 2.4.1, 2.4.6, 4.1.2)
- User-supplied string → use as-is, apply best-effort mapping

### 5. Step 2: State Load + Rotation
Read `agent/state/ux_evolution.json`. Create with initial structure if missing.
Initial structure: schema_version, last_run, run_count, status, alerts,
findings (array), area_rotation (object), cycle_coverage (object).

**Area Rotation Logic** — prevent perpetual focus on one area:
Read `area_rotation` from state. This object maps each focus_area to
`last_scanned_cycle` (integer, default 0).
Select the N areas with the lowest `last_scanned_cycle` value for this cycle,
where N = min(3, total focus_areas). If lens focus_items are loaded, include
those areas regardless of rotation order.
Update `last_scanned_cycle` for selected areas after the scan.

### 6. Step 3: Install + Launch Playwright

Check if Playwright is available:
```bash
npx playwright --version 2>/dev/null
```
If unavailable, attempt install: `npm install --save-dev @playwright/test && npx playwright install chromium`
If install fails: print `Playwright unavailable. Running heuristic-only mode (no screenshots).`
Set `playwright_available = false` and continue without screenshots.

Launch browser (if playwright_available):
```javascript
const browser = await chromium.launch();
const page = await browser.newPage();
```

For each URL in `health_endpoints` (from config) or `localhost:3000` as fallback:
- Navigate to the URL + each path in the selected focus_areas list
- Capture screenshot to `/tmp/ux-scan/{area_slug}-{cycle_N}.png`
- Extract: page title, visible text, form fields, button labels, image alt attributes, color values of prominent elements

### 7. Step 4: Heuristic Evaluation

For each captured page/component:
Apply each heuristic from the resolved framework. For each violation found:

```
{
  "heuristic": "{heuristic_id} — {short_name}",
  "element": "{CSS selector or description}",
  "finding": "{specific, concise description}",
  "severity": "critical | high | medium | low",
  "screenshot": "{path or null}",
  "fix_hint": "{one sentence}",
  "area": "{focus_area name}"
}
```

Severity guide:
- critical: blocks task completion or fails WCAG AA
- high: significantly impairs usability
- medium: noticeable friction, workaround exists
- low: polish item, minor inconsistency

Apply lens `learned_thresholds` to adjust severity if loaded.

### 8. Step 5: State Write
Write to `agent/state/ux_evolution.json`: schema_version, last_run (ISO 8601),
run_count (incremented), status (critical if any critical findings, degraded if
any high, healthy otherwise), alerts (critical and high findings as alerts),
findings (full list, append to history — keep last 100), area_rotation (updated),
cycle_coverage map of areas scanned this cycle.

### 9. Step 6: Report
```
scan-ux — {ISO timestamp}
Status: {healthy|degraded|critical}
Areas scanned: {area_list} (rotation cycle {N})
Playwright: {available|heuristic-only mode}

Findings ({N} total — {N} critical, {N} high, {N} medium, {N} low):

  [critical] {heuristic} | {element}: {finding}
             Fix: {fix_hint}

  [high]     {heuristic} | {element}: {finding}
             Fix: {fix_hint}

  (medium and low counts summarized, not listed individually)

Top fix: {highest severity finding in 1 sentence}
```

If no findings: `No violations found in scanned areas. Next cycle: {next_areas}.`

If all URLs were unreachable and Playwright was also unavailable (zero pages
evaluated): set `status: "no_data"`, write state with empty findings, and report:
`No pages could be evaluated. Check that the service is running and endpoints are configured.`

### 10. Graceful Degradation Table
Cover: HALT, context.json missing, lens.json corrupt (warn and continue),
Playwright unavailable (heuristic-only mode), service not running (skip URL,
log and continue), all URLs unreachable (status "no_data", write empty state),
state file missing (create defaults), screenshot capture fails (continue
without screenshot), cost limit hit (write partial state).

---

## References Files to Create

**references/context.json** — user interview answers as structured JSON.
The skill reads this on every run for: frontend_stack, key_flows, ux_framework,
focus_areas. Keep it up to date as the UI evolves.

---

## Validation Checklist

Before finalizing the generated SKILL.md, verify:

- [ ] YAML frontmatter has all required fields (contract_version, name, ooda_phase, version, status, description, input.files, output.files, safety.halt_check, safety.read_only)
- [ ] `contract_version` equals `"1.0"`
- [ ] `status` is `active` (or `deprecated` if intentional)
- [ ] `name` equals `scan-ux`
- [ ] `ooda_phase` equals `observe`
- [ ] `safety.halt_check` is `true`
- [ ] `safety.read_only` is `true`
- [ ] `references/context.json` listed in `input.files`
- [ ] Step 0.5 (Adaptive Lens) section present and reads `agent/state/ux_evolution/lens.json`
- [ ] Step 1 includes HALT file check before any other work
- [ ] Area rotation logic present in Step 2 (reads and updates `area_rotation`)
- [ ] Playwright install + fallback heuristic-only mode described
- [ ] Severity levels defined (critical/high/medium/low) with clear criteria
- [ ] Screenshot capture step present (with graceful fallback)
- [ ] State file structure includes `area_rotation` and `cycle_coverage`
- [ ] Report section shows per-severity counts
- [ ] Graceful degradation table covers Playwright unavailable case
