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
  <a href="#작동-방식">작동 방식</a> ·
  <a href="#codex가-자동으로-파악하는-것">설정</a> ·
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
       - 실행 모드: foreground 와 background 중 무엇으로 할까요?
       - 전부 제거할 때까지 실행할까요, 아니면 N회 반복으로 제한할까요?

       실행 모드를 고른 뒤 "go"라고 답하면 시작합니다.
       변경할 사항이 있으면 알려주세요.

사용자: Background, go. 밤새 돌려줘.

Codex: background 실행을 시작합니다 -- 베이스라인: 47.
       detached runtime 이 이미 반복을 이어가고 있습니다.
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

아래 다이어그램은 먼저 대화형 시작 흐름을, 그다음 공유되는 루프 코어를 보여줍니다. 루프에 들어가기 전에 Codex는 환경을 점검하고, 재개 가능한 세션이 있는지 확인하고, 설정을 확정한 뒤, `foreground` 와 `background` 중 하나를 반드시 선택하게 합니다.

```
              +----------------------+
              |   환경 탐지          |  <-- CPU/GPU/RAM/툴체인 감지
              +----------+-----------+
                         |
              +----------v-----------+
              | 세션 재개?           |  <-- 이전 결과/상태 확인
              +----------+-----------+
                         |
              +----------v-----------+
              | 컨텍스트 읽기        |  <-- scope + 교훈 + repo 상태
              +----------+-----------+
                         |
              +----------v-----------+
              | wizard 확인          |  <-- 목표/지표/verify/guard
              | + 모드 선택          |      + foreground 또는 background
              +----------+-----------+
                         |
               +---------+---------+
               |                   |
     +---------v--------+  +-------v---------+
     | foreground 실행  |  | background 실행 |
     | 현재 세션        |  | manifest + ctl  |
     | runtime 파일 없음|  | detached runtime|
     +---------+--------+  +-------+---------+
               |                   |
               +---------+---------+
                         |
              +----------v-----------+
              | 공유 루프 코어       |
              | baseline -> change   |
              | -> verify/guard ->   |
              | keep/discard/log     |
              +----------+-----------+
                         |
              +----------v-----------+
              | supervisor 결과      |  <-- continue / stop / needs_human
              +----------------------+
```

Foreground 와 background 는 동일한 실험 프로토콜을 공유합니다. 차이는 루프가 어디에서 실행되느냐뿐입니다. foreground 는 현재 Codex 세션 안에서, background 는 detached runtime controller 에서 실행됩니다. 둘 다 중단될 때까지(무제한) 또는 정확히 N회 반복(`Iterations: N`으로 상한 설정)까지 동작합니다.

**의사 코드:**

```
PHASE 0: 환경을 탐색하고, 재개 가능한 세션이 있는지 확인
PHASE 1: 컨텍스트 + 교훈 파일 읽기
PHASE 2: 설정을 확인하고 foreground 또는 background 선택

IF foreground:
  현재 Codex 세션에서 루프 실행
ELSE background:
  autoresearch-launch.json 을 기록하고 detached runtime 시작

공유 루프 (영구 or N회):
  1. 현재 상태 + git 이력 + 결과 로그 + 교훈 확인
  2. 가설 하나 선택 (퍼스펙티브를 적용하고, 환경으로 필터링)
     -- 병렬 모드 활성 시 N개의 가설을 선택
  3. 원자적 변경 하나 수행
  4. git commit (검증 전에)
  5. 기계적 검증 + guard 실행
  6. 개선 -> 유지 (교훈 추출). 악화 -> 승인된 롤백 전략. 크래시 -> 수정 또는 스킵.
  7. 결과 기록
  8. 상태 점검 (디스크, git, 검증 건전성)
  9. 3회 이상 연속 폐기 -> REFINE, 5회 이상 -> PIVOT, 2회 PIVOT -> Web 검색
  10. 반복. 절대 멈추지 않는다. 절대 질문하지 않는다.
```

---

## 작동 방식

한 문장으로 말하세요. Codex가 나머지를 처리합니다.

리포지토리를 스캔하고, 계획을 제안하고, 확인을 받은 후, 자율적으로 반복합니다:

| 당신이 말하는 것 | 일어나는 일 |
|----------------|-----------|
| "테스트 커버리지를 올려줘" | 리포지토리 스캔, 지표 제안, 목표 달성 또는 중단까지 반복 |
| "실패하는 12개 테스트를 고쳐줘" | 실패 감지, 하나씩 수리하여 0이 될 때까지 |
| "왜 API가 503을 반환하는 거야?" | 반증 가능한 가설과 증거로 근본 원인 추적 |
| "이 코드는 안전한가?" | STRIDE + OWASP 감사 실행, 모든 발견에 코드 증거 첨부 |
| "릴리스해줘" | 준비 상태 검증, 체크리스트 생성, 게이트 기반 릴리스 |
| "최적화하고 싶은데 뭘 측정해야 할지 모르겠어" | 리포지토리 분석, 지표 제안, 바로 사용 가능한 설정 생성 |

뒤에서 Codex는 당신의 말을 7가지 전문 모드
(loop, plan, debug, fix, security, ship, exec) 중 하나에 매핑합니다.
모드를 선택할 필요 없이 -- 목표만 설명하면 됩니다.

---

## Codex가 자동으로 파악하는 것

Codex는 당신의 말과 리포지토리에서 모든 것을 추론합니다. 설정을 작성할 필요가 없습니다.

| 필요한 것 | 획득 방법 | 예시 |
|----------|----------|------|
| 목표 | 당신의 한 문장 | "모든 any 타입을 제거해줘" |
| 범위 | 리포지토리 구조 스캔 | src/**/*.ts 자동 발견 |
| 지표 | 목표 + 툴체인 기반 제안 | any 카운트 (현재: 47) |
| 방향 | "개선" / "감소" / "제거"에서 추론 | 감소 |
| 검증 명령어 | 리포지토리 툴과 매칭 | grep 카운트 + tsc --noEmit |
| 가드 (선택) | 리그레션 위험이 있으면 제안 | npm test |

시작 전에 Codex는 항상 발견한 내용을 보여주고 확인을 요청합니다.
최소 1라운드, 최대 5라운드의 확인이 있습니다. 그 다음 `foreground` 또는 `background` 를 고르고 "go"라고 말합니다. `foreground` 에서는 현재 세션에서 계속 반복하고, `background` 에서는 detached runtime 으로 넘긴 뒤 자리를 비울 수 있습니다.
정말 무인으로 돌리려면, Codex CLI의 승인 / 샌드박스 설정이 `git commit`이나 `git revert`에서 멈추지 않도록 미리 맞춰야 합니다. 일회성 또는 신뢰할 수 있는 저장소라면 Codex에 더 넓은 권한을 주는 것이 가장 간단합니다.

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
       - 실행 모드: foreground 와 background 중 무엇으로 할까요?
       - 0이 될 때까지 실행할까요, 아니면 N회 반복으로 제한할까요?

       실행 모드를 고른 뒤 "go"라고 답하면 시작합니다.

사용자: Background, go. 밤새 돌려줘.

Codex: background 실행을 시작합니다. 먼저 베이스라인을 만들고, 그다음 detached iteration 으로 넘어갑니다.
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
       - 실행 모드: foreground 와 background 중 무엇으로 할까요?
       - ruff로 가드해서 lint 문제를 방지할까요?
       - 전부 수정할까요, 특정 모듈에 집중할까요?

       실행 모드를 고른 뒤 "go"라고 답하면 시작합니다.

사용자: Foreground, go. 전부 수정하고 ruff 가드도 사용해.
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

`exec` 를 제외한 모든 반복 실행에서 구조화된 교훈이 추출됩니다 -- 무엇이 효과적이었는지, 무엇이 실패했는지, 그리고 왜인지. 교훈은 `autoresearch-lessons.md`(결과 로그와 마찬가지로 커밋되지 않음)에 저장되며, 향후 실행 시작 시 참조되어 입증된 전략으로 가설 생성을 편향시키고 알려진 막다른 길을 회피합니다. `exec` 모드는 기존 교훈을 읽을 수는 있지만 새로 만들거나 갱신하지는 않습니다.

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

Codex가 인터랙티브 모드에서 이전에 중단된 run 을 감지하면 처음부터 다시 시작하는 대신 마지막 일관된 상태에서 재개할 수 있습니다. 주요 복구 소스는 `autoresearch-state.json`으로, 각 반복마다 원자적으로 업데이트되는 컴팩트한 상태 스냅샷입니다. `exec` 모드에서는 상태가 `/tmp/codex-autoresearch-exec/...` 아래의 임시 파일에만 존재하며, `exec` 워크플로가 종료 전에 이를 명시적으로 정리해야 합니다. `foreground` 는 `research-results.tsv` 와 `autoresearch-state.json` 으로 직접 재개하고, 분리된 `background` 런타임 컨트롤러가 직접 재개하려면 기존 `autoresearch-launch.json` 이 계속 필요합니다.

복구 우선순위(인터랙티브 모드):

1. **JSON + TSV 일치, 그리고 launch manifest 존재:** 즉시 재개, 마법사 건너뛰기
2. **JSON 유효, TSV 불일치:** 미니 마법사 (1라운드 확인)
3. **JSON 없음 또는 손상, TSV 존재:** 보조 스크립트가 유지 상태를 재구성해 확인한 뒤 새 시작 매니페스트로 계속 진행
4. **둘 다 없음:** 새로 시작 (이전의 영속적인 run-control 아티팩트를 보관)

`references/session-resume-protocol.md` 참조.

---

## CI/CD 모드 (exec)

자동화 파이프라인을 위한 비대화형 모드. 모든 설정은 사전에 제공됩니다 -- 위저드 없음, 항상 상한 있음, JSON 출력.

```yaml
# GitHub Actions 예시
- name: Autoresearch optimization
  run: |
    codex exec --dangerously-bypass-approvals-and-sandbox <<'PROMPT'
    $codex-autoresearch
    Mode: exec
    Goal: Reduce type errors
    Scope: src/**/*.ts
    Metric: type error count
    Direction: lower
    Verify: tsc --noEmit 2>&1 | grep -c error
    Iterations: 20
    PROMPT
```

종료 코드: 0 = 개선됨, 1 = 개선 없음, 2 = 하드 블로커.

CI에서 `codex exec`를 사용하기 전에 Codex CLI 인증을 미리 구성하세요. 통제된 자동화 환경에서는 독립적인 `exec` 실행도 managed runtime 의 기본 정책 `danger_full_access` 와 맞추기 위해 `codex exec --dangerously-bypass-approvals-and-sandbox ...` 사용을 권장합니다. 프로그래밍 방식 실행에는 API key 인증이 권장됩니다.

`Mode: exec` 를 skill 에 포함된 helper script 로 구동할 때는 repo 루트의 기존 아티팩트를 수동으로 이름 변경하지 마세요. `autoresearch_init_run.py --mode exec ...` 가 기본 `research-results.tsv` 와 `autoresearch-state.json` 을 `research-results.prev.tsv` 와 `autoresearch-state.prev.json` 으로 자동 보관한 뒤 새 실행을 초기화합니다.

자세한 내용은 `references/exec-workflow.md` 참조.

---

## 결과 로그

각 반복은 두 가지 보완적인 형식으로 기록됩니다:

- **`research-results.tsv`** -- 전체 감사 추적. 각 반복은 하나의 메인 행으로 기록하고, 필요하면 병렬 worker 행을 추가
- **`autoresearch-state.json`** -- 인터랙티브 모드의 빠른 세션 재개를 위한 컴팩트한 상태 스냅샷

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

`exec` 모드에서는 상태 스냅샷이 `/tmp/codex-autoresearch-exec/...` 임시 위치에만 존재하고, `exec` 워크플로가 종료 전에 이를 명시적으로 정리해야 합니다. 이러한 아티팩트는 대상 저장소의 `scripts/` 디렉터리가 아니라 `<skill-root>/scripts/...` 아래의 bundled helper scripts로 업데이트하세요.

두 파일 모두 git에 커밋하지 않습니다. 세션 재개 시 JSON 상태는 TSV 메인 반복 요약과 교차 검증되며, 단순 행 수 자체를 기준으로 삼지 않습니다. 진행 요약은 5회 반복마다 출력됩니다. 유한 실행은 마지막에 기준선에서 최고값까지의 요약을 출력합니다.

이 상태 아티팩트는 `<skill-root>/scripts/...` 아래의 helper scripts 가 관리하지만, 대부분의 사용자는 계속해서 유일한 사람용 진입점인 **`$codex-autoresearch`** 만 쓰면 됩니다. 여기서 `<skill-root>` 는 현재 로드된 `SKILL.md` 가 있는 디렉터리를 뜻하며, 일반적인 repo-local 설치에서는 `.agents/skills/codex-autoresearch` 입니다.

control-plane 을 스크립팅하거나 디버깅할 때는 repo 중심 helper 가 기본적으로 `--repo <repo>` 를 우선 사용합니다. 다음 형태를 권장합니다.

- `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_launch_gate.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`

`--results-path`, `--state-path`, `--launch-path`, `--runtime-path` 는 고급 override 로 계속 사용할 수 있습니다. `autoresearch_resume_prompt.py` 와 `autoresearch_supervisor_status.py` 를 직접 호출할 때도 같은 repo-first 규약을 따릅니다.

사람 사용자를 위한 공개 진입점은 이제 **`$codex-autoresearch`** 하나뿐입니다.

- 첫 대화형 실행에서는 목표를 자연스럽게 설명하고, 확인 질문에 답하고, `foreground` 또는 `background` 를 명시적으로 고른 뒤 `go`라고 말하면 됩니다
- `foreground` 에서는 Codex가 현재 세션에 머물며 계속 반복하고, `research-results.tsv`, `autoresearch-state.json`, lessons 만 기록합니다
- `background` 에서는 Codex가 `autoresearch-launch.json` 을 기록하고 분리된 실행 컨트롤러를 자동으로 시작합니다
- `foreground` 와 `background` 는 같은 loop 프로토콜, metric 의미, repo/scope 규칙을 공유하지만 같은 repo/run 에 대해서는 서로 배타적입니다. 같은 primary repo 아티팩트에 두 모드를 동시에 적용하지 마세요
- 나중에 같은 interactive run 을 다른 모드로 이어가고 싶더라도, 계속 같은 `$codex-autoresearch` 진입점을 사용해야 합니다. 이어가기 전에 skill 이 내부적으로 공유 state 를 목표 모드로 동기화하며, background `start` 도 같은 동기화를 자동으로 수행합니다
- 단일 저장소 실행은 여전히 기본 경로이며, 이 경우 선언한 scope 는 run-control 아티팩트를 보관하는 primary repo 에만 적용됩니다
- 실험이 여러 저장소에 걸치면, 확인된 launch manifest 에 companion repos 와 각 저장소별 scope 를 함께 선언할 수 있습니다. runtime preflight 는 모든 managed repo 를 검사하지만 `research-results.tsv`, `autoresearch-state.json`, 그리고 runtime-control 아티팩트는 계속 primary repo 에 남습니다
- 이 모델에서 TSV 의 `commit` 열은 계속 primary repo 의 commit 만 기록하고, companion repo 별 commit provenance 는 `autoresearch-state.json` 에 저장됩니다
- 이후 각 `background` managed runtime cycle 은 runtime prompt 를 stdin 으로 전달하는 비대화형 `codex exec` 세션으로 실행됩니다
- `execution_policy` 는 중첩 Codex 세션을 시작하는 경로, 즉 `background` 와 `exec` 에만 적용됩니다. 이 skill 의 기본값은 `danger_full_access` 입니다
- 이후 `status`, `stop`, `resume` 요청도 계속 같은 `$codex-autoresearch` 를 통해 처리하지만, `status/stop` 은 `background` 에만 적용됩니다
- `Mode: exec` 는 CI 또는 완전히 지정된 자동화를 위한 고급 경로로 유지됩니다

스크립팅이나 실행 계층 디버깅을 위한 직접 제어 명령도 계속 사용할 수 있습니다.

- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`


---

## 보안 모델

| 우려 사항 | 처리 방식 |
|-----------|-----------|
| 더티 워크트리 | runtime 사전 점검이 범위 밖 변경이 정리되거나 격리될 때까지 시작과 재시작을 차단 |
| 실패한 변경 | 시작 전에 승인된 롤백 전략을 사용합니다. 격리된 실험 브랜치/워크트리에서 승인된 경우 `git reset --hard HEAD~1`, 그 외에는 `git revert --no-edit HEAD`를 사용합니다. 결과 로그가 감사 추적입니다 |
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
| 컨텍스트 드리프트 (장시간 실행) | 10회 반복마다 프로토콜 핑거프린트 검사; compaction 이후에는 빈도를 높이고, 실패 시 디스크에서 재로드 |

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
    validate_skill_structure.sh     # structure validator
    autoresearch_helpers.py         # TSV / JSON / runtime 을 다루는 공용 헬퍼
    autoresearch_launch_gate.py     # 시작 전에 fresh / resumable / needs_human 을 판정
    autoresearch_resume_prompt.py   # 저장된 설정에서 runtime 관리용 프롬프트를 만든다
    autoresearch_runtime_ctl.py     # runtime 의 launch / create-launch / start / status / stop 을 제어
    autoresearch_commit_gate.py     # git / artifact / rollback gate
    autoresearch_decision.py        # structured keep / discard / crash policy helpers
    autoresearch_health_check.py    # executable health checks
    autoresearch_lessons.py         # structured lessons append / list helpers
    autoresearch_init_run.py        # initialize baseline log + state
    autoresearch_record_iteration.py # append one main iteration + update state
    autoresearch_resume_check.py    # decide full_resume / mini_wizard / fallback
    autoresearch_select_parallel_batch.py # log worker rows + batch winner
    autoresearch_exec_state.py      # resolve / cleanup exec scratch state
    autoresearch_supervisor_status.py # decide relaunch / stop / needs_human
    check_skill_invariants.py       # validate real skill-run artifacts
    run_skill_e2e.sh                # disposable Codex CLI smoke harness
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

**실행 간에 학습하나요?** 예. 교훈은 각 `keep`, 각 `pivot`, 그리고 최근 교훈이 없는 상태로 관리형 실행이 종료될 때 추출됩니다. 교훈 파일은 세션 간에 유지됩니다. `exec` 는 기존 교훈만 읽고 새 교훈은 쓰지 않습니다.

**중단 후 재개할 수 있나요?** 예. `foreground` 는 `research-results.tsv` 와 `autoresearch-state.json` 에서 재개하고, `background` 는 여기에 더해 `autoresearch-launch.json` 도 필요합니다. 확인된 launch state 가 없으면 일반 `background` launch 흐름으로 새 run 을 시작하세요.

**Web 검색이 가능한가요?** 예. 여러 번의 전략 피봇 후 정체되었을 때 사용됩니다. Web 검색 결과는 가설로 취급되어 기계적으로 검증됩니다.

**CI에서 사용하려면?** `Mode: exec` 또는 `codex exec`를 사용하세요. 통제된 자동화 환경에서는 기본 runtime 권한과 맞추기 위해 `codex exec --dangerously-bypass-approvals-and-sandbox ...` 사용을 권장합니다. 모든 설정은 사전에 제공되며, 출력은 JSON 형식이고, 종료 코드가 성공/실패를 나타냅니다.

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
