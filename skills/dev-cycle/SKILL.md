---
name: dev-cycle
description: Full implementation cycle pipeline. Takes the highest-RICE action from the action queue and implements it through a structured test → implement → verify workflow. Primary skill for the implementation domain — invoked by evolve when implementation is selected.
ooda_phase: support
version: "1.0.0"
input:
  files:
    - agent/state/evolve/action_queue.json
    - agent/state/evolve/state.json
    - config.json
    - CLAUDE.md
  config_keys:
    - safety.halt_file
    - safety.max_files_per_pr
    - safety.max_lines_per_pr
    - safety.protected_paths
    - test_command
output:
  files: [agent/state/evolve/action_queue.json]
safety:
  halt_check: true
  read_only: false
  branch_prefix: "auto/dev-cycle/"
  cost_limit_usd: 0.10
domains:
  - implementation
chain_triggers:
  - target: scan-health
    condition: "pr_created == true"
    note: "Recommend post-merge health check after implementation PR is merged"
---

# dev-cycle: Full Implementation Cycle Pipeline

The "builder" of the harness. Takes the highest-priority action from the action
queue, implements it in a dedicated branch, verifies it passes tests, and
creates a Draft PR for human review.

dev-cycle is the primary skill for the implementation domain. When evolve's
Orient step selects implementation as the winning domain, it calls dev-cycle.
All changes go through branch + PR — dev-cycle never commits directly to main.

- ALWAYS creates Draft PRs — human review is mandatory for implementation
- NEVER uses `git add -A` — only explicit file staging to prevent secret leaks
- NEVER auto-merges — implementation is always Risk Tier 3

---

## Safety Rules

1. **HALT file** — Mandatory first check. If present, print reason and stop.
2. **Level gate** — Requires `progressive_complexity >= 3` or direct user invocation. Below Level 3, exit cleanly.
3. **PR size limits** — Respect `config.safety.max_files_per_pr` and `config.safety.max_lines_per_pr`. Exceeding either triggers a partial PR.
4. **Protected paths** — Any change touching `config.safety.protected_paths` forces Risk Tier 3 (already enforced — Draft only).
5. **Explicit staging** — `git add {file}` per file. `git add -A` is forbidden.
6. **Test retry cap** — Maximum 3 fix attempts after a test failure. Beyond that, mark action as `"blocked"` and exit.

---

## Step 0: Safety

### 0-A: HALT Check

```
if file exists at config.safety.halt_file:
  Print "[HALT] dev-cycle stopped. Reason: {file_content}"
  Print "Remove to resume: rm {config.safety.halt_file}"
  EXIT immediately.
```

### 0-B: Level Gate

```
Read config.json → progressive_complexity.current_level  (authoritative source)
Also check config.json → implementation.enabled
if implementation.enabled == false AND not manually invoked by user:
  Print "Implementation domain is disabled. Enable with: /ooda-config implementation enable"
  EXIT cleanly (not an error).
if progressive_complexity.current_level < 3 AND not manually invoked by user:
  Print "Implementation requires Level 3. Current: {current_level}"
  EXIT cleanly (not an error).
```

Manual invocation means the user explicitly called `/dev-cycle` or `/evolve`
in this session (as opposed to being triggered automatically by evolve on a
schedule). When in doubt, treat as manual invocation and allow execution.

---

## Step 1: Select Action from Queue

Read `agent/state/evolve/action_queue.json`.

Find the top pending item by highest `effective_rice` (after decay adjustment):

```
data = read action_queue.json as JSON object
if data is not a valid object:
  Print "Action queue is empty or malformed. Nothing to implement."
  EXIT cleanly.

# The canonical format uses {pending:[], in_progress:[], completed:[]}
# Read from data.pending (preferred). Fallback: if data.actions exists, filter
# items with status=="pending". Fallback: if data is a plain array, filter by status.
candidates = data.pending   # or fallback as described above

if candidates is empty or not a list:
  Print "No pending actions. Nothing to implement."
  EXIT cleanly.

# Sort by effective_rice. If effective_rice is missing, fall back to rice_score.
for item in candidates:
  if item.effective_rice is undefined:
    item.effective_rice = item.rice_score * (1.0 - (item.decay_applied or 0.0))
selected = max(candidates, key=lambda x: x.effective_rice)

if selected.effective_rice <= 0:
  Print "Top candidate RICE score is {selected.effective_rice} (≤ 0). Skipping."
  EXIT cleanly.
```

Print selected action details:
```
Selected action: {selected.title}
  RICE score  : {selected.effective_rice}
  Source      : {selected.source_domain}
  Related     : {selected.related_files}
```

Update the action's status to `"in_progress"` in `action_queue.json` and write
the file before proceeding. If the file write fails, abort and print the error.

---

## Step 2: Create Branch

Generate a URL-safe slug from the action title:
1. Lowercase the title.
2. Replace spaces and underscores with hyphens.
3. Strip all characters except `[a-z0-9-]`.
4. Collapse consecutive hyphens into one and trim leading/trailing hyphens.
5. If the slug is empty after stripping (e.g., non-ASCII title like Korean),
   use the action ID as the slug instead (e.g., `action-001`). If the action ID
   is also empty, generate a random 8-char hex string.
6. Truncate to 40 characters (cut at a hyphen boundary if possible).

Get today's date in `YYYYMMDD` format.

```bash
git checkout -b auto/dev-cycle/{date}-{action-title-slug}
```

If the branch already exists (e.g., retry or duplicate title), append `-2`,
`-3`, etc., up to `-9`. If all suffixes are taken, abort with an error.

Print:
```
Branch: auto/dev-cycle/{date}-{action-title-slug}
```

---

## Step 3: Implementation

Read context files before writing any code:

1. If `CLAUDE.md` exists at the project root, read it for project conventions.
2. For each path in `selected.related_files`:
   - If the file exists, read it to understand the affected code.
   - If it does not exist, print `"WARN: related file not found: {path} — skipping"` and continue.
   - If `related_files` is empty or not set, print `"INFO: No related files listed — proceeding with action title and source report only."`.
3. Read `selected.source_domain` report (if referenced) to understand the
   motivation behind this action.

Analyze what needs to change based on the action title and source report, then
implement the changes (write and/or edit files).

**Protected paths enforcement:**

Before writing any file, check against `config.safety.protected_paths`.
This prevents dev-cycle from modifying safety-critical files that could
compromise the framework's integrity (self-modification prevention).

```
protected = config.safety.protected_paths    -- e.g., ["agent/safety/*", "skills/evolve/*", "agent/contracts/*"]

before writing or editing any file:
  for each pattern in protected:
    if file path matches glob pattern:
      Print "BLOCKED: {file} matches protected path '{pattern}'. Skipping."
      Print "Protected paths cannot be modified by dev-cycle, even at Level 3."
      Add to PR body notes: "⚠ Protected path {file} was NOT modified (blocked by safety policy)."
      DO NOT write/edit this file — continue to next file.
```

If ALL planned files are protected, mark the action as "blocked" with memo
"All target files are protected paths" and EXIT cleanly.

**Size limit enforcement:**

Track changes as you write. After each file edit, run `git diff --stat` on
the working tree to get authoritative counts (do not estimate):
```
files_changed = 0
lines_changed = 0  # counted as (additions + deletions) from git diff --numstat
```

Before writing each file:
```
if files_changed >= config.safety.max_files_per_pr:
  Print "PR size limit reached ({max_files_per_pr} files). Creating partial PR."
  Print "Remaining work noted in action-queue memos."
  Add memo to action-queue: "Partial implementation — {files_changed} files changed."
  GOTO Step 4 (verify what was done so far)

if lines_changed + estimated_lines_for_this_file > config.safety.max_lines_per_pr:
  Print "PR line limit reached ({max_lines_per_pr} lines). Creating partial PR."
  GOTO Step 4
```

When partial: note unfinished scope in `action_queue.json` under the action's
`memos` field so the next dev-cycle cycle picks up where this one stopped.

---

## Step 4: Verify

**If `config.test_command` is not configured or is empty:**
```
Print "No test_command configured. Skipping tests."
test_status = "skipped"
GOTO Step 5
```

**If configured**, run tests:
```bash
{config.test_command}
```

Track attempts:
```
attempt = 1
max_attempts = 3

while attempt <= max_attempts:
  run test_command
  if exit_code == 0:
    test_status = "passed"
    break
  else:
    Print "Tests failed (attempt {attempt}/{max_attempts})."
    if attempt < max_attempts:
      Print "Attempting fix..."
      targeted_fix(test_output):
        1. Parse test runner output for the first failing test name and assertion message.
        2. Read the source file containing the failing assertion.
        3. Apply a single-location edit (≤ 15 lines) that addresses the assertion.
        4. Do NOT modify test files — only fix production code.
        5. If the failure is an import/module error, fix the import only.
    attempt += 1

if test_status != "passed" after 3 attempts:
  Print "[BLOCKED] Tests failed after 3 attempts. Action marked as blocked."
  Print "Review test output above and fix manually."
  Update action status to "blocked" in action_queue.json
  git stash  (preserve work without committing)
  EXIT with non-zero status.
```

When fixing between attempts: make targeted changes only — address the
specific failing assertion or import error. Do not rewrite large sections.

---

## Step 5: Create PR

Stage only the files that were explicitly changed in Step 3 **and** any files
edited during test-fix retries in Step 4. Maintain a cumulative
`changed_files` list across both steps.

Never use `git add -A` or `git add .`.

```bash
# Verify each file exists before staging (skip deleted files with a warning)
for file in changed_files:
  if file exists on disk:
    git add {file}
  else:
    Print "WARN: {file} no longer exists — skipping stage"
git commit -m "{selected.title}"
git push origin HEAD
```

If `git push` fails:
```
if error contains "conflict" or "rejected" or "non-fast-forward":
  Print "ERROR: merge conflict detected — {error}"
  Print "Resolve manually, then: git push origin {branch_name}"
  Update action status to "blocked" with memo "merge conflict with main"
else:
  Print "ERROR: git push failed — {error}"
  Print "Push manually with: git push origin {branch_name}"
  Record push error in action-queue memos.
EXIT with non-zero status.
```

Create the PR as Draft (always):
```bash
gh pr create \
  --title "{selected.title}" \
  --body "$(cat <<'EOF'
<!-- ooda:meta source_domain={selected.source_domain} rice={selected.effective_rice} action_id={selected.id} -->

## Source
- **Domain**: {selected.source_domain}
- **RICE Score**: {selected.effective_rice}
- **Action ID**: {selected.id}

## Changes
| File | Description |
|------|-------------|
| `{file1}` | {one-line description} |

## Test Results
- **Status**: {test_status}
- **Command**: `{config.test_command}`
- **Attempts**: {attempt}/{max_attempts}
- **Output** (last run): `{last 5 lines of test output or "tests skipped"}`

## Notes
{any partial PR notes, size limit warnings, or protected-path flags}

---
Generated by OODA-loop dev-cycle v1.0.0
EOF
)" \
  --draft
```

If `gh` is not available:
```
Print "gh (GitHub CLI) not found. PR creation skipped."
Print "Push the branch and create a PR manually:"
Print "  git push origin {branch_name}"
Print "  gh pr create --draft --title \"{selected.title}\""
pr_number = null
```

Update `action_queue.json`:
```json
{
  "status": "proposed",
  "pr_number": {number or null},
  "pr_url": "{url or null}",
  "proposed_at": "{ISO 8601}"
}
```

---

## Step 6: Report

Print the final summary:

```
dev-cycle complete — {ISO timestamp}
Action  : {selected.title} (RICE: {selected.effective_rice})
Branch  : auto/dev-cycle/{slug}
PR      : #{pr_number} (Draft)  |  {pr_url}
Files   : {files_changed} changed
Lines   : {lines_changed} changed
Tests   : {test_status}
Status  : proposed
```

If PR was not created (gh unavailable):
```
PR      : not created — push branch and create manually
```

---

## Graceful Degradation

| Scenario | Behavior |
|---|---|
| HALT file present | Print reason, exit immediately |
| Level < 3, not manual | Print level message, exit cleanly |
| action_queue.json missing | Print "Action queue not found at agent/state/evolve/action_queue.json", exit cleanly |
| No pending actions | Print "No pending actions", exit cleanly |
| Branch already exists | Append suffix (`-2`, `-3`), continue |
| PR size limit hit | Create partial PR, note remaining scope in action memos |
| Tests fail after 3 tries | Mark action "blocked", stash changes, exit non-zero |
| `git push` fails | Record error in memos, print manual instructions, exit non-zero |
| `gh` not installed | Skip PR creation, print manual instructions, exit 0 |
| `test_command` not configured | Skip tests, record "skipped", continue to PR |
| `related_files` missing/empty | Proceed with action title and source report only |
| Protected path changed | Already in Draft mode — note in PR body as protected-path change |
| Merge conflict on push | Abort push, mark action `"blocked"` with memo `"merge conflict with main"`, stash changes, exit non-zero |
| `action_queue.json` malformed | Print parse error, exit cleanly |
| Branch suffix exhausted (`-9`) | Print error, mark action `"blocked"`, exit non-zero |
