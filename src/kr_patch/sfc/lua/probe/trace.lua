-- Count executions of PCs listed in TRACE (hex, comma separated) and log registers and the
-- 16-bit values at LOG addresses (hex, comma separated, optional) at each hit; trace.txt at the end.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local f, hits, log = 0, {}, {}
local extra = {}
for a in string.gmatch(os.getenv("LOG") or "", "[^,]+") do extra[#extra + 1] = a end
local limit = tonumber(os.getenv("LIMIT") or "400")
for a in string.gmatch(os.getenv("TRACE"), "[^,]+") do
  local addr = tonumber(a, 16)
  emu.addMemoryCallback(function()
    hits[a] = (hits[a] or 0) + 1
    if #log < limit then
      local m = emu.memType.snesMemory
      local st = emu.getState()
      local t = {string.format("%d %s A=%04X X=%04X Y=%04X D=%04X DB=%02X", f, a, st["cpu.a"], st["cpu.x"], st["cpu.y"], st["cpu.d"], st["cpu.dbr"])}
      for _, x in ipairs(extra) do t[#t + 1] = string.format("%s=%04X", x, emu.read16(tonumber(x, 16), m)) end
      log[#log + 1] = table.concat(t, " ")
    end
  end, emu.callbackType.exec, addr, addr)
end
local maxf = tonumber(os.getenv("MAXF") or "1500")
emu.addEventCallback(function()
  f = f + 1
  if f == maxf - 1 then
    local t = {}
    for k, v in pairs(hits) do t[#t + 1] = k .. " " .. v end
    L.write("trace.txt", table.concat(t, "\n") .. "\n---\n" .. table.concat(log, "\n"))
  end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
