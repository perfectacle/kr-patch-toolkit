-- Log writes to SRAM offsets SFROM..STO (hex) after frame SWF: frame, PC, DB, offset, value; swatch.txt at the end.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local a, b = tonumber(os.getenv("SFROM"), 16), tonumber(os.getenv("STO"), 16)
local from = tonumber(os.getenv("SWF") or "0")
local f, log = 0, {}
emu.addMemoryCallback(function(addr, v)
  if f < from or #log > 200 then return end
  local s = emu.getState()
  log[#log + 1] = string.format("%d pc=%02X%04X db=%02X %04X=%02X", f, s["cpu.k"], s["cpu.pc"], s["cpu.dbr"], addr, v)
end, emu.callbackType.write, a, b, emu.cpuType.snes, emu.memType.snesSaveRam)
local maxf = tonumber(os.getenv("MAXF") or "1500")
emu.addEventCallback(function()
  f = f + 1
  if f == maxf - 1 then L.write("swatch.txt", table.concat(log, "\n")) end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
