# ooda-harness 작업 컨텍스트

이 문서는 이전 세션에서 축적된 설계 결정과 리뷰 결과를 새 세션에 전달하기 위한 것.

## 배경

fwd.page(URL 단축 서비스)에서 OODA 자율운영 시스템을 만들어 14사이클 실전 운영했다.
이 시스템을 범용 오픈소스 하네스로 추출하는 것이 이 프로젝트의 목적.

GitHub, 학술논문, 특허 전수 조사 결과 OODA 루프 + 자율 전략 수립 + 멀티에이전트 토론 + 자동 PR + 리스크 기반 머지를 통합한 시스템은 세계 최초.

## 결정 사항

| 항목 | 결정 |
|------|------|
| 이름 | ooda-harness |
| 플랫폼 | Claude Code 전용 |
| 언어 | 영어 우선, 출력은 locale 설정 |
| 설치 | git clone → /ooda-setup wizard |
| MVP | 코어 엔진(evolve) + 기본 5개 스킬 + wizard 3개 |
| 라이선스 | MIT |
| 타겟 유저 | Solo indie hacker, side project, 신규 서비스 |

## 레퍼런스 구현

원본: `/Users/mataeil/myproject/thehackathon-dev/fwd/agent/`

핵심 파일:
- `skills/meta/evolve/SKILL.md` — OODA 오케스트레이터 (700줄, 범용화 대상)
- `contracts/schema.md` — 스킬 인터페이스 계약
- `safety/autonomous-mode.md` — 안전 정책
- `state/evolve/` — 상태 파일 구조

evolve에서 하드코딩된 fwd.page 참조 6곳 (반드시 config로 교체):
1. 도메인 목록 (Step 1-A)
2. 가중치 테이블 (Step 3-B)
3. 목표 기여 매트릭스 (Step 3-D)
4. 스킬 라우팅 테이블 (Step 4-A)
5. 긴급 신호 테이블 (Step 3-C)
6. 브랜치-도메인 매핑 (Step 2-B)

## 7-Agent 리뷰 핵심 (1차 3명 + 2차 4명)

### 보안 전문가 (P0)
- agent 자기 수정 자동 머지 방지 → safety/meta/contracts는 Level 3 필수
- git add -A → 명시적 스테이징 (시크릿 유출 방지)
- Level 1 자동 머지 후 헬스체크 → 실패 시 자동 revert + HALT
- skill_allowlist 강제
- PR 크기 제한 (max_files 20, max_lines 500)

### 기술 아키텍트
- config.json 풀 스키마 정의 (domains, weights, chains, safety 등)
- Crash recovery: cycle_in_progress.json WAL
- State 버전관리: schema_version 모든 JSON
- 동시실행 Lock
- Score 동점 규칙

### DX 전문가
- Wizard 3단계 (자동감지 → 도메인 확인 → 완료)
- /ooda status 대시보드
- /evolve --dry-run
- 첫 사이클 관찰 전용
- Progressive complexity Level 0→3
- Graceful degradation (GitHub/테스트/CI 없어도 동작)
- CONCEPTS.md 용어 정리

### 제품 전략가
- 타겟: Solo indie hacker
- Elevator pitch: "Autonomous brain for your codebase"
- 런칭: HN → Reddit → Dev.to → Disquiet → PH (7일)
- Social proof: fwd.page 14사이클 실데이터

### 자가발전 전문가
- 3-tier 메모리: Working(20) → Episodes(52주) → Principles(영구)
- 도메인 자동 제안 (skill-gap 클러스터링)
- Contrarian check (10사이클마다 반론 의무)
- Prediction tracking (예측 → 검증 → 확신도 교정)
- Action-queue decay (14일+ 방치 → confidence -0.05)

### 초보 사용자 시뮬레이터
- evolve 라우팅 테이블 config 기반으로 (하드코딩 제거)
- 스킬 등록 가이드: config + symlink + contracts 3단계
- 최소 커스텀 스킬 예시 30줄
- Python/Flask 프로젝트로 검증 필수

### 오픈소스 커뮤니티 전문가
- CONTRIBUTING.md (Skills / Docs / Core 3-tier)
- SECURITY.md
- .github/ (issue templates, PR template)
- "good first issue" 15개 사전 생성
- asciinema 터미널 GIF
- Social preview image (1280x640)

## 구현 순서

| Phase | 작업 | 시간 |
|-------|------|------|
| 1 | 프로젝트 초기화 (README, CONCEPTS.md, LICENSE, .gitignore, CONTRIBUTING, SECURITY) | 1h |
| 2 | 코어 엔진 (evolve 범용화, config schema, contracts, safety, state templates) | 3h |
| 3 | 기본 스킬 5개 (영어, config 기반, graceful degradation) | 3h |
| 4 | wizard 스킬 3개 (/ooda-setup, /ooda-config, /ooda-status) | 2h |
| 5 | 예시 + 문서 (examples/fwd-page, SKILL_TEMPLATE, domain-examples) | 1h |
| 6 | .claude/ 심링크 + GitHub push | 30m |

## 프로젝트 구조

```
ooda-harness/
├── README.md
├── CLAUDE.md
├── CONCEPTS.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE (MIT)
├── .gitignore
├── config.example.json
├── agent/
│   ├── skills/
│   │   ├── meta/evolve/SKILL.md
│   │   ├── observe/scan-health/SKILL.md
│   │   ├── detect/check-tests/SKILL.md
│   │   ├── strategize/plan-backlog/SKILL.md
│   │   ├── execute/run-deploy/SKILL.md
│   │   └── support/dev-cycle/SKILL.md
│   ├── contracts/schema.md
│   ├── safety/autonomous-mode.md
│   └── state/
│       ├── evolve/ (blank templates)
│       └── external/
├── .claude/skills/
│   ├── ooda-setup/SKILL.md
│   ├── ooda-config/SKILL.md
│   ├── ooda-status/SKILL.md
│   └── (symlinks to agent/skills/)
├── templates/
│   └── SKILL_TEMPLATE.md
└── examples/
    ├── fwd-page/
    └── minimal-skill/
```
