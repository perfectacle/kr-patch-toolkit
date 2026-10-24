# kr-patch-toolkit

[English](README.md) | 한국어

번역 패치를 만들고 검증할 때 쓰는, 게임과 무관한 도구 모음입니다. 일부는
기종과도 무관하고(IPS 패치, LZSS 코덱, 파일 비교, 스크린샷 비교, macOS OCR 을
곁들인 비트맵 글리프 도구, 녹음에서 끊김 없이 반복되는 배경음악 잘라 내기),
나머지는 슈퍼패미컴(SNES)용입니다: 카트리지 매퍼,
헤더 체크섬, 65c816 디스어셈블러, 타일·BG 렌더링, 헤드리스 libretro 테스트
실행기, Mesen 2·MesenCE 용 Lua 스크립트. 다른 기종(NDS 부터)도 지원할 예정이며, 기종마다
`krpatch <기종>` 명령을 따로 둡니다.

여러 한글 패치가 함께 쓰는 부분을 모은 것입니다. 한 게임에만 해당하는 것
(대본 형식, 포인터 테이블, RAM 주소)은 그 게임의 저장소에 두고 인자로
넘깁니다.

롬 데이터는 들어 있지 않습니다. 테스트는 작은 합성 롬 이미지를 직접 만들어
돌립니다.

## 설치

Python 3.15 이상이 필요합니다.

```sh
pip install git+https://github.com/perfectacle/kr-patch-toolkit@v0.2.0
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
| `krpatch audio segments\|period\|loop\|seamcheck\|loudness` | 곡 경계, 반복 주기, 반복 재생용 파일, 음량 |
| `krpatch snes dis` | 65c816 코드 디스어셈블 |
| `krpatch snes checksum` | 내부 헤더 체크섬 확인·수정 |
| `krpatch snes tiles` | planar 타일 렌더링 |
| `krpatch snes bg`, `bgrefs` | VRAM/CGRAM 덤프에서 BG 레이어 |
| `krpatch snes run` | 헤드리스 libretro 실행기 |
| `krpatch snes lua` | 함께 들어 있는 Mesen 2·MesenCE 용 Lua 스크립트 경로 |

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

### `audio`: 녹음에서 반복 재생용 파일 만들기

에뮬레이터에서 녹음한 게임 음악(예: `krpatch snes run --wav`)을 다룹니다.
입력은 16비트 PCM WAV 이고, 시간은 따로 적지 않으면 초 단위입니다. 채널을
모노로 섞지 않으므로 좌우 위상이 반대인 음성도 사라지지 않습니다.

```sh
krpatch audio segments rec.wav                                   # 곡: 시작, 끝, 길이
krpatch audio period rec.wav --start 36.4 --end 250.25           # 한 곡의 주기 후보
krpatch audio loop rec.wav song.wav --start 36.4 --end 250.25 --period-range 100:115 --json song.json
krpatch audio loop rec.wav song.wav --start 36.4 --end 250.25 --period 5136108 --seam-range 40:70
krpatch audio seamcheck song.wav --source rec.wav --render check.wav
krpatch audio loudness song.wav --target -20
```

`segments` 는 녹음을 무음에서 나눕니다. 모든 채널에 걸친 50 ms 창
(`--window`)의 RMS 가 30(`--threshold`, int16 단위) 아래인 구간이
0.3초(`--min-gap`) 이상 이어지면 곡 사이로 봅니다. `--gaps` 를 주면 곡 대신
무음 구간을 출력합니다.

`period` 는 구간의 로그 스펙트럼(512샘플마다 2048점 FFT)을 `--min-lag`(5초)
이상의 모든 지연만큼 밀어 자기 자신과 비교하고, 채널별 결과를 평균해 가장
비슷한 지연을 출력합니다. `segments` 로 찾은 곡 하나의 범위를 주세요. 여러
곡이나 곡 뒤의 무음까지 들어가면 그것들을 가로지르는 긴 지연이 높게
나옵니다. 반복할 때마다 파형이 조금씩 달라도 찾아내지만, 정밀도는 한
홉(48 kHz 에서 약 11 ms)입니다. 곡이 반복 구간 안에서 악절을 되풀이하면 진짜
주기의 배수나 약수가 가장 높게 나올 수 있습니다. 들어 보고 고른 다음
`--range` 나 `loop --period-range` 로 좁히세요.

`loop` 는 `--start` 부터 loopEnd 까지에 꼬리를 붙여 쓰고, 다음을 출력합니다.

```json
{"loopStart": 6.651625, "loopEnd": 113.653875, "duration": 114.153875,
 "loopStartSample": 319278, "loopEndSample": 5455386, "loopLengthSample": 5136108,
 "durationSamples": 5479386, "sampleRate": 48000, "period": 5136108,
 "sourceStartSample": 1747200, "seamScore": 0.9983}
```

위치는 새로 쓴 파일 기준입니다. `loopEndSample` 은 반복 구간에 들어가지
않습니다. 반복 구간은 `loopStartSample` 부터 `loopEndSample - 1` 까지이고,
`loopLengthSample` 이 주기입니다. `sourceStartSample` 은 파일이 녹음의 어디서
시작하는지입니다.

- 주기: `--period`(샘플)로 주거나, `--period-range` 안에서(없으면
  `--min-lag` 이상에서) `period` 와 같은 방법으로 찾습니다. 찾은 주기는 범위
  안 일곱 곳에서 파형 3초(`--refine-length`)를 한 주기 뒤와 맞춰 보아 샘플
  단위로 다듬습니다. `periodScore` 가 그 일치도입니다.
- 이음매 T: T 앞뒤 0.5초(`--window`)가 T + 주기 앞뒤 0.5초와 모든 채널을
  함께 보아 가장 잘 맞는 곳입니다. `--seam-range`(기본값: `--end` 앞까지
  녹음에 들어가는 범위 전체)를 50 ms 간격으로 훑고, 그 근처를 16샘플 간격으로
  훑은 다음, ±200샘플 안에서 양쪽 64샘플의 차이가 가장 작은 샘플로 정합니다.
  50 ms 간격 단계에서는 최고 점수와 0.003(`--seam-delta`) 이하로 차이 나는
  위치 중 가장 이른 곳을 고릅니다. 반복되는 부분 안이면 어디서 이어도
  매끄럽고, 이를수록 파일이 짧아지기 때문입니다. `--seam-pick best` 를 주면
  최고 점수 위치를 고릅니다. `seamScore` 는 T 에서의 일치도로, 반복이 거의
  같으면 1에 가깝고 반복마다 음성이 조금씩 다르면 0.9 안팎으로 낮아집니다.
- 크로스페이드: loopEnd 앞 60 ms(`--fade-ms`)를 T 앞 60 ms 로 바꿔 가서,
  되돌아가는 순간 이미 T 뒤와 같은 소리가 나게 합니다. 기본값
  `--fade-shape equal-gain`(들어오는 쪽 sin², 나가는 쪽 1 − sin²)은 좋은
  이음매처럼 양쪽 소리가 같을 때 음량을 그대로 둡니다. `equal-power`(sin/cos)는
  이런 소리에서 페이드 중간이 최대 3 dB 커집니다.
- 꼬리: T 뒤의 0.5초(`--tail`), 곧 플레이어가 되돌아간 뒤 듣는 소리입니다.
  손실 압축 인코더가 붙이는 여백이 반복 구간에 들어가지 않게 하려는 것이므로,
  플레이어는 파일 끝이 아니라 `loopStart`/`loopEnd` 로 반복해야 합니다.
  `--tail-from end` 를 주면 녹음에서 loopEnd 뒤에 이어지던 소리를 씁니다.
- `--end` 를 주지 않았는데 `--start` 뒤에서 `segments` 가 곡을 둘 이상
  찾으면 경고합니다.
- `--legacy` 는 이 명령들 이전의 스크립트처럼 동작합니다. equal-power
  페이드, loopEnd 뒤의 꼬리, 최고 점수 이음매, 채널 합으로 매긴 이음매
  점수를 씁니다. 그 스크립트로 만든 파일을 바이트까지 똑같이 다시 만듭니다.

`seamcheck` 는 플레이어처럼 인트로와 반복 구간 세 번(되돌아가기 두 번)을 이어
붙이고(`--render` 로 저장) 첫 번째로 되돌아가는 지점의 스펙트럼 플럭스, 곧
소리가 얼마나 급하게 커지는지를 잽니다. `--source` 를 주면 원래 녹음에서 곡이
loopEnd 를 지나 그대로 이어지는 같은 프레임도 잽니다. 파일이 녹음의 어디서
시작하는지는 JSON 의 `sourceStartSample` 이나 `--source-start` 로 압니다. 두
값은 같은 프레임 격자에서 재므로, 원래 녹음과 똑같이 이어지는 반복은 같은
값이 나옵니다. 결과는 JSON 으로 출력합니다. 이음매의 플럭스가 원래 녹음 값의
1.25배(`--ratio`)를 넘으면 종료 코드 1로 끝납니다. `--source` 가 없으면 곡
전체 99번째 백분위수의 1.25배를 기준으로 삼습니다. 반복이 북소리로 시작하면
원래 녹음에서도 그 지점의 값이 크므로 `--source` 를 주는 편이 정확합니다.

`loudness` 는 ITU-R BS.1770-4 / EBU R128 통합 음량(K 가중, 400 ms 블록,
-70 LUFS 절대 게이트와 -10 LU 상대 게이트)과 샘플 최댓값을 모노·스테레오에
대해 출력합니다. `--target LUFS` 를 주면 그 음량에 맞출 이득도 출력합니다.
무음이면 두 값 모두 `null` 이고 이득은 출력하지 않습니다. 트루 피크는 재지
않으므로 `ffmpeg -i song.wav -af ebur128=peak=true -f null -` 를 쓰세요.

읽을 수 없거나 잘린 WAV 파일은 오류입니다(종료 코드 2).

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
- `--wav OUT.wav`: 코어가 내는 소리를 코어가 알려 주는 샘플레이트의 16비트
  스테레오로 녹음합니다(bsnes 는 48000 Hz. snes9x 는 32040.5 Hz 를 알려 주는데,
  WAV 헤더에는 정수로 반올림해 적습니다). 샘플이 들어오는 대로 파일에 쓰므로
  오래 녹음해도 메모리에 쌓이지 않습니다.

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

`examples/snes/run_all.sh` 는 모든 시나리오를 모든 코어에서 돌리고(`MESEN` 을
주면 Mesen 2, `MESENCE` 를 주면 MesenCE 에서도) 실행마다 결과 한 줄을 모읍니다.

### `snes lua`: Mesen 2·MesenCE 스크립트

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
| `probe/*.lua` | `watch`, `peek`, `wtrace`, `wdump`, `wrange`, `swatch`, `cgram`, `trace`, `regs`, `ppu`, `apuports`, `voices`, `calls`. 각 파일 첫 줄들에 환경 변수가 적혀 있고, 입력은 `boot.lua` 로 처리 |
| `probe/apuports.lua` | APU 포트 `$2140-$2143` 에 쓴 값이 바뀔 때마다 프레임과 PC 와 함께 기록: 곡·효과음 명령. `APUPORTS="1,3"` 을 주면 그 포트만 기록 |
| `probe/voices.lua` | `VSTEP` 프레임마다 S-DSP 음성 8개의 엔벨로프 크기 |
| `probe/calls.lua` | `CALLS` 주소가 불릴 때마다 A, X, Y 와 복귀 주소 |

모두 출력 파일을 `SHOT_DIR` 에 씁니다. `script.lua` 에는 `WATCH` 대신
`WATCH_WRAM` 을 쓰세요. zsh 가 `WATCH` 와 `WATCHFMT` 를 자체 파라미터로 씁니다.

Mesen 2 는 2.1.1 이 마지막 버전이고, 저장소(SourMesen/Mesen2)는 2026년 6월에
보관 처리됐습니다. 뒤를 잇는 것은 MesenCE(nesdev-org/MesenCE)입니다. 실행
파일 이름이 그대로 `Mesen` 이라 위 명령을 두 판에서 똑같이 씁니다. MesenCE 는
`MesenCE` 폴더(macOS 에서는 `~/Library/Application Support/MesenCE`)가 있으면
거기에, 없으면 `Mesen2` 폴더에 데이터를 두고, 세이브는 그 안의 `Saves` 에
있습니다. 여기 들어 있는 스크립트는 모두 시험 롬으로 Mesen 2.1.1 과 MesenCE
2.2.1 에서 전원을 켤 때 RAM 을 0 으로 채워(`--snes.ramPowerOnState=AllZeros`)
돌려 봤습니다. 스크린샷, 메모리 덤프, 기록은 두 판이 같았고, 다른 곳은 한 판
안에서도 실행마다 달라지는 부분뿐이었습니다. 세이브 스테이트 파일만 바이트가
다릅니다.

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

from kr_patch.audio import loudness, wav

x, rate = wav.read("song.wav")          # int16, (프레임, 채널) 모양
print(loudness.integrated(x / 32768, rate))
```

## 계획

- `kr_patch.nds` 와 `krpatch nds ...` 로 NDS 지원.
- `game.toml`: 게임 프로젝트가 매퍼, 감시할 RAM, 에뮬레이터 조합, 시나리오를
  파일 하나에 적어 두어 명령에 넘길 인자를 줄입니다.

## 개발

```sh
uv sync --locked
uv run pytest
uv run ruff check .
```

`uv.lock` 은 개발·CI 환경을 고정하며, 나온 지 7일이 지난 릴리스만 받습니다.
코딩 에이전트는 [AGENTS.md](AGENTS.md) 에서 시작합니다.

## 라이선스

MIT. [LICENSE](LICENSE) 를 보세요.
