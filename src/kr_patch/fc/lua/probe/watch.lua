-- From frame WF to WT log the values at WATCH ("0050,0051:2", CPU addresses, 1-4 bytes little-endian)
-- each frame they change; watch.txt at frame WT.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local f, log, last = 0, {}, nil
local a, b = tonumber(os.getenv("WF") or "1"), tonumber(os.getenv("WT"))
local ws = {}
for x, len in string.gmatch(os.getenv("WATCH"), "(%x+):?(%d*)") do ws[#ws + 1] = {x, tonumber(x, 16), tonumber(len) or 1} end
emu.addEventCallback(function()
  f = f + 1
  if f >= a and f <= b then
    local t = {}
    for _, w in ipairs(ws) do
      local v = 0
      for k = w[3] - 1, 0, -1 do v = v * 256 + emu.read(w[2] + k, L.mem) end
      t[#t + 1] = string.format("%s=%0" .. (w[3] * 2) .. "X", w[1], v)
    end
    local s = table.concat(t, " ")
    if s ~= last then log[#log + 1] = f .. " " .. s; last = s end
  end
  if f == b then L.write("watch.txt", table.concat(log, "\n") .. "\n") end
end, emu.eventType.endFrame)
L.drive()
