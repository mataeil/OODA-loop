# CLAUDE.md — OODA-loop

Autonomous operations agent harness built on Boyd's OODA loop for Claude Code.

## Code Rules

- All files written in **English**
- No secrets in config.json — use environment variable references only (`$ENV_VAR`)
- Every skill must start with a HALT file check
- No `git add -A` — explicit file staging only

## Session Continuity

Design decisions, 7-Agent review results, and implementation plans from prior sessions:
- `.claude/context.md`
- `.claude/plans/OODA-loop-plan.md`

---

## 한국어 참고

Boyd의 OODA 루프 기반 자율운영 AI 에이전트 하네스.

### 코드 규칙

- 모든 파일은 **영어**로 작성
- config.json에 시크릿 직접 저장 금지 — 환경변수 참조만 (`$ENV_VAR`)
- 스킬은 반드시 HALT 파일 체크로 시작
- `git add -A` 금지 — 명시적 파일 스테이징만
