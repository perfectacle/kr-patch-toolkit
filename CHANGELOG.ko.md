# 변경 기록

[English](CHANGELOG.md) | 한국어

## 미출시

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
