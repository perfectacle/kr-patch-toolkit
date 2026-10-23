---
name: ci
description: GitHub Actions 워크플로를 바꾸거나 CI 가 실패했을 때. 필수 체크 ci-ok, 자동 머지, 실패 대응 원칙.
---

# CI

이 스킬이 CI-01, CI-02 의 정본이다. 워크플로는 `.github/workflows/ci.yml`(검사)과 `links.yml`(외부 링크 주간 점검)이다. 잡 목록은 워크플로 파일을 본다.

## 절차 — CI 가 실패했을 때

1. **실패한 잡과 로그를 본다** — `gh run view <run-id> --log-failed`.
   완료: 실패 원인을 한 문장으로 말할 수 있다.
2. **로컬에서 재현한다** — 깨끗한 환경에서 같은 명령을 돌린다(`rm -rf .venv && uv sync --locked`). CI 는 Linux arm64 라 macOS 전용인 `krpatch ocr`(Vision)는 "macOS 가 필요하다"는 오류 경로만 검사하고, macOS 에서는 그 테스트가 건너뛰어진다. Lua 테스트(`tests/test_lua.py`)는 Lua 5.3 이상이 없으면 건너뛰어진다.
   완료: 재현되거나, 로컬에서는 통과한다.
3. **원인을 고치고 같은 PR 에 push 한다**(CI-02).
   완료: 새 커밋의 `ci-ok` 가 초록.

## 규칙

### CI-01 — ci-ok 와 자동 머지

main 은 `ci-ok` 체크 통과가 필수다(저장소 ruleset). `ci-ok` 는 모든 잡을 모아 하나라도 실패·취소·skip 이면 실패한다. 통과한 PR 은 GitHub 자동 머지로 머지된다.

- 새 잡을 추가하면 `ci-ok` 의 `needs` 에 넣는다. 빠지면 그 잡이 실패해도 머지된다.
- 자동 머지는 체크가 통과하는 순간 일어난다. PR 에 커밋을 더 올릴 계획이면 다 올린 뒤에 `gh pr merge --auto --merge` 를 건다.
- 이 저장소의 CI 는 몇 분이면 끝나서, 블로그 저장소처럼 결과를 캐시해 잡을 건너뛰는 장치는 두지 않는다. 잡이 10분을 넘기기 시작하면 그때 들인다.

### CI-02 — 실패는 원인을 고친다

검사가 실패하면 기준(ruff 규칙, 테스트 허용 오차, audit)을 낮추지 않고 원인을 고친다. 기준을 바꾸는 것은 측정 방식 자체가 틀렸다는 근거가 있을 때뿐이고, 그 근거를 PR 에 적는다.

- 테스트가 불안정하면 재시도를 늘리지 말고 비결정적인 부분(시간, 부동소수점 비교, 파일 순서)을 찾는다.

## 참고

- **외부 링크 점검**: `links.yml` 이 매주 깨진 외부 링크를 `broken-links` 이슈로 올린다. 머지 조건이 아니다.
- **보안 점검**: `zizmor` 잡이 워크플로를 검사한다. checkout 에는 `persist-credentials: false`(이 워크플로는 push 하지 않는다). `actionlint` 가 문법을 본다. `ubuntu-26.04-arm` 을 actionlint 가 아직 모르는 라벨이라 `.github/actionlint.yaml` 에 적어 두었다.
- **동시 실행 한도**: 무료 계정은 동시 20잡이다. 대기열에 오래 머물면 다른 실행과 겹친 것이다. PR 이 main 과 충돌하면 `pull_request` 워크플로가 아예 시작되지 않는다.
