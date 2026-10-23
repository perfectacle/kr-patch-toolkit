-- Derive a save state: load STATE, write POKE="addr=val;..." once (CPU bus
-- addresses), save to OUT.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
L.loadState(os.getenv("STATE"))
local n = 0
emu.addEventCallback(function()
  n = n + 1
  if n == 3 then
    for a, v in string.gmatch(os.getenv("POKE"), "(%x+)=(%x+)") do
      emu.write(tonumber(a, 16), tonumber(v, 16), emu.memType.snesMemory)
    end
  elseif n == 5 then
    L.saveState(os.getenv("OUT"))   -- runs on the next instruction
  elseif n == 8 then
    emu.stop(0)
  end
end, emu.eventType.endFrame)
