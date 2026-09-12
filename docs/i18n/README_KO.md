# Codex Autoresearch

[English](../../README.md) | **한국어**

Codex를 위한 자율적이고 측정 가능한 실험 루프입니다.

숫자로 확인할 수 있는 목표를 전달하면 Codex가 저장소를 조사하고 설정을 확인한 뒤, 한 가지 변경, 검증, 개선 유지, 실패 되돌리기를 목표 달성까지 반복합니다.

테스트 실패 수, 커버리지, 타입 오류, 경고, 지연 시간, 바이너리 크기, 재현 가능한 보안 결과 등에 적합합니다.

## 빠른 시작

Codex에서 설치합니다.

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

깨끗한 Git 저장소를 Full Access로 여는 것을 권장합니다.

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

그다음 실행합니다.

```text
$codex-autoresearch `python3 scripts/score.py`의 error_count를 0으로 줄여줘
```

첫 쓰기 전에 목표, 수정 범위, 기준값, 목표값, 측정 명령, 선택적 guard, foreground/background를 확인합니다.

이미 전달한 선택과 승인은 유지됩니다. 시작 후에는 실험마다 재확인을 요청하지 않습니다. 중지한 백그라운드 실행은 "재개"로 기존 설정을 이어갈 수 있으며, 새 방향을 덧붙여도 됩니다.

## 동작 방식

```text
증거 확인 -> 하나의 가설 변경 -> 커밋 및 측정
                                  |
                     개선 + guard 통과: 유지
                     그 외: git revert
                                  |
                            기록 후 반복
```

Codex는 가설과 코드 수정을 담당하고, 제어 스크립트는 Git 경계, 측정, 롤백, 상태를 담당합니다.

## Foreground와 Background

| | Foreground | Background |
|---|---|---|
| 실행 위치 | 현재 Codex 작업 | 분리된 controller |
| 지속 실행 | 공식 Codex Goal | 반복마다 하나의 `codex exec` worker |
| 용도 | 실시간 관찰과 지시 | 장시간 또는 야간 실행 |
| 제어 | Goal pause/resume | `$codex-autoresearch` status/stop/resume |

Foreground는 공식 Goal로 계속 실행됩니다. Background는 Goal 없이 controller가 지속 실행합니다. 설치 과정에서 Codex 설정은 변경되지 않습니다.

## 결과

커밋되지 않는 `autoresearch-results/`에 저장됩니다.

| 경로 | 용도 |
|---|---|
| `run.json` | 확인된 불변 설정 |
| `events.jsonl` | 추가 전용 상태 및 감사 기록 |
| `logs/` | 측정, guard, worker 전체 출력 |
| `runtime.json` | 백그라운드 프로세스 상태 |
| `runtime.log` | controller 수명 주기 이벤트 |

`events.jsonl`이 유일한 실행 상태입니다. 누락, 손상, 충돌이 있으면 추측해 복구하지 않고 명확하게 실패합니다.

## 기록과 보고서

```text
$codex-autoresearch show experiment history
$codex-autoresearch export experiment history as TSV
$codex-autoresearch generate an HTML report
```

기록 표와 HTML은 검증된 이벤트에서 생성됩니다. HTML 스냅샷은 `autoresearch-results/report.html`에 저장되며 실행 상태나 복구에는 사용되지 않습니다.

## 신뢰성

- 새 실행에는 깨끗한 이름 있는 Git 브랜치가 필요합니다.
- 한 실행은 저장소 하나, 지표 하나, 목표값 하나를 관리합니다.
- 모든 실험은 커밋되고 실패하면 `git revert`됩니다.
- 범위 밖 수정, Git 드리프트, 잘못된 지표, 명령 실패, 시간 초과, 롤백 실패는 로그와 함께 실행을 중단합니다.
- 유지된 지표가 목표값에 도달해야만 `complete`입니다.

## 요구 사항

- Skills와 Goals를 지원하는 최신 Codex CLI
- Python 3.11+
- Git

[설치](../INSTALL.md), [사용자 가이드](../GUIDE.md), [예제](../EXAMPLES.md)를 참고하세요.

MIT License. [Karpathy의 autoresearch](https://github.com/karpathy/autoresearch)에서 영감을 받았습니다.
