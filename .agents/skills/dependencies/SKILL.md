---
name: dependencies
description: Python 의존성·Python·uv·GitHub Actions 버전을 추가하거나 올릴 때, 또는 Renovate PR 이나 audit 잡이 실패했을 때. 7일 쿨다운, uv.lock, 라이브러리 범위.
---

# 의존성

이 스킬이 DEP-01, DEP-02 의 정본이다. 평소 업데이트는 Renovate 가 PR 로 올리고 CI 가 통과하면 자동 머지된다(`renovate.json`). 사람이나 에이전트가 직접 손대는 것은 새 의존성 추가와 Renovate PR·`audit` 잡이 실패했을 때다. 급한 업데이트는 Renovate 대시보드 이슈에서 체크해 바로 PR 을 만들게 한다.

## 절차 — 의존성 추가·변경

1. **추가한다** — 런타임은 `uv add '<pkg>>=<최소 버전>'`, 개발용은 `uv add --dev <pkg>`. `pyproject.toml` 의 `exclude-newer` 가 7일 안 된 버전을 알아서 건너뛴다.
   완료: `pyproject.toml` 과 `uv.lock` 이 함께 바뀌었다.
2. **검증한다** — `uv sync --locked && uv run pytest -q && uv run ruff check .`.
   완료: 전부 통과.

## 규칙

### DEP-01 — 7일 쿨다운

릴리스된 지 7일이 지난 버전만 쓴다. uv(`[tool.uv] exclude-newer = "7 days"`)와 Renovate(`minimumReleaseAge: 7 days`) 양쪽에 걸려 있다.

- 이유: 공급망 공격은 대개 배포 직후 며칠 안에 발견·회수된다.
- 예외는 보안 수정 하나다. Renovate 는 취약점 PR 에 쿨다운을 적용하지 않는다(`vulnerabilityAlerts`). uv 쪽은 `[tool.uv] exclude-newer-package` 에 그 패키지만 넣어야 lock 에 들어간다. 근거(advisory 링크)를 PR 에 적고, 쿨다운이 지나면 그 항목을 지운다.
- `audit` 잡(사용자가 설치하는 런타임 의존성만 `pip-audit`)이 새 advisory 로 실패하면: 수정 버전이 쿨다운 밖이면 `uv lock --upgrade-package <pkg>`, 안이면 위 예외, 수정 버전이 없으면 PR 에 advisory 와 영향 여부를 적고 저장소 주인에게 넘긴다. `audit` 은 시간에 따라 결과가 바뀌므로 코드 변경 없이도 실패할 수 있다.
- GitHub Actions 도 같은 기준이다. 액션은 커밋 SHA 로 고정하고 `# vX.Y.Z` 주석을 단다. actionlint 이미지는 digest 로, zizmor 는 잡 env 의 `ZIZMOR`, uv 는 `setup-uv` 의 `version: X # uv` 한 곳에 두고 `renovate.json` 의 customManager 가 올린다.

### DEP-02 — lockfile

`pyproject.toml` 을 바꾸면 `uv.lock` 도 같이 바뀌어야 하고 `uv sync --locked` 가 통과해야 한다.

- 충돌이 나면 main 의 lock 을 가져와(`git checkout origin/main -- uv.lock`) `uv lock` 으로 다시 만든다. 손으로 고치지 않는다.
- lock 은 개발·CI 용이다. 패키지를 설치하는 사람(게임 저장소)은 `pyproject.toml` 의 범위를 따른다.

## 참고

- **라이브러리 범위**: `dependencies` 는 `>=` 최소 버전만 적는다. 상한을 걸면 게임 저장소가 다른 패키지와 함께 풀 때 충돌한다. 최소 버전을 올릴 때는 그 버전이 필요한 이유를 주석으로 남긴다(예: numpy 2.5.2 가 Python 3.15 휠이 있는 첫 릴리스). Renovate 는 범위를 두고 `uv.lock` 만 올린다(`rangeStrategy: update-lockfile`).
- **Python 버전**은 `.python-version`(uv 와 CI 가 읽는다)과 `requires-python` 이 정한다. Renovate 가 `.python-version` 을 올린다.
- **Renovate PR 이 실패했을 때**: CI 로그로 원인을 찾아 같은 브랜치에 커밋해 고친다([ci](../ci/SKILL.md)). 새 major 가 API 를 바꿨으면 코드를 맞추되 최소 버전도 함께 올린다.
