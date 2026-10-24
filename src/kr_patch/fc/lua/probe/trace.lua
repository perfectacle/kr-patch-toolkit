-- Count executions of the CPU addresses in TRACE (hex, comma separated) and log frame, PRG offset,
-- A X Y S P and the bytes at LOG addresses (hex, comma separated, optional) at each hit,
-- up to LIMIT lines; trace.txt at frame MAXF-1.
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
      local st = emu.getState()
      local off = L.prgOffset(addr)
      local t = {string.format("%d %s prg=%s A=%02X X=%02X Y=%02X S=%02X P=%02X", f, a,
        off and string.format("%05X", off) or "-", st["cpu.a"], st["cpu.x"], st["cpu.y"], st["cpu.sp"], st["cpu.ps"])}
      for _, x in ipairs(extra) do t[#t + 1] = string.format("%s=%02X", x, emu.read(tonumber(x, 16), L.mem)) end
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
    table.sort(t)
    L.write("trace.txt", table.concat(t, "\n") .. "\n---\n" .. table.concat(log, "\n"))
  end
end, emu.eventType.endFrame)
L.drive()
