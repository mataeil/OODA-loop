"""Deterministic rail driver for the OODA-loop E2E suite.

OODA-loop has no shipped binary — the canonical executor is Claude interpreting
skills/evolve/SKILL.md. This driver is a VERBATIM TRANSCRIPTION of the spec's
*mechanical rails* (locking, crash recovery, interval gating, breakers, cost
ledger, action-queue hygiene, decision-log/episode persistence, 6-D git commit)
so they can be exercised end-to-end against a real filesystem, real git, real
processes, and an injected clock — fully isolated inside a Docker container.

Every block cites the SKILL.md section it transcribes. If the spec changes,
change this file in the same PR — reviewers diff the two side by side.

What this driver deliberately does NOT transcribe: Decide scoring (covered by
scripts/dryrun_score.py), the auto-merge gate (scripts/auto_merge_gate.py), and
long-horizon threshold arithmetic (scripts/sim_longhorizon.py) — those already
have deterministic references checked by tests/verify.py. Scenario tests inject
the *outcome* of a cycle (domain, result, output) and assert the rails react
exactly as specified.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def iso_week(d: dt.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


@dataclass
class CycleResult:
    status: str                 # completed | skip_halt | skip_locked | skip_interval
                                # | halt_midcycle | halt_corrupt_ledger
    cycle: int | None = None
    logs: list = field(default_factory=list)
    halt_created: bool = False
    crash_recovered: bool = False
    stale_lock_removed: bool = False
    committed: bool = False

    def has_log(self, fragment: str) -> bool:
        return any(fragment in l for l in self.logs)


class Engine:
    """One Engine per sandbox project directory (as /evolve sees it)."""

    def __init__(self, project: Path):
        self.p = Path(project)
        self.ev = self.p / "agent" / "state" / "evolve"

    # -- paths -------------------------------------------------------------
    @property
    def cfg(self) -> dict:
        return read_json(self.p / "config.json", {}) or {}

    @property
    def safety(self) -> dict:
        return self.cfg.get("safety", {}) or {}

    @property
    def halt_path(self) -> Path:
        return self.p / self.safety.get("halt_file", "agent/safety/HALT")

    @property
    def lock_path(self) -> Path:
        # [SKILL.md 0-B] lock_file = agent/state/evolve/.lock
        return self.ev / ".lock"

    def state(self) -> dict:
        return read_json(self.ev / "state.json", {
            "schema_version": "1.0.0", "cycle_count": 0, "last_cycle": None,
            "cycle_in_progress": False, "decision_log": [],
        })

    # -- crash simulation ---------------------------------------------------
    def simulate_crash(self, now: str) -> None:
        """Leave the exact debris a SIGKILL'd cycle leaves: a live lock file
        [0-B] plus cycle_in_progress=true [set before Step 1]."""
        write_json(self.lock_path, {"pid": 0, "started_at": now})
        st = self.state()
        st["cycle_in_progress"] = True
        write_json(self.ev / "state.json", st)

    def spawn_and_kill_real_cycle(self, now: str) -> None:
        """Spawn a REAL child process that acquires the lock + marks the cycle
        in progress (what a starting cycle does), then SIGKILL it mid-run —
        verifying the substrate, not a simulation of it."""
        # The child sets BOTH the lock (0-B) AND cycle_in_progress (pre-Step-1),
        # then signals readiness with a sentinel file written LAST. The parent
        # waits for the sentinel before SIGKILL — so the crash debris (lock +
        # cycle_in_progress) is always fully present, no write-ordering race.
        child = (
            "import json,sys,time;from pathlib import Path;"
            "p=Path(sys.argv[1]);now=sys.argv[2];ev=p/'agent/state/evolve';"
            "ev.mkdir(parents=True,exist_ok=True);"
            "(ev/'.lock').write_text(json.dumps({'pid':0,'started_at':now}));"
            "sp=ev/'state.json';st=json.loads(sp.read_text());"
            "st['cycle_in_progress']=True;sp.write_text(json.dumps(st));"
            "(ev/'.crash_ready').write_text('1');"   # sentinel, written LAST
            "time.sleep(300)"
        )
        proc = subprocess.Popen(["python3", "-c", child, str(self.p), now])
        import time
        ready = self.ev / ".crash_ready"
        for _ in range(500):                          # up to ~5s
            if ready.exists():
                break
            time.sleep(0.01)
        else:
            proc.kill()
            raise RuntimeError("child never reached the crash point")
        proc.kill()          # SIGKILL — no cleanup runs, exactly like a crash
        proc.wait()
        ready.unlink(missing_ok=True)                 # sentinel is test-only debris

    # -- the cycle ----------------------------------------------------------
    def run_cycle(self, now: str, outcome: dict | None = None) -> CycleResult:
        """Run one /evolve cycle's rails at injected wall-clock `now` (ISO).

        `outcome` is what Claude/the domain skill would have produced this
        cycle — the driver controls the rails AROUND it:
          selected_domain / selected_skill / result ("success"|"error")
          had_output (bool — folds 2-A2's "created PR OR extracted actions OR
                      new alerts OR changed confidence" into one injected flag)
          pr_number / score / confidence
        """
        o = {"selected_domain": "test_coverage", "selected_skill": "/check-tests",
             "result": "success", "had_output": False, "pr_number": None,
             "score": 1.0, "confidence": 0.7}
        o.update(outcome or {})
        now_dt = dt.datetime.fromisoformat(now)
        r = CycleResult(status="completed")
        safety = self.safety

        # ---- Step 0-Pre: cost ledger missing vs corrupt --------------------
        # [SKILL.md: "If cost_ledger.json is MISSING (fresh install) ... create"
        #  / "If it EXISTS but is CORRUPT ... fail closed — back it up, HALT,
        #  delete the lock first, EXIT"]
        lp = self.ev / "cost_ledger.json"
        if not lp.exists():
            write_json(lp, {"schema_version": "1.0.0", "date": str(now_dt.date()),
                            "entries": [], "total_estimated_usd": 0.0})
            r.logs.append("[Init] cost_ledger.json created (fresh)")
        elif read_json(lp) is None:
            lp.rename(lp.with_suffix(".json.corrupt"))
            self._create_halt("cost ledger corrupt — today's spend unknown; "
                              "refusing to run without cost accounting")
            if self.lock_path.exists():
                self.lock_path.unlink()
            r.status, r.halt_created = "halt_corrupt_ledger", True
            r.logs.append("[HALT] corrupt cost ledger — fail closed")
            return r

        # ---- 0-A: HALT check [SKILL.md 0-A] --------------------------------
        if self.halt_path.exists():
            r.status = "skip_halt"
            r.logs.append("[HALT] Agent stopped.")
            return r

        # ---- 0-B: lock with inline staleness [SKILL.md 0-B, v1.3.0] --------
        if self.lock_path.exists():
            lock = read_json(self.lock_path, {}) or {}
            started = dt.datetime.fromisoformat(lock.get("started_at", now))
            age_min = (now_dt - started).total_seconds() / 60
            timeout = safety.get("lock_timeout_minutes", 30)
            if age_min < timeout:
                r.status = "skip_locked"
                r.logs.append(f"[SKIP] Another evolve cycle is running (lock age {age_min:.0f}m).")
                return r
            self.lock_path.unlink()   # stale → remove, fall through to 0-C
            r.stale_lock_removed = True
            r.logs.append(f"[WARN] Stale lock detected (age {age_min:.0f}m >= {timeout}m). Removing and recovering.")
        write_json(self.lock_path, {"pid": 0, "started_at": now})

        # ---- 0-C: crash recovery [SKILL.md 0-C, v1.3.x diagnostics fix] ----
        st = self.state()
        if st.get("cycle_in_progress"):
            crashed = st["cycle_count"] + 1     # crashed cycle never reached Step 6
            log = st.get("decision_log", [])
            last = log[-1] if log else None
            r.crash_recovered = True
            r.logs.append(f"[WARN] Cycle #{crashed} did not complete (crash/kill detected).")
            if last:
                r.logs.append(f"  Last completed: #{last['cycle']} — domain {last.get('selected_domain')}")
            st["cycle_in_progress"] = False
            self._memo(st, {"type": "crash_recovery", "cycle": crashed,
                            "last_completed": last["cycle"] if last else None})

        # ---- 0-D: min cycle interval [SKILL.md 0-D, v1.3.0 lock release] ---
        if st.get("last_cycle"):
            elapsed_min = (now_dt - dt.datetime.fromisoformat(st["last_cycle"])).total_seconds() / 60
            if elapsed_min < safety.get("min_cycle_interval_minutes", 30):
                if not self._critical_alert_present():
                    self.lock_path.unlink()     # the v1.3.0 fix under test
                    write_json(self.ev / "state.json", st)
                    r.status = "skip_interval"
                    r.logs.append("[SKIP] Too soon.")
                    return r
                r.logs.append("[URGENT] Critical alert detected, bypassing interval.")

        st["cycle_in_progress"] = True          # [before Step 1]
        write_json(self.ev / "state.json", st)

        # ---- 2-A2: saturation breaker — evaluates the PREVIOUS completed
        # cycle [SKILL.md 2-A2, v1.3.0: prev-cycle + missing-field init] ------
        st.setdefault("consecutive_observe_only_cycles", 0)
        sat = self.cfg.get("saturation", {}) or {}
        log = st.get("decision_log", [])
        if log:
            if log[-1].get("had_output"):
                st["consecutive_observe_only_cycles"] = 0
            else:
                st["consecutive_observe_only_cycles"] += 1
                n = st["consecutive_observe_only_cycles"]
                if n == sat.get("warn_threshold", 5):
                    self._memo(st, {"type": "saturation_warning", "cycles": n})
                    r.logs.append(f"[Orient] ⚠ Saturation warning: {n} consecutive observe-only cycles.")
                if n == sat.get("boost_threshold", 10):
                    self._saturation_boost(sat.get("implementation_boost", 5.0))
                    r.logs.append("[Orient] ⚠ Saturation boost applied.")
                if n >= sat.get("halt_threshold", 15) and sat.get("auto_halt", True):
                    self._create_halt(f"Observation saturation: {n} cycles without actionable output.")
                    r.halt_created = True
                    r.logs.append(f"[Orient] 🛑 Saturation halt: {n} cycles.")
        write_json(self.ev / "state.json", st)  # persist counter before any exit

        # ---- 4-A: mid-cycle HALT re-check [SKILL.md 4-A, v1.3.0 lock release]
        if self.halt_path.exists():
            self.lock_path.unlink()
            st["cycle_in_progress"] = False
            write_json(self.ev / "state.json", st)
            r.status = "halt_midcycle"
            r.logs.append("[Act] HALT appeared mid-cycle — lock released, exiting.")
            return r

        # ---- Act outcome + 4-B rule 4: silent-failure breaker --------------
        # [SKILL.md 4-B r4, v1.3.0: counter + HALT after clean completion]
        st.setdefault("consecutive_silent_failures", 0)
        if o["result"] == "error":
            self._skill_gap(f"execution error in {o['selected_skill']}")
            st["consecutive_silent_failures"] += 1
            if st["consecutive_silent_failures"] >= safety.get("max_silent_failures", 3):
                self._create_halt(
                    f"{st['consecutive_silent_failures']} consecutive skill executions failed. "
                    "Unattended operation paused for human review.")
                r.halt_created = True
                r.logs.append("[Act] 🛑 max_silent_failures reached — HALT created (cycle still completes).")
        else:
            st["consecutive_silent_failures"] = 0

        # ---- Step 6 ---------------------------------------------------------
        cycle_id = st["cycle_count"] + 1

        # 6-C5b/6-C8: ledger daily reset, entry, sequence-gap backfill
        # [SKILL.md "Daily reset" + 6-C8 multi-cycle gap backfill]
        ledger = read_json(lp)
        if ledger["date"] != str(now_dt.date()):
            ledger = {"schema_version": "1.0.0", "date": str(now_dt.date()),
                      "entries": [], "total_estimated_usd": 0.0}
            r.logs.append("[Reflect] Cost ledger daily reset (UTC date changed).")
        recorded = {e["cycle_id"] for e in ledger["entries"]}
        if recorded:
            missing = [c for c in range(min(recorded), cycle_id) if c not in recorded]
            cap = (self.cfg.get("cost") or {}).get("max_backfill_cycles", 100)
            for c in missing[-cap:]:
                ledger["entries"].append({"cycle_id": c, "skill": "(backfilled)",
                                          "estimated_usd": 0.0, "synthetic": True})
            if missing:
                r.logs.append(f"[Reflect] Cost ledger gate: backfilled {len(missing)} cycle(s).")
        ledger["entries"].append({"cycle_id": cycle_id, "skill": o["selected_skill"],
                                  "estimated_usd": 0.02})
        ledger["entries"].sort(key=lambda e: e["cycle_id"])
        ledger["total_estimated_usd"] = round(
            sum(e["estimated_usd"] for e in ledger["entries"]), 4)
        write_json(lp, ledger)

        # 6-C6 hygiene sweep [SKILL.md v1.3.0 action lifecycle]
        self._action_hygiene(st, cycle_id, r)

        # 6-C9 Outcome Record [SKILL.md v1.4.0] — deterministic quality signal
        self._outcome_record(st, cycle_id, now, o)

        # Step 6 decision_log append — CANONICAL selected_* keys
        # [SKILL.md Step 6 + working_memory_size cap]
        entry = {"cycle": cycle_id, "timestamp": now,
                 "selected_domain": o["selected_domain"],
                 "selected_skill": o["selected_skill"],
                 "score": o["score"], "confidence": o["confidence"],
                 "result": o["result"], "pr_number": o["pr_number"],
                 "had_output": o["had_output"], "score_verified": True}
        st.setdefault("decision_log", []).append(entry)
        cap = (self.cfg.get("memory") or {}).get("working_memory_size", 20)
        while len(st["decision_log"]) > cap:
            st["decision_log"].pop(0)

        # Tier 2 episodes — fixture-canonical schema, id-existence guard
        # [SKILL.md "Tier 2 -- Episodes", v1.3.0 duplicate-generation fix]
        self._maybe_episode(st, now_dt, r)

        # 6-D git commit with gitignore guard [SKILL.md 6-D, v1.3.0 #31 guard]
        self._git_commit(cycle_id, r)

        # finalize [SKILL.md Step 6 end: lock deleted at end of Step 6]
        st["cycle_count"] = cycle_id
        st["last_cycle"] = now
        st["cycle_in_progress"] = False
        write_json(self.ev / "state.json", st)
        self.lock_path.unlink()
        r.cycle = cycle_id
        return r

    # -- helpers -------------------------------------------------------------
    def _create_halt(self, reason: str) -> None:
        self.halt_path.parent.mkdir(parents=True, exist_ok=True)
        self.halt_path.write_text(reason + "\nDelete this file to resume.\n")

    def _memo(self, st: dict, memo: dict) -> None:
        mp = self.ev / "memos.json"
        m = read_json(mp, {"schema_version": "1.1.0", "score_adjustments": {},
                           "interventions": [], "history": []})
        m.setdefault("history", []).append({**memo, "at_cycle": st.get("cycle_count")})
        m["history"] = m["history"][-10:]      # [SKILL.md 5-C: history cap 10]
        write_json(mp, m)

    def _skill_gap(self, desc: str) -> None:
        gp = self.ev / "skill_gaps.json"
        g = read_json(gp, {"schema_version": "1.0.0", "gaps": []})
        g["gaps"].append({"description": desc, "resolved": False})
        # [SKILL.md 6-C8 tail: cap 50, resolved evicted first]
        while len(g["gaps"]) > 50:
            idx = next((i for i, x in enumerate(g["gaps"]) if x.get("resolved")), 0)
            g["gaps"].pop(idx)
        write_json(gp, g)

    def _saturation_boost(self, boost: float) -> None:
        qp = self.ev / "action_queue.json"
        q = read_json(qp, {"pending": [], "completed": []})
        for item in q.get("pending", []):
            item["effective_rice"] = item.get("effective_rice", item.get("rice_score", 0)) + boost
        write_json(qp, q)

    def _critical_alert_present(self) -> bool:
        # [SKILL.md 0-D EXCEPTION: any domain state file with severity critical]
        for name, dom in (self.cfg.get("domains") or {}).items():
            sf = read_json(self.p / dom.get("state_file", f"agent/state/{name}.json"), {}) or {}
            if any(a.get("severity") == "critical" for a in sf.get("alerts", []) or []):
                return True
        return False

    def _action_hygiene(self, st: dict, cycle_id: int, r: CycleResult) -> None:
        qp = self.ev / "action_queue.json"
        q = read_json(qp)
        if not q:
            return
        pending = q.get("pending", [])
        for item in list(pending):
            if item.get("status") == "in_progress" and item.get("claimed_cycle", 0) < cycle_id:
                item["status"] = "pending"     # orphaned by a dead run
                self._memo(st, {"type": "action_requeued", "id": item.get("id")})
                r.logs.append(f"[Reflect] Re-queued orphaned action '{item.get('title')}'.")
            if item.get("status") == "blocked":
                pending.remove(item)
                q.setdefault("completed", []).append(item)
                r.logs.append(f"[Reflect] Blocked action '{item.get('title')}' moved to completed.")
        write_json(qp, q)

    def _maybe_episode(self, st: dict, now_dt: dt.datetime, r: CycleResult) -> None:
        ep_path = self.ev / "episodes.json"
        eps = read_json(ep_path, {"schema_version": "1.0.0", "episodes": []})
        summarized = iso_week(now_dt.date() - dt.timedelta(days=7))
        if iso_week(now_dt.date()) == summarized:      # same week — defensive
            return
        ep_id = f"EP-{summarized}"
        if any(e.get("id") == ep_id for e in eps["episodes"]):
            return                                      # id-existence guard
        week_entries = [e for e in st.get("decision_log", [])
                        if iso_week(dt.datetime.fromisoformat(e["timestamp"]).date()) == summarized]
        if not week_entries:
            return
        dom_counts: dict = {}
        for e in week_entries:
            dom_counts[e["selected_domain"]] = dom_counts.get(e["selected_domain"], 0) + 1
        eps["episodes"].append({
            "id": ep_id,
            "week_start": str((now_dt.date() - dt.timedelta(days=now_dt.weekday() + 7))),
            "week_end": str((now_dt.date() - dt.timedelta(days=now_dt.weekday() + 1))),
            "cycle_range": [week_entries[0]["cycle"], week_entries[-1]["cycle"]],
            "total_cycles": len(week_entries),
            "summary": f"{len(week_entries)} cycles in {summarized}",
            "domains_selected": dom_counts,
            "prs_created": sum(1 for e in week_entries if e.get("pr_number")),
            "prs_merged": 0, "prs_rejected": 0,
            "key_decisions": [], "lessons": [],
            "confidence_snapshot": {},
            "skill_gaps_found": 0, "contrarian_checks": 0,
            "patterns_detected": [], "created_at": now_dt.isoformat(),
        })
        write_json(ep_path, eps)
        r.logs.append(f"[Reflect] Episode {ep_id} generated.")

    def _outcome_record(self, st: dict, cycle_id: int, now: str, o: dict) -> None:
        """6-C9: append the deterministic quality signal via the shared reference
        (scripts/score_outcome.py — same source of truth as Tier 0)."""
        import importlib.util
        repo = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location("so", repo / "scripts" / "score_outcome.py")
        so = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(so)
        cyc = {"result": o["result"], "pr_number": o.get("pr_number"),
               "pr_outcome": o.get("pr_outcome"), "had_output": o.get("had_output")}
        rt, q = so.score(cyc)
        op = self.ev / "outcomes.json"
        outc = read_json(op, {"schema_version": "1.0.0", "entries": []})
        outc["entries"].append({"cycle_id": cycle_id, "timestamp": now,
                                "domain": o["selected_domain"], "skill": o["selected_skill"],
                                "result_type": rt, "quality_multiplier": q,
                                "on_mission": o.get("on_mission"),
                                "pr_number": o.get("pr_number"), "verifier_verdict": None})
        cap = (self.cfg.get("memory") or {}).get("outcomes_buffer_size", 200)
        outc["entries"] = outc["entries"][-cap:]
        write_json(op, outc)
        # cycle_log.jsonl append-only
        line = json.dumps({"cycle_id": cycle_id, "timestamp": now, "domain": o["selected_domain"],
                           "skill": o["selected_skill"], "result": o["result"], "result_type": rt,
                           "quality_multiplier": q, "had_output": o.get("had_output", False)})
        with open(self.ev / "cycle_log.jsonl", "a") as fh:
            fh.write(line + "\n")
        # counters
        c = read_json(self.ev / "metrics.json", {}).get("counters", {}) if (self.ev / "metrics.json").exists() else {}

    def _git_commit(self, cycle_id: int, r: CycleResult) -> None:
        if not (self.p / ".git").exists():
            return
        probe = subprocess.run(["git", "check-ignore", "-q", "agent/state/evolve/state.json"],
                               cwd=self.p, capture_output=True)
        if probe.returncode == 0:
            # [SKILL.md 6-D guard, v1.3.0 #31]
            r.logs.append("[WARN] agent/state/ is gitignored — state commits are NO-OPs.")
            return
        # explicit staging only — NEVER git add -A [SKILL.md 6-D]
        for f in ["agent/state/evolve/state.json", "agent/state/evolve/cost_ledger.json",
                  "agent/state/evolve/memos.json", "agent/state/evolve/action_queue.json",
                  "agent/state/evolve/skill_gaps.json", "agent/state/evolve/episodes.json"]:
            if (self.p / f).exists():
                subprocess.run(["git", "add", f], cwd=self.p, capture_output=True)
        done = subprocess.run(["git", "commit", "-q", "-m", f"evolve: cycle #{cycle_id} state"],
                              cwd=self.p, capture_output=True)
        r.committed = done.returncode == 0
