# OODA-loop — OODA 자율운영 에이전트 하네스 오픈소스

## Context

fwd.page에서 만든 OODA 자율운영 시스템을 범용 오픈소스 하네스로 추출.
"AI가 전략을 세우고, 코드를 만들고, 배포하는" 시스템을 누구나 자기 프로젝트에 적용.

## 결정 사항

- 이름: **OODA-loop**
- 플랫폼: Claude Code 전용
- 언어: **영어 우선** (출력 언어는 locale 설정)
- 설치: git clone → /ooda-setup wizard
- MVP: 코어 엔진 + 기본 5개 스킬
- 경로: `/Users/mataeil/myproject/OODA-loop`

## 7-Agent 리뷰 반영사항 (1차 3명 + 2차 4명)

| 리뷰어 | 핵심 지적 | 반영 |
|--------|----------|------|
| 전략가 | 타겟 페르소나 명시 | Solo indie hacker / side project |
| 전략가 | Dry-run 모드 | `/evolve --dry-run` 추가 |
| 전략가 | 외부 시그널 패턴 | `agent/state/external/` 디렉토리 |
| 아키텍트 | config.json 풀 스키마 | domains, weights, skills, chains 포함 |
| 아키텍트 | Crash recovery | `cycle_in_progress.json` WAL |
| 아키텍트 | Secret 관리 | 환경변수 참조 + `.gitignore` |
| 아키텍트 | State 버전관리 | `schema_version: "1.0.0"` |
| 아키텍트 | 동시실행 Lock | `.lock` 파일 |
| DX | Wizard 3단계로 축소 | 자동감지 → 도메인 확인 → 완료 |
| DX | `/ooda status` 명령 | 전체 상태 한눈에 |
| DX | 첫 사이클 관찰 전용 | observe-only 모드 |
| DX | Progressive complexity | Level 0→3 단계 |
| DX | CONCEPTS.md + 용어집 | 필수 문서 |
| DX | Graceful degradation | 없는 기능은 비활성화 |

---

## 프로젝트 구조

```
OODA-loop/
├── README.md                              # English, showcase-quality
├── CLAUDE.md                              # Claude Code integration guide
├── CONCEPTS.md                            # Glossary + architecture (NEW)
├── LICENSE                                # MIT
├── .gitignore                             # config.json 등 secret 제외
│
├── agent/
│   ├── skills/
│   │   ├── meta/
│   │   │   └── evolve/SKILL.md            # OODA orchestrator (generic)
│   │   ├── observe/
│   │   │   └── scan-health/SKILL.md       # Service health monitoring
│   │   ├── detect/
│   │   │   └── check-tests/SKILL.md       # Test coverage
│   │   ├── strategize/
│   │   │   └── plan-backlog/SKILL.md      # GitHub Issues RICE scoring
│   │   ├── execute/
│   │   │   └── run-deploy/SKILL.md        # Deployment (workflow_dispatch)
│   │   └── support/
│   │       └── dev-cycle/SKILL.md         # Full cycle orchestration
│   │
│   ├── contracts/
│   │   └── schema.md                      # Skill interface spec + template
│   │
│   ├── safety/
│   │   └── autonomous-mode.md             # Safety policy
│   │
│   └── state/
│       ├── evolve/
│       │   ├── state.json                 # {schema_version, cycle_count, ...}
│       │   ├── confidence.json
│       │   ├── goals.json
│       │   ├── skill_gaps.json
│       │   ├── memos.json
│       │   ├── action_queue.json
│       │   ├── CHANGELOG.md
│       │   └── metrics.json               # Long-term counters (NEW)
│       └── external/                      # External signal drop zone (NEW)
│
├── .claude/
│   └── skills/
│       ├── evolve -> ../../agent/skills/meta/evolve
│       ├── ooda-setup/SKILL.md            # Setup wizard (3-step)
│       ├── ooda-config/SKILL.md           # Config CLI commands
│       ├── ooda-status/SKILL.md           # Status dashboard (NEW)
│       ├── scan-health -> ...
│       ├── check-tests -> ...
│       ├── plan-backlog -> ...
│       ├── run-deploy -> ...
│       └── dev-cycle -> ...
│
├── config.example.json                    # Full schema example (secrets blank)
├── templates/
│   ├── SKILL_TEMPLATE.md                  # Custom skill authoring guide
│   └── domain-examples.yaml              # Example domain configs
│
└── examples/
    └── fwd-page/                         # Reference implementation
```

---

## 핵심 신규 요소 (리뷰 반영)

### 1. config.example.json (풀 스키마)

```json
{
  "schema_version": "1.0.0",
  "project": {
    "name": "my-app",
    "locale": "en",
    "timezone": "UTC"
  },
  "domains": {
    "service_health": {
      "weight": 2.0,
      "state_file": "agent/state/health/state.json",
      "primary_skill": "/scan-health",
      "chain": [],
      "fallback": true
    }
  },
  "implementation": {
    "enabled": true,
    "weight": 1.5,
    "primary_skill": "/plan-change",
    "observe_loop_escape_bonus": 5.0
  },
  "safety": {
    "halt_file": "agent/safety/HALT",
    "confidence_threshold": 0.6,
    "min_cycle_interval_minutes": 30,
    "max_prs_per_cycle": 1,
    "first_cycle_observe_only": true
  },
  "test_command": "npm test",
  "health_endpoints": [],
  "deploy_workflow": "deploy.yml",
  "notifications": {
    "telegram": {
      "enabled": false,
      "bot_token": "$OODA_TELEGRAM_BOT_TOKEN",
      "chat_id": "$OODA_TELEGRAM_CHAT_ID"
    }
  }
}
```

실제 config.json은 `.gitignore`에 포함. 환경변수로 secret 참조.

### 2. /ooda-setup (3단계 wizard)

```
[1/3] Scanning your project...
  Language: TypeScript (Next.js)
  Tests: jest (npm test)
  CI: GitHub Actions (deploy.yml)
  Endpoints: http://localhost:3000

[2/3] Recommended domains:
  ✓ service_health (weight 2.0)
  ✓ test_coverage (weight 0.5)
  ✓ backlog (weight 0.3)
  Add more? (or press Enter)
  >

[3/3] Setup complete!
  Created: agent/state/evolve/config.json
  Run /evolve to start (first cycle is observe-only)
```

### 3. /ooda status

```
╔═══════════════════════════════════════╗
║  OODA-loop status                  ║
╠═══════════════════════════════════════╣
║ Cycle: #14  Last: 2h ago  Next: 2h   ║
╠═══════════════════════════════════════╣
║ Domain          Score  Conf  Last     ║
║ health          8.27   0.9   2h       ║
║ strategy        6.42   0.9   4h       ║
║ tests           4.17   0.7   6h       ║
║ implementation  2.36   0.8   1h (PR)  ║
╠═══════════════════════════════════════╣
║ Actions: 4 pending, 1 proposed        ║
║ Next PR: og_overrides (RICE 95)       ║
║ Telegram: ✓ connected                 ║
╚═══════════════════════════════════════╝
```

### 4. Dry-run 모드

`/evolve --dry-run` → Step 0-3(Observe→Orient→Decide) 실행, Step 4(Act) 건너뜀.
스코어 테이블 출력 후 "Would execute: /scan-market" 표시만.

### 5. 첫 사이클 관찰 전용

`first_cycle_observe_only: true` (config 기본값)
첫 `/evolve` 실행 시 모든 도메인 관찰만, Act 안 함.
"First cycle complete. Here's what I found. Run /evolve again to take action."

### 6. Progressive Complexity

```
Level 0 — "Just watching" (1 domain)
  service_health만. 관찰만 반복. PR 없음.

Level 1 — "Watching + testing" (2 domains)
  + test_coverage. 테스트 커버리지 추적.

Level 2 — "Full observation" (3+ domains)
  + backlog, strategy, ux 등. 리포트 생성.

Level 3 — "Autonomous" (implementation 활성화)
  + implementation domain. Draft PR 자동 생성.
  사용자가 /ooda-config implementation enable 으로 활성화.
```

---

## 구현 순서

| Phase | 작업 | 시간 |
|-------|------|------|
| 1 | 프로젝트 초기화 (README, CLAUDE.md, CONCEPTS.md, LICENSE, .gitignore) | 1h |
| 2 | 코어 엔진 (evolve 범용화, config schema, contracts, safety, state templates) | 3h |
| 3 | 기본 스킬 5개 (영어, config 기반, graceful degradation) | 3h |
| 4 | wizard 스킬 3개 (/ooda-setup, /ooda-config, /ooda-status) | 2h |
| 5 | 예시 + 문서 (examples/fwd-page, SKILL_TEMPLATE, domain-examples) | 1h |
| 6 | .claude/ 심링크 + GitHub push | 30m |

총 **~10.5시간**

---

## 2차 리뷰 추가 반영사항

### 보안 (P0)
- `agent/safety/*`, `agent/skills/meta/*`, `agent/contracts/*` → Level 3 필수 (자기 수정 방지)
- `git add -A` → 명시적 파일 스테이징으로 교체 (시크릿 유출 방지)
- Level 1 자동 머지 후 2분 대기 → scan-health → 실패 시 자동 revert + HALT
- skill_allowlist: config에 등록된 스킬만 evolve가 호출 가능
- PR 크기 제한: max_files 20, max_lines 500 (초과 시 Level 3 강제)

### 자가발전
- 3-tier 메모리: episodes.json (52주) + principles.json (영구)
- 도메인 자동 제안: skill-gap 3개가 같은 미등록 도메인 참조 시 → domain-suggestions.json
- Contrarian check: 10사이클마다 지배 전략에 반론 1개 의무
- Cost tracking 하드게이트: 일일 한도 초과 시 사이클 중단

### 초보 사용자 대응
- evolve 라우팅 테이블 → config.json에서 읽기 (하드코딩 제거)
- 스킬 등록 가이드: config + symlink + contracts 3단계 명시
- 최소 커스텀 스킬 예시: `examples/minimal-skill/` (30줄)
- 다국어 스택 예시: Python(pytest), Go(go test), TypeScript(jest)

### 커뮤니티 인프라
- CONTRIBUTING.md (3-tier: Skills / Docs / Core)
- SECURITY.md (위협 모델 + 시크릿 가이드)
- .github/ (issue templates, PR template, Discussion categories)
- "good first issue" 15개 사전 생성
- 런칭 전략: HN → Reddit → Dev.to → Disquiet → PH (7일)

## 검증

1. **Python Flask 프로젝트**에 OODA-loop 복사 (Go가 아닌 다른 언어)
2. `/ooda-setup` → Python 감지 → pytest 설정 → config 생성 확인
3. `/evolve --dry-run` → 스코어 테이블 출력 확인
4. `/evolve` → 첫 사이클 관찰 전용 확인
5. `/evolve` 2회째 → scan-health 실행 (config 기반 엔드포인트)
6. `/ooda status` → 상태 대시보드 출력 확인
7. `/ooda-config domain add analytics` → 도메인 추가 확인
8. 커스텀 스킬 추가 → config 등록 → evolve가 인식하는지 확인
9. Level 1 변경 자동 머지 후 헬스체크 → 정상/실패 시나리오 모두 테스트
