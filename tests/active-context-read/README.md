# Fixture: active-context-read

## Purpose

Verify that evolve Step 1 loads `config.active_context.path` as an opaque
blob and passes it to the winning skill's invocation as a context variable
in Step 4-B. Formalizes the Lynceus `active_context: "contexts/lee_junseok_22.json"`
pattern (Lynceus config.json:8).

## Setup

`seed/config.json` has:

```json
"active_context": {
  "path": "contexts/persona-demo.json",
  "refresh_skill": null,
  "refresh_interval_hours": 168
}
```

`seed/contexts/persona-demo.json` is a minimal persona blob used by the
fixture to prove the loader works (content is opaque to evolve).

## Expected dry-run output

```
[Observe] active_context loaded: contexts/persona-demo.json (age: 0m)
[Act] /{skill} starting...
  context_vars:
    - active_context: { ... contents of persona-demo.json ... }
```

If `refresh_skill` is set and the file mtime exceeds `refresh_interval_hours`,
a memo entry is added to `memos.json` queuing the refresh_skill for the next
cycle. In this fixture, `refresh_skill` is null so no refresh occurs.

## Edge cases

- **Missing path**: `[Observe] active_context not loadable: file not found. Proceeding without context.`
- **Malformed JSON**: same message with `parse error` suffix. Cycle continues — active_context is optional.

## Config

Single-domain config with `active_context` pointing at the demo persona.
