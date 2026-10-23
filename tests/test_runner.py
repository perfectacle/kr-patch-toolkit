"""Runner.run against a fake core: the ctypes callbacks are real, the core is Python."""
import ctypes as C
import ctypes.util

import pytest
from PIL import Image

from kr_patch.snes import libretro, script


class FakeCore:
    """Stands in for a CDLL. Attributes are plain functions so the runner can set .restype."""

    def __init__(self, wram_size=0x20000, expose_wram=True, load_ok=True):
        self.wram = C.create_string_buffer(wram_size)
        self.sram = C.create_string_buffer(0x2000)
        self.vbuf = C.create_string_buffer(256 * 224 * 2)
        self.calls, self.cheats, self.a_held = [], [], []
        self.frame = 0
        core = self

        def retro_set_environment(cb): core.env = cb
        def retro_set_video_refresh(cb): core.video = cb
        def retro_set_audio_sample(cb): pass
        def retro_set_audio_sample_batch(cb): pass
        def retro_set_input_poll(cb): pass
        def retro_set_input_state(cb): core.inp = cb

        def retro_init():
            core.calls.append("init")
            fmt = C.c_int(libretro.PIX_RGB565)
            core.env(10, C.addressof(fmt))

        def retro_load_game(gi):
            core.calls.append("load")
            return load_ok

        def retro_run():
            core.frame += 1
            core.a_held.append(core.inp(0, 1, 0, script.BUTTONS["a"]))
            core.video(C.addressof(core.vbuf), 256, 224, 512)

        def retro_get_memory_data(i):
            if i == libretro.MEM_SYSTEM_RAM:
                return C.addressof(core.wram) if expose_wram else None
            return C.addressof(core.sram)

        def retro_get_memory_size(i):
            return len(core.wram) if i == libretro.MEM_SYSTEM_RAM else len(core.sram)

        def retro_cheat_set(i, enabled, code): core.cheats.append((core.frame, i, enabled, code.decode()))
        def retro_cheat_reset(): core.cheats.append((core.frame, "reset"))
        def retro_unload_game(): core.calls.append("unload")
        def retro_deinit(): core.calls.append("deinit")

        for name, fn in list(locals().items()):
            if name.startswith("retro_"):
                setattr(self, name, fn)


@pytest.fixture
def rom(tmp_path):
    p = tmp_path / "t.sfc"
    p.write_bytes(bytes(0x8000))
    return p


def _run(monkeypatch, tmp_path, rom, fake, lines, **kw):
    monkeypatch.setattr(libretro, "load_core", lambda path: fake)
    r = libretro.Runner("fake", str(rom), str(tmp_path / "out"), script.parse(lines), **kw)
    return r, r.run()


def test_run_pokes_watches_dumps_shots(monkeypatch, tmp_path, rom):
    fake = FakeCore()
    lines = ["2 a 2", "5 poke 0010 1234", "6 shot", "7 dump", "10 end"]
    r, n = _run(monkeypatch, tmp_path, rom, fake, lines, watches=[script.Watch.parse("10:2")])
    out = tmp_path / "out"
    assert n == 10 and fake.frame == 10
    assert fake.wram.raw[0x10:0x12] == b"\x34\x12"
    assert (out / "wram.log").read_text().splitlines() == ["1 0000", "5 1234"]
    assert (out / "wram_7.bin").stat().st_size == 0x20000
    assert (out / "sram_7.bin").stat().st_size == 0x2000
    assert Image.open(out / "f00006.png").size == (256, 224)
    assert (out / "end.png").exists()
    # input for frame f is what the core sees during its f+1-th retro_run
    assert fake.a_held[1:5] == [0, 1, 1, 0]
    assert fake.calls == ["init", "load", "unload", "deinit"]


def test_poke_outside_core_wram(monkeypatch, tmp_path, rom):
    fake = FakeCore(wram_size=0x1000)
    with pytest.raises(ValueError, match="outside the core's 0x1000-byte WRAM"):
        _run(monkeypatch, tmp_path, rom, fake, ["5 poke 0FFF 1", "10 end"])
    assert fake.calls == ["init", "load", "unload", "deinit"]


def test_watch_outside_core_wram(monkeypatch, tmp_path, rom):
    fake = FakeCore(wram_size=0x1000)
    with pytest.raises(ValueError, match="watch"):
        _run(monkeypatch, tmp_path, rom, fake, ["10 end"], watches=[script.Watch.parse("FFF:2")])


def test_cheat_indices_and_expiry(monkeypatch, tmp_path, rom):
    fake = FakeCore(expose_wram=False)
    _run(monkeypatch, tmp_path, rom, fake, ["5 poke 0010 1234", "10 poke 0020 ABCD", "30 end"],
         cheat_hold=10)
    assert fake.cheats == [
        (5, 0, True, "7E001034"), (5, 1, True, "7E001112"),
        (10, 2, True, "7E0020CD"), (10, 3, True, "7E0021AB"),
        (15, 0, False, "7E001034"), (15, 1, False, "7E001112"),
        (20, 2, False, "7E0020CD"), (20, 3, False, "7E0021AB"),
        (20, "reset"),
    ]
    assert (tmp_path / "out" / "wram.log").read_text() == ""


def test_rejected_rom(monkeypatch, tmp_path, rom):
    fake = FakeCore(load_ok=False)
    with pytest.raises(libretro.LoadError, match="LOAD FAILED"):
        _run(monkeypatch, tmp_path, rom, fake, ["10 end"])
    assert fake.calls == ["init", "load", "deinit"]


def test_load_core_errors(tmp_path):
    with pytest.raises(libretro.LoadError, match="LOAD FAILED"):
        libretro.load_core(str(tmp_path / "missing_libretro.so"))
    libc = ctypes.util.find_library("c")
    if libc:
        with pytest.raises(libretro.LoadError, match="retro_"):
            libretro.load_core(libc)
