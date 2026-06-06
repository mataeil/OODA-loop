# Minimal domain skill example

The smallest end-to-end custom domain for OODA-loop: a `disk_usage` domain with a
~30-line Observe skill ([`SKILL.md`](SKILL.md)). Copy it, rename, and adjust.

## 1. Add the skill

Put the skill where the plugin discovers skills:

```
skills/scan-disk/SKILL.md      # copy templates/minimal-domain-skill/SKILL.md here
```

## 2. Register the domain in `config.json`

```json
{
  "domains": {
    "disk_usage": {
      "weight": 1.0,
      "status": "active",
      "skill": "/scan-disk",
      "state_file": "agent/state/disk_usage/state.json"
    }
  }
}
```

## 3. Allowlist the skill (safety)

```json
{
  "safety": { "skill_allowlist": ["/scan-disk", "..."] }
}
```

## 4. Run

```
/scan-disk        # run it directly to verify it writes state
/evolve           # the engine now scores disk_usage each cycle
/ooda-status      # see the domain in the dashboard
```

That's the whole loop: a skill that observes and records, a domain entry that
registers it, and the allowlist that authorizes it. Everything else (scoring,
the Adaptive Lens, the Cycle Card) the engine handles for you.

See [`../SKILL_TEMPLATE.md`](../SKILL_TEMPLATE.md) for the full skill contract and
[`../../agent/contracts/schema.md`](../../agent/contracts/schema.md) for the I/O spec.
