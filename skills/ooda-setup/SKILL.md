---
name: ooda-setup
description: 3-step project setup wizard. Auto-detects language, test framework, CI, and endpoints. Creates config.json from config.example.json.
ooda_phase: support
version: "1.1.0"
input:
  files: [config.example.json]
  config_keys: []
output:
  files: [config.json]
  prs: none
safety:
  halt_check: true
  read_only: true
domains: []
chain_triggers: []
---

# ooda-setup — Project Setup Wizard

Entry point for new users. Run `/ooda-setup` after cloning OODA-loop.
Runs a 3-step interactive wizard: scan → confirm domains → write config.json.

---

## Safety Check (Always First)

Read `agent/safety/HALT`. If the file exists → print `[HALT] Setup blocked. Remove agent/safety/HALT to continue.` and stop immediately.

If `config.json` already exists → back up to `config.json.bak` and ask:
```
[WARNING] config.json already exists.
  (o) Overwrite — discard current config, start fresh
  (m) Merge     — keep existing domains and safety settings, update detected values only
  (a) Abort     — cancel setup
  Choice (o/m/a):
```
- `o` → overwrite entirely (backed up to config.json.bak)
- `m` → read existing config, preserve user-modified fields (domains, safety, progressive_complexity.current_level, cost), only update auto-detected values (project.name, test_command, deploy_workflow, health_endpoints)
- `a` or anything else → abort

---

## Step 1/3: Scan Project

Print: `[1/3] Scanning your project...`

**Detect Monorepo** — before language detection, check for monorepo indicators:
- `package.json` has `"workspaces"` field → npm/yarn workspaces monorepo
- `pnpm-workspace.yaml` exists → pnpm monorepo
- `lerna.json` exists → Lerna monorepo
- `packages/` or `apps/` directory exists with multiple sub-`package.json` files → probable monorepo

If monorepo detected, scan each workspace root for its own indicator files and aggregate results. Print:
```
  Structure: monorepo ({N} packages detected)
```
If not a monorepo, print `  Structure: single-package`.

For monorepos, auto-detect values from the root config first, then fall back to the first workspace that has the relevant indicator. Use the root `package.json` scripts for test/build commands unless a workspace-level override exists.

**Detect Language** — use Glob to check for indicator files:

| Indicator | Language |
|---|---|
| `package.json` | TypeScript (if `*.ts` files exist) or JavaScript |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `pyproject.toml` / `requirements.txt` | Python |
| `Gemfile` | Ruby |
| `pom.xml` / `build.gradle` | Java |

Check framework hints:
- `package.json`: `"next"` → Next.js, `"react"` → React, `"express"` → Express
- `requirements.txt` / `pyproject.toml`: `fastapi` → FastAPI, `django` → Django, `flask` → Flask
- `go.mod`: `gin` → Gin, `echo` → Echo, `fiber` → Fiber

If no indicator found → language = null.
For monorepos, report the primary language (most common across packages) and note others: e.g. `TypeScript (3 packages), Go (1 package)`.

**Detect Test Command** (first match wins):
1. `package.json` has `scripts.test` → `npm test`
2. `pytest.ini` or `conftest.py` exists → `pytest` (enhanced: if `pytest-cov` found in `requirements.txt` or `pyproject.toml` dependencies, append `--cov`; detect main source directory from project structure for `--cov=<dir>`)
3. `go.mod` present → `go test ./...`
4. `Cargo.toml` present → `cargo test`
5. `Gemfile` contains `rspec` → `bundle exec rspec`
6. No match → `""` (warn user)

**Detect CI** — Glob `.github/workflows/*.yml`. If a file contains `deploy` in its name → deploy_workflow = that filename. If workflows exist but none named deploy → use the first one. None found → null.

**Detect Health Endpoints** — multi-strategy detection:
1. Check `package.json` `scripts.start` for a port, or `docker-compose.yml` port mappings.
2. **Source-code scan**: grep for health route patterns in source files:
   - Python: `@app.get("/health")`, `@app.route("/health")`, `path("health/"`, `url(r"^health")`
   - JS/TS: `app.get('/health')`, `router.get('/health')`
   - Go: `HandleFunc("/health"`, `Handle("/health"`
   If a `/health` route is found, include it with the detected port.
3. Framework defaults: Next.js/Express → `http://localhost:3000`, FastAPI/Django → `http://localhost:8000`, Go → `http://localhost:8080`.
4. None detected → `[]`.

**Detect Project Name** — from `package.json` `.name`, `go.mod` module last segment, `Cargo.toml` `[package] name`, or current directory name.

**Check Git** — run `git rev-parse --is-inside-work-tree 2>/dev/null`. If fails → `[WARN] Not a git repo. backlog domain will be disabled.` Set is_git_repo = false.

Print summary:
```
[1/3] Scanning your project...
  Language:  TypeScript (Next.js)
  Tests:     jest (npm test)
  CI:        GitHub Actions (deploy.yml)
  Endpoints: http://localhost:3000
  Name:      my-app
```
Show `(not detected)` for any missing item.

---

## Step 2/3: Domain Configuration

Print:
```
[2/3] Recommended domains:
  ✓ service_health (weight 2.0)    — always recommended
  ✓ test_coverage (weight 0.5)     — if test command detected
  ✓ backlog (weight 0.3)           — if git repo detected
  ? business_strategy (weight 1.0) — optional
  ? ux_evolution (weight 1.0)      — optional
  ? competitors (weight 0.3)       — optional

Which domains to enable? (Enter for recommended, or list names separated by spaces)
```

Defaults: `service_health` always; `test_coverage` if test_command detected; `backlog` if is_git_repo = true.

Read input: empty → use defaults. Space-separated names → enable exactly those. Validate against known domain names; re-ask once if invalid.

---

## Step 3/3: Create Config

Print: `[3/3] Creating config.json...`

Locate the config template. Search in order (first found wins):
1. `${CLAUDE_PLUGIN_ROOT}/config.example.json` (plugin installation)
2. `~/.ooda-loop/config.example.json` (global git clone installation)
3. `./config.example.json` (running from the OODA-loop repo itself)

If none found → generate a minimal config with sensible defaults (all fields from the
schema with default values). Print `[WARN] config.example.json not found — using built-in defaults.`

Apply detected values:

- `project.name` → detected name
- `test_command` → detected command or `""`
- `deploy_workflow` → detected filename or null
- `health_endpoints` → detected array or `[]`
- `progressive_complexity.current_level` → `0`
- Each domain: `enabled` = true if in user-chosen list, false otherwise

Graceful degradation:
- No language detected → ask user: `What language does your project use?`
- No test command → set `""`, print `[WARN] Set test_command in config.json manually.`
- No CI → set null, print `[INFO] deploy_workflow set to null.`
- Not a git repo → force backlog enabled = false

Validate the JSON structure before writing. Write to `config.json`. Never write tokens, keys, or passwords — skip any detected value that looks like a secret and warn.

**Scaffold project directories** — create the OODA runtime directories if they don't exist:
```bash
mkdir -p agent/state/evolve
mkdir -p agent/safety
```
Initialize state files: `state.json`, `confidence.json`, `metrics.json`, `action_queue.json`,
`memos.json` (with `"score_adjustments": {}, "interventions": [], "history": []`),
`goals.json`, `episodes.json`, `principles.json`, `skill_gaps.json`,
`reflections.json` (`{"schema_version": "1.0.0", "reflections": []}`),
`outcomes.json` (`{"schema_version": "1.0.0", "entries": []}`),
`cost_ledger.json`, `CHANGELOG.md` in `agent/state/evolve/`. Use canonical schemas.
(`cascades.json`, `cycle_log.jsonl`, and per-domain `lens.json` are created lazily by evolve.)

Add to `.gitignore` if not already present:
```
config.json
agent/safety/HALT
agent/state/**/*.lock
agent/state/evolve/.lock
```
Do NOT gitignore `agent/state/` itself: evolve Step 6-D deliberately commits the
state JSONs (decision history, confidence, episodes — the auditable memory of
the loop). Ignoring the directory silently turns every 6-D commit into a no-op
and the project loses its own learning trail (issue #31). Only the transient
lock files (and the HALT kill-switch) stay untracked.

Print:
```
[3/3] Setup complete!
  Created: config.json
  Level:   0 (Just watching)
  Domains: service_health, test_coverage, backlog

  Next steps:
    /evolve           — Run first cycle (observe-only)
    /ooda-status      — Check current state
    /ooda-config      — Modify configuration
```

### Step 4/4: First Look (Verification Mini-Cycle)

After printing the "Setup complete!" block, run a quick verification pass against
the just-written config.json. This gives the user real data from their project
within 60 seconds of setup, before they ever run `/evolve`.

Print: `[4/4] Taking a first look at your project...`

Each domain check runs independently so one failure cannot block the others.
Apply a 15-second overall timeout for all checks combined and a 10-second per-domain timeout:

1. **test_coverage**: If `config.test_command` is non-empty, run it with a 10-second
   timeout. Parse the output for pass/fail counts and coverage percentage.
   Print: `  test_coverage    {passed}/{total} passing ({coverage}% coverage)`
   If test_command is empty: print `  test_coverage    [Skip] No test_command configured`
   If command fails or times out: print `  test_coverage    [Error] Test command failed`

2. **service_health**: If `config.health_endpoints` is non-empty, curl each endpoint
   with `--max-time 5`. Print status code and response time.
   Print: `  service_health   {url} → {status} ({time}ms)`
   If array is empty: print `  service_health   [Skip] No health endpoints configured`
   If curl fails: print `  service_health   {url} → unreachable`

3. **backlog**: Run `gh issue list --state open --limit 100 --json number 2>/dev/null`.
   Count results.
   Print: `  backlog          {count} open issues`
   If `gh` is not installed or fails: print `  backlog          [Skip] gh CLI not available`
   If no issues: print `  backlog          0 open issues`

Print: `Ready. Run /evolve for your first full cycle.`

This step is informational only — it does not write state files or modify config.json.
If the entire step fails or times out, print `[4/4] Verification skipped.` and continue.

---

After the verification mini-cycle, read the domains from the written config.json. For any domain where `status: "available"` (i.e., not enabled and not explicitly disabled), append:

```
  3 optional skills are available but not yet configured:
    /scan-market      — market research and strategic analysis
    /scan-ux          — UX audit and UI analysis
    /scan-competitors — competitor monitoring

  Create any of these when you're ready:
    /ooda-skill create <name>

  Or disable ones you don't need:
    /ooda-skill disable <name>
```

Only list domains whose `status` field equals `"available"` in the generated config. If no domains have `status: "available"`, omit this block entirely.
