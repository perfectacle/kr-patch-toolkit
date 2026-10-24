-- From frame WF to WT log 16-bit values at WATCH addresses (hex, comma separated) each frame; watch.txt at the end.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local f, log = 0, {}
local a, b = tonumber(os.getenv("WF")), tonumber(os.getenv("WT"))
emu.addEventCallback(function()
  f = f + 1
  if f >= a and f <= b then
    local t = {tostring(f)}
    for x in string.gmatch(os.getenv("WATCH"), "[^,]+") do
      t[#t + 1] = string.format("%s=%04X", x, emu.read16(tonumber(x, 16), emu.memType.snesMemory))
    end
    log[#log + 1] = table.concat(t, " ")
  end
  if f == b then L.write("watch.txt", table.concat(log, "\n")) end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
