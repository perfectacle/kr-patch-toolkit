-- Savestate calls are only legal inside a CPU exec callback, so queue them
-- and run them from a one-shot exec hook on the next instruction.
local M = {}
M.out = os.getenv("SHOT_DIR") or "."
M.mem = emu.memType.nesMemory
local pending = {}
local hook
local function runPending()
  local list = pending; pending = {}
  emu.removeMemoryCallback(hook, emu.callbackType.exec, 0, 0xFFFF)
  hook = nil
  for _, fn in ipairs(list) do fn() end
end
function M.defer(fn)
  pending[#pending + 1] = fn
  if not hook then hook = emu.addMemoryCallback(runPending, emu.callbackType.exec, 0, 0xFFFF) end
end
function M.write(name, data) local f = assert(io.open(M.out .. "/" .. name, "wb")); f:write(data); f:close() end
function M.readFile(p) local f = assert(io.open(p, "rb")); local d = f:read("*a"); f:close(); return d end
function M.saveState(name) M.defer(function() M.write(name, emu.createSavestate()) end) end
function M.loadState(path) local d = M.readFile(path); M.defer(function() emu.loadSavestate(d) end) end
function M.shot(name) M.write(name, emu.takeScreenshot()) end
function M.dump(name, memType, size)
  size = size or emu.getMemorySize(memType)
  local t = {}
  for i = 0, size - 1 do t[#t + 1] = string.char(emu.read(i, memType)) end
  M.write(name, table.concat(t))
end
-- Every RAM a board can have; the ones it lacks (size 0) are skipped.
M.areas = {
  {"ram", emu.memType.nesInternalRam}, {"wram", emu.memType.nesWorkRam}, {"sram", emu.memType.nesSaveRam},
  {"chr", emu.memType.nesChrRam}, {"nt", emu.memType.nesNametableRam}, {"pal", emu.memType.nesPaletteRam},
  {"oam", emu.memType.nesSpriteRam},
}
function M.dumpAll(prefix)
  for _, a in ipairs(M.areas) do
    local size = emu.getMemorySize(a[2])
    if size > 0 then M.dump(prefix .. "." .. a[1], a[2], size) end
  end
end
-- PRG ROM offset of a CPU address under the current bank mapping, or nil.
function M.prgOffset(addr)
  local c = emu.convertAddress(addr, M.mem)
  if c and c.memType == emu.memType.nesPrgRom then return c.address end
  return nil
end
-- Probes end by running the input driver: boot.lua (power on) unless DRIVER names another,
-- e.g. DRIVER=$LIBDIR/seq.lua to start from a savestate.
function M.drive()
  dofile(os.getenv("DRIVER") or (os.getenv("LIBDIR") .. "/boot.lua"))
end
-- Input must be applied from the inputPolled event, otherwise the game never sees it.
M.held = nil
emu.addEventCallback(function() if M.held then emu.setInput(M.held, 0) end end, emu.eventType.inputPolled)
function M.press(btns) M.held = btns end
function M.release() M.held = nil end
return M
