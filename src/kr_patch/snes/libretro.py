"""Minimal headless libretro frontend for compatibility runs.

Plays a script (see harness.script) on a libretro core and writes f<frame>.png
screenshots, end.png, optional WRAM/SRAM dumps and wram.log (frame and the
watched WRAM values, one line per change) to the output directory, and
optionally the core's audio output as a 16-bit stereo WAV.

env LRVARS="key=value,key=value" overrides core options; LRLOG=1 prints core logs.
"""
import ctypes as C
import os
import sys
import wave

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


class AvInfo(C.Structure):
    _fields_ = [("base_width", C.c_uint), ("base_height", C.c_uint), ("max_width", C.c_uint),
                ("max_height", C.c_uint), ("aspect_ratio", C.c_float), ("fps", C.c_double),
                ("sample_rate", C.c_double)]


def env_vars(s):
    return {k: v for k, v in (kv.split("=", 1) for kv in (s or "").split(",") if kv)}


def to_image(data, w, h, pitch, pixfmt):
    if pixfmt == PIX_RGB565:
        return Image.frombuffer("RGB", (w, h), data, "raw", "BGR;16", pitch, 1)
    if pixfmt == PIX_XRGB8888:
        return Image.frombuffer("RGBX", (w, h), data, "raw", "BGRX", pitch, 1).convert("RGB")
    return Image.frombuffer("RGB", (w, h), data, "raw", "BGR;15", pitch, 1)


class LoadError(RuntimeError):
    pass


REQUIRED = ("retro_set_environment", "retro_set_video_refresh", "retro_set_audio_sample",
            "retro_set_audio_sample_batch", "retro_set_input_poll", "retro_set_input_state",
            "retro_init", "retro_deinit", "retro_load_game", "retro_unload_game", "retro_run",
            "retro_get_memory_data", "retro_get_memory_size", "retro_cheat_set", "retro_cheat_reset")


def load_core(path):
    try:
        core = C.CDLL(path)
        for name in REQUIRED:
            getattr(core, name)
    except (OSError, AttributeError) as e:
        raise LoadError(f"LOAD FAILED: {e}") from None
    return core


class Runner:
    """Plays one script on one core.

    Use one Runner per process: cores keep global state and ctypes reuses an
    already loaded library, so a second run in the same process would not start
    from a fresh core.
    """

    def __init__(self, core, rom, out, script, srm=None, watches=(), variables=None,
                 verbose=None, cheat_hold=40, wav=None):
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
        self.wav = wav
        self.sink = None    # open wave writer while recording
        self.frame = 0
        self.pixfmt = PIX_0RGB1555
        self.last = None

    def _log(self, msg):
        if self.verbose:
            sys.stderr.write(msg)
            sys.stderr.flush()

    def _callbacks(self):
        sysdir = C.c_char_p(self.out.encode())
        # The log callback is variadic in C; ctypes cannot read the arguments, so
        # the core's format string is printed as-is, with its % fields unexpanded.
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

        def audio(left, right):
            if self.sink:
                self.sink.writeframesraw(left.to_bytes(2, "little", signed=True)
                                         + right.to_bytes(2, "little", signed=True))

        def audio_batch(data, frames):
            if self.sink:
                self.sink.writeframesraw(C.string_at(data, frames * 4))
            return frames

        def inp(port, device, index, id_):
            if port != 0 or device != 1:
                return 0
            return int(id_ in self.held)

        # ctypes callbacks must outlive the core's use of them, i.e. until after retro_deinit
        self._keep = (sysdir, log_fn, log_iface, ENV_CB(env), VID_CB(video), AUD_CB(audio),
                      AUDB_CB(audio_batch), POLL_CB(lambda: None), IN_CB(inp))
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
        core = load_core(self.core_path)
        core.retro_get_memory_data.restype = C.c_void_p
        core.retro_get_memory_size.restype = C.c_size_t
        env, video, audio, audio_batch, poll, inp = self._callbacks()
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
        loaded = False
        try:
            rom = open(self.rom_path, "rb").read()
            buf = C.create_string_buffer(rom, len(rom))
            gi = GameInfo(os.path.abspath(self.rom_path).encode(), C.cast(buf, C.c_void_p), len(rom), None)
            if not core.retro_load_game(C.byref(gi)):
                raise LoadError("LOAD FAILED: the core rejected the ROM")
            loaded = True
            if self.wav:
                rate = self._sample_rate(core)
                # streamed so long recordings do not sit in memory; close() fixes up the header
                self.sink = wave.open(self.wav, "wb")
                self.sink.setnchannels(2)
                self.sink.setsampwidth(2)
                self.sink.setframerate(round(rate))    # WAV holds an integer rate; snes9x reports 32040.5
            self._play(core)
        finally:
            if self.sink:
                self.sink.close()
                self.sink = None
            if loaded:
                core.retro_unload_game()
            core.retro_deinit()
        if self.last:
            self.save_png(os.path.join(self.out, "end.png"))
        return self.frame

    def _sample_rate(self, core):
        try:
            get = core.retro_get_system_av_info
        except AttributeError:
            raise LoadError("LOAD FAILED: the core has no retro_get_system_av_info") from None
        av = AvInfo()
        get(C.byref(av))
        if not av.sample_rate > 0:
            raise LoadError(f"LOAD FAILED: the core reports a sample rate of {av.sample_rate}")
        return av.sample_rate

    def _check_wram(self, size):
        for f, pokes in self.script.pokes.items():
            for a, _ in pokes:
                if a + S.POKE_SIZE > size:
                    raise ValueError(f"poke at frame {f}: ${a:X} is outside the core's {size:#x}-byte WRAM")
        for w in self.watches:
            if w.offset + w.size > size:
                raise ValueError(f"watch ${w.offset:X}:{w.size} is outside the core's {size:#x}-byte WRAM")

    def _play(self, core):
        sc = self.script
        if self.srm is not None:
            self._inject_srm(core)
        wram = core.retro_get_memory_data(MEM_SYSTEM_RAM)
        if wram:
            self._check_wram(core.retro_get_memory_size(MEM_SYSTEM_RAM))
        cheats = {}         # index -> (frame it expires, code)
        next_cheat = 0
        prev = None
        with open(os.path.join(self.out, "wram.log"), "w") as log:
            while self.frame < sc.end:
                self.held = sc.held(self.frame)
                core.retro_run()
                self.frame += 1
                f = self.frame
                if self.srm is not None and f == 1:   # some cores clear SRAM during their first frame
                    self._inject_srm(core)
                for a, v in sc.pokes.get(f, ()):
                    if wram:
                        C.memmove(wram + a, bytes([v & 0xFF, v >> 8]), 2)
                        continue
                    # bsnes and Supafaust expose no WRAM pointer, so fall back to cheats.
                    # bsnes writes each enabled code to its address once per frame; hold
                    # it long enough to win over the game's own writes. After release the
                    # value stays until the game overwrites it.
                    for code in S.par_codes(a, v):
                        core.retro_cheat_set(next_cheat, True, code.encode())
                        cheats[next_cheat] = (f + self.cheat_hold, code)
                        next_cheat += 1
                expired = [i for i, (until, _) in cheats.items() if f >= until]
                for i in expired:
                    core.retro_cheat_set(i, False, cheats.pop(i)[1].encode())
                if expired and not cheats:
                    core.retro_cheat_reset()
                    next_cheat = 0
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
