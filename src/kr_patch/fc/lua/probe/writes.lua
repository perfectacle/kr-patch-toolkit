-- From frame FROM log which instructions write to the WATCH ranges ("0000-07FF,6000-7FFF", CPU addresses),
-- one line per range and writing PC with its first frame, count and a sample; writes.txt at frame MAXF-1.
-- Write callbacks see the next instruction's PC, so the PC is taken from the last exec callback.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local from = tonumber(os.getenv("FROM") or "0")
local n, seen, order, cur = 0, {}, {}, 0
emu.addMemoryCallback(function(a) cur = a end, emu.callbackType.exec, 0, 0xFFFF)
for a, b in string.gmatch(os.getenv("WATCH"), "(%x+)-(%x+)") do
  local lo, hi = tonumber(a, 16), tonumber(b, 16)
  emu.addMemoryCallback(function(addr, value)
    if n < from then return end
    local key = string.format("%04X-%04X pc=%04X", lo, hi, cur)
    local e = seen[key]
    if not e then
      local off = L.prgOffset(cur)
      e = {first = n, count = 0, off = off and string.format("%05X", off) or "-",
           sample = string.format("addr=%04X val=%02X", addr, value)}
      seen[key] = e; order[#order + 1] = key
    end
    e.count = e.count + 1
  end, emu.callbackType.write, lo, hi)
end
local maxf = tonumber(os.getenv("MAXF") or "1500")
emu.addEventCallback(function()
  n = n + 1
  if n == maxf - 1 then
    local t = {}
    for _, k in ipairs(order) do
      local e = seen[k]
      t[#t + 1] = string.format("%s prg=%s first=%d n=%d %s", k, e.off, e.first, e.count, e.sample)
    end
    L.write("writes.txt", table.concat(t, "\n") .. "\n")
  end
end, emu.eventType.endFrame)
L.drive()
