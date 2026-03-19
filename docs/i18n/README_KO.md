<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Aim. Iterate. Arrive.</b></h2>

<p align="center">
  <i>Codex를 위한 자율 목표 기반 실험 엔진.</i>
</p>

<p align="center">
  <a href="https://developers.openai.com/codex/skills"><img src="https://img.shields.io/badge/Codex-Skill-blue?logo=openai&logoColor=white" alt="Codex Skill"></a>
  <a href="https://github.com/leo-lilinxiao/codex-autoresearch"><img src="https://img.shields.io/github/stars/leo-lilinxiao/codex-autoresearch?style=social" alt="GitHub Stars"></a>
  <a href="../../LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
</p>

<p align="center">
  <a href="../../README.md">English</a> ·
  <a href="README_ZH.md">🇨🇳 中文</a> ·
  <a href="README_JA.md">🇯🇵 日本語</a> ·
  <b>🇰🇷 한국어</b> ·
  <a href="README_FR.md">🇫🇷 Français</a> ·
  <a href="README_DE.md">🇩🇪 Deutsch</a> ·
  <a href="README_ES.md">🇪🇸 Español</a> ·
  <a href="README_PT.md">🇧🇷 Português</a> ·
  <a href="README_RU.md">🇷🇺 Русский</a>
</p>

<p align="center">
  <a href="#빠른-시작">빠른 시작</a> ·
  <a href="#무엇을-하는가">무엇을 하는가</a> ·
  <a href="#아키텍처">아키텍처</a> ·
  <a href="#모드">모드</a> ·
  <a href="#설정">설정</a> ·
  <a href="#크로스런-학습">학습</a> ·
  <a href="#병렬-실험">병렬</a> ·
  <a href="../GUIDE.md">운영 매뉴얼</a> ·
  <a href="../EXAMPLES.md">레시피 모음</a>
</p>

---

## 빠른 시작

**1. 설치:**

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

또는 Codex에서 skill installer 사용:
```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

**2. 프로젝트에서 Codex를 열고, 원하는 것을 말하세요:**

```text
$codex-autoresearch
TypeScript 코드의 모든 any 타입을 제거해줘
```

**3. Codex가 스캔하고, 확인한 후, 자율적으로 반복합니다:**

```
Codex: src/**/*.ts에서 47개의 `any`를 발견했습니다.

       확인 완료:
       - 목표: src/**/*.ts의 모든 any 타입 제거
       - 지표: any 출현 횟수(현재 47), 방향: 감소
       - 검증: grep 카운트 + tsc --noEmit 가드

       추가 확인 필요:
       - 전부 제거할 때까지 실행할까요, 아니면 N회 반복으로 제한할까요?

       "go"라고 답하면 시작합니다. 변경할 사항이 있으면 알려주세요.

사용자: go, 밤새 돌려줘.

Codex: 시작 -- 베이스라인: 47. 중단될 때까지 반복합니다.
```

개선은 누적되고, 실패는 롤백되며, 모든 것이 기록됩니다.

추가 설치 방법은 [INSTALL.md](../INSTALL.md) 참조. 전체 운영 매뉴얼은 [GUIDE.md](../GUIDE.md) 참조.

---

## 무엇을 하는가

코드베이스에서 "수정-검증-판단" 루프를 실행하는 Codex skill입니다. 각 반복에서 하나의 원자적 변경을 수행하고, 기계적 지표로 검증한 후, 결과를 유지하거나 폐기합니다. 진행 상황은 git에 누적되고, 실패는 자동으로 리버트됩니다. 모든 언어, 모든 프레임워크, 모든 측정 가능한 목표에 대응합니다.

[Karpathy의 autoresearch](https://github.com/karpathy/autoresearch) 원칙에서 영감을 받아, ML을 넘어 범용화했습니다.

### 왜 만들었는가

Karpathy의 autoresearch는 단순한 루프 -- 수정, 검증, 유지 또는 폐기, 반복 -- 가 하룻밤 만에 ML 훈련을 베이스라인에서 새로운 고점으로 끌어올릴 수 있음을 입증했습니다. codex-autoresearch는 그 루프를 소프트웨어 엔지니어링에서 숫자가 있는 모든 것에 범용화합니다. 테스트 커버리지, 타입 오류, 성능 레이턴시, lint 경고 -- 지표가 있으면 자율적으로 반복할 수 있습니다.

---

## 아키텍처

```
              +---------------------+
              |  Environment Probe  |  <-- Phase 0: detect CPU/GPU/RAM/toolchains
              +---------+-----------+
                        |
              +---------v-----------+
              |  Session Resume?    |  <-- check for prior run artifacts
              +---------+-----------+
                        |
              +---------v-----------+
              |   Read Context      |  <-- read scope + lessons file
              +---------+-----------+
                        |
              +---------v-----------+
              | Establish Baseline  |  <-- iteration #0
              +---------+-----------+
                        |
         +--------------v--------------+
         |                             |
         |  +----------------------+   |
         |  | Choose Hypothesis    |   |  <-- consult lessons + perspectives
         |  | (or N for parallel)  |   |      filter by environment
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | Make ONE Change      |   |
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | git commit           |   |
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | Run Verify + Guard   |   |
         |  +---------+------------+   |
         |            |                |
         |        improved?            |
         |       /         \           |
         |     yes          no         |
         |     /              \        |
         |  +-v------+   +----v-----+ |
         |  |  KEEP  |   | REVERT   | |
         |  |+lesson |   +----+-----+ |
         |  +--+-----+        |       |
         |      \            /         |
         |   +--v----------v---+      |
         |   |   Log Result    |      |
         |   +--------+--------+      |
         |            |               |
         |   +--------v--------+      |
         |   |  Health Check   |      |  <-- disk, git, verify health
         |   +--------+--------+      |
         |            |               |
         |     3+ discards?           |
         |    /             \         |
         |  no              yes       |
         |  |          +----v-----+   |
         |  |          | REFINE / |   |  <-- pivot-protocol escalation
         |  |          | PIVOT    |   |
         |  |          +----+-----+   |
         |  |               |         |
         +--+------+--------+         |
         |         (repeat)           |
         +----------------------------+
```

루프는 중단될 때까지(무제한) 또는 정확히 N회 반복(`Iterations: N`으로 상한 설정)까지 실행됩니다.

**의사 코드:**

```
PHASE 0: 환경을 탐색하고, 세션 재개 가능 여부를 확인
PHASE 1: 컨텍스트 + 교훈 파일을 읽기

LOOP (영구 or N회):
  1. 현재 상태 + git 이력 + 결과 로그 + 교훈 확인
  2. 가설 하나 선택 (퍼스펙티브를 적용하고, 환경으로 필터링)
     -- 병렬 모드 활성 시 N개의 가설을 선택
  3. 원자적 변경 하나 수행
  4. git commit (검증 전에)
  5. 기계적 검증 + guard 실행
  6. 개선 -> 유지 (교훈 추출). 악화 -> git reset. 크래시 -> 수정 또는 스킵.
  7. 결과 기록
  8. 상태 점검 (디스크, git, 검증 건전성)
  9. 3회 이상 연속 폐기 -> REFINE, 5회 이상 -> PIVOT, 2회 PIVOT -> Web 검색
  10. 반복. 절대 멈추지 않는다. 절대 질문하지 않는다.
```

---

## 모드

7가지 모드, 통일된 호출 패턴: `$codex-autoresearch` 뒤에 자연어 한 문장. Codex가 자동으로 모드를 감지하고 대화를 통해 설정을 완성합니다.

| 모드 | 사용 시기 | 정지 조건 |
|------|-----------|-----------|
| `loop` | 측정 가능한 최적화 목표가 있을 때 | 중단 또는 N회 반복 |
| `plan` | 목표는 있지만 설정이 불분명할 때 | 설정 블록이 생성됨 |
| `debug` | 증거 기반의 근본 원인 분석이 필요할 때 | 모든 가설 테스트 완료 또는 N회 반복 |
| `fix` | 고장난 것을 수리해야 할 때 | 오류 수가 0이 됨 |
| `security` | 구조화된 취약점 감사가 필요할 때 | 모든 공격 면 커버 또는 N회 반복 |
| `ship` | 게이트 기반 릴리스 검증이 필요할 때 | 모든 체크리스트 항목 통과 |
| `exec` | CI/CD 파이프라인, 사람이 없을 때 | N회 반복(항상 상한 있음), JSON 출력 |

**빠른 선택:**

```
"X를 개선하고 싶다"              -->  loop (지표가 불분명하면 plan)
"뭔가 고장났다"                  -->  fix  (원인이 불분명하면 debug)
"이 코드는 안전한가?"            -->  security
"릴리스 준비"                    -->  ship
codex exec --skill ...           -->  exec (CI/CD, 위저드 없음)
```

---

## 설정

### 필수 필드 (loop 모드)

| 필드 | 타입 | 예시 |
|------|------|------|
| `Goal` | 달성 목표 | `Reduce type errors to zero` |
| `Scope` | 수정 가능한 파일 glob | `src/**/*.ts` |
| `Metric` | 추적할 수치 | `type error count` |
| `Direction` | `higher` 또는 `lower` | `lower` |
| `Verify` | 지표를 출력하는 명령어 | `tsc --noEmit 2>&1 \| wc -l` |

### 선택 필드

| 필드 | 기본값 | 용도 |
|------|--------|------|
| `Guard` | 없음 | 리그레션 방지 안전 명령어 |
| `Iterations` | 무제한 | N회 반복으로 상한 설정 |
| `Run tag` | 자동 | 이번 실행의 라벨 |
| `Stop condition` | 없음 | 사용자 정의 조기 정지 규칙 |

필수 필드가 누락된 경우, 인터랙티브 위저드가 저장소를 스캔하고 시작 전에 반드시 확인을 받습니다(최대 5라운드). 필드 이름을 알 필요는 없습니다.

### 이중 게이트 검증

두 개의 명령어가 각각 다른 역할을 수행합니다:

- **Verify** = "목표 지표가 개선되었는가?" (진행도 측정)
- **Guard** = "다른 것이 망가지지 않았는가?" (리그레션 방지)

```text
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'   # 커버리지가 올라갔는가?
Guard: npx tsc --noEmit                                                              # 타입이 통과하는가?
```

Verify가 통과하지만 Guard가 실패하면, 변경이 재조정됩니다(최대 2회). 이후 롤백됩니다. Guard 대상 파일은 수정되지 않습니다.

---

## 빠른 판단 가이드

| 원하는 것 | 모드 | 주요 설정 |
|-----------|------|-----------|
| 밤새 지표를 한 방향으로 밀어붙이기 | `loop` | Goal + Metric + Verify |
| 어떤 지표를 추적해야 할지 파악 | `plan` | Goal만 |
| 뭔가 고장난 원인 찾기 | `debug` | Scope + Symptom |
| 실패하는 테스트/타입/lint 통과시키기 | `fix` | Target 명령어 |
| 코드의 취약점 감사 | `security` | Scope + Focus |
| 자신 있게 릴리스 | `ship` | "ship it" 또는 "dry run first"라고 전달 |
| CI/CD에서 대화 없이 실행 | `exec` | 모든 필드 사전 지정 + Iterations |

---

## 모드 상세

### loop

기본 모드. 측정 가능한 목표를 향해 반복합니다.

```
사용자: TypeScript 코드의 모든 any 타입을 제거해줘

Codex: src/**/*.ts에서 47개의 `any`를 발견했습니다.

       확인 완료:
       - 목표: 모든 any 타입 제거
       - 지표: any 횟수(현재 47), 방향: 감소
       - 검증: grep 카운트, 가드: tsc --noEmit

       추가 확인 필요:
       - 0이 될 때까지 실행할까요, 아니면 N회 반복으로 제한할까요?

       "go"라고 답하면 시작합니다.

사용자: go, 밤새 돌려줘.
```

### plan

모호한 목표를 검증된 루프 설정으로 변환합니다.

```
사용자: API를 빠르게 만들고 싶은데 어디서 시작해야 할지 모르겠어

Codex: 저장소를 스캔했습니다. API 레이어는 src/api/에 있으며 Express + Prisma를 사용합니다.

       추가 확인 필요:
       - p95 레이턴시, 처리량, 콜드 스타트 중 무엇을 중시하나요?
       - 전체 API를 벤치마크할까요, 특정 엔드포인트만 할까요?

       우선순위를 알려주세요.

사용자: p95 레이턴시, /search 엔드포인트가 가장 느려.
```

### debug

증거 기반 버그 추적. 각 반복에서 하나의 반증 가능한 가설을 테스트합니다.

```
사용자: API가 고부하 시 무작위로 503을 반환하는데, 이유를 모르겠어

Codex: src/db/pool.ts에 커넥션 풀링, src/middleware/에 레이트 리미팅,
       그리고 에러 바운더리가 없는 3개의 비동기 핸들러가 있습니다.

       확인 완료:
       - 증상: 동시 부하에서 간헐적 503 발생
       - 범위: src/api/, src/db/, src/middleware/

       추가 확인 필요:
       - 언제부터 발생했나요? 특정 변경 이후인가요, 아니면 이전부터인가요?
       - 원인을 찾으면 수정도 할까요?

       컨텍스트를 알려주세요.

사용자: 지난주 커넥션 풀 리팩토링 후 시작됐어. 먼저 원인을 찾아줘.
```

### fix

오류 수가 0이 될 때까지 반복적으로 수리합니다.

```
사용자: 리팩토링 후 pytest가 12개 테스트에서 실패해

Codex: tests/에서 12개의 실패를 확인했습니다.

       확인 완료:
       - 목표: 모든 pytest 테스트 통과
       - 현재: 12개 실패

       추가 확인 필요:
       - ruff로 가드해서 lint 문제를 방지할까요?
       - 전부 수정할까요, 특정 모듈에 집중할까요?

       "go"라고 답하면 시작합니다.

사용자: 전부 수정, ruff 가드 사용. Go.
```

### security

읽기 전용 STRIDE + OWASP + 레드팀 감사. 모든 발견에 코드 증거가 필요합니다.

```
사용자: API에 인젝션 취약점이 있는지 확인해줘

Codex: 확인 완료:
       - 범위: src/api/ 및 src/middleware/ (14개 파일)
       - 중점: SQL 인젝션, XSS, 입력 검증

       추가 확인 필요:
       - 보고서만 작성할까요, 심각한 문제도 수정할까요?
       - 인증/접근 제어도 포함할까요?

       선호 사항을 알려주세요.

사용자: 먼저 보고서, 인증도 확인해줘.
```

### ship

게이트 기반 릴리스 검증. 무엇을 릴리스하는지(PR, 배포, 릴리스) 자동 감지합니다.

```
사용자: 릴리스해줘

Codex: 감지: main으로의 PR, 3개 커밋.

       확인 완료:
       - 유형: 코드 PR
       - 대상: main 브랜치

       추가 확인 필요:
       - 먼저 드라이런을 할까요, 바로 진행할까요?
       - 릴리스 후 모니터링은? (5분 / 15분 / 스킵)

       선호 사항을 알려주세요.

사용자: 먼저 드라이런.
```

각 모드의 상세 사용법과 고급 옵션은 [GUIDE.md](../GUIDE.md) 참조.

---

## 모드 조합

모드는 순차적으로 조합할 수 있습니다:

```
plan  -->  loop              # 먼저 설정을 생성하고, 그다음 실행
debug -->  fix               # 먼저 버그를 찾고, 그다음 수리
security + fix               # 감사와 수정을 한 번에 수행
```

---

## 크로스런 학습

모든 실행에서 구조화된 교훈이 추출됩니다 -- 무엇이 효과적이었는지, 무엇이 실패했는지, 그리고 왜인지. 교훈은 `autoresearch-lessons.md`(결과 로그와 마찬가지로 커밋되지 않음)에 저장되며, 향후 실행 시작 시 참조되어 입증된 전략으로 가설 생성을 편향시키고 알려진 막다른 길을 회피합니다.

- 유지된 각 반복 후 긍정적 교훈 기록
- 각 PIVOT 결정 후 전략적 교훈 기록
- 실행 완료 시 요약 교훈 기록
- 용량: 최대 50개 항목, 오래된 항목은 시간 감쇠로 요약

자세한 내용은 `references/lessons-protocol.md` 참조.

---

## 스마트 정체 회복

실패 후 맹목적으로 재시도하는 대신, 루프는 단계적 에스컬레이션 시스템을 사용합니다:

| 트리거 | 액션 |
|--------|------|
| 3회 연속 폐기 | **REFINE** -- 현재 전략 내에서 조정 |
| 5회 연속 폐기 | **PIVOT** -- 전략을 포기하고, 근본적으로 다른 접근 방식을 시도 |
| 개선 없는 PIVOT 2회 | **Web 검색** -- 외부 해결책을 탐색 |
| 개선 없는 PIVOT 3회 | **소프트 블로커** -- 경고를 발행하고 더 대담한 변경으로 계속 |

1회의 성공적인 유지로 모든 카운터가 리셋됩니다. 자세한 내용은 `references/pivot-protocol.md` 참조.

---

## 병렬 실험

격리된 git worktree 내의 서브에이전트 워커를 사용하여 여러 가설을 동시에 테스트합니다:

```
오케스트레이터 (메인 에이전트)
  +-- 워커 A (worktree-a) -> 가설 1
  +-- 워커 B (worktree-b) -> 가설 2
  +-- 워커 C (worktree-c) -> 가설 3
```

오케스트레이터가 최고의 결과를 선택하고 머지한 후 나머지를 폐기합니다. 위저드 중에 병렬 실험에 "예"라고 답하면 활성화됩니다. worktree가 지원되지 않으면 직렬 실행으로 폴백합니다.

자세한 내용은 `references/parallel-experiments-protocol.md` 참조.

---

## 세션 재개

Codex가 이전에 중단된 실행(결과 로그, 교훈 파일, 실험 커밋)을 감지하면, 처음부터 다시 시작하는 대신 마지막 일관 상태에서 재개할 수 있습니다:

- **일관 상태:** 즉시 재개, 위저드 스킵
- **부분 일관:** 미니 위저드(1라운드)로 재확인
- **비일관 또는 다른 목표:** 새로 시작(기존 로그는 이름 변경)

자세한 내용은 `references/session-resume-protocol.md` 참조.

---

## CI/CD 모드 (exec)

자동화 파이프라인을 위한 비대화형 모드. 모든 설정은 사전에 제공됩니다 -- 위저드 없음, 항상 상한 있음, JSON 출력.

```yaml
# GitHub Actions 예시
- name: Autoresearch optimization
  run: codex exec --skill codex-autoresearch
         --goal "Reduce type errors" --scope "src/**/*.ts"
         --metric "type error count" --direction lower
         --verify "tsc --noEmit 2>&1 | grep -c error"
         --iterations 20
```

종료 코드: 0 = 개선됨, 1 = 개선 없음, 2 = 하드 블로커.

자세한 내용은 `references/exec-workflow.md` 참조.

---

## 결과 로그

각 반복은 TSV 파일(`research-results.tsv`)에 기록됩니다:

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

5회 반복마다 진행 요약이 출력됩니다. 유한 실행 종료 시 베이스라인에서 최고값까지의 요약이 출력됩니다.

---

## 보안 모델

| 우려 사항 | 처리 방식 |
|-----------|-----------|
| 더티 워크트리 | 루프가 시작을 거부. `plan` 모드 또는 클린 브랜치를 제안 |
| 실패한 변경 | `git reset --hard HEAD~1`로 이력을 깨끗하게 유지. 결과 로그가 감사 추적 |
| Guard 실패 | 최대 2회 재조정 후 롤백 |
| 구문 오류 | 즉시 수정. 반복으로 카운트하지 않음 |
| 런타임 크래시 | 최대 3회 수정 시도 후 스킵 |
| 리소스 고갈 | 리버트 후 더 작은 변형을 시도 |
| 프로세스 행 | 타임아웃 후 종료, 리버트 |
| 정체 (3회 이상 연속 폐기) | REFINE으로 전략 조정, 5회 이상은 PIVOT으로 새 접근 방식 시도, 필요시 Web 검색으로 에스컬레이트 |
| 루프 중 불확실성 | 모범 사례를 자율적으로 적용. 사용자에게 질문하지 않음 |
| 외부 부작용 | `ship` 모드는 프리런치 위저드에서 명시적 확인을 요구 |
| 환경 제약 | 시작 시 프로빙하여 실행 불가능한 가설을 자동으로 필터링 |
| 중단된 세션 | 다음 호출 시 마지막 일관 상태에서 재개 |

---

## 프로젝트 구조

```
codex-autoresearch/
  SKILL.md                          # skill 진입점 (Codex가 로드)
  README.md                         # 영문 문서
  CONTRIBUTING.md                   # 기여 가이드
  LICENSE                           # MIT
  agents/
    openai.yaml                     # Codex UI 메타데이터
  image/
    banner.png                      # 프로젝트 배너
  docs/
    INSTALL.md                      # 설치 가이드
    GUIDE.md                        # 운영 매뉴얼
    EXAMPLES.md                     # 분야별 레시피 모음
    i18n/
      README_ZH.md                  # 중국어
      README_JA.md                  # 일본어
      README_KO.md                  # 본 파일
      README_FR.md                  # 프랑스어
      README_DE.md                  # 독일어
      README_ES.md                  # 스페인어
      README_PT.md                  # 포르투갈어
      README_RU.md                  # 러시아어
  scripts/
    validate_skill_structure.sh     # 구조 검증 스크립트
  references/
    core-principles.md              # 범용 원칙
    autonomous-loop-protocol.md     # 루프 프로토콜 사양
    plan-workflow.md                # plan 모드 사양
    debug-workflow.md               # debug 모드 사양
    fix-workflow.md                 # fix 모드 사양
    security-workflow.md            # security 모드 사양
    ship-workflow.md                # ship 모드 사양
    exec-workflow.md                # CI/CD 비대화형 모드 사양
    interaction-wizard.md           # 인터랙티브 설정 계약
    structured-output-spec.md       # 출력 포맷 사양
    modes.md                        # 모드 인덱스
    results-logging.md              # TSV 포맷 사양
    lessons-protocol.md             # 크로스런 학습
    pivot-protocol.md               # 스마트 정체 회복 (PIVOT/REFINE)
    web-search-protocol.md          # 정체 시 Web 검색
    environment-awareness.md        # 하드웨어/리소스 감지
    parallel-experiments-protocol.md # 서브에이전트 병렬 테스트
    session-resume-protocol.md      # 중단된 실행 재개
    health-check-protocol.md        # 셀프 모니터링
    hypothesis-perspectives.md      # 멀티렌즈 가설 추론
```

---

## FAQ

**지표는 어떻게 고르나요?** `Mode: plan`을 사용하세요. 코드베이스를 분석하고 제안해줍니다.

**어떤 언어를 지원하나요?** 전부입니다. 프로토콜은 언어에 의존하지 않습니다. 검증 명령어만 도메인에 특화됩니다.

**어떻게 멈추나요?** Codex를 중단하거나 `Iterations: N`을 설정하세요. 커밋이 검증 전에 이루어지므로 git 상태는 항상 일관됩니다.

**security 모드가 코드를 수정하나요?** 아닙니다. 읽기 전용 분석입니다. 설정 시 Codex에 "심각한 문제도 수정해줘"라고 말하면 수정을 선택할 수 있습니다.

**몇 번 반복하나요?** 작업에 따라 다릅니다. 타겟 수정은 5회, 탐색적인 것은 10-20회, 야간 실행은 무제한입니다.

**실행 간에 학습하나요?** 예. 각 실행 후 교훈이 추출되고, 다음 실행 시작 시 참조됩니다. 교훈 파일은 세션 간에 유지됩니다.

**중단 후 재개할 수 있나요?** 예. 다음 호출 시 이전 실행을 감지하고 마지막 일관 상태에서 재개합니다.

**Web 검색이 가능한가요?** 예. 여러 번의 전략 피봇 후 정체되었을 때 사용됩니다. Web 검색 결과는 가설로 취급되어 기계적으로 검증됩니다.

**CI에서 사용하려면?** `Mode: exec` 또는 `codex exec`를 사용하세요. 모든 설정은 사전에 제공되며, 출력은 JSON 형식이고, 종료 코드가 성공/실패를 나타냅니다.

**여러 아이디어를 동시에 테스트할 수 있나요?** 예. 설정 중에 병렬 실험을 활성화하세요. git worktree를 사용하여 최대 3개의 가설을 동시에 테스트합니다.

---

## 감사의 말

이 프로젝트는 [Karpathy의 autoresearch](https://github.com/karpathy/autoresearch) 아이디어를 기반으로 구축되었습니다. Codex skills 플랫폼은 [OpenAI](https://openai.com)에서 제공합니다.

---

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

---

## 라이선스

MIT -- [LICENSE](../../LICENSE) 참조.
