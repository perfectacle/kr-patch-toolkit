-- Record 256-byte WRAM pages ($7E/$7F) that are ever written; wpages.txt at the end.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local hit = {}
emu.addMemoryCallback(function(addr) hit[addr >> 8] = true end, emu.callbackType.write, 0x7E0000, 0x7FFFFF)
local f = 0
local maxf = tonumber(os.getenv("MAXF") or "1500")
emu.addEventCallback(function()
  f = f + 1
  if f == maxf - 1 then
    local t = {}
    for k in pairs(hit) do t[#t + 1] = string.format("%04X", k) end
    table.sort(t)
    L.write("wpages.txt", table.concat(t, "\n"))
  end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
