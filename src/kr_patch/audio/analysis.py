"""Song boundaries and loop periods of a recording.

Emulated game music repeats with sample-exact timing, but the waveform of a
repeat is often not identical (echo buffers, voice phases, sound effects), so
the period is found coarsely on spectra first and refined on the waveform.
Channels are never mixed down: a voice panned in anti-phase would cancel.
"""
import numpy as np


def fast_len(n):
    """Smallest 2^a 3^b 5^c >= n, a size numpy's FFT handles quickly."""
    best = 1 << max(0, (n - 1).bit_length())
    p5 = 1
    while p5 < best:
        p35 = p5
        while p35 < best:
            q = p35
            while q < n:
                q *= 2
            best = min(best, q)
            p35 *= 3
        p5 *= 5
    return best


def as_float(x):
    """Samples as float64 (frames, channels) in [-1, 1]."""
    x = np.asarray(x, np.float64)
    return (x[:, None] if x.ndim == 1 else x) / 32768


def segments(x, rate, window=0.05, threshold=30.0, min_gap=0.3):
    """Sounding stretches and quiet gaps, as lists of (start, end) in seconds.

    A gap is a run of at least min_gap seconds of windows whose RMS over all
    channels (int16 units) is below threshold.
    """
    x = np.asarray(x, np.float64)
    if x.ndim == 1:
        x = x[:, None]
    hop = max(1, round(window * rate))
    nwin = -(-len(x) // hop)
    sq = np.zeros(nwin * hop)
    sq[:len(x)] = (x * x).mean(1)
    rms = np.sqrt(sq.reshape(nwin, hop).mean(1))
    quiet = np.concatenate(([False], rms < threshold, [False]))
    edges = np.flatnonzero(np.diff(quiet.astype(np.int8)))
    need = max(1, round(min_gap / window))
    total = len(x) / rate
    gaps = [(i * hop / rate, min(j * hop / rate, total))
            for i, j in zip(edges[::2], edges[1::2]) if j - i >= need]
    songs, t = [], 0.0
    for a, b in gaps + [(total, total)]:
        if a > t:
            songs.append((t, a))
        t = b
    return songs, gaps


def spectrogram(m, n_fft=2048, hop=512, chunk=4096):
    """Log-magnitude frames of one channel, each zero-mean and unit-length so a dot product is a cosine similarity."""
    if len(m) < n_fft:
        raise ValueError("audio shorter than one FFT frame")
    frames = np.lib.stride_tricks.sliding_window_view(m, n_fft)[::hop]
    win = np.hanning(n_fft)
    out = np.empty((len(frames), n_fft // 2 + 1), np.float32)
    for i in range(0, len(frames), chunk):
        s = np.log1p(100 * np.abs(np.fft.rfft(frames[i:i + chunk] * win, axis=1)))
        s -= s.mean(1, keepdims=True)
        s /= np.linalg.norm(s, axis=1, keepdims=True) + 1e-9
        out[i:i + chunk] = s
    return out


def lag_similarity(S, cols=64):
    """sim[L] = mean over t of S[t] . S[t+L], for every lag L, via per-bin autocorrelation."""
    T = len(S)
    n = fast_len(2 * T - 1)
    acc = np.zeros(T)
    for c in range(0, S.shape[1], cols):
        f = np.fft.rfft(S[:, c:c + cols].astype(np.float64), n, axis=0)
        acc += np.fft.irfft(f * np.conj(f), n, axis=0)[:T].sum(1)
    return acc / (T - np.arange(T))


def period_candidates(x, rate, min_lag=5.0, lag_range=None, top=6, n_fft=2048, hop=512):
    """Best loop periods by spectral self-similarity, as [(lag in samples, score)].

    x is float (frames, channels); the similarity is averaged over channels.
    Lags need min_lag seconds of overlap on both sides. Peaks closer than one
    second to a better one are dropped. A peak can be a multiple (or a
    fraction) of the true period when the music repeats inside its loop.
    """
    x = x[:, None] if x.ndim == 1 else x
    sim = np.mean([lag_similarity(spectrogram(x[:, c], n_fft, hop)) for c in range(x.shape[1])], 0)
    fps = rate / hop
    lo, hi = int(min_lag * fps), len(sim) - int(min_lag * fps)
    if lag_range:
        lo, hi = max(lo, int(lag_range[0] * fps)), min(hi, int(np.ceil(lag_range[1] * fps)) + 1)
    if hi <= lo:
        raise ValueError("no lag to test: the range is too short for the minimum lag or the period range")
    order = lo + np.argsort(-sim[lo:hi], kind="stable")
    picked = []
    for L in order:
        if all(abs(L - q) > fps for q in picked):
            picked.append(int(L))
            if len(picked) == top:
                break
    return [(L * hop, float(sim[L])) for L in picked]


def ncc_scan(hay, ref):
    """Normalised cross-correlation of ref at every offset of hay (offsets 0..len(hay)-len(ref)).

    Multichannel input is one vector signal: products and energies are summed
    over channels, so channels in anti-phase still count.
    """
    hay = hay[:, None] if hay.ndim == 1 else hay
    ref = ref[:, None] if ref.ndim == 1 else ref
    n = len(ref)
    k = len(hay) - n + 1
    size = fast_len(len(hay) + n - 1)
    c = np.fft.irfft(np.fft.rfft(hay, size, axis=0) * np.conj(np.fft.rfft(ref, size, axis=0)), size,
                     axis=0)[:k].sum(1)
    e = np.concatenate(([0.0], np.cumsum((hay * hay).sum(1))))
    return c / (np.sqrt(np.maximum(e[n:n + k] - e[:k], 0) * float(np.sum(ref * ref))) + 1e-12)


def refine_period(x, rate, guess, start, end, length=3.0, span=0.1, tries=7):
    """Sample-exact period near guess, as (period, ncc).

    A length-second window is matched against the audio one period later,
    within +-span seconds, at `tries` places spread over start..end (samples);
    the best match wins. One place is not enough: the window may fall on the
    intro, an ending or a stretch where voices differ between repeats.
    """
    n, d = int(length * rate), int(span * rate)
    last = min(end, len(x)) - guess - d - n
    if last < start or start + guess - d < 0:
        raise ValueError("the range is too short to refine the period: it needs one period plus "
                         f"{length + span:g} s")
    best = (guess, -2.0)
    for at in np.linspace(start, last, tries).astype(int):
        lo = at + guess - d
        c = ncc_scan(x[lo:lo + 2 * d + n], x[at:at + n])
        k = int(np.argmax(c))
        if c[k] > best[1]:
            best = (guess - d + k, float(c[k]))
    return best
