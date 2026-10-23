"""Minimal headless libretro frontend for compatibility runs.

Plays a script (see harness.script) on a libretro core and writes f<frame>.png
screenshots, end.png, optional WRAM/SRAM dumps and wram.log (frame and the
watched WRAM values, one line per change) to the output directory.

env LRVARS="key=value,key=value" overrides core options; LRLOG=1 prints core logs.
"""
import ctypes as C
import os
import sys

from PIL import Image

from . import script as S

ENV_CB = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VID_CB = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUD_CB = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDB_CB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL_CB = C.CFUNCTYPE(None)
IN_CB = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
LOG_CB = C.CFUNCTYPE(None, C.c_int, C.c_char_p)

MEM_SAVE_RAM, MEM_SYSTEM_RAM = 0, 2
PIX_0RGB1555, PIX_XRGB8888, PIX_RGB565 = 0, 1, 2


class LogIface(C.Structure):
    _fields_ = [("log", C.c_void_p)]


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


def env_vars(s):
    return {k: v for k, v in (kv.split("=", 1) for kv in (s or "").split(",") if kv)}


def to_image(data, w, h, pitch, pixfmt):
    if pixfmt == PIX_RGB565:
        return Image.frombuffer("RGB", (w, h), data, "raw", "BGR;16", pitch, 1)
    if pixfmt == PIX_XRGB8888:
        return Image.frombuffer("RGBX", (w, h), data, "raw", "BGRX", pitch, 1).convert("RGB")
    return Image.frombuffer("RGB", (w, h), data, "raw", "BGR;15", pitch, 1)


class Runner:
    def __init__(self, core, rom, out, script, srm=None, watches=(), variables=None,
                 verbose=None, cheat_hold=40):
        self.core_path, self.rom_path, self.out = core, rom, out
        self.script = script
        self.srm = open(srm, "rb").read() if srm else None
        self.srm_path = srm
        self.watches = list(watches)
        self.verbose = bool(os.getenv("LRLOG")) if verbose is None else verbose
        vs = env_vars(os.getenv("LRVARS"))
        vs.update(variables or {})
        self.vars = {k: C.c_char_p(v.encode()) for k, v in vs.items()}
        self.cheat_hold = cheat_hold
        self.frame = 0
        self.pixfmt = PIX_0RGB1555
        self.last = None

    def _log(self, msg):
        if self.verbose:
            sys.stderr.write(msg)
            sys.stderr.flush()

    def _callbacks(self):
        sysdir = C.c_char_p(self.out.encode())
        log_fn = LOG_CB(lambda level, fmt: self._log(fmt.decode(errors="replace")))
        log_iface = LogIface(C.cast(log_fn, C.c_void_p))

        def env(cmd, data):
            self._log(f"ENV {cmd}\n")
            cmd &= 0xFFFF
            if cmd in (9, 31):            # GET_SYSTEM_DIRECTORY, GET_SAVE_DIRECTORY
                C.cast(data, C.POINTER(C.c_char_p))[0] = sysdir
                return True
            if cmd == 10:                 # SET_PIXEL_FORMAT
                self.pixfmt = C.cast(data, C.POINTER(C.c_int))[0]
                return True
            if cmd == 27:                 # GET_LOG_INTERFACE
                C.cast(data, C.POINTER(LogIface))[0] = log_iface
                return True
            if cmd == 15:                 # GET_VARIABLE
                key = C.cast(data, C.POINTER(C.c_char_p))[0].decode()
                if key in self.vars:
                    C.cast(data, C.POINTER(C.c_char_p))[1] = self.vars[key]
                    return True
                return False
            if cmd == 3:                  # GET_CAN_DUPE
                C.cast(data, C.POINTER(C.c_bool))[0] = True
                return True
            return False

        def video(data, w, h, pitch):
            if data:
                self.last = (C.string_at(data, pitch * h), w, h, pitch)

        def inp(port, device, index, id_):
            if port != 0 or device != 1:
                return 0
            return int(id_ in self.held)

        # ctypes callbacks must outlive the core's use of them
        self._keep = (sysdir, log_fn, log_iface, ENV_CB(env), VID_CB(video), AUD_CB(lambda l, r: None),
                      AUDB_CB(lambda d, n: n), POLL_CB(lambda: None), IN_CB(inp))
        return self._keep[3:]

    def save_png(self, path):
        data, w, h, pitch = self.last
        to_image(data, w, h, pitch, self.pixfmt).save(path)

    def _inject_srm(self, core):
        p, n = core.retro_get_memory_data(MEM_SAVE_RAM), core.retro_get_memory_size(MEM_SAVE_RAM)
        if p:
            C.memmove(p, self.srm, min(n, len(self.srm)))
        self._log(f"SRAM ptr={p} size={n}\n")

    def run(self):
        os.makedirs(self.out, exist_ok=True)
        core = C.CDLL(self.core_path)
        core.retro_get_memory_data.restype = C.c_void_p
        core.retro_get_memory_size.restype = C.c_size_t
        env, video, audio, audio_batch, poll, inp = self._callbacks()
        sc = self.script
        self.held = set()

        if self.srm is not None:
            # cores without a SAVE_RAM pointer (bsnes) read <save dir>/<rom name>.srm instead
            base = os.path.splitext(os.path.basename(self.rom_path))[0]
            with open(os.path.join(self.out, base + ".srm"), "wb") as fp:
                fp.write(self.srm)
        core.retro_set_environment(env)
        core.retro_set_video_refresh(video)
        core.retro_set_audio_sample(audio)
        core.retro_set_audio_sample_batch(audio_batch)
        core.retro_set_input_poll(poll)
        core.retro_set_input_state(inp)
        core.retro_init()
        rom = open(self.rom_path, "rb").read()
        buf = C.create_string_buffer(rom, len(rom))
        gi = GameInfo(os.path.abspath(self.rom_path).encode(), C.cast(buf, C.c_void_p), len(rom), None)
        if not core.retro_load_game(C.byref(gi)):
            raise RuntimeError("LOAD FAILED")

        if self.srm is not None:
            self._inject_srm(core)
        wram = core.retro_get_memory_data(MEM_SYSTEM_RAM)
        cheat_off = 0
        prev = None
        with open(os.path.join(self.out, "wram.log"), "w") as log:
            while self.frame < sc.end:
                self.held = sc.held(self.frame)
                core.retro_run()
                self.frame += 1
                f = self.frame
                if self.srm is not None and f == 1:   # some cores clear SRAM during their first frame
                    self._inject_srm(core)
                for j, (a, v) in enumerate(sc.pokes.get(f, ())):
                    if wram:
                        C.memmove(wram + a, bytes([v & 0xFF, v >> 8]), 2)
                    else:
                        # bsnes and Supafaust expose no WRAM pointer. Their cheats patch
                        # reads, so hold the value long enough for the game to read it.
                        for k, code in enumerate(S.par_codes(a, v)):
                            core.retro_cheat_set(j * 2 + k, True, code.encode())
                        cheat_off = f + self.cheat_hold
                if cheat_off and f >= cheat_off:
                    core.retro_cheat_reset()
                    cheat_off = 0
                if wram and self.watches:
                    v = tuple(int.from_bytes(C.string_at(wram + w.offset, w.size), "little") for w in self.watches)
                    if v != prev:
                        log.write(f"{f} " + " ".join(w.format(x) for w, x in zip(self.watches, v)) + "\n")
                        prev = v
                if f in sc.dumps:
                    for i, name in ((MEM_SYSTEM_RAM, "wram"), (MEM_SAVE_RAM, "sram")):
                        ptr, n = core.retro_get_memory_data(i), core.retro_get_memory_size(i)
                        if ptr:
                            with open(os.path.join(self.out, f"{name}_{f}.bin"), "wb") as fp:
                                fp.write(C.string_at(ptr, n))
                if f in sc.shots and self.last:
                    self.save_png(os.path.join(self.out, f"f{f:05d}.png"))
        if self.last:
            self.save_png(os.path.join(self.out, "end.png"))
        return self.frame
