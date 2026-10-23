# 불변식 카탈로그

이 저장소가 지키는 규칙의 목록이다. 이 파일에는 규칙의 요지와 **소유자**(규칙 본문이 있는 스킬의 절)만 있다. 본문·이유·예외는 소유자에서 읽는다. 규칙을 바꿀 때는 소유자 한 곳만 고치고, 이 표의 요지가 달라졌으면 이 줄도 고친다.

## 도구 — 게임 저장소의 빌드를 깨지 않는다

| ID        | 요지                                                                                 | 소유자                                                                     |
| --------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| COMPAT-01 | 기존 명령·함수는 같은 입력·옵션에 같은 출력 바이트. 기본값을 바꾸지 않고 새 옵션으로 | [toolkit-code §COMPAT-01](../skills/toolkit-code/SKILL.md#compat-01--출력-호환) |
| SCOPE-01  | 한 게임에만 해당하는 형식·주소·데이터를 넣지 않는다. 인자로 받는다                  | [toolkit-code §SCOPE-01](../skills/toolkit-code/SKILL.md#scope-01--게임-무관)   |
| ROM-01    | 롬 데이터를 커밋하지 않는다. 테스트는 합성 롬                                        | [toolkit-code §ROM-01](../skills/toolkit-code/SKILL.md#rom-01--롬-데이터-금지)  |
| DOC-01    | 사용자에게 보이는 변경은 README·CHANGELOG 의 영어판과 한국어판에 함께 적는다         | [toolkit-code §DOC-01](../skills/toolkit-code/SKILL.md#doc-01--영어판과-한국어판) |
| REL-01    | 버전은 semver, `pyproject.toml`·`__version__`·README 설치 줄이 같다. 태그는 불변     | [release §REL-01](../skills/release/SKILL.md#rel-01--버전과-태그)               |
| COPY-01   | 한국어 문서는 합니다체, 번역투 없이, 용어집을 따른다                                 | [korean-copy](../skills/korean-copy/SKILL.md)                                   |

## 의존성·CI·git

| ID     | 요지                                                                   | 소유자                                                                            |
| ------ | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| DEP-01 | 릴리스된 지 7일 지난 버전만 쓴다(보안 수정만 예외)                     | [dependencies §DEP-01](../skills/dependencies/SKILL.md#dep-01--7일-쿨다운)        |
| DEP-02 | 의존성을 바꾸면 `uv.lock` 이 같이 바뀌고 `uv sync --locked` 가 통과한다 | [dependencies §DEP-02](../skills/dependencies/SKILL.md#dep-02--lockfile)          |
| CI-01  | main 은 `ci-ok` 통과가 필수, 통과한 PR 은 자동 머지                    | [ci §CI-01](../skills/ci/SKILL.md#ci-01--ci-ok-와-자동-머지)                      |
| CI-02  | 실패하면 기준을 낮추지 말고 원인을 고친다                              | [ci §CI-02](../skills/ci/SKILL.md#ci-02--실패는-원인을-고친다)                    |
| GIT-01 | 모든 변경은 브랜치 → PR, 머지 전 로컬 검증                             | [git-workflow §GIT-01](../skills/git-workflow/SKILL.md#git-01--브랜치와-pr)       |
| GIT-02 | 작업마다 최신 `origin/main` 에서 워크트리를 파고, 머지가 끝나면 지운다 | [git-workflow §GIT-02](../skills/git-workflow/SKILL.md#git-02--작업마다-워크트리) |
