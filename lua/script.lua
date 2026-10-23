-- Play an `sfckr run` input script on Mesen 2, so every emulator gets the same input.
-- Mesen 2 --testrunner; env: LIBDIR SCRIPT SHOT_DIR [SRM] [WATCH_WRAM="7E0052:3,..."] [WATCH_FMT="%06X"]
-- SRM is copied into the save RAM on the first frames, as the libretro runner does.
-- Writes f<frame>.png, end.png, wram_<frame>.bin/sram_<frame>.bin for dumps, and wram.log.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")

local function wram(a) if a >= 0x7E0000 then return a end return 0x7E0000 + a end

local presses, shots, dumps, pokes, last = {}, {}, {}, {}, 0
for line in io.lines(os.getenv("SCRIPT")) do
  local p = {}
  for w in line:gmatch("%S+") do p[#p + 1] = w end
  if #p >= 2 and p[1]:sub(1, 1) ~= "#" then
    local f = tonumber(p[1])
    if p[2] == "shot" then shots[f] = true
    elseif p[2] == "end" then last = f
    elseif p[2] == "dump" then dumps[f] = true
    elseif p[2] == "poke" then
      pokes[f] = pokes[f] or {}
      pokes[f][#pokes[f] + 1] = {wram(tonumber(p[3], 16)), tonumber(p[4], 16) & 0xFFFF}
    elseif p[2] == "tap" then
      for t = f, tonumber(p[5]) - 1, tonumber(p[4]) do presses[#presses + 1] = {t, t + 4, p[3]} end
    else presses[#presses + 1] = {f, f + tonumber(p[3]), p[2]} end
  end
end

local watches = {}
for a, n in string.gmatch(os.getenv("WATCH_WRAM") or "", "(%x+):?(%d*)") do
  watches[#watches + 1] = {wram(tonumber(a, 16)), tonumber(n) or 1}
end
local fmt = os.getenv("WATCH_FMT")

local m = emu.memType.snesMemory
local srm = os.getenv("SRM") and L.readFile(os.getenv("SRM"))
local log = io.open(L.out .. "/wram.log", "w")
local prev, n = nil, 0
emu.addEventCallback(function()
  n = n + 1
  -- some cores clear SRAM during their first frame, so write it twice
  if srm and n <= 2 then
    for i = 1, #srm do emu.write(i - 1, srm:byte(i), emu.memType.snesSaveRam) end
  end
  local held
  for _, p in ipairs(presses) do
    if p[1] <= n and n < p[2] then
      held = held or {}
      for b in p[3]:gmatch("[^+]+") do held[b] = true end
    end
  end
  if held then L.press(held) else L.release() end
  for _, pk in ipairs(pokes[n] or {}) do emu.write16(pk[1], pk[2], m) end
  if #watches > 0 then
    local t = {}
    for _, w in ipairs(watches) do
      local v = 0
      for k = w[2] - 1, 0, -1 do v = v * 256 + emu.read(w[1] + k, m) end
      t[#t + 1] = string.format(fmt or ("%0" .. (w[2] * 2) .. "X"), v)
    end
    local s = table.concat(t, " ")
    if s ~= prev then log:write(n .. " " .. s .. "\n"); log:flush(); prev = s end
  end
  if dumps[n] then
    L.dump(string.format("wram_%d.bin", n), emu.memType.snesWorkRam, emu.getMemorySize(emu.memType.snesWorkRam))
    L.dump(string.format("sram_%d.bin", n), emu.memType.snesSaveRam, emu.getMemorySize(emu.memType.snesSaveRam))
  end
  if shots[n] then L.shot(string.format("f%05d.png", n)) end
  if n >= last then log:close(); L.shot("end.png"); emu.stop(0) end
end, emu.eventType.endFrame)
