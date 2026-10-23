"""16-bit PCM WAV files as (frames, channels) int16 arrays, through the stdlib wave module."""
import wave

import numpy as np


def read(path):
    """Return (samples, rate); samples is int16 with shape (frames, channels)."""
    try:
        with wave.open(str(path), "rb") as w:
            if w.getsampwidth() != 2:
                raise ValueError(f"{path}: {8 * w.getsampwidth()}-bit samples; only 16-bit PCM is supported")
            ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
            data = w.readframes(n)
    except (wave.Error, EOFError) as e:
        raise ValueError(f"{path}: not a readable PCM WAV file ({str(e) or 'unexpected end of file'})") from None
    if len(data) != n * ch * 2:
        raise ValueError(f"{path}: truncated, {len(data) // (ch * 2)} of {n} frames")
    return np.frombuffer(data, "<i2").reshape(-1, ch), rate


def write(path, samples, rate):
    """Write samples (frames, channels), rounding and clipping floats to int16."""
    x = np.asarray(samples)
    if x.ndim == 1:
        x = x[:, None]
    if x.dtype != np.int16:
        x = np.clip(np.round(x), -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(x.astype("<i2").tobytes())
