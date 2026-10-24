-- From frame FROM to TO record every executed PRG ROM offset with the CPU address it first ran at;
-- cover.txt lines "OFFSET ADDR COUNT" (hex, hex, decimal) for `krpatch nes listing`.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local from, to = tonumber(os.getenv("FROM") or "1"), tonumber(os.getenv("TO") or os.getenv("MAXF") or "1500") - 1
local rom = emu.memType.nesPrgRom
local size = emu.getMemorySize(rom)
local n, cnt, cpu, cb = 0, {}, {}, nil
-- Callbacks registered on PRG ROM still receive the CPU address, so it is converted here.
local function onExec(addr)
  local off = emu.convertAddress(addr, L.mem).address
  local c = cnt[off]
  if c then cnt[off] = c + 1 else cnt[off] = 1; cpu[off] = addr end
end
emu.addEventCallback(function()
  n = n + 1
  if n == from then cb = emu.addMemoryCallback(onExec, emu.callbackType.exec, 0, size - 1, emu.cpuType.nes, rom) end
  if n == to then
    emu.removeMemoryCallback(cb, emu.callbackType.exec, 0, size - 1, emu.cpuType.nes, rom)
    local t = {}
    for off, c in pairs(cnt) do t[#t + 1] = string.format("%05X %04X %d", off, cpu[off], c) end
    table.sort(t)
    L.write("cover.txt", table.concat(t, "\n") .. "\n")
  end
end, emu.eventType.endFrame)
L.drive()
