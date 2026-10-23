---
name: toolkit-code
description: 도구 코드(src/kr_patch, Lua 스크립트, tests)를 바꾸거나 새 명령을 더할 때. 출력 호환, 게임 무관, 롬 금지, 영/한 문서와 변경 후 검증.
---

# 도구 코드

이 스킬이 COMPAT-01, SCOPE-01, ROM-01, DOC-01 의 정본이다. 구조: 기종 무관 도구는 `src/kr_patch/`(`ips`·`lzss`·`diff`·`shots`·`glyph`·`audio`), SNES 전용은 `src/kr_patch/snes/`(매퍼·체크섬·디스어셈블러·타일·libretro 실행기), Mesen 2 Lua 스크립트는 `src/kr_patch/snes/lua/`, 명령 정의는 `src/kr_patch/cli.py` 한 곳이다. 새 기종은 `src/kr_patch/<기종>/` 과 `krpatch <기종>` 하위 명령으로 둔다.

## 절차

1. **바꾸려는 동작의 기존 테스트를 찾는다** — `tests/test_<모듈>.py`. 없으면 지금 동작을 고정하는 테스트부터 쓴다.
   완료: 바꾸기 전 동작을 고정하는 테스트가 있다.
2. **고친다** — 출력이 바뀌는 변경이면 [COMPAT-01](#compat-01--출력-호환) 를 먼저 읽는다.
   완료: 새 동작의 테스트가 있다.
3. **문서를 고친다** — 명령·옵션·출력이 바뀌면 `README.md`·`README.ko.md` 의 해당 절과 `CHANGELOG.md` 의 `Unreleased`·`CHANGELOG.ko.md` 의 `미출시` 에 함께 적는다([DOC-01](#doc-01--영어판과-한국어판)).
   완료: 영어판과 한국어판의 내용이 같다.
4. **CI 와 같은 검사를 돌린다**:
   ```sh
   uv sync --locked
   uv run pytest -q
   uv run ruff check .
   find src/kr_patch/snes/lua -name '*.lua' -print0 | xargs -0 -n1 luac -p   # Lua 를 고쳤으면
   ```
   완료: 전부 통과.
5. **PR 로 올린다** — [git-workflow](../git-workflow/SKILL.md).
   완료: `ci-ok` 초록.

## 규칙

### COMPAT-01 — 출력 호환

이미 릴리스된 명령·함수는 같은 입력과 옵션에 같은 출력 바이트를 낸다. 기본값을 바꾸지 않는다. 다른 출력이 필요하면 새 옵션을 더하고 기본값은 그대로 둔다.

- 이유: 게임 저장소는 태그로 이 도구를 고정하고 배포한 IPS 를 바이트 단위로 다시 만든다. 고정 버전을 올릴 때 출력이 달라지면 롬 없이는 원인을 가릴 수 없다.
- 예: IPS `--gap` 기본값 6, LZSS 인코더 출력, `audio loop --legacy` 가 옛 스크립트를 바이트 단위로 재현하는 것.
- 버그 수정으로 출력이 바뀌는 경우(잘못된 패치를 내던 경우)는 예외지만 CHANGELOG 에 "출력이 바뀐다"고 분명히 적는다.

### SCOPE-01 — 게임 무관

한 게임에만 해당하는 것(대본 형식, 포인터 테이블, RAM 주소, 문자 코드표)은 넣지 않는다. 그 게임 저장소에 두고 인자로 넘긴다.

- 이유: 여러 게임이 같은 버전을 공유한다. 한 게임의 사정이 들어오면 다른 게임의 빌드가 그 변경을 따라 움직인다.
- 두 게임 이상이 같은 것을 다시 짜고 있을 때 옮겨 온다.

### ROM-01 — 롬 데이터 금지

롬과 그 일부(그래픽, 대본 덤프, 세이브)를 커밋하지 않는다. 테스트는 작은 합성 롬 이미지를 코드로 만든다(`tests/conftest.py`). `.gitignore` 가 `*.sfc`·`*.smc`·`*.srm` 을 막는다.

- 이유: 저작물이고, 저장소가 공개다.

### DOC-01 — 영어판과 한국어판

README 와 CHANGELOG 는 영어판(`*.md`)과 한국어판(`*.ko.md`)이 짝이다. 사용자에게 보이는 변경은 두 판에 함께 적고, 맨 위의 언어 전환 링크를 유지한다.

- 이유: 한쪽만 고치면 다른 쪽이 조용히 틀린 문서가 된다. 짝이 있는지는 CI(`lint` 잡)가 보지만 내용이 같은지는 사람이 본다.
- README 설치 줄의 태그는 `tests/test_version.py` 가 검사한다.
- 에이전트 문서(`AGENTS.md`, `CLAUDE.md`, `.agents/`)만 한국어 한 벌이다.

## 참고

- **Lua 스크립트**는 Mesen 2 가 읽는다. `tests/test_lua.py` 가 로컬 Lua 5.3/5.4 로 일부를 돌리고, CI 는 `luac5.4 -p` 로 문법만 본다.
- **ruff** 규칙은 버그를 잡는 것만 켰다(`pyproject.toml` 의 `[tool.ruff.lint]`). 한 줄에 짧은 문장을 모으는 기존 스타일은 의도라 고치지 않는다. 포맷터는 쓰지 않는다.
