-- At frame CGF write CGRAM (512 bytes) to cgram.bin and a screenshot.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local f = 0
local at = tonumber(os.getenv("CGF"))
emu.addEventCallback(function()
  f = f + 1
  if f == at then
    local b = {}
    for i = 0, 511 do b[#b + 1] = string.char(emu.read(i, emu.memType.snesCgRam)) end
    L.write("cgram.bin", table.concat(b))
    L.shot("cg.png")
  end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
