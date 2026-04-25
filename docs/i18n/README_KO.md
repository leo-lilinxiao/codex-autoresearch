<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>조준. 반복. 도달.</b></h2>

<p align="center">
  <i>Codex를 위한 자율 목표 지향 실험 엔진.</i>
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

---

핵심 아이디어: Codex에게 개선하고 싶은 것을 말하고 자리를 비우세요. 코드를 수정하고, 결과를 검증하고, 유지하거나 폐기하고, 반복합니다. 돌아오면 실험 로그와 더 나은 코드베이스가 기다리고 있습니다.

[Karpathy의 autoresearch](https://github.com/karpathy/autoresearch)에서 영감을 받아, ML을 넘어 기계적으로 검증할 수 있는 모든 목표로 일반화: 테스트 커버리지, 타입 에러, 레이턴시, lint 경고, 보안 취약점, 릴리스 준비 — 명령어로 개선 여부를 판단할 수 있다면 루프가 반복할 수 있습니다.

## 빠른 시작

```text
# Codex에 설치 (권장)
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Codex를 다시 시작한 뒤 프로젝트에서 열고:

```
당신:  $codex-autoresearch
       TypeScript 코드의 모든 any 타입을 제거해줘

Codex: src/**/*.ts에서 47개의 `any`를 발견했습니다.
       Results 디렉터리: ./autoresearch-results/
       지표: any 발생 횟수 (현재 47), 방향: 감소
       검증: grep 카운트 + tsc --noEmit 가드
       실행 모드: foreground 또는 background?

당신:  Background, go. 밤새 돌려줘.

Codex: 백그라운드 실행 시작 — 베이스라인: 47. 반복 중.
```

개선은 누적되고, 실패는 롤백되며, 모든 것이 기록됩니다.

수동 복사, symlink, 사용자 범위 설치는 [INSTALL.md](../INSTALL.md), 전체 매뉴얼은 [GUIDE.md](../GUIDE.md) 참조.

## 작동 방식

```
한 문장으로 말하기  →  Codex가 스캔 & 확인  →  "go"라고 말하기
                                                  |
                                     +------------+------------+
                                     |                         |
                                foreground                background
                              (현재 세션)              (분리, 밤새 실행)
                                     |                         |
                                     +------------+------------+
                                                  |
                                                  v
                                        +-------------------+
                                        |    핵심 루프       |
                                        |                   |
                                        |  하나 수정        |
                                        |  git commit       |
                                        |  검증 실행        |
                                        |  개선? 유지       |
                                        |  악화? 롤백       |
                                        |  결과 기록        |
                                        |  반복             |
                                        +-------------------+
```

이게 전부입니다. 둘 중 하나를 선택합니다: foreground는 현재 세션에서 루프를 실행하고, background는 분리된 프로세스에 넘겨서 자리를 비울 수 있습니다. 같은 루프지만 동시에 실행할 수는 없습니다.

## 당신이 말하는 것 vs 일어나는 일

| 당신이 말하는 것 | 일어나는 일 |
|----------------|-----------|
| "테스트 커버리지를 올려줘" | 목표 달성 또는 중단까지 반복 |
| "실패한 12개 테스트를 고쳐줘" | 하나씩 수정하여 전부 통과할 때까지 |
| "왜 API가 503을 반환하지?" | 반증 가능한 가설로 근본 원인 추적 |
| "이 코드 안전해?" | STRIDE + OWASP 감사, 모든 발견에 코드 증거 포함 |
| "배포해줘" | 준비 상태 검증, 체크리스트 생성, 게이트 릴리스 |
| "최적화하고 싶은데 뭘 측정해야 할지 모르겠어" | 저장소 분석, 지표 제안, 설정 생성 |

내부적으로 Codex는 7개 모드(loop, plan, debug, fix, security, ship, exec) 중 하나에 매핑합니다. 모드를 선택할 필요가 없습니다.

## Codex가 자동으로 파악하는 것

설정을 작성할 필요가 없습니다. Codex가 당신의 말과 저장소에서 모든 것을 추론합니다:

| 필요한 정보 | 획득 방법 | 예시 |
|------------|----------|------|
| 목표 | 당신의 한 마디 | "모든 any 타입 제거" |
| 범위 | 저장소 구조 스캔 | `src/**/*.ts` |
| 지표 | 목표 + 도구 체인 기반 제안 | any 카운트 (현재: 47) |
| 방향 | "개선" / "감소" / "제거"에서 추론 | 감소 |
| 검증 명령 | 저장소 도구와 매칭 | `grep` 카운트 + `tsc --noEmit` |
| 가드 | 회귀 위험이 있으면 제안 | `npm test` |

시작 전에 Codex는 항상 발견한 내용을 보여주고 확인을 요청합니다. 그 후 foreground 또는 background를 선택하고 "go"라고 말합니다.
기본적으로 Results 디렉터리는 시작 컨텍스트에 머뭅니다. Codex를 git 저장소 안에서 시작했다면 그 저장소 루트가 기본 workspace root이고, git 저장소 밖에서 시작했다면 현재 시작 디렉터리가 기본 workspace root입니다. 더 넓은 멀티 리포 workspace를 사용하겠다고 명시적으로 확인하지 않는 한, Codex가 이를 상위 디렉터리로 조용히 넓혀서는 안 됩니다. 시작 전에 확인 요약에는 선택된 Results 디렉터리가 항상 표시되어야 합니다.

## 막혔을 때

맹목적으로 재시도하지 않고 단계적으로 에스컬레이션합니다:

| 트리거 | 액션 |
|--------|------|
| 3회 연속 실패 | **REFINE** — 현재 전략 내에서 조정 |
| 5회 연속 실패 | **PIVOT** — 근본적으로 다른 접근 시도 |
| 진전 없는 PIVOT 2회 | **웹 검색** — 외부 솔루션 탐색 |
| 진전 없는 PIVOT 3회 | **중단** — 사람의 판단이 필요하다고 보고 |

한 번의 성공으로 모든 카운터가 리셋됩니다.

## 결과 로그

각 반복은 `autoresearch-results/results.tsv`에 기록됩니다:

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module
2          -        49      +8      discard   generic wrapper introduced new anys
3          d4e5f6g  38      -3      keep      type-narrow API response handlers
```

실패한 실험은 git에서 롤백되지만 로그에는 남습니다. 로그가 진정한 감사 추적이며, `autoresearch-results/state.json`은 재개 스냅샷입니다.

## 추가 기능

다음은 [GUIDE.md](../GUIDE.md)에서 자세히 설명합니다:

- **크로스런 학습** — 과거 실행의 교훈이 미래 가설 생성에 영향
- **병렬 실험** — git worktree로 최대 3개 가설을 동시 테스트
- **세션 재개** — 중단된 실행은 마지막 일관된 상태에서 재개
- **CI/CD 모드** (`exec`) — 비대화형, JSON 출력, 자동화 파이프라인용
- **이중 게이트 검증** — verify(개선되었나?)와 guard(다른 것이 깨지지 않았나?)를 분리
- **세션 hooks** — 자동 설치; 세션 경계를 넘어 Codex 상태 유지

## FAQ

**매번 작은 변경만 한다. 더 큰 아이디어를 시도할 수 있나?**
기본적으로 루프는 작고 검증 가능한 단계를 선호합니다 — 이것은 의도된 설계입니다. 하지만 더 큰 것도 가능합니다: 프롬프트에서 더 큰 가설을 설명하면(예: "attention 메커니즘을 linear attention으로 교체하고 전체 eval을 실행해줘") 하나의 완전한 실험으로 검증합니다. 사람이 연구 방향을 정하고 에이전트가 실행과 분석을 담당하는 것이 최적의 사용법입니다.

**이건 엔지니어링 최적화용인가, 연구용인가?**
목표와 지표가 명확할 때 가장 강력합니다 — 커버리지 올리기, 에러 줄이기, 레이턴시 낮추기. 연구 방향 자체가 불확실하다면 먼저 `plan` 모드로 탐색하고, 무엇을 측정할지 정한 후 `loop`으로 전환하세요. 인간-AI 협업으로 생각하세요: 당신이 판단을 제공하고, 에이전트가 반복 속도를 제공합니다.

**어떻게 멈추나요?** Foreground: Codex를 중단. Background: `$codex-autoresearch`에서 중단 요청.

**중단 후 재개 가능한가요?** 네. `autoresearch-results/state.json`에서 자동으로 재개합니다.

**CI에서 어떻게 사용하나요?** `Mode: exec`와 `codex exec`. 모든 설정 사전 제공, JSON 출력, 종료 코드 0/1/2.

## 문서

| 문서 | 내용 |
|-----|------|
| [INSTALL.md](../INSTALL.md) | 모든 설치 방법, skill 발견 경로, hooks 설정 |
| [GUIDE.md](../GUIDE.md) | 전체 운영 매뉴얼: 모드, 설정 필드, 안전 모델, 고급 사용법 |
| [EXAMPLES.md](../EXAMPLES.md) | 도메인별 레시피: 커버리지, 성능, 타입, 보안 등 |

## 감사의 말

[Karpathy의 autoresearch](https://github.com/karpathy/autoresearch) 아이디어를 기반으로 구축. Codex skills 플랫폼은 [OpenAI](https://openai.com) 제공.

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

## 라이선스

MIT — [LICENSE](../../LICENSE) 참조.
