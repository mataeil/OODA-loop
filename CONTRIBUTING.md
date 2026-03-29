# Contributing to ooda-harness

Thank you for your interest in contributing. All contributions are valued — whether you are
fixing a typo, improving a skill prompt, or proposing a change to the core engine. This guide
explains how to contribute effectively.

Please review our Code of Conduct before participating. By contributing you agree to abide by it.

---

## Three Contribution Tiers

Contributions fall into three tiers based on scope and risk. Start with the tier that matches
your familiarity with the project.

### Tier 1: Skills (recommended entry point)

Skills are self-contained slash commands in `agent/skills/`. They are the easiest way to extend
ooda-harness without touching the core engine.

What you can do:
- Write new domain skills (observe, detect, strategize, execute, support)
- Improve existing skill prompts for clarity, accuracy, or robustness
- Add skill chains that compose multiple skills together
- Create integrations with external tools or APIs

Requirements:
- All skills must conform to the interface defined in `agent/contracts/schema.md`
- Register new skills in `config.example.json` under an appropriate domain
- Use `templates/SKILL_TEMPLATE.md` as your starting point (see Quick Guide below)
- Skills must check for the HALT file at the top of their execution logic

### Tier 2: Documentation

Good documentation lowers the barrier for everyone. Contributions here have broad impact.

What you can do:
- Improve README, CONCEPTS.md, or inline comments
- Add domain configuration examples under `examples/` or `templates/domain-examples.yaml`
- Translate documentation into other languages
- Write tutorials, how-to guides, or blog-style walkthroughs
- Fix typos, broken links, or unclear explanations

No approval is needed before starting documentation changes. Open a PR when ready.

### Tier 3: Core Engine

Core changes affect every user and every cycle. They require extra care.

What falls under Tier 3:
- Modifying the evolve orchestrator (`agent/skills/meta/evolve/`)
- Changing scoring formulas or domain weights
- Modifying safety policies (`agent/safety/autonomous-mode.md`)
- Changing the contract interface (`agent/contracts/schema.md`)
- Altering state file schemas (`agent/state/evolve/`)

**Open an issue before starting.** Describe the problem you are solving and your proposed
approach. Wait for feedback from maintainers before writing code. Core changes have implications
for autonomous operation safety and self-modification protection — they need thorough review.

---

## Development Setup

```bash
git clone https://github.com/ooda-harness/ooda-harness.git
cd ooda-harness
cp config.example.json config.json
# Edit config.json for your test project
# Never commit config.json — it is in .gitignore
```

Run the setup wizard to configure a test project:

```
/ooda-setup
```

Use dry-run mode to test the orchestrator without executing actions:

```
/evolve --dry-run
```

---

## Pull Request Guidelines

- One logical change per PR. Split unrelated changes into separate PRs.
- Write clear commit messages. Use `feat:`, `fix:`, `docs:`, `refactor:` prefixes.
- Add or update tests if your change affects behavior.
- Update documentation if you change the user-facing interface or config schema.
- Keep PRs within the safety limits: max 20 files, 500 lines changed. Larger PRs require
  explicit maintainer approval and are subject to the same review process as Tier 3 changes.
- Use descriptive branch names: `feat/skill-name`, `fix/issue-description`, `docs/section-name`

---

## Code Style

- All code and documentation must be written in English.
- Skill files must follow the contract interface defined in `agent/contracts/schema.md`.
- Any change to config behavior must be reflected in `config.example.json`.
- Do not use `git add -A`. Stage files explicitly to avoid accidentally committing secrets or
  generated files.
- Do not hardcode secrets. Use `$ENV_VAR` references in config files. The `$` prefix signals
  that the value should be read from the environment at runtime.

---

## Creating a New Skill

A quick three-step process:

**Step 1.** Copy the template to your target location:

```bash
cp templates/SKILL_TEMPLATE.md agent/skills/<phase>/<skill-name>/SKILL.md
```

Valid phases: `observe`, `detect`, `strategize`, `execute`, `support`

**Step 2.** Register the skill in `config.json` under the appropriate domain:

```json
"domains": {
  "my_domain": {
    "primary_skill": "/my-skill-name",
    "weight": 1.0
  }
}
```

**Step 3.** Create a symlink so Claude Code can find it:

```bash
ln -s ../../agent/skills/<phase>/<skill-name> .claude/skills/<skill-name>
```

The skill is now available as `/<skill-name>` in Claude Code and the evolve orchestrator will
discover it from config.

---

## Reporting Issues

**Bug reports** should include:
- Your `config.json` with secrets redacted (replace values with `"REDACTED"`)
- The full error output or unexpected behavior observed
- Steps to reproduce, including which skill or command was running

**Feature requests** should describe the use case and the problem you are trying to solve.
Avoid jumping straight to a solution — understanding the use case helps maintainers evaluate fit.

**Security issues** must not be reported as public GitHub issues. See SECURITY.md for the
responsible disclosure process. Security bugs affecting autonomous operation or secret handling
are treated as high priority.

---

## Good First Issues

Issues labeled **good first issue** on the GitHub issues page are specifically curated for
newcomers. They are scoped, self-contained, and come with enough context to get started without
deep knowledge of the codebase. If you are looking for a place to begin, start there.
