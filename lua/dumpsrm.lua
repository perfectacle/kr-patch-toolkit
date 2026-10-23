-- Write the save RAM of a Mesen 2 save state to save.srm (Mesen 2 --testrunner).
-- env: LIBDIR STATE SHOT_DIR
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
L.loadState(os.getenv("STATE"))
local n = 0
emu.addEventCallback(function()
  n = n + 1
  if n == 5 then
    local t = emu.memType.snesSaveRam
    local size = emu.getMemorySize(t)
    local b = {}
    for i = 0, size - 1 do b[#b + 1] = string.char(emu.read(i, t)) end
    L.write("save.srm", table.concat(b))
    L.shot("shot.png")
    emu.stop(0)
  end
end, emu.eventType.endFrame)
