#!/usr/bin/env bash
# OODA-loop HALT guard — a PreToolUse hook (wired in hooks/hooks.json).
#
# Makes the HALT kill-switch DETERMINISTIC: while agent/safety/HALT exists, this
# blocks file-writing / shell / merge tools at the Claude Code level — not by
# skill cooperation. So a runaway autonomous cycle (/loop or a cloud routine)
# stops the moment HALT appears, even if a skill forgot its Step-0 check.
#
# - No-ops outside an OODA-loop project (no config.json) so it never interferes
#   with other repos when the plugin is enabled globally.
# - ALWAYS allows actions that reference the HALT file, so you (or the agent) can
#   remove it and resume. Block = exit 2 (PreToolUse "deny"); allow = exit 0.
# - Dependency-free (bash only) — runs in the cloud routine sandbox too.
#
# Custom halt_file path? This guards the canonical agent/safety/HALT; if you set
# a different config.safety.halt_file, edit the HALT= line below to match.
set -euo pipefail
INPUT="$(cat 2>/dev/null || true)"
ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$ROOT/config.json" ] || exit 0          # not an OODA-loop project → allow
HALT="$ROOT/agent/safety/HALT"
[ -f "$HALT" ] || exit 0                       # no HALT → allow
case "$INPUT" in
  *agent/safety/HALT*) exit 0 ;;               # clearing/inspecting HALT → allow
esac
echo "[OODA-loop] 🛑 HALT active — tool blocked. Remove agent/safety/HALT to resume." >&2
exit 2
