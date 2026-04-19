# Fixture: lens-pre-init

## Purpose

Verify that evolve Step 1-A creates `agent/state/{domain}/lens.json` for every
active domain before any observe skill runs. Production deployments (fwd.page
152 cycles) had zero lens files because the only init path was inside Step 5-E's
observe-skill loop, which custom observe skills never triggered.

## Setup

Seed state: nothing. The fixture's seed directory intentionally contains
**no** `agent/state/*/lens.json` files.

`config.json` at the fixture root enables three domains — `service_health`,
`test_coverage`, and `backlog` — all with `status: "active"`.

## Expected dry-run output

At Step 1-A, three `[Observe] Initialized lens for {domain}.` lines print
(one per active domain). Even though `/evolve --dry-run` does not write
state files, it should still log the init decision it *would* make, so the
operator sees the expected fresh-init behavior.

Repeat run with seeded lens files (copy them into `seed/agent/state/<domain>/`)
should print nothing for existing files.

## Config

Three active domains, zero lens files. No custom observe skill overrides.
