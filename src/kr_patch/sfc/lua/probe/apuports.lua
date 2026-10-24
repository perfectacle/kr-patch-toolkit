-- Log CPU writes to the APU ports $2140-$2143 that change a port's value, from frame APUF (default 0):
-- frame, port, value, PC with bank; apuports.txt at the end. Song and sound effect commands show up
-- here between the bulk uploads of sound programs and samples. APUPORTS="1,3" limits the log to those
-- ports (default 0,1,2,3); uploads write thousands of times per frame, and only logged writes pay for
-- the CPU state read.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local f, log, last, want = 0, {}, {}, {}
local from = tonumber(os.getenv("APUF") or "0")
for p in string.gmatch(os.getenv("APUPORTS") or "0,1,2,3", "%d") do want[tonumber(p)] = true end
emu.addMemoryCallback(function(addr, value)
  local k = addr & 3
  if want[k] and last[k] ~= value then
    last[k] = value
    if f >= from then
      local s = emu.getState()
      log[#log + 1] = string.format("%d %04X %02X %02X:%04X", f, addr, value, s["cpu.k"], s["cpu.pc"])
    end
  end
end, emu.callbackType.write, 0x2140, 0x2143)
local maxf = tonumber(os.getenv("MAXF") or "1500")
emu.addEventCallback(function()
  f = f + 1
  if f == maxf - 1 then L.write("apuports.txt", table.concat(log, "\n") .. "\n") end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
