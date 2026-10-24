-- Log writes to WADDR..WADDR+2 (hex, CPU address) after frame WFROM: frame, PC, value; wtrace.txt at the end.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local addr = tonumber(os.getenv("WADDR"), 16)
local from = tonumber(os.getenv("WFROM") or "0")
local f, log = 0, {}
emu.addMemoryCallback(function(a, v)
  if f < from or #log > 300 then return end
  local s = emu.getState()
  log[#log + 1] = string.format("%d %02X%04X %06X=%02X", f, s["cpu.k"], s["cpu.pc"], a, v)
end, emu.callbackType.write, addr, addr + 2)
local maxf = tonumber(os.getenv("MAXF") or "1500")
emu.addEventCallback(function()
  f = f + 1
  if f == maxf - 1 then L.write("wtrace.txt", table.concat(log, "\n")) end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
