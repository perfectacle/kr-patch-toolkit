-- Play a `krpatch sfc run` input script on Mesen 2, so every emulator gets the same input.
-- Mesen 2 --testrunner; env: LIBDIR SCRIPT SHOT_DIR [SRM] [WATCH_WRAM="7E0010:2,..."] [WATCH_FMT="%06X"]
-- SRM is copied into the save RAM on the first frames, as the libretro runner does.
-- Writes f<frame>.png, end.png, wram_<frame>.bin/sram_<frame>.bin for dumps, and wram.log.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")

-- WRAM bus address of a $7E/$7F address or a WRAM offset, checked so `size` bytes fit
local function wram(a, size, what)
  if a >= 0x7E0000 and a <= 0x7FFFFF then a = a - 0x7E0000 end
  if a + size > 0x20000 then error(string.format("%s: $%X + %d bytes is outside WRAM", what, a, size)) end
  return 0x7E0000 + a
end

local BUTTONS = {a=1, b=1, x=1, y=1, l=1, r=1, start=1, select=1, up=1, down=1, left=1, right=1}
local function buttons(spec, n)
  spec = spec:lower()
  for b in spec:gmatch("[^+]+") do
    if not BUTTONS[b] then error(string.format("line %d: unknown button '%s'", n, b)) end
  end
  return spec
end

local presses, shots, dumps, pokes, last = {}, {}, {}, {}, nil
local frames = {}
local n = 0
for line in io.lines(os.getenv("SCRIPT")) do
  n = n + 1
  local p = {}
  for w in line:gmatch("%S+") do p[#p + 1] = w end
  if #p > 0 and p[1]:sub(1, 1) ~= "#" then
    if #p < 2 then error(string.format("line %d: expected 'frame command ...'", n)) end
    local f, cmd = tonumber(p[1]), p[2]:lower()
    if cmd == "end" then last = f
    else
      frames[#frames + 1] = {f, n}
      if cmd == "shot" then shots[f] = true
      elseif cmd == "dump" then dumps[f] = true
      elseif cmd == "poke" then
        pokes[f] = pokes[f] or {}
        pokes[f][#pokes[f] + 1] = {wram(tonumber(p[3], 16), 2, "line " .. n), tonumber(p[4], 16) & 0xFFFF}
      elseif cmd == "tap" then
        local b = buttons(p[3], n)
        for t = f, tonumber(p[5]) - 1, tonumber(p[4]) do presses[#presses + 1] = {t, t + 4, b} end
      else presses[#presses + 1] = {f, f + tonumber(p[3]), buttons(cmd, n)} end
    end
  end
end
if not last then error("script has no 'end' command") end
for _, fr in ipairs(frames) do
  if fr[1] > last then error(string.format("line %d: frame is after 'end' at frame %d", fr[2], last)) end
end

local watches = {}
for a, sz in string.gmatch(os.getenv("WATCH_WRAM") or "", "(%x+):?(%d*)") do
  sz = tonumber(sz) or 1
  if sz < 1 or sz > 4 then error("WATCH_WRAM " .. a .. ": size must be 1-4 bytes") end
  watches[#watches + 1] = {wram(tonumber(a, 16), sz, "WATCH_WRAM " .. a), sz}
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
