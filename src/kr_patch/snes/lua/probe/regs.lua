-- At each exec of DUMPAT (hex, comma separated) log frame, A, X, D, 16 SRAM bytes from
-- SRAMAT (hex) and 24 stack bytes; regs.txt at the end.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local f, log = 0, {}
local sa = tonumber(os.getenv("SRAMAT") or "0", 16)
for a in string.gmatch(os.getenv("DUMPAT"), "[^,]+") do
  emu.addMemoryCallback(function()
    local s = emu.getState()
    local b = {}
    for i = 0, 15 do b[#b + 1] = string.format("%02X", emu.read(sa + i, emu.memType.snesSaveRam)) end
    local st = {}
    for i = 1, 24 do st[#st + 1] = string.format("%02X", emu.read(s["cpu.sp"] + i, emu.memType.snesMemory)) end
    log[#log + 1] = string.format("%d %s A=%04X X=%04X D=%04X sram=%s stack=%s", f, a, s["cpu.a"], s["cpu.x"], s["cpu.d"], table.concat(b, " "), table.concat(st, " "))
  end, emu.callbackType.exec, tonumber(a, 16), tonumber(a, 16))
end
local maxf = tonumber(os.getenv("MAXF") or "1500")
emu.addEventCallback(function()
  f = f + 1
  if f == maxf - 1 then L.write("regs.txt", table.concat(log, "\n")) end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
