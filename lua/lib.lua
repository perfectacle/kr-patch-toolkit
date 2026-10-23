-- Savestate calls are only legal inside a main-CPU exec callback, so queue them
-- and run them from a one-shot exec hook on the next instruction.
local M = {}
M.out = os.getenv("SHOT_DIR") or "."
local pending = {}
local hook
local function runPending()
  local list = pending; pending = {}
  emu.removeMemoryCallback(hook, emu.callbackType.exec, 0, 0xFFFFFF)
  hook = nil
  for _, fn in ipairs(list) do fn() end
end
function M.defer(fn)
  pending[#pending + 1] = fn
  if not hook then hook = emu.addMemoryCallback(runPending, emu.callbackType.exec, 0, 0xFFFFFF) end
end
function M.write(name, data) local f = assert(io.open(M.out .. "/" .. name, "wb")); f:write(data); f:close() end
function M.readFile(p) local f = assert(io.open(p, "rb")); local d = f:read("*a"); f:close(); return d end
function M.saveState(name) M.defer(function() M.write(name, emu.createSavestate()) end) end
function M.loadState(path) local d = M.readFile(path); M.defer(function() emu.loadSavestate(d) end) end
function M.shot(name) M.write(name, emu.takeScreenshot()) end
function M.dump(name, memType, size)
  local t = {}
  for i = 0, size - 1 do t[#t + 1] = string.char(emu.read(i, memType)) end
  M.write(name, table.concat(t))
end
-- Input must be applied from the inputPolled event, otherwise the game never sees it.
M.held = nil
emu.addEventCallback(function() if M.held then emu.setInput(M.held, 0) end end, emu.eventType.inputPolled)
function M.press(btns) M.held = btns end
function M.release() M.held = nil end
return M
