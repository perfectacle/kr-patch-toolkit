-- At frame DUMPF write WSTART..+WLEN (hex, CPU addresses) to wram.bin.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local f = 0
local at = tonumber(os.getenv("DUMPF"))
local a0 = tonumber(os.getenv("WSTART"), 16)
local n = tonumber(os.getenv("WLEN"), 16)
emu.addEventCallback(function()
  f = f + 1
  if f == at then
    local b = {}
    for i = 0, n - 1 do b[#b + 1] = string.char(emu.read(a0 + i, emu.memType.snesMemory)) end
    L.write("wram.bin", table.concat(b))
  end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
