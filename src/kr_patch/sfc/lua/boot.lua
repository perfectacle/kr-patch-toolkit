-- Boot from power-on with periodic button taps and screenshots.
-- env: MAXF, EVERY (screenshot interval), TAP="A" buttons tapped every PERIOD frames for 4 frames,
--      TAPUNTIL (stop periodic taps at this frame), SEQ="start@400:3,..." (button@frame:len) explicit presses, SHOT_DIR
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local n = 0
local maxf = tonumber(os.getenv("MAXF") or "1500")
local every = tonumber(os.getenv("EVERY") or "60")
local period = tonumber(os.getenv("PERIOD") or "0")
local tap = os.getenv("TAP") or "a"
local tapUntil = tonumber(os.getenv("TAPUNTIL") or "999999")
local presses = {}
for b, f, l in string.gmatch(os.getenv("SEQ") or "", "([%w+]+)@(%d+):(%d+)") do
  presses[#presses + 1] = {b, tonumber(f), tonumber(l)}
end
emu.addEventCallback(function()
  n = n + 1
  L.release()
  local t = nil
  for _, p in ipairs(presses) do
    if n >= p[2] and n < p[2] + p[3] then
      t = t or {}
      for b in p[1]:gmatch("[^+]+") do t[b] = true end
    end
  end
  if not t and period > 0 and n < tapUntil and n % period < 4 then t = {}; for b in tap:gmatch("[^+]+") do t[b] = true end end
  if t then L.press(t) end
  if every > 0 and n % every == 0 then L.shot(string.format("f%05d.png", n)) end
  if n >= maxf then emu.stop(0) end
end, emu.eventType.endFrame)
