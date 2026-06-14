# Fixture: scorecard

Verifies the **Loop Scorecard** (`scripts/loop_scorecard.py`) — OODA-loop's
headline measurement artifact. Seeds a 6-cycle outcome history spanning every
band (observe → action → PR created → merged → merged-and-held → futile) plus
matching metrics counters, and asserts the computed canon KPIs:

| KPI | Expected |
|---|---|
| Loop Value Score (mean quality) | (0.1+0.2+0.5+0.8+1.0+0.0)/6 = **0.433** |
| Task Completion Rate (merged & held) | 2/6 = **33.3%** |
| Futile Cycle Rate | 1/6 = **16.7%** |
| PR Merge Rate | 1/1 = **100%** |
| Action Queue Resolution | 2/4 = **50%** |
| Cost / Successful cycle | $0.30 / 2 = **$0.15** |

Tier-0 (`verify.py`) computes these from the seed and asserts the numbers.
