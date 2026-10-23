# kr-patch-toolkit

[English](README.md) | 한국어

번역 패치를 만들고 검증할 때 쓰는, 게임과 무관한 도구 모음입니다. 일부는
기종과도 무관하고(IPS 패치, LZSS 코덱, 파일 비교, 스크린샷 비교, macOS OCR 을
곁들인 비트맵 글리프 도구), 나머지는 슈퍼패미컴(SNES)용입니다: 카트리지 매퍼,
헤더 체크섬, 65c816 디스어셈블러, 타일·BG 렌더링, 헤드리스 libretro 테스트
실행기, Mesen 2 Lua 스크립트. 다른 기종(NDS 부터)도 지원할 예정이며, 기종마다
`krpatch <기종>` 명령을 따로 둡니다.

여러 한글 패치가 함께 쓰는 부분을 모은 것입니다. 한 게임에만 해당하는 것
(대본 형식, 포인터 테이블, RAM 주소)은 그 게임의 저장소에 두고 인자로
넘깁니다.

롬 데이터는 들어 있지 않습니다. 테스트는 작은 합성 롬 이미지를 직접 만들어
돌립니다.

## 설치

Python 3.15 이상이 필요합니다.

```sh
pip install git+https://github.com/perfectacle/kr-patch-toolkit@v0.1.0
```

`krpatch` 명령과 `kr_patch` 패키지가 설치됩니다. 게임 프로젝트에서는
(`requirements.txt` 나 `pyproject.toml` 에) 태그를 고정해 두어야 도구가 바뀌어도
빌드 결과물이 달라지지 않습니다.

## 명령

모든 옵션은 `krpatch <명령> -h`(또는 `krpatch snes <명령> -h`)로 볼 수 있습니다.
주소와 오프셋은 따로 적지 않으면 16진수입니다.

| 명령 | 하는 일 |
| --- | --- |
| `krpatch ips make\|apply` | IPS 패치 생성·적용 |
| `krpatch lzss decode\|encode` | LZSS 코덱 |
| `krpatch diff` | 두 파일이 다른 바이트 범위 |
| `krpatch shotcmp` | 스크린샷을 비교해 텍스트로 출력 |
| `krpatch contact` | 스크린샷 모아 보기(contact sheet) |
| `krpatch glyph show\|make\|set` | JSON 저장소의 비트맵 글리프 |
| `krpatch ocr` | macOS Vision 으로 글리프 읽기 |
| `krpatch snes dis` | 65c816 코드 디스어셈블 |
| `krpatch snes checksum` | 내부 헤더 체크섬 확인·수정 |
| `krpatch snes tiles` | planar 타일 렌더링 |
| `krpatch snes bg`, `bgrefs` | VRAM/CGRAM 덤프에서 BG 레이어 |
| `krpatch snes run` | 헤드리스 libretro 실행기 |
| `krpatch snes lua` | 함께 들어 있는 Mesen 2 Lua 스크립트 경로 |

### `ips`: IPS 패치 생성·적용

```sh
krpatch ips make original.sfc patched.sfc out.ips --headered out-headered.ips
krpatch ips apply original.sfc out.ips result.sfc
```

`make` 는 패치를 쓰기 전에 각 패치가 패치된 파일을 그대로 재현하는지
확인합니다. `--headered` 를 주면 512바이트 카피어 헤더가 붙은 SNES 덤프용
패치도 함께 씁니다. `--gap N` 은 같은 바이트가 몇 개 이어지면 레코드를
끊을지 정합니다(기본값 6). gap 이 다른 패치도 똑같이 유효하지만 바이트까지
같지는 않으므로, 프로젝트가 이미 배포한 값을 그대로 쓰세요. IPS 의 24비트
오프셋 한계 때문에 파일은 16 MB 보다 작아야 합니다.

### `lzss`: LZSS 코덱

형식: u16 출력 크기 뒤에, 플래그 바이트 하나가 이끄는 8개 항목 묶음이
이어집니다(LSB 먼저). 1 = 리터럴 바이트, 0 = u16 워드로 길이 `(w & 0xF) + 3`,
거리 `w >> 4`. 시작 위치보다 앞은 0으로 읽습니다.

```sh
krpatch lzss decode game.sfc 0A8000 font.bin [--planar]
krpatch lzss encode font.bin font.lz [--planar]
```

`--planar` 는 두 planar 절반으로 저장된 SNES 2bpp 타일을 SNES 순서로 바꾸거나
그 반대로 바꿉니다. 스트림이 잘렸거나 거리가 0인 복사가 있으면 오류입니다.

### `diff`: 두 파일이 다른 바이트 범위

```sh
krpatch diff a.sfc b.sfc --gap 16
```

### `shotcmp`, `contact`: 스크린샷을 텍스트로

```sh
krpatch shotcmp out/new-snes9x-v1 ref/new-snes9x-v1            # 디렉터리, 파일 이름으로 짝지음
krpatch shotcmp actual.png ref.png --box 0,160,256,64 --tol 8 --crop diff.png
krpatch shotcmp actual.png --box 0,160,256,64 --crop crop.png  # 잘라내기만
krpatch contact 'out/new-*/end.png' sheet.png --cols 8
```

`shotcmp` 는 `same` 또는 다른 픽셀 수와 그 경계 상자를 출력하고, 다른 쌍이
하나라도 있으면 1로 끝납니다. 어느 색 채널이든 `--tol` 보다 크게 다르면 다른
픽셀입니다. 디렉터리를 비교할 때 한쪽에만 있는 PNG 는 차이로 세고, 양쪽 모두
PNG 가 없으면 오류입니다.

### `glyph`, `ocr`: 비트맵 글리프

글리프는 JSON `{"가": ["0110...", ...]}` 으로 저장합니다.

```sh
krpatch glyph show glyphs.json 각략
krpatch glyph make glyphs.json 갹 략 'ini=각:0-6,0-5'   # 바탕 글리프, 그다음 다른 글리프에서 복사할 행,열
krpatch glyph set glyphs.json 갹 '.##.' '#..#'
krpatch ocr glyphs.json ocr-rows/ --per-row 10 --fix-mo  # macOS 전용
```

`glyph show` 는 저장소에 없는 글자가 있으면 그 글자를 알려 주고 1로 끝납니다.

`ocr` 은 글리프를 줄 단위로 그려 macOS Vision 프레임워크로 각 줄을 읽고
`key<TAB>char` 를 출력합니다(줄 길이가 맞지 않으면 `?`). Vision 도우미
(`ocr.swift`)는 처음 쓸 때 `xcrun swiftc` 로 컴파일해
`~/.cache/kr-patch-toolkit` 에 둡니다. `--fix-mo` 는 글리프 모서리를 보고
ㅁ/ㅇ 을 다시 판정합니다. ㅁ 은 모서리를 채우고 ㅇ 은 비우는 픽셀 폰트에
맞으며, 매끈한 폰트에서는 맞는 결과를 틀리게 바꿀 수 있습니다.

## SNES 명령

### `snes dis`: 65c816 코드 디스어셈블

```sh
krpatch snes dis game.sfc 808000 40              # $80:8000 부터 명령어 40개
krpatch snes dis game.sfc C08000 --mapper sa1    # lorom | hirom | exhirom | sa1 | auto(기본값)
krpatch snes dis game.sfc 808000 --m16 --x16     # 16비트 A·X/Y 로 시작
```

`REP`/`SEP` 를 만나면 해독하면서 레지스터 폭을 바꿉니다. 블록 이동은 어셈블러
순서 `MVN src,dst` 로 출력합니다. `auto` 는 내부 헤더를 읽어 매퍼를 고르고,
512바이트 카피어 헤더는 건너뜁니다. SA-1 은 전원을 켰을 때의 Super MMC
블록(0-3)을 씁니다. 다른 블록은 `kr_patch.snes.mapper.SA1(blocks=...)` 로
넘깁니다.

### `snes checksum`: 헤더 체크섬 확인·수정

```sh
krpatch snes checksum game.sfc          # 매퍼, 제목, 저장된 값과 계산한 값 출력. 틀리면 1로 끝남
krpatch snes checksum game.sfc --fix    # 보수와 체크섬을 제자리에서 다시 씀
```

내부 헤더를 알아볼 수 없으면 `--fix` 는 거부합니다. `--mapper` 를 주면
진행합니다. 크기가 2의 거듭제곱이 아니면 카트리지가 미러링하는 방식대로
더합니다.

### `snes tiles`: planar 타일 렌더링

```sh
krpatch snes tiles game.sfc 1C0000 2000 font.png --bpp 2
krpatch snes tiles game.sfc 1C0000 2000 font.png --bpp 2 --rows 12 --stride 20   # 0x20바이트 칸의 8x12 글리프
krpatch snes tiles vram.bin 4000 2000 vram.png --bpp 2 --tall                    # 타일 쌍으로 된 8x16 글리프
```

START 와 LENGTH 는 어떤 파일(롬, VRAM 덤프, 압축 푼 데이터)에서든 바이트
오프셋입니다.

### `snes bg`, `snes bgrefs`: VRAM/CGRAM 덤프에서 BG 레이어

```sh
krpatch snes bg vram.bin cgram.bin 0 0x1000 4 bg1.png             # 타일맵·CHR 워드 주소, bpp
krpatch snes bgrefs vram.bin --layer 0:0x1000:4 --layer 0x400:0x2000:4 --layer 0x800:0x3000:2 --range 6000-7FFF
```

`bgrefs` 는 각 레이어의 타일맵이 VRAM 범위의 어느 부분을 쓰는지 알려 줍니다.
새 글리프를 넣을 빈 VRAM 을 찾을 때 씁니다.

### `snes run`: 헤드리스 libretro 실행기

```sh
krpatch snes run cores/snes9x_libretro.dylib game.sfc out/ s_new.txt [save.srm] --watch 7E0010:2
```

입력 스크립트를 재생하면서 `f<frame>.png` 스크린샷, `end.png`, 덤프,
`wram.log`(프레임과 감시하는 WRAM 값, 값이 바뀔 때마다 한 줄)를 `out/` 에
씁니다. 끝나면 `OK <frames>` 를 출력합니다. 코어를 불러오지 못하면(파일 없음,
`retro_*` 심볼 없음, 롬 거부) stderr 에 `LOAD FAILED: ...` 를 출력하고 종료
코드 3으로 끝납니다. 코어가 전역 상태를 갖고 있으므로 프로세스 하나에
스크립트 하나만 돌리세요.

- `--watch ADDR[:SIZE]`(여러 번 가능): WRAM 오프셋 또는 `$7E`/`$7F` 주소와 크기, 1-4바이트.
- `--watch-fmt SPEC`: 감시 값에 쓸 Python 형식 지정자(기본값 `0<2*SIZE>X`).
- `--var KEY=VALUE` 또는 환경 변수 `LRVARS="k=v,k=v"`: 코어 옵션. `LRLOG=1` 또는 `-v`:
  코어 로그(코어의 형식 문자열을 인자 없이 출력합니다).
- `save.srm` 은 불러온 직후와 첫 프레임 뒤에 한 번 더 세이브 RAM 에 복사하고,
  디스크에서 읽는 코어를 위해 `out/<롬 이름>.srm` 으로도 씁니다.

스크립트 형식은 한 줄에 명령 하나이며, 프레임은 전원을 켠 때부터 셉니다.

```
500 start 4             500프레임부터 Start 를 4프레임 누름
800 a+b 2               A 와 B 를 함께 누름
900 tap a 40 2000       2000프레임까지 40프레임마다 A 를 4프레임씩 누름
1000 shot               스크린샷 f01000.png
1000 dump               wram_1000.bin 과 sram_1000.bin
1100 poke 0010 1234     1100프레임 뒤 16비트 WRAM 쓰기
3000 end                3000프레임 뒤 멈춤
```

버튼(대소문자 무관): `a b x y l r start select up down left right`. `#` 으로
시작하는 줄은 주석입니다. `end` 는 꼭 있어야 하고, end 프레임 뒤의 명령은
오류입니다. poke 와 watch 는 128 KB WRAM 안(그리고 코어가 내주는 범위 안)에
있어야 합니다. WRAM 포인터가 없는 코어(bsnes, Supafaust)에서는 poke 를 Pro
Action Replay 치트로 `--cheat-hold` 프레임(기본값 40) 동안 적용하며, 겹치는
poke 는 치트 슬롯을 따로 씁니다.

`examples/snes/run_all.sh` 는 모든 시나리오를 모든 코어(와 Mesen 2)에서 돌리고
실행마다 결과 한 줄을 모읍니다.

### `snes lua`: Mesen 2 스크립트

```sh
krpatch snes lua    # 함께 들어 있는 Lua 스크립트의 디렉터리를 출력
```

`Mesen --testrunner rom.sfc <script>` 와 `LIBDIR=$(krpatch snes lua)` 로 실행합니다.

| 스크립트 | 하는 일 |
| --- | --- |
| `lib.lua` | 공통 도우미: 스크린샷, 세이브 스테이트, 메모리 덤프, 입력 |
| `boot.lua` | 전원 켜기, 주기적 탭(`TAP`, `PERIOD`, `TAPUNTIL`), 누르기(`SEQ="start@400:3"`), `MAXF` 까지 `EVERY` 프레임마다 스크린샷 |
| `script.lua` | `krpatch snes run` 스크립트를 같은 해석 규칙으로 재생(`SCRIPT`, `SRM`, `WATCH_WRAM`, `WATCH_FMT`) |
| `seq.lua` | 세이브 스테이트에서 `SEQ="btn:frames,wait:frames"` 를 `POKE`/`WATCH` 와 함께 재생 |
| `poke_state.lua` | `STATE` 를 불러와 `POKE` 를 한 번 쓰고 `OUT` 에 저장 |
| `dumpsrm.lua` | 세이브 스테이트의 세이브 RAM 을 `save.srm` 으로 씀 |
| `probe/*.lua` | `watch`, `peek`, `wtrace`, `wdump`, `wrange`, `swatch`, `cgram`, `trace`, `regs`, `ppu`. 각 파일 첫 줄들에 환경 변수가 적혀 있고, 입력은 `boot.lua` 로 처리 |

모두 출력 파일을 `SHOT_DIR` 에 씁니다. `script.lua` 에는 `WATCH` 대신
`WATCH_WRAM` 을 쓰세요. zsh 가 `WATCH` 와 `WATCHFMT` 를 자체 파라미터로 씁니다.

## Python API

```python
from kr_patch import ips
from kr_patch.snes import header
from kr_patch.snes.dis65816 import disasm

rom = open("game.sfc", "rb").read()
mp = header.detect(rom)                 # LoROM / HiROM / ExHiROM / SA1
print(disasm(rom, 0x808000, 20, mapper=mp))
fixed, csum = header.fix(rom, mp)
patch = ips.make(rom, fixed)
```

## 계획

- `kr_patch.nds` 와 `krpatch nds ...` 로 NDS 지원.
- `game.toml`: 게임 프로젝트가 매퍼, 감시할 RAM, 에뮬레이터 조합, 시나리오를
  파일 하나에 적어 두어 명령에 넘길 인자를 줄입니다.

## 개발

```sh
uv venv -p 3.15.0 .venv && uv pip install -p .venv -e '.[test]'
.venv/bin/python -m pytest
```

## 라이선스

MIT. [LICENSE](LICENSE) 를 보세요.
