"""Audio analysis on synthetic recordings: an intro, then a pattern that repeats with a known period."""
import json

import numpy as np
import pytest

from kr_patch import cli
from kr_patch.audio import analysis, loop, loudness, wav

RATE = 8000
INTRO = 3 * RATE + 123          # loop start in samples
PERIOD = 6 * RATE + 2917        # 6.36 s


def notes(rng, n):
    """Stereo 'music': notes of random pitch and length with decaying envelopes."""
    out = np.zeros((n, 2))
    t = 0
    while t < n:
        d = int(rng.uniform(0.08, 0.3) * RATE)
        f = rng.uniform(150, 2500)
        k = np.arange(d)
        tone = np.sin(2 * np.pi * f * k / RATE) * np.exp(-k / (0.4 * d)) * rng.uniform(2000, 8000)
        seg = out[t:t + d]
        seg += np.outer(tone[:len(seg)], [rng.uniform(0.5, 1), rng.uniform(0.5, 1)])
        t += d
    return out


def song(repeats=4, noise=30.0, seed=1):
    rng = np.random.default_rng(seed)
    x = np.concatenate([notes(rng, INTRO)] + [notes(np.random.default_rng(seed + 1), PERIOD)] * repeats)
    return np.round(x + rng.normal(0, noise, x.shape)).astype(np.int16)   # repeats differ by the noise


@pytest.fixture(scope="module")
def rec(tmp_path_factory):
    p = tmp_path_factory.mktemp("rec") / "song.wav"
    wav.write(p, song(), RATE)
    return p


def run(capsys, *args):
    code = 0
    try:
        cli.main([str(a) for a in args])
    except SystemExit as e:
        code = e.code
    o = capsys.readouterr()
    return code, o.out, o.err


def test_wav_round_trip(tmp_path):
    x = (np.arange(-300, 300).reshape(-1, 2) * 100).astype(np.int16)
    wav.write(tmp_path / "a.wav", x, 32000)
    y, rate = wav.read(tmp_path / "a.wav")
    assert rate == 32000 and y.dtype == np.int16 and np.array_equal(x, y)
    wav.write(tmp_path / "m.wav", np.array([0.4, -0.6, 40000.0, -40000.0]), 8000)   # mono floats round and clip
    y, _ = wav.read(tmp_path / "m.wav")
    assert y.shape == (4, 1) and y[:, 0].tolist() == [0, -1, 32767, -32768]


def test_wav_rejects_8_bit(tmp_path):
    import wave
    with wave.open(str(tmp_path / "b.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(1); w.setframerate(8000); w.writeframes(b"\x80" * 10)
    with pytest.raises(ValueError, match="16-bit"):
        wav.read(tmp_path / "b.wav")


def test_segments():
    rng = np.random.default_rng(0)
    gap = lambda s: np.zeros((int(s * RATE), 2))
    x = np.concatenate([gap(0.5), notes(rng, 2 * RATE), gap(1.0), notes(rng, 3 * RATE), gap(0.2),
                        notes(rng, RATE)])
    songs, gaps = analysis.segments(x, RATE)
    assert len(songs) == 2 and len(gaps) == 2          # the 0.2 s pause is not a gap
    tol = 0.05 + 0.3                                    # one window, plus quiet note tails
    for (a, b), (ea, eb) in zip(songs, [(0.5, 2.5), (3.5, 7.7)]):
        assert abs(a - ea) <= 0.05 and abs(b - eb) <= tol
    assert analysis.segments(x, RATE, min_gap=0.1)[1][-1][1] == pytest.approx(6.7, abs=0.05)


def test_period_candidates_find_the_period_or_a_multiple(rec):
    x, rate = wav.read(rec)
    cands = analysis.period_candidates(analysis.as_float(x), rate)
    lag = cands[0][0]
    k = round(lag / PERIOD)
    assert k >= 1 and abs(lag - k * PERIOD) <= 512        # one spectral frame
    lag, _ = analysis.period_candidates(analysis.as_float(x), rate, lag_range=(5.5, 7.5))[0]
    assert abs(lag - PERIOD) <= 512


def test_refine_period_is_sample_exact(rec):
    x, rate = wav.read(rec)
    p, score = analysis.refine_period(analysis.as_float(x), rate, PERIOD + 300, 0, len(x))
    assert p == PERIOD and score > 0.99


def test_refine_period_too_short():
    with pytest.raises(ValueError, match="too short"):
        analysis.refine_period(np.zeros(RATE * 4), RATE, 3 * RATE, 0, RATE * 4)


@pytest.mark.parametrize("legacy", [False, True])
def test_seam_lands_in_the_repeating_part(legacy):
    x = song()
    win = RATE // 4
    s = loop.Seam(x, PERIOD, win, legacy=legacy)
    span = (win + 600, len(x) - PERIOD - win - 600, RATE // 20, 16, 200, 64)
    best = s.find(*span)
    early = s.find(*span, delta=0.003)
    assert best >= INTRO + win - RATE // 20 and s.score(best) > 0.99
    assert INTRO <= early <= best and s.score(early) > 0.99     # earliest pick stays out of the intro
    assert early < INTRO + RATE
    assert s.score(INTRO - win) < 0.9                     # a window over the intro does not repeat


def test_render_equal_gain_keeps_identical_repeats():
    x = song(repeats=3, noise=0)
    T, fade, tail = INTRO + RATE, 480, 4000
    y = loop.render(x, 100, T, PERIOD, fade, tail)
    e = T + PERIOD - 100
    assert len(y) == e + tail
    assert np.array_equal(y[:e - fade], x[100:T + PERIOD - fade])     # untouched before the fade
    assert np.allclose(y[e - 1], x[T - 1], atol=1e-6)                  # last sample leads into loopStart
    assert np.array_equal(y[e:], x[T:T + tail])                       # tail = what follows the jump
    # both sides of the fade are the same audio, so the output is the plain continuation
    out = np.round(y[e - fade:e])
    assert np.abs(out - x[T + PERIOD - fade:T + PERIOD]).max() == 0
    assert np.abs(out).max() <= np.abs(x[T + PERIOD - fade:T + PERIOD]).max()


def test_render_equal_gain_formula():
    x = song(repeats=3)
    T, fade = INTRO + RATE, 480
    y = loop.render(x, 0, T, PERIOD, fade, 0)
    g = np.sin(np.linspace(0, np.pi / 2, fade))[:, None] ** 2
    e = T + PERIOD
    assert np.allclose(y[e - fade:e], x[e - fade:e] * (1 - g) + x[T - fade:T] * g)


def test_render_legacy():
    x = song(repeats=3, noise=0)
    T, fade, tail = INTRO + RATE, 480, 4000
    y = loop.render(x, 100, T, PERIOD, fade, tail, "equal-power", "end")
    e = T + PERIOD - 100
    assert np.array_equal(y[e:], x[T + PERIOD:T + PERIOD + tail])     # tail = what followed loopEnd
    g = np.sin(np.linspace(0, np.pi / 2, fade))[:, None]
    assert np.allclose(g ** 2 + g[::-1] ** 2, 1)                       # equal power
    assert np.allclose(y[e - fade:e], x[T + PERIOD - fade:T + PERIOD] * g[::-1] + x[T - fade:T] * g)
    assert np.abs(y[e - fade:e]).max() > np.abs(x[T + PERIOD - fade:T + PERIOD]).max() * 1.3   # the +3 dB bump


@pytest.mark.parametrize("offset", [0, 64, 128, 192, 1000])
def test_seamcheck_exact_loop_matches_its_source(offset):
    # with no fade an exact loop is sample for sample the uncut recording, whatever the file's start
    x = song(repeats=3, noise=0)
    A, T = 1000 + offset, INTRO + RATE + 37
    y = np.round(loop.render(x, A, T, PERIOD, 0, RATE // 2)).astype(np.int16)
    res, _ = loop.check(y, RATE, T - A, T + PERIOD - A, x, A)
    assert res["ok"] and res["seamFlux"] == res["sourceFlux"]


def test_loop_cli_known_period(tmp_path, rec, capsys):
    code, out, err = run(capsys, "audio", "loop", rec, tmp_path / "l.wav", "--start", "0.5",
                         "--period", PERIOD, "--seam-range", "3:5", "--json", tmp_path / "l.json")
    assert code == 0, err
    m = json.loads(out)
    assert m == json.loads((tmp_path / "l.json").read_text())
    assert set(m) == {"loopStart", "loopEnd", "duration", "loopStartSample", "loopEndSample", "loopLengthSample",
                      "durationSamples", "sampleRate", "period", "sourceStartSample", "seamScore"}
    A = RATE // 2
    assert m["sourceStartSample"] == A and m["sampleRate"] == RATE and m["period"] == PERIOD
    assert m["loopEndSample"] - m["loopStartSample"] == m["loopLengthSample"] == PERIOD
    assert m["durationSamples"] - m["loopEndSample"] == RATE // 2
    assert m["loopStartSample"] + A >= INTRO and m["seamScore"] > 0.99
    assert m["loopStart"] == round(m["loopStartSample"] / RATE, 6)
    y, rate = wav.read(tmp_path / "l.wav")
    assert len(y) == m["durationSamples"] and rate == RATE

    code, out, err = run(capsys, "audio", "seamcheck", tmp_path / "l.wav", "--source", rec)
    res = json.loads(out)
    assert code == 0 and res["ok"] and res["sourceFlux"] is not None
    assert set(res) == {"seamFlux", "p50", "p90", "p99", "sourceFlux", "limit", "ok"}


def test_loop_cli_searches_the_period(tmp_path, rec, capsys):
    code, out, err = run(capsys, "audio", "loop", rec, tmp_path / "l.wav", "--period-range", "5.5:7.5")
    assert code == 0, err
    m = json.loads(out)
    assert m["period"] == PERIOD and m["periodScore"] > 0.99
    assert m["loopStartSample"] >= INTRO
    assert "period 50917 samples" in err


def test_seamcheck_flags_a_bad_jump(tmp_path, capsys):
    # loopStart in a burst of noise, loopEnd in quiet music: the jump is a sudden onset
    rng = np.random.default_rng(3)
    loud = np.repeat(rng.normal(0, 8000, (2 * RATE, 1)), 2, 1)
    quiet = notes(rng, 20 * RATE) * 0.05
    wav.write(tmp_path / "b.wav", np.concatenate([loud, quiet]), RATE)
    (tmp_path / "b.json").write_text(json.dumps({"loopStart": 1.0, "loopEnd": 21.0}))
    code, out, err = run(capsys, "audio", "seamcheck", tmp_path / "b.wav", "--render", tmp_path / "c.wav")
    res = json.loads(out)
    assert code == 1 and not res["ok"] and res["seamFlux"] > res["limit"]
    assert len(wav.read(tmp_path / "c.wav")[0]) == 21 * RATE + 2 * 20 * RATE


def test_loop_cli_errors(tmp_path, rec, capsys):
    code, out, err = run(capsys, "audio", "loop", rec, tmp_path / "l.wav", "--period", "1000",
                         "--period-range", "5:7")
    assert code == 2 and "not both" in err
    code, out, err = run(capsys, "audio", "loop", rec, tmp_path / "l.wav", "--period", PERIOD,
                         "--seam-range", "20:22")
    assert code == 2 and "full period" in err
    code, out, err = run(capsys, "audio", "loop", rec, tmp_path / "l.wav", "--start", "99")
    assert code == 2 and "outside" in err
    assert not (tmp_path / "l.wav").exists()


def test_segments_period_cli(tmp_path, rec, capsys):
    x = np.concatenate([np.zeros((RATE, 2), np.int16), song(repeats=2)])
    wav.write(tmp_path / "s.wav", x, RATE)
    code, out, err = run(capsys, "audio", "segments", tmp_path / "s.wav")
    assert code == 0 and len(out.splitlines()) == 1 and out.split()[0] == "1.00"
    code, out, err = run(capsys, "audio", "segments", tmp_path / "s.wav", "--gaps")
    assert out.split()[:2] == ["0.00", "1.00"]
    code, out, err = run(capsys, "audio", "period", rec, "--top", "3")
    assert code == 0 and len(out.splitlines()) == 3 and "multiple" in err


# EBU Tech 3341 test signals (1 kHz sines; dBFS of the peak) and BS.1770-4 filter coefficients.

def sine(db, seconds, rate=48000):
    t = np.arange(int(seconds * rate)) / rate
    s = 10 ** (db / 20) * np.sin(2 * np.pi * 1000 * t)
    return np.stack([s, s], 1)


def test_k_filter_matches_bs1770_at_48k():
    (b1, a1), (b2, a2) = loudness.k_filter(48000)
    assert np.allclose(b1, [1.53512485958697, -2.69169618940638, 1.19839281085285], atol=1e-12)
    assert np.allclose(a1, [1.0, -1.69065929318241, 0.73248077421585], atol=1e-12)
    assert np.allclose(b2, [1.0, -2.0, 1.0]) and np.allclose(a2, [1.0, -1.99004745483398, 0.99007225036621],
                                                             atol=1e-12)


@pytest.mark.parametrize("parts,want", [
    ([(-23, 20)], -23.0),                                  # 3341 case 1
    ([(-33, 20)], -33.0),                                  # case 2
    ([(-36, 10), (-23, 60), (-36, 10)], -23.0),            # case 3: relative gate
    ([(-72, 10), (-36, 10), (-23, 60), (-36, 10), (-72, 10)], -23.0),   # case 4: absolute gate
])
def test_integrated_loudness_ebu3341(parts, want):
    x = np.concatenate([sine(db, s) for db, s in parts])
    assert loudness.integrated(x, 48000) == pytest.approx(want, abs=0.1)


def test_loudness_cli(tmp_path, capsys):
    wav.write(tmp_path / "t.wav", sine(-23, 5) * 32768, 48000)
    code, out, err = run(capsys, "audio", "loudness", tmp_path / "t.wav", "--target", "-20")
    res = json.loads(out)
    assert code == 0 and set(res) == {"integrated", "samplePeak", "gain"}
    assert res["integrated"] == pytest.approx(-23.0, abs=0.1) and res["gain"] == pytest.approx(3.0, abs=0.1)
    assert res["samplePeak"] == pytest.approx(-23.0, abs=0.05)
    assert loudness.integrated(np.zeros((48000, 2)), 48000) == float("-inf")


def test_audio_help(capsys):
    code, out, err = run(capsys, "audio", "--help")
    assert code == 0
    for c in ("segments", "period", "loop", "seamcheck", "loudness"):
        assert c in out


def test_fast_len():
    assert [analysis.fast_len(n) for n in (1, 7, 17, 97, 1025, 4097)] == [1, 8, 18, 100, 1080, 4320]


def test_loop_legacy_and_options(tmp_path, rec, capsys):
    base = ["audio", "loop", rec, tmp_path / "l.wav", "--period", PERIOD, "--seam-range", "3:5"]
    code, out, err = run(capsys, *base, "--legacy")
    legacy = json.loads(out)
    assert code == 0 and legacy["durationSamples"] - legacy["loopEndSample"] == RATE // 2
    y, _ = wav.read(tmp_path / "l.wav")
    x, _ = wav.read(rec)
    T, E = legacy["loopStartSample"], legacy["loopEndSample"]
    assert np.array_equal(y[E:], x[E:E + RATE // 2])          # tail from the end
    code, out, err = run(capsys, *base, "--seam-pick", "best")
    best = json.loads(out)
    code, out, err = run(capsys, *base)
    early = json.loads(out)
    assert early["loopStartSample"] <= best["loopStartSample"]
    y, _ = wav.read(tmp_path / "l.wav")
    assert np.array_equal(y[early["loopEndSample"]:], x[early["loopStartSample"]:early["loopStartSample"] + RATE // 2])


def test_loop_warns_about_several_songs(tmp_path, capsys):
    x = np.concatenate([song(repeats=3), np.zeros((RATE, 2), np.int16), song(repeats=1, seed=7)])
    wav.write(tmp_path / "two.wav", x, RATE)
    code, out, err = run(capsys, "audio", "loop", tmp_path / "two.wav", tmp_path / "l.wav", "--period", PERIOD,
                         "--seam-range", "3:5")
    assert code == 0 and "2 songs" in err and "--end" in err
    end = (INTRO + 3 * PERIOD) / RATE
    code, out, err = run(capsys, "audio", "loop", tmp_path / "two.wav", tmp_path / "l.wav", "--period", PERIOD,
                         "--seam-range", "3:5", "--end", end)
    assert code == 0 and "songs" not in err
    code, out, err = run(capsys, "audio", "loop", tmp_path / "two.wav", tmp_path / "l.wav", "--period", PERIOD,
                         "--seam-range", "3:5", "--end", end, "--tail", "15", "--legacy")
    assert code == 2 and "--tail" in err


@pytest.mark.parametrize("arg", [["--fine-step", "0"], ["--coarse-step", "-1"], ["--period", "0"], ["--fade-ms", "0"]])
def test_loop_rejects_non_positive(tmp_path, rec, capsys, arg):
    code, out, err = run(capsys, "audio", "loop", rec, tmp_path / "l.wav", *arg)
    assert code == 2 and "must be positive" in err


def test_anti_phase_stereo(tmp_path, capsys):
    # left and right cancel in a mono mix; nothing may depend on one
    x = song().astype(np.int32)
    x[:, 1] = -x[:, 0]
    x = np.concatenate([np.zeros((RATE, 2), np.int32), x]).astype(np.int16)
    wav.write(tmp_path / "anti.wav", x, RATE)
    songs, _ = analysis.segments(x, RATE)
    assert len(songs) == 1 and songs[0][0] == pytest.approx(1.0, abs=0.05)
    code, out, err = run(capsys, "audio", "loop", tmp_path / "anti.wav", tmp_path / "l.wav", "--period-range", "5.5:7.5",
                         "--json", tmp_path / "l.json")
    m = json.loads(out)
    assert code == 0 and m["period"] == PERIOD and m["seamScore"] > 0.99 and m["loopStartSample"] + RATE >= INTRO
    code, out, err = run(capsys, "audio", "seamcheck", tmp_path / "l.wav", "--source", tmp_path / "anti.wav")
    res = json.loads(out)
    assert code == 0 and res["p50"] > 0


def test_seamcheck_sample_only_json(tmp_path, rec, capsys):
    x, _ = wav.read(rec)
    T = INTRO + RATE
    y = np.concatenate([x[:T + PERIOD], x[T:T + RATE // 2]])
    wav.write(tmp_path / "s.wav", y, RATE)
    (tmp_path / "s.json").write_text(json.dumps({"loopStartSample": T, "loopEndSample": T + PERIOD}))
    code, out, err = run(capsys, "audio", "seamcheck", tmp_path / "s.wav")
    assert code == 0 and json.loads(out)["ok"]
    (tmp_path / "s.json").write_text(json.dumps({"loopEndSample": T + PERIOD}))
    code, out, err = run(capsys, "audio", "seamcheck", tmp_path / "s.wav")
    assert code == 2 and "loopStart" in err


def test_bad_wav_files(tmp_path, rec, capsys):
    (tmp_path / "junk.wav").write_bytes(b"not a wave file at all")
    data = rec.read_bytes()
    (tmp_path / "cut.wav").write_bytes(data[:len(data) // 2])
    for name, msg in (("junk.wav", "not a readable PCM WAV"), ("cut.wav", "truncated")):
        with pytest.raises(ValueError, match=msg):
            wav.read(tmp_path / name)
        code, out, err = run(capsys, "audio", "segments", tmp_path / name)
        assert code == 2 and name in err


def test_loudness_silence_is_valid_json(tmp_path, capsys):
    wav.write(tmp_path / "z.wav", np.zeros((48000, 2), np.int16), 48000)
    code, out, err = run(capsys, "audio", "loudness", tmp_path / "z.wav", "--target", "-20")
    res = json.loads(out, parse_constant=lambda c: pytest.fail(f"non-JSON constant {c}"))
    assert code == 0 and res == {"integrated": None, "samplePeak": None}


def test_loudness_rejects_surround():
    with pytest.raises(ValueError, match="channels"):
        loudness.integrated(np.zeros((48000, 6)), 48000)
