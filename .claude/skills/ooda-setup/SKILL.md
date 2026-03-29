---
name: ooda-setup
description: 3-step project setup wizard. Auto-detects language, test framework, CI, and endpoints. Creates config.json from config.example.json.
---

# ooda-setup — Project Setup Wizard

Entry point for new users. Run `/ooda-setup` after cloning OODA-loop.
Runs a 3-step interactive wizard: scan → confirm domains → write config.json.

---

## Safety Check (Always First)

Read `agent/safety/HALT`. If the file exists → print `[HALT] Setup blocked. Remove agent/safety/HALT to continue.` and stop immediately.

If `config.json` already exists → ask:
```
[WARNING] config.json already exists. Overwrite? (yes/no)
```
If answer is not "yes" → abort.

---

## Step 1/3: Scan Project

Print: `[1/3] Scanning your project...`

**Detect Language** — use Glob to check for indicator files:

| Indicator | Language |
|---|---|
| `package.json` | TypeScript (if `*.ts` files exist) or JavaScript |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `pyproject.toml` / `requirements.txt` | Python |
| `Gemfile` | Ruby |
| `pom.xml` / `build.gradle` | Java |

Check framework hints in `package.json` (`"next"` → Next.js, `"react"` → React, `"express"` → Express). If no indicator found → language = null.

**Detect Test Command** (first match wins):
1. `package.json` has `scripts.test` → `npm test`
2. `pytest.ini` or `conftest.py` exists → `pytest`
3. `go.mod` present → `go test ./...`
4. `Cargo.toml` present → `cargo test`
5. `Gemfile` contains `rspec` → `bundle exec rspec`
6. No match → `""` (warn user)

**Detect CI** — Glob `.github/workflows/*.yml`. If a file contains `deploy` in its name → deploy_workflow = that filename. If workflows exist but none named deploy → use the first one. None found → null.

**Detect Health Endpoints** — check `package.json` `scripts.start` for a port, or `docker-compose.yml` port mappings. Framework defaults: Next.js/Express → `http://localhost:3000`, FastAPI/Django → `http://localhost:8000`, Go → `http://localhost:8080`. None detected → `[]`.

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

Read `config.example.json` (if missing → `[ERROR] config.example.json not found.` and stop). Apply detected values:

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

After printing the "Setup complete!" block, read the domains from the written config.json. For any domain where `status: "available"` (i.e., not enabled and not explicitly disabled), append:

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
