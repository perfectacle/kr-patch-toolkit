-- Replay a button script from a savestate.
-- SEQ format: "btn:frames,wait:frames,..." e.g. "start:3,wait:30,a:3"
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
L.loadState(os.getenv("STATE"))
local steps = {}
for tok in string.gmatch(os.getenv("SEQ") or "", "[^,]+") do
  local b, f = tok:match("([%w+]+):(%d+)")
  steps[#steps + 1] = {b, tonumber(f)}
end
-- POKE="0050=FF;..." is re-applied every frame (CPU addresses).
local pokes = {}
for a, v in string.gmatch(os.getenv("POKE") or "", "(%x+)=(%x+)") do pokes[#pokes + 1] = {tonumber(a, 16), tonumber(v, 16)} end
-- WATCH="name=0050:2;..." logs little-endian values (CPU addresses, 1-4 bytes) to watch.txt
-- every EVERY frames and at the end, so state can be read as text instead of from screenshots.
local watches = {}
for name, a, len in string.gmatch(os.getenv("WATCH") or "", "([%w_]+)=(%x+):?(%d*)") do
  watches[#watches + 1] = {name, tonumber(a, 16), tonumber(len) or 1}
end
local watchLog = {}
local function sample(tag)
  if #watches == 0 then return end
  local parts = {tag}
  for _, w in ipairs(watches) do
    local v = 0
    for k = w[3] - 1, 0, -1 do v = v * 256 + emu.read(w[2] + k, L.mem) end
    parts[#parts + 1] = string.format("%s=%0" .. (w[3] * 2) .. "X", w[1], v)
  end
  watchLog[#watchLog + 1] = table.concat(parts, " ")
end
local every = tonumber(os.getenv("EVERY") or "60")
local tail = tonumber(os.getenv("TAIL") or "120")
local shots = os.getenv("SHOTS") ~= "0"
local i, left, n, done = 1, nil, 0, nil
emu.addEventCallback(function()
  n = n + 1
  if n < 3 then return end
  for _, p in ipairs(pokes) do emu.write(p[1], p[2], L.mem) end
  L.release()
  if i <= #steps then
    local s = steps[i]
    if left == nil then left = s[2] end
    if s[1] ~= "wait" then
      local t = {}
      for b in s[1]:gmatch("[^+]+") do t[b] = true end
      L.press(t)
    end
    left = left - 1
    if left <= 0 then i = i + 1; left = nil end
  elseif not done then done = n end
  if every > 0 and n % every == 0 then
    if shots then L.shot(string.format("q%05d.png", n)) end
    sample(string.format("f%05d", n))
  end
  if done and n == done + tail then
    sample("end")
    if #watchLog > 0 then L.write("watch.txt", table.concat(watchLog, "\n") .. "\n") end
    L.shot("end.png"); L.saveState("end.mss")
    L.dumpAll("end")
  end
  if done and n >= done + tail + 5 then emu.stop(0) end
end, emu.eventType.endFrame)
