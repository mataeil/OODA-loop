# CLAUDE.md — ooda-harness

## 프로젝트 개요

ooda-harness는 Boyd의 OODA 루프 기반 **자율운영 AI 에이전트 하네스** 오픈소스 프로젝트.
fwd.page(URL 단축 서비스)에서 14사이클 실전 운영한 시스템을 범용 하네스로 추출한다.

**핵심 가치**: "코딩하는 AI"가 아니라 **"전략을 짜는 AI"**. AI가 스스로 무엇을 만들지 결정하고, 코드를 만들고, 배포한다. 사람은 PR을 리뷰할 뿐.

**세계 최초**: OODA 루프 + 자율 전략 수립 + 멀티에이전트 토론 + 자동 PR 생성 + 리스크 기반 자동 머지/배포를 통합한 하네스는 기존에 없음 (GitHub, 학술논문, 특허 전수 조사 완료).

## 결정 사항

- **이름**: ooda-harness
- **플랫폼**: Claude Code 전용
- **언어**: 영어 우선 (출력 언어는 locale 설정)
- **설치**: git clone → /ooda-setup wizard
- **MVP**: 코어 엔진(evolve) + 기본 5개 스킬 + wizard 3개
- **라이선스**: MIT
- **타겟 유저**: Solo indie hacker, side project, 신규 서비스

## 레퍼런스 구현 (fwd.page)

원본 코드베이스: `/Users/mataeil/myproject/thehackathon-dev/fwd/agent/`
- `skills/meta/evolve/SKILL.md` — OODA 오케스트레이터 (범용화 대상)
- `skills/observe/scan-health/SKILL.md` — 헬스 모니터링 (범용화 대상)
- `contracts/schema.md` — 스킬 인터페이스 계약
- `safety/autonomous-mode.md` — 안전 정책
- `state/evolve/` — 상태 파일 구조 (state.json, confidence.json, goals.json 등)

## 구현 계획

상세 플랜: `/Users/mataeil/.claude/plans/toasty-launching-tide.md`

### 프로젝트 구조

```
ooda-harness/
├── README.md                              # English, showcase-quality
├── CLAUDE.md                              # 이 파일
├── CONCEPTS.md                            # Glossary + architecture
├── CONTRIBUTING.md                        # 3-tier contribution guide
├── SECURITY.md                            # Threat model + secret guide
├── LICENSE                                # MIT
├── .gitignore                             # config.json 등 secret 제외
├── config.example.json                    # Full schema (secrets blank)
│
├── agent/
│   ├── skills/
│   │   ├── meta/evolve/SKILL.md           # OODA orchestrator (generic)
│   │   ├── observe/scan-health/SKILL.md   # Service health monitoring
│   │   ├── detect/check-tests/SKILL.md    # Test coverage
│   │   ├── strategize/plan-backlog/SKILL.md # GitHub Issues RICE
│   │   ├── execute/run-deploy/SKILL.md    # Deployment
│   │   └── support/dev-cycle/SKILL.md     # Full cycle orchestration
│   ├── contracts/schema.md                # Skill interface spec
│   ├── safety/autonomous-mode.md          # Safety policy
│   └── state/
│       ├── evolve/                        # State templates (blank)
│       └── external/                      # External signal drop zone
│
├── .claude/skills/                        # Symlinks + wizard skills
│   ├── ooda-setup/SKILL.md               # 3-step setup wizard
│   ├── ooda-config/SKILL.md              # Config CLI commands
│   └── ooda-status/SKILL.md              # Status dashboard
│
├── templates/
│   └── SKILL_TEMPLATE.md                 # Custom skill authoring guide
│
└── examples/
    ├── fwd-page/                         # Reference implementation
    └── minimal-skill/                    # 30-line example skill
```

### 구현 순서

| Phase | 작업 | 시간 |
|-------|------|------|
| 1 | 프로젝트 초기화 (README, CLAUDE.md, CONCEPTS.md, LICENSE, .gitignore, CONTRIBUTING, SECURITY) | 1h |
| 2 | 코어 엔진 (evolve 범용화, config schema, contracts, safety, state templates) | 3h |
| 3 | 기본 스킬 5개 (영어, config 기반, graceful degradation) | 3h |
| 4 | wizard 스킬 3개 (/ooda-setup, /ooda-config, /ooda-status) | 2h |
| 5 | 예시 + 문서 (examples/fwd-page, SKILL_TEMPLATE, domain-examples) | 1h |
| 6 | .claude/ 심링크 + GitHub push | 30m |

## 7-Agent 리뷰 핵심 요구사항

### 보안 (P0)
- `agent/safety/*`, `agent/skills/meta/*`, `agent/contracts/*` → Level 3 필수 (자기 수정 방지)
- `git add -A` 금지 → 명시적 파일 스테이징 (시크릿 유출 방지)
- Level 1 자동 머지 후 scan-health → 실패 시 자동 revert + HALT
- skill_allowlist: config에 등록된 스킬만 evolve가 호출
- Secret은 환경변수 참조 (`$OODA_TELEGRAM_BOT_TOKEN`), config.json은 .gitignore

### 코어 엔진 범용화
- evolve SKILL.md의 하드코딩 6곳 파라미터화: 도메인 목록, 가중치, 목표 기여 매트릭스, 스킬 라우팅, 긴급 신호, 브랜치 매핑 → 전부 config.json에서 읽기
- Crash recovery: `cycle_in_progress.json` WAL 패턴
- State 버전관리: `schema_version: "1.0.0"` 모든 JSON에
- 동시실행 Lock: `.lock` 파일

### DX (개발자 경험)
- /ooda-setup wizard: 3단계 (자동감지 → 도메인 확인 → 완료)
- /ooda-config: 설정 변경 CLI (`domain add`, `goal add`, `telegram setup`)
- /ooda status: 전체 상태 대시보드
- /evolve --dry-run: Act 없이 스코어링만
- 첫 사이클 관찰 전용 (first_cycle_observe_only)
- Progressive complexity: Level 0(관찰) → 3(자율실행)
- Graceful degradation: GitHub/테스트/CI 없어도 동작

### 자가발전
- 3-tier 메모리: Working(20) → Episodes(52주) → Principles(영구)
- 도메인 자동 제안: skill-gap 클러스터링 → domain-suggestions.json
- Contrarian check: 10사이클마다 지배 전략에 반론 의무
- Cost tracking 하드게이트

### 커뮤니티
- CONTRIBUTING.md (Skills / Docs / Core 3-tier)
- SECURITY.md (위협 모델 + 시크릿 가이드)
- .github/ (issue templates, PR template)
- 런칭 전략: HN → Reddit → Dev.to → Disquiet → PH

## 코드 규칙

- 모든 스킬 파일은 **영어**로 작성
- 기술 용어: domain, skill, cycle, confidence, chain, action-queue
- config.json에 시크릿 직접 저장 금지 — 환경변수 참조만
- fwd.page 하드코딩 절대 금지 — 모든 값은 config에서 읽기
- 스킬은 반드시 HALT 파일 체크로 시작
