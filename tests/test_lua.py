"""lua/script.lua must accept and reject the same scripts as the Python parser.

Runs the script under a stand-in `emu` table with a stock Lua 5.3+ interpreter.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from sfc_kr.harness import script

LUA_DIR = Path(__file__).resolve().parent.parent / "lua"

STUB = r"""
local cb
local mem = {}
local keys = {__index = function(_, k) return k end}
emu = {
  memType = setmetatable({}, keys), eventType = setmetatable({}, keys), callbackType = setmetatable({}, keys),
  addEventCallback = function(f, t) if t == "endFrame" then cb = f end end,
  addMemoryCallback = function() end, removeMemoryCallback = function() end, setInput = function() end,
  read = function(a) return mem[a] or 0 end,
  write = function(a, v) mem[a] = v end,
  write16 = function(a, v) mem[a] = v & 0xFF; mem[a + 1] = v >> 8 end,
  getMemorySize = function() return 16 end,
  takeScreenshot = function() return "png" end,
  createSavestate = function() return "" end,
  stop = function() STOPPED = true end,
}
dofile(arg[1])
for _ = 1, 100000 do if STOPPED then break end cb() end
"""


def _lua():
    for name in ("lua5.4", "lua5.3", "lua"):
        exe = shutil.which(name)
        if exe:
            v = subprocess.run([exe, "-v"], capture_output=True, text=True)
            if "Lua 5.3" in v.stdout + v.stderr or "Lua 5.4" in v.stdout + v.stderr:
                return exe
    return None


LUA = _lua()
pytestmark = pytest.mark.skipif(LUA is None, reason="needs a Lua 5.3+ interpreter")


def _run(tmp_path, text, watch=""):
    (tmp_path / "s.txt").write_text(text)
    (tmp_path / "stub.lua").write_text(STUB)
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    env = dict(os.environ, LIBDIR=str(LUA_DIR), SCRIPT=str(tmp_path / "s.txt"), SHOT_DIR=str(out),
               WATCH_WRAM=watch)
    return subprocess.run([LUA, str(tmp_path / "stub.lua"), str(LUA_DIR / "script.lua")],
                          capture_output=True, text=True, env=env), out


def test_runs_a_script(tmp_path):
    r, out = _run(tmp_path, "2 A 2\n3 shot\n4 poke 7E0010 1234\n5 dump\n6 end\n", watch="10:2")
    assert r.returncode == 0, r.stderr
    assert (out / "wram.log").read_text().splitlines() == ["1 0000", "4 1234"]
    assert (out / "f00003.png").exists() and (out / "end.png").exists()
    assert (out / "wram_5.bin").exists() and (out / "sram_5.bin").exists()


@pytest.mark.parametrize("text,match", [
    ("10 z 4\n20 end\n", "unknown button"),
    ("10\n20 end\n", "line 1"),
    ("10 poke 1FFFF 1\n20 end\n", "outside WRAM"),
    ("10 poke 7D0000 1\n20 end\n", "outside WRAM"),
    ("10 shot\n", "no 'end'"),
    ("10 end\n20 shot\n", "after 'end'"),
])
def test_rejects_like_python(tmp_path, text, match):
    with pytest.raises(ValueError):
        script.parse(text.splitlines())
    r, _ = _run(tmp_path, text)
    assert r.returncode != 0 and match in r.stderr


def test_rejects_bad_watch(tmp_path):
    r, _ = _run(tmp_path, "10 end\n", watch="1FFFF:2")
    assert r.returncode != 0 and "outside WRAM" in r.stderr
