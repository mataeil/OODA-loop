# CLAUDE.md — OODA-loop

Boyd의 OODA 루프 기반 자율운영 AI 에이전트 하네스.

## 코드 규칙

- 모든 파일은 **영어**로 작성
- config.json에 시크릿 직접 저장 금지 — 환경변수 참조만 (`$ENV_VAR`)
- 스킬은 반드시 HALT 파일 체크로 시작
- `git add -A` 금지 — 명시적 파일 스테이징만

## 작업 이어가기

이전 세션의 설계 결정, 7-Agent 리뷰 결과, 구현 계획:
- `.claude/context.md`
- `.claude/plans/OODA-loop-plan.md`
