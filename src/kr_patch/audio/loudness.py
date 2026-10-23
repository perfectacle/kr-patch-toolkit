"""Integrated loudness (ITU-R BS.1770-4 / EBU R128) for mono and stereo, numpy only.

The two K-weighting biquads are applied in the frequency domain over the whole
signal, zero-padded so their decaying response does not wrap around. True peak
is not measured; the sample peak is.
"""
import numpy as np

from .analysis import fast_len

# BS.1770 pre-filter (high shelf) and RLB high-pass, as analogue prototypes so any sample rate works.
SHELF = (1681.974450955533, 3.999843853973347, 0.7071752369554196)   # fc Hz, gain dB, Q
HIGHPASS = (38.13547087602444, 0.5003270373238773)                    # fc Hz, Q


def k_filter(rate):
    """Biquad coefficients (b, a) of both K-weighting stages at rate."""
    fc, gain, q = SHELF
    K = np.tan(np.pi * fc / rate)
    Vh = 10 ** (gain / 20)
    Vb = Vh ** 0.4996667741545416
    a0 = 1 + K / q + K * K
    shelf = ([(Vh + Vb * K / q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / q + K * K) / a0],
             [1.0, 2 * (K * K - 1) / a0, (1 - K / q + K * K) / a0])
    fc, q = HIGHPASS
    K = np.tan(np.pi * fc / rate)
    a0 = 1 + K / q + K * K
    hp = ([1.0, -2.0, 1.0], [1.0, 2 * (K * K - 1) / a0, (1 - K / q + K * K) / a0])
    return shelf, hp


def _response(stages, n):
    z = np.exp(-2j * np.pi * np.arange(n // 2 + 1) / n)
    h = np.ones_like(z)
    for b, a in stages:
        h *= np.polyval(b[::-1], z) / np.polyval(a[::-1], z)
    return h


def k_weight(x, rate, pad=1.0):
    """K-weighted copy of x (frames, channels)."""
    n = fast_len(len(x) + int(pad * rate))
    h = _response(k_filter(rate), n)
    return np.fft.irfft(np.fft.rfft(x, n, axis=0) * h[:, None], n, axis=0)[:len(x)]


def integrated(x, rate):
    """Integrated loudness in LUFS of float samples (frames, channels) at full scale 1.0.

    400 ms blocks every 100 ms, absolute gate -70 LUFS, relative gate -10 LU.
    Channels are weighted 1.0 (left, right, mono); surround weights are not
    implemented, so more than two channels is an error. Returns -inf when no
    block passes the absolute gate (silence).
    """
    x = np.asarray(x, np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[1] > 2:
        raise ValueError(f"{x.shape[1]} channels; only mono and stereo are supported")
    blk, step = int(0.4 * rate), int(0.1 * rate)
    if len(x) < blk:
        raise ValueError("audio shorter than one 400 ms block")
    y = k_weight(x, rate) ** 2
    c = np.concatenate([np.zeros((1, y.shape[1])), np.cumsum(y, 0)])
    starts = np.arange(0, len(x) - blk + 1, step)
    z = ((c[starts + blk] - c[starts]) / blk).sum(1)
    lk = -0.691 + 10 * np.log10(np.maximum(z, 1e-20))
    z = z[lk > -70]
    if not len(z):
        return float("-inf")
    rel = -0.691 + 10 * np.log10(z.mean()) - 10
    z = z[-0.691 + 10 * np.log10(z) > rel]
    return float(-0.691 + 10 * np.log10(z.mean()))


def sample_peak(x):
    """Highest absolute sample in dBFS of float samples at full scale 1.0."""
    p = float(np.max(np.abs(x))) if len(x) else 0.0
    return 20 * np.log10(p) if p else float("-inf")
