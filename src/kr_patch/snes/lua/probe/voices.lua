-- Every VSTEP frames (default 6) log the envelope level of the eight S-DSP voices: frame and
-- eight values; voices.txt at the end. Voices that sound only briefly are often sound effects.
package.path = os.getenv("LIBDIR") .. "/?.lua;" .. package.path
local L = require("lib")
local f, log = 0, {}
local step = tonumber(os.getenv("VSTEP") or "6")
local maxf = tonumber(os.getenv("MAXF") or "1500")
emu.addEventCallback(function()
  f = f + 1
  if f % step == 0 then
    local s = emu.getState()
    local row = {tostring(f)}
    for v = 0, 7 do
      local key = "spc.dsp.voices[" .. v .. "].envVolume"
      if s[key] == nil then error("no " .. key .. " in emu.getState(); this Mesen version names DSP state differently") end
      row[#row + 1] = tostring(s[key])
    end
    log[#log + 1] = table.concat(row, " ")
  end
  if f == maxf - 1 then L.write("voices.txt", table.concat(log, "\n") .. "\n") end
end, emu.eventType.endFrame)
dofile(os.getenv("LIBDIR") .. "/boot.lua")
