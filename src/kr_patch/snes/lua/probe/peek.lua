-- At frame PEEKF log 16-bit values at PEEK addresses (hex, comma separated) to peek.txt.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local f = 0
local at = tonumber(os.getenv("PEEKF"))
emu.addEventCallback(function()
  f = f + 1
  if f == at then
    local t = {}
    for a in string.gmatch(os.getenv("PEEK"), "[^,]+") do
      t[#t + 1] = string.format("%s=%04X", a, emu.read16(tonumber(a, 16), emu.memType.snesMemory))
    end
    L.write("peek.txt", table.concat(t, " "))
  end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
