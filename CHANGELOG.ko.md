# 변경 기록

[English](CHANGELOG.md) | 한국어

## 미출시

## 0.8.0

- NDS: `krpatch nds font info|sheet` 와 `kr_patch.nds.font` 가 NFTR 비트맵
  폰트(FINF, CGLP, CWDH, CMAP 종류 0·1·2)를 읽습니다. 글리프 비트맵, 코드에서
  글리프 번호, 폭을 얻고 글리프를 PNG 표로 그립니다.

## 0.7.0

- `ips make --rle`(와 `ips.make(..., rle=True)`)가 같은 바이트가 16개 이상
  이어지는 곳을 RLE 레코드로 씁니다. 롬을 늘리는 패치에 늘린 자리의 채움
  바이트가 그대로 실리지 않습니다. 기본값은 끔이고, 끄면 출력은 그대로입니다.

## 0.6.0

- `xdelta apply` 가 `xdelta3` 기본 설정의 LZMA 2차 압축(`-S lzma`)으로 만든
  패치를 읽습니다. 배포되는 패치는 대개 이렇게 만들어지는데 지금까지는
  오류였습니다. 다른 2차 압축(DJW, FGK)은 여전히 오류이고, 이제 어느 압축기인지
  밝힙니다. `vcdiff.header` 가 `secondary`(압축기 이름 또는 `None`)도
  돌려줍니다. `xdelta make` 출력은 그대로입니다.
- README: Mesen 2 와 MesenCE 에서 실행을 비교할 때 챙길 것(켤 때 RAM,
  스크린샷 시점, 세이브 스테이트를 만드는 판, 프레임 어긋남)을 적었습니다.

## 0.5.0

- FC(패미컴): `krpatch fc info|dis|listing|lua`. `kr_patch.fc.ines` 가 iNES·
  NES 2.0 헤더를 읽고, `kr_patch.fc.dis6502` 가 6502 코드를 PRG 오프셋과 CPU
  주소로 디스어셈블하며 커버리지로 실행된 명령만 리스팅합니다.
  `kr_patch/fc/lua/` 에 MesenCE Lua 스크립트 `boot.lua`, `seq.lua`,
  `mkstate.lua` 와 프로브 `cover`, `reads`, `writes`, `trace`, `watch` 를
  넣었습니다. 프로브에 `DRIVER=$LIBDIR/seq.lua` 를 주면 세이브스테이트에서
  시작합니다.

## 0.4.0

- **호환이 깨지는 변경:** 슈퍼 패미콤 도구의 이름을 모두 SFC 로 바꿨습니다.
  `krpatch snes …` 하위 명령은 `krpatch sfc …`(`dis`, `checksum`, `tiles`,
  `bg`, `bgrefs`, `run`, `lua`)입니다. 옛 이름은 별칭으로 남기지 않습니다.
  패키지 `kr_patch.snes` 는 `kr_patch.sfc`(Lua 스크립트는
  `kr_patch/sfc/lua/` 아래), `tiles.planar_to_snes`/`snes_to_planar` 는
  `planar_to_sfc`/`sfc_to_planar`, `examples/snes/` 는 `examples/sfc/` 입니다.
  명령의 출력은 그대로입니다.

## 0.3.0

- NDS: `krpatch nds info|ls|unpack|pack` 와 `kr_patch.nds.rom` 이 DS 롬의 헤더,
  이름 표, FAT, 오버레이 표를 읽고, 파일시스템을 폴더로 풀고, 파일을 바꾼 롬을
  다시 묶습니다(들어가면 제자리, 아니면 끝으로 옮김. FAT, 사용 크기, 장치 용량,
  헤더 CRC 를 고침).
- `krpatch lz11 decode|encode`(`kr_patch.lz11`): 닌텐도 LZ10/LZ11 코덱.
  `--vram` 은 VRAM 으로 바로 푸는 BIOS 루틴을 위해 거리 1 참조를 쓰지 않습니다.
- `krpatch xdelta make|apply`(`kr_patch.vcdiff`): VCDIFF 패치. `make` 는 2차
  압축과 헤더의 파일 이름 없이 `xdelta3` 를 돌리고, `apply` 는 창마다
  Adler-32 를 확인하는 순수 Python 디코더입니다.
- `krpatch linear`(`kr_patch.linear`): 1/2/4/8bpp 선형 비트맵을 바이트 안 픽셀
  순서를 골라 렌더링합니다.
- CI 가 `xdelta3` 를 설치해 `xdelta make` 테스트를 돌립니다.
- `examples/snes/run_all.sh`: `MESENCE`(세이브 폴더는 `MESENCE_SAVES`)를 주면
  보관 처리된 Mesen 2 의 후속인 MesenCE 에서도 모든 시나리오를 돌립니다.
  `MESEN` 은 전과 같이 Mesen 2 를 돌립니다.
- 함께 들어 있는 Lua 스크립트(`krpatch snes lua`)를 Mesen 2.1.1 과 MesenCE
  2.2.1 에서 확인했습니다. 고치지 않고 두 판에서 그대로 돌아갑니다.

## 0.2.0

녹음한 게임 음악을 다루는 도구를 더했습니다. numpy 2.5.2 이상이 필요합니다.

- `audio`(`krpatch audio ...`). 채널을 모노로 섞지 않습니다.
  - `segments`: 무음으로 곡 경계 찾기.
  - `period`: 곡 하나의 스펙트럼 자기 유사도로 반복 주기 후보 찾기.
  - `loop`: 샘플 단위 주기와 이음매(기본값은 충분히 좋은 가장 이른 이음매)를
    찾아 equal-gain 크로스페이드와 이음매 뒤에서 가져온 꼬리를 붙인 반복
    재생용 파일과 JSON 을 씁니다. `--legacy` 는 이전 `make_loop.py`
    스크립트가 만든 파일을 바이트까지 똑같이 다시 만듭니다.
  - `seamcheck`: 이음매의 스펙트럼 플럭스를 같은 프레임 격자에서 잰 원래
    녹음, 또는 곡의 99번째 백분위수와 비교합니다.
  - `loudness`: 모노·스테레오의 BS.1770 / EBU R128 통합 음량. 무음이면 `null`.
  - WAV 입출력은 표준 라이브러리 `wave` 로 하며, 읽을 수 없거나 잘린 파일은
    오류입니다.
- `snes run --wav`: 코어가 내는 소리를 코어의 샘플레이트로 16비트 스테레오
  WAV 에 녹음합니다. 샘플은 들어오는 대로 디스크에 씁니다. 옵션을 주지 않으면
  동작은 그대로입니다.
- `lua/probe/`: APU 포트 쓰기(`apuports.lua`, `APUPORTS` 로 포트 거르기),
  S-DSP 음성 엔벨로프(`voices.lua`), 함수 호출과 복귀 주소(`calls.lua`).
- sdist 에 한국어 README 와 변경 기록을 넣습니다.

## 0.1.0

첫 릴리스입니다. Python 3.15 가 필요합니다.

기종과 무관한 도구(`kr_patch`):

- `ips`: 생성·적용, RLE 레코드와 truncation 확장, 512바이트 카피어 헤더가 붙은
  덤프용 출력(선택), 레코드 gap 설정.
- `lzss`: LZSS 코덱(12비트 거리, 4비트 길이).
- `diff`: 두 파일이 다른 바이트 범위.
- `shots`: 스크린샷 비교(채널별 허용 오차, 잘라내기, 디렉터리 모드)와
  모아 보기(contact sheet).
- `glyph`: 사각형 이식을 지원하는 JSON 글리프 저장소, 한글 도우미, 픽셀
  폰트용 ㅁ/ㅇ 보정(선택)을 곁들인 macOS Vision OCR.

SNES(`kr_patch.snes`):

- `mapper`: LoROM, HiROM, ExHiROM, SA-1(Super MMC 블록 레지스터).
- `header`: 내부 헤더 감지, 체크섬 확인과 수정(크기가 2의 거듭제곱이 아니면
  미러링), 카피어 헤더 처리.
- `dis65816`: 매퍼를 주입받는 65c816 디스어셈블러.
- `tiles`, `bg`: 1/2/4/8bpp 타일, planar 2bpp 변환, VRAM/CGRAM 덤프에서 BG
  레이어 렌더링, 타일맵의 VRAM 참조.
- `libretro`, `script`: 헤드리스 libretro 실행기와 그 입력 스크립트 형식
  (press, tap, shot, dump, poke, end, WRAM 값 감시, WRAM 포인터가 없는 코어용
  치트 대체).
- `lua/`: Mesen 2 도우미, Python 파서와 같은 규칙을 따르는 스크립트 재생기,
  프로브.

SNES 명령을 `krpatch snes ...` 아래에 둔 `krpatch` 명령줄 인터페이스.
