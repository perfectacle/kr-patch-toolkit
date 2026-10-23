---
name: release
description: 새 버전을 릴리스할 때. 버전 번호 정하기, pyproject·__version__·README·CHANGELOG 맞추기, 태그와 GitHub 릴리스.
---

# 릴리스

이 스킬이 REL-01 의 정본이다. PyPI 에는 올리지 않는다. 게임 저장소는 `git+https://github.com/perfectacle/kr-patch-toolkit@vX.Y.Z` 로 태그를 고정해 설치한다.

## 절차

1. **버전을 정한다** — `CHANGELOG.md` 의 `Unreleased` 를 보고 semver 로. 0.x 동안은 새 명령·옵션이면 minor, 버그 수정만이면 patch. 기존 출력이 바뀌면([COMPAT-01](../toolkit-code/SKILL.md#compat-01--출력-호환) 예외) minor 이상.
   완료: 새 버전 `X.Y.Z` 를 정했다.
2. **릴리스 PR 을 만든다** — 한 PR 에서 함께 바꾼다:
   - `pyproject.toml` 의 `version`, `src/kr_patch/__init__.py` 의 `__version__`
   - `README.md`·`README.ko.md` 설치 줄의 `@vX.Y.Z`
   - `CHANGELOG.md` 의 `Unreleased` → `## X.Y.Z`(위에 빈 `## Unreleased` 를 남김), `CHANGELOG.ko.md` 의 `미출시` 도 같게
   - `uv lock`(프로젝트 버전이 lock 에 들어 있다)
   완료: `uv run pytest -q` 통과(`tests/test_version.py` 가 세 곳의 버전을 맞춰 본다).
3. **머지 후 main 의 머지 커밋에 태그를 단다** — 서명된 태그로.
   ```sh
   git fetch origin main
   git tag -s vX.Y.Z -m vX.Y.Z origin/main
   git push origin vX.Y.Z
   gh release create vX.Y.Z --title vX.Y.Z --notes-file <CHANGELOG 의 해당 절>
   ```
   완료: `gh release view vX.Y.Z` 가 보인다.
4. **게임 저장소의 고정 버전은 그쪽 Renovate PR 로 올라간다** — 직접 올리지 않는다. 그 PR 은 롬으로 다시 빌드해 IPS 를 비교한 뒤 사람이 머지한다.

## 규칙

### REL-01 — 버전과 태그

버전은 semver 이고 `pyproject.toml`·`kr_patch.__version__`·README 설치 줄이 같은 값이다. 태그 `vX.Y.Z` 는 한 번 push 하면 옮기거나 지우지 않는다(저장소 ruleset 이 막는다). 잘못 릴리스했으면 다음 patch 버전을 낸다.

- 이유: 게임 저장소는 태그 이름으로 고정한다. 태그가 움직이면 같은 고정 버전에서 환경마다 다른 도구가 설치되고, `uv.lock` 에 기록된 커밋과도 어긋난다.
