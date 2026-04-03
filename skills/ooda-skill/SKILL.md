---
name: ooda-skill
description: Create, disable, and enable domain skills. Generates project-specific SKILL.md files via a short interview.
ooda_phase: support
version: "1.0.0"
input:
  files: [config.json]
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

# ooda-skill — Domain Skill Wizard

Manages domain skills: create new skills via guided interview, disable or
enable domains, and list current domain status. Generates a complete, project-
specific SKILL.md by combining user answers with a generator template.

---

## Step 0: HALT Check (Always First)

Read `agent/safety/HALT`. If the file exists:
`[HALT] ooda-skill blocked. Remove agent/safety/HALT to continue.` — stop.

If `config.json` is missing:
`config.json not found. Run /ooda-setup first.` — stop.

Parse the subcommand from the user's invocation:
`create | disable | enable | list`
Unknown subcommand → print Usage block and exit.

---

## Subcommand: list

Print a table of all domains from `config.domains`, sorted by status then name.

```
Domain              Status      Skill
──────────────────────────────────────────────────
service_health      active      /scan-health
ux_evolution        available   /scan-ux
business_strategy   available   /scan-market
competitors         disabled    /scan-competitors
```

Status values:
- `active`    — skill created and configured, evolve will invoke it
- `available` — domain defined in config, skill not yet created
- `disabled`  — domain exists but status set to "disabled"

Footer: `Total: {N} domains — {N} active, {N} available, {N} disabled`
If `config.domains` is empty: `No domains configured. Run /ooda-setup first.`

---

## Subcommand: disable {domain-name}

1. Look up `config.domains.{domain-name}`. Not found → print `Domain not found: {name}` and exit.
2. Already disabled → print `{name} is already disabled.` and exit.
3. Back up `config.json` to `config.json.bak`.
4. Set `config.domains.{domain-name}.status = "disabled"`.
5. Write and re-parse config.json to confirm valid JSON.
6. Print:
   ```
   {name} disabled.
   Re-enable with: /ooda-skill enable {name}
   ```

---

## Subcommand: enable {domain-name}

1. Look up `config.domains.{domain-name}`. Not found → print `Domain not found: {name}` and exit.
2. Check if a skill file exists at `skills/{name}/SKILL.md`.
   - If yes → restore status to `"active"`.
   - If no  → restore status to `"available"`.
3. Back up config.json to config.json.bak.
4. Write updated status. Re-parse to confirm valid JSON.
5. Print:
   ```
   {name} enabled (status: {active|available}).
   ```
   If status is "available": `Run /ooda-skill create {name} to generate the skill.`

---

## Subcommand: create {skill-name}

### Step 1: Validate domain

Look up `config.domains` for an entry whose `primary_skill` matches `/{skill-name}`.
If not found → `No domain found for skill: {skill-name}. Check /ooda-skill list.` — exit.
If `domain.status != "available"`:
- `"active"` → `{skill-name} already exists. Find it at skills/{skill-name}/SKILL.md`
- `"disabled"` → `{skill-name} is disabled. Run /ooda-skill enable {domain-name} first.`
Exit in both cases.

Check that the generator template exists:
`templates/skill-generators/{skill-name}.prompt.md`
If missing → `Generator template not found: templates/skill-generators/{skill-name}.prompt.md` — exit.

### Step 2: Interview

Print: `Creating skill: {skill-name}`
Print: `Answer a few questions to tailor this skill to your project.`
Print: `(Press Enter to accept defaults where shown)`

Run the question set for the specific skill (see Question Sets below).
Store all answers in memory as `user_context`.

### Step 3: Generate SKILL.md

Read the following files:
1. `templates/skill-generators/{skill-name}.prompt.md` — generator instructions
2. `templates/SKILL_TEMPLATE.md` — structural skeleton
3. `agent/contracts/schema.md` — contract format

Compose a generation prompt:
```
You are generating a SKILL.md for the OODA-loop harness.

Generator instructions:
{contents of skill-generators/{skill-name}.prompt.md}

Skill template structure:
{contents of SKILL_TEMPLATE.md}

Contract schema:
{contents of agent/contracts/schema.md}

User's project context:
{user_context as labeled key-value pairs}

Generate a complete, production-ready SKILL.md for the {skill-name} skill.
Follow the generator instructions exactly. Use the user's project context
throughout — no generic placeholders.
```

Use Claude to generate the SKILL.md content.

### Step 4: Validate generated output

Before writing any file, verify the generated SKILL.md contains:

| Check | Rule |
|---|---|
| YAML frontmatter | `---` block at top with name, ooda_phase, version, description |
| `contract_version` field | Present and set to `"1.0"` |
| `name` field | Equals `{skill-name}` |
| `ooda_phase` field | One of: meta, observe, detect, strategize, execute, support |
| `status` field | Present — `active` or `deprecated` (default: `active`) |
| `safety.halt_check` | `true` |
| `safety.read_only` | Present |
| `input.files` | Non-empty list |
| `output.files` | Non-empty list |
| Step 0 (Adaptive Lens) | Section reading `agent/state/{domain}/lens.json` |
| Step 1 (HALT check) | HALT file check before any action |
| `references/context.json` | Skill reads this file in input.files or Step 1 |

If any check fails: print `[WARN] Generated skill missing: {check}. Regenerating...`
and retry generation once with the specific gap highlighted. If second attempt
also fails, write the file anyway and append a `## TODO` section listing the
missing items for manual completion.

### Step 5: Write files

Create directory: `skills/{skill-name}/`
Write: `skills/{skill-name}/SKILL.md` (generated content)

Write `skills/{skill-name}/references/context.json`:
```json
{
  "schema_version": "1.0.0",
  "skill": "{skill-name}",
  "generated_at": "{ISO 8601 timestamp}",
  "user_context": {
    {user_context key-value pairs as JSON}
  }
}
```

For scan-market also write `skills/{skill-name}/references/known-entities.md`:
```markdown
# Known Entities — {skill-name}

## Product
{product_description from user answers}

## Target Customer
{target_customer from user answers}

## Competitors
{competitors list from user answers, one per line as - name}

## Data Sources
{data_sources from user answers}
```

### Step 6: Update config + symlink

Back up `config.json` to `config.json.bak`.
Set `config.domains.{domain-name}.status = "active"` in config.json.
Write and re-parse config.json to confirm valid JSON.

### Step 7: Print summary

```
Skill created: {skill-name}

  SKILL.md:      skills/{skill-name}/SKILL.md
  References:    skills/{skill-name}/references/context.json
  Domain status: active

Next steps:
  Review:  skills/{skill-name}/SKILL.md
  Run:     /{skill-name}
  Config:  /ooda-config domain list
```

---

## Question Sets

### scan-market (5 questions)

```
Q1: What does your product do? (1-2 sentences)
    > {user input}
    → stored as: product_description

Q2: Who is your target customer?
    (e.g., "solo indie hackers", "B2B SaaS teams", "e-commerce stores")
    > {user input}
    → stored as: target_customer

Q3: What are your top 3 business goals?
    (e.g., "grow to 1000 users", "reduce churn below 5%", "launch in new market")
    > {user input}
    → stored as: business_goals

Q4: What data sources can you access?
    (e.g., "Google Analytics, Stripe dashboard, GitHub stars, HN upvotes")
    > {user input}
    → stored as: data_sources

Q5: Name 2-5 competitors (product names or URLs, comma-separated)
    > {user input}
    → stored as: competitors
```

### scan-ux (4 questions)

```
Q1: What is your frontend stack?
    (e.g., "React + TypeScript", "Vue 3", "vanilla HTML/CSS", "Next.js")
    > {user input}
    → stored as: frontend_stack

Q2: What are the key user flows to audit?
    (e.g., "signup, checkout, onboarding, settings page")
    > {user input}
    → stored as: key_flows

Q3: What UX framework or heuristics to apply?
    (e.g., "Nielsen's 10 heuristics", "WCAG 2.1 AA", or "use defaults")
    [default: use defaults]
    > {user input}
    → stored as: ux_framework

Q4: Any specific pages or components to focus on?
    (e.g., "/pricing, /signup, <Header> component" — or "all" for site-wide)
    [default: all]
    > {user input}
    → stored as: focus_areas
```

### scan-competitors (3 questions)

```
Q1: Who are your top 3-5 competitors? (names or URLs, comma-separated)
    > {user input}
    → stored as: competitors

Q2: What to track?
    (options: pricing, features, changelog, all)
    [default: all]
    > {user input}
    → stored as: track_what

Q3: Any competitor URLs to monitor directly?
    (paste URLs comma-separated, or press Enter to use search-based discovery)
    > {user input}
    → stored as: competitor_urls
```

---

## Graceful Degradation

| Condition | Behavior |
|---|---|
| HALT file exists | Print reason, exit immediately |
| config.json missing | Print setup message, exit |
| Domain not found for skill | Print message with /ooda-skill list hint, exit |
| Generator template missing | Print message with file path, exit |
| Generation fails | Print error, suggest manual creation via SKILL_TEMPLATE.md |
| Symlink target already exists | Skip silently, continue |
| config.json write fails | Print error, revert from config.json.bak |

---

## Usage

```
/ooda-skill create {skill-name}    Create a new domain skill via interview
/ooda-skill disable {domain-name}  Disable a domain (sets status to "disabled")
/ooda-skill enable {domain-name}   Re-enable a domain
/ooda-skill list                   Show all domains with status
```

Supported skill-name values for `create`: `scan-market`, `scan-ux`, `scan-competitors`
