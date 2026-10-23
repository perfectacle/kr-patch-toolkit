# 에이전트 진입 문서

이 저장소는 한글 패치 여러 개가 함께 쓰는 게임 무관 도구 모음 kr-patch-toolkit 의 소스다(Python 패키지 `kr_patch`, 명령 `krpatch`). 게임 저장소([kr-patches](https://github.com/perfectacle/kr-patches))는 릴리스 태그로 이 도구를 고정하고, 배포한 IPS 를 바이트 단위로 다시 만들어 낸다. 그래서 **같은 입력에 같은 출력**을 지키는 것이 가장 중요한 제약이다. 이 문서는 모든 코딩 에이전트(Claude Code, Codex, Cursor 등)가 처음 읽는 곳이다. 규칙의 정본은 `.agents/` 에 한 벌만 있고, 여기에는 요약과 "무엇을 하려면 어디를 읽나" 만 있다.

도구별 경로는 정본을 가리킨다: `CLAUDE.md` 는 이 파일을 import 하고, `.claude/skills` 는 `.agents/skills` 의 심볼릭 링크다. 스킬을 고칠 때는 `.agents/skills/` 실경로를 쓴다 — 심볼릭 링크 너머 경로는 `git add` 가 거부한다.

## 절대 규칙

어떤 도구를 쓰든 지킨다. 각 줄의 링크가 정본이다.

- **기존 명령의 출력 바이트와 기본값을 바꾸지 않는다** — 게임 저장소의 배포 패치 재현이 깨진다. 바꿔야 하면 새 옵션으로. [COMPAT-01](.agents/skills/toolkit-code/SKILL.md#compat-01--출력-호환)
- **한 게임에만 해당하는 것(대본 형식, 포인터, RAM 주소)을 넣지 않는다** — 인자로 받는다. [SCOPE-01](.agents/skills/toolkit-code/SKILL.md#scope-01--게임-무관)
- **롬 데이터를 커밋하지 않는다** — 테스트는 합성 롬을 만든다. [ROM-01](.agents/skills/toolkit-code/SKILL.md#rom-01--롬-데이터-금지)
- **릴리스 태그는 옮기거나 지우지 않는다** — 게임 저장소가 태그로 고정한다. [REL-01](.agents/skills/release/SKILL.md#rel-01--버전과-태그)
- **릴리스된 지 7일 안 된 의존성을 들이지 않는다** — 보안 수정만 예외. [DEP-01](.agents/skills/dependencies/SKILL.md#dep-01--7일-쿨다운)
- **작업마다 최신 `origin/main` 에서 워크트리를 파고, 머지가 끝나면 지운다** — [GIT-02](.agents/skills/git-workflow/SKILL.md#git-02--작업마다-워크트리)
- **모든 변경은 브랜치 → PR, `ci-ok` 를 통과시킨다** — [GIT-01](.agents/skills/git-workflow/SKILL.md#git-01--브랜치와-pr), [CI-01](.agents/skills/ci/SKILL.md#ci-01--ci-ok-와-자동-머지)
- **검사가 실패하면 기준을 낮추지 말고 원인을 고친다** — [CI-02](.agents/skills/ci/SKILL.md#ci-02--실패는-원인을-고친다)

전체 목록: [불변식 카탈로그](.agents/invariants/INVARIANTS.md)

## 무엇을 하려면 어디를 읽나

| 하려는 일                                               | 읽을 정본                                            |
| ------------------------------------------------------- | ---------------------------------------------------- |
| 도구 코드(`src/kr_patch`, Lua 스크립트, 테스트)를 바꾼다 | [toolkit-code](.agents/skills/toolkit-code/SKILL.md) |
| 새 버전을 릴리스한다                                    | [release](.agents/skills/release/SKILL.md)           |
| 의존성·Python·uv·Actions 버전을 바꾸거나 Renovate PR 을 고친다 | [dependencies](.agents/skills/dependencies/SKILL.md) |
| 워크플로를 바꾸거나 CI 실패를 고친다                    | [ci](.agents/skills/ci/SKILL.md)                     |
| 워크트리·브랜치·커밋·PR 을 만들거나 정리한다            | [git-workflow](.agents/skills/git-workflow/SKILL.md) |
| 한국어 문서(README.ko, CHANGELOG.ko)를 쓴다             | [korean-copy](.agents/skills/korean-copy/SKILL.md)   |

명령은 `pyproject.toml`, CI 구성은 `.github/workflows/ci.yml` 에서 바로 확인한다.
