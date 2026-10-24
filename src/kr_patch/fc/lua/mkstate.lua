-- Run the input driver and at frame SAVEAT write a savestate named STATE (default start.mss)
-- and a screenshot of the same name with .png.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local at = tonumber(os.getenv("SAVEAT"))
local name = os.getenv("STATE_OUT") or "start.mss"
local n = 0
emu.addEventCallback(function()
  n = n + 1
  if n == at then
    L.saveState(name)
    L.shot((name:gsub("%.mss$", "")) .. ".png")
  end
end, emu.eventType.endFrame)
L.drive()
