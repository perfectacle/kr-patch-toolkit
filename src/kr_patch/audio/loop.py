"""Seamless loop files: find the seam, cut intro + one period, crossfade the jump, check it.

A loop file holds the song from its start A to loopEnd = T + P, plus a tail.
Players jump from loopEnd back to loopStart = T. The last fade samples before
loopEnd are crossfaded with the audio just before T, so at the jump the file
already sounds like what follows T. The tail is never played when looping;
it keeps a lossy encoder's padding out of the loop.
"""
import numpy as np


class Seam:
    """Seam search on one recording with period P (samples).

    The score is the NCC of all channels as one vector signal. legacy=True
    scores the channel sum instead, as the scripts this replaces did; a voice
    in anti-phase cancels there.
    """

    def __init__(self, x, period, window, legacy=False):
        self.x = np.asarray(x, np.float64)
        self.s = self.x.sum(1) if legacy else self.x
        self.P, self.win = period, window

    def score(self, t):
        """ncc of the window around t with the window around t + P."""
        u = self.s[t - self.win:t + self.win]
        v = self.s[t - self.win + self.P:t + self.win + self.P]
        return float(np.sum(u * v) / (np.sqrt(np.sum(u * u) * np.sum(v * v)) + 1e-9))

    def diff(self, t, n):
        return float(np.abs(self.x[t:t + n] - self.x[t + self.P:t + self.P + n]).sum())

    def find(self, t0, t1, coarse, fine, snap, snap_len, delta=None):
        """Seam in [t0, t1): coarse steps, then fine steps around the pick, then the
        sample within +-snap where both sides agree best sample by sample.

        The coarse pick is the best position, or with delta the earliest one
        scoring within delta of the best: any seam inside the repeating part
        loops cleanly, and an early one keeps the file short.
        """
        ts = range(t0, t1, coarse)
        sc = [self.score(t) for t in ts]
        top = max(sc)
        c = ts[sc.index(top) if delta is None else next(i for i, v in enumerate(sc) if v >= top - delta)]
        t = max(range(c - coarse, c + coarse, fine), key=self.score)
        return min(range(t - snap, t + snap), key=lambda q: self.diff(q, snap_len))


def render(x, start, seam, period, fade, tail, shape="equal-gain", tail_from="seam"):
    """Intro from start, one period after the seam with the crossfade, then the tail, as float samples.

    equal-gain (sin^2 and 1 - sin^2) keeps the level of the correlated audio
    on both sides of a good seam; equal-power (sin/cos) suits uncorrelated
    audio and peaks at +3 dB on correlated audio. The tail is what follows
    the seam, i.e. what a player hears after the jump, or with tail_from="end"
    what followed loopEnd in the recording.
    """
    end = seam + period
    x = np.asarray(x, np.float64)
    after = x[seam:seam + tail] if tail_from == "seam" else x[end:end + tail]
    y = np.concatenate([x[start:end], after])
    if fade:
        g = np.sin(np.linspace(0, np.pi / 2, fade))[:, None]
        out, into = (1 - g * g, g * g) if shape == "equal-gain" else (g[::-1], g)
        e = end - start
        y[e - fade:e] = y[e - fade:e] * out + x[seam - fade:seam] * into
    return y


def check(y, rate, loop_start, loop_end, source=None, source_start=None, ratio=1.25, n_fft=1024, hop=256):
    """Spectral flux at the first jump of intro + loop three times against the song's own flux.

    With the source recording and the file's start in it, also the flux of the
    uncut recording over the same frames, i.e. where the song simply continues
    past loopEnd. Both use one frame grid from the file's start, so an exact
    loop measures the same as its source. The seam passes up to ratio times
    that continuation, or without a source, ratio times the song's 99th
    percentile: a loop that starts on a drum hit is loud at the seam either way.
    Returns (stats, rendered).
    """
    z = np.concatenate([y[:loop_end], y[loop_start:loop_end], y[loop_start:loop_end]])
    flux = _flux(z, n_fft, hop)
    j = loop_end // hop
    seam = _local(z, j, n_fft, hop)
    p50, p90, p99 = (float(v) for v in np.percentile(flux, [50, 90, 99]))
    out = {"seamFlux": round(seam, 1), "p50": round(p50, 1), "p90": round(p90, 1), "p99": round(p99, 1),
           "sourceFlux": None}
    if source is not None:
        hi = source_start + (j + 4) * hop + n_fft
        if source_start < 0 or hi > len(source):
            raise ValueError("the source recording does not cover loopEnd")
        out["sourceFlux"] = round(_local(source[source_start:hi], j, n_fft, hop), 1)
    ref = out["sourceFlux"] if source is not None else p99
    out["limit"] = round(ratio * ref, 1)
    out["ok"] = seam <= ratio * ref
    return out, z


def _local(x, j, n_fft, hop):
    """Highest flux among frames j-4..j+4 of x, on the grid of frames starting at multiples of hop."""
    k0 = max(0, j - 4)
    return float(_flux(x[k0 * hop:(j + 4) * hop + n_fft], n_fft, hop).max())


def _flux(x, n_fft, hop, chunk=8192):
    """Spectral flux (sum of rises in log magnitude) per frame step; channels combine by power."""
    x = np.asarray(x, np.float64)
    x = x[:, None] if x.ndim == 1 else x
    frames = np.lib.stride_tricks.sliding_window_view(x, n_fft, axis=0)[::hop]   # (frames, ch, n_fft)
    win = np.hanning(n_fft)
    out = []
    for i in range(0, len(frames) - 1, chunk):
        X = np.abs(np.fft.rfft(frames[i:i + chunk + 1] * win, axis=2))
        S = np.log1p(np.sqrt((X * X).sum(1)) / 100)
        out.append(np.maximum(S[1:] - S[:-1], 0).sum(1))
    return np.concatenate(out)
