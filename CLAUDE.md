# CLAUDE.md — ooda-harness

Boyd의 OODA 루프 기반 자율운영 AI 에이전트 하네스.
AI가 스스로 전략을 세우고, 코드를 만들고, 배포한다. 사람은 PR을 리뷰할 뿐.

## 프로젝트 규칙

- Claude Code 전용
- 모든 파일은 **영어**로 작성
- config.json에 시크릿 직접 저장 금지 — 환경변수 참조만 (`$ENV_VAR`)
- fwd.page 하드코딩 절대 금지 — 모든 값은 config에서 읽기
- 스킬은 반드시 HALT 파일 체크로 시작
- `agent/safety/*`, `agent/skills/meta/*`, `agent/contracts/*` 변경은 Level 3 (사람 리뷰 필수)
- `git add -A` 금지 — 명시적 파일 스테이징만

## 참고 문서

- 구현 플랜 + 7-Agent 리뷰 결과: `.claude/plans/ooda-harness-plan.md`
- 작업 컨텍스트 (배경, 결정 사항, 아키텍처): `.claude/context.md`
- 레퍼런스 구현 (fwd.page): `/Users/mataeil/myproject/thehackathon-dev/fwd/agent/`
