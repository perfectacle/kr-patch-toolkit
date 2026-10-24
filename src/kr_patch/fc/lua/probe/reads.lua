-- From frame FROM to TO count PRG ROM data reads per reading instruction;
-- reads.txt lines "pc=OFFSET(ADDR) n=COUNT range=LO-HI first=FRAME", PRG offsets, most reads first.
-- The 6502 also makes dummy reads (the byte after one-byte instructions, branch targets, return
-- addresses) and reads interrupt vectors, so only reads by instructions with a memory operand
-- (loads, compares, arithmetic, read-modify-write, JMP indirect) are counted, leaving out the
-- instruction's own bytes, the next opcode (an interrupt reads it twice) and $FFFA-$FFFF.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local from, to = tonumber(os.getenv("FROM") or "1"), tonumber(os.getenv("TO") or os.getenv("MAXF") or "1500") - 1
local rom = emu.memType.nesPrgRom
local size = emu.getMemorySize(rom)
-- instruction length by opcode (unofficial opcodes count as 1)
local LEN = "1211122112111331221112211311133132112221121133312211122113111331121112211211333122111221131113311211122112113331221112211311133112112221111133312211222113111311222122211211333122112221131133312211222112113331221112211311133122112221121133312211122113111331"
-- 1 for opcodes that read a memory operand
local DATA = "0100011000000110010001100100011001001110000011100100011001000110010001100000011001000110010001100100011000001110010001100100011000000000000000000000000000000000010011100000111001001110010011100100111000001110010001100100011001001110000011100100011001000110"
local n, st, cur, curEnd, reads, cbs = 0, {}, -1, -1, false, {}
-- Callbacks registered on PRG ROM still receive the CPU address, so it is converted here.
local curPc = 0
local function onExec(addr)
  cur = emu.convertAddress(addr, L.mem).address
  curPc = addr
  local op = emu.read(cur, rom)
  curEnd = cur + tonumber(LEN:sub(op + 1, op + 1))
  reads = DATA:byte(op + 1) == 49
end
local function onRead(addr)
  if not reads or addr >= 0xFFFA then return end
  local off = emu.convertAddress(addr, L.mem).address
  if off >= cur and off <= curEnd then return end
  local e = st[cur]
  if not e then e = {n = 0, lo = off, hi = off, f = n, pc = curPc}; st[cur] = e end
  e.n = e.n + 1
  if off < e.lo then e.lo = off end
  if off > e.hi then e.hi = off end
end
emu.addEventCallback(function()
  n = n + 1
  if n == from then
    cbs[1] = emu.addMemoryCallback(onExec, emu.callbackType.exec, 0, size - 1, emu.cpuType.nes, rom)
    cbs[2] = emu.addMemoryCallback(onRead, emu.callbackType.read, 0, size - 1, emu.cpuType.nes, rom)
  end
  if n == to then
    emu.removeMemoryCallback(cbs[1], emu.callbackType.exec, 0, size - 1, emu.cpuType.nes, rom)
    emu.removeMemoryCallback(cbs[2], emu.callbackType.read, 0, size - 1, emu.cpuType.nes, rom)
    local t = {}
    for off, e in pairs(st) do t[#t + 1] = {off, e} end
    table.sort(t, function(a, b) if a[2].n ~= b[2].n then return a[2].n > b[2].n end return a[1] < b[1] end)
    local out = {}
    for _, x in ipairs(t) do
      local e = x[2]
      out[#out + 1] = string.format("pc=%05X(%04X) n=%d range=%05X-%05X first=%d", x[1], e.pc, e.n, e.lo, e.hi, e.f)
    end
    L.write("reads.txt", table.concat(out, "\n") .. "\n")
  end
end, emu.eventType.endFrame)
L.drive()
