-- At each exec of the CALLS addresses (hex, comma separated) log frame, address, A, X, Y and the
-- caller: the return address on the stack, ret=BB:AAAA. The bank byte is only meaningful when the
-- address is entered by JSL; after JSR the low 16 bits are the caller's and BB is whatever was
-- on the stack. Stops logging after LIMIT lines (default 100000); calls.txt at the end.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local f, log = 0, {}
local limit = tonumber(os.getenv("LIMIT") or "100000")
local m = emu.memType.snesMemory
local calls = os.getenv("CALLS")
if not calls or calls == "" then error("set CALLS to the addresses to log, e.g. CALLS=838200,00CD60") end
for a in string.gmatch(calls, "[^,]+") do
  local addr = tonumber(a, 16)
  emu.addMemoryCallback(function()
    if #log >= limit then return end
    local s = emu.getState()
    local sp = s["cpu.sp"]
    local ret = ((emu.read(sp + 1, m) | emu.read(sp + 2, m) << 8) + 1) & 0xFFFF
    log[#log + 1] = string.format("%d %06X A=%04X X=%04X Y=%04X ret=%02X:%04X", f, addr, s["cpu.a"], s["cpu.x"],
      s["cpu.y"], emu.read(sp + 3, m), ret)
  end, emu.callbackType.exec, addr, addr)
end
local maxf = tonumber(os.getenv("MAXF") or "1500")
emu.addEventCallback(function()
  f = f + 1
  if f == maxf - 1 then L.write("calls.txt", table.concat(log, "\n") .. "\n") end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
