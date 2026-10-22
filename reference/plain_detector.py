"""The ParaDigMa tremor detector rebuilt with only an FFT and plain arithmetic.

Every step is written the way it would be written in C: fixed sizes, loops over
arrays, and no library call except a real-input FFT. It takes one 4 second
window at 100 Hz (400 samples x 3 gyroscope axes, degrees per second).
"""
import math
import numpy as np

FS = 100.0
N = 400                      # 4 s window
PSD_SEG, PSD_STEP, PSD_NFFT = 300, 60, 400      # 3 s slices, 80% overlap, 0.25 Hz steps
SPG_SEG, SPG_STEP, SPG_NFFT = 200, 40, 200      # 2 s slices, 80% overlap, 0.5 Hz steps
N_FILT, N_COEF = 15, 12


def hann_symmetric(n):
    return [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]


def hann_periodic(n):
    return [0.5 - 0.5 * math.cos(2 * math.pi * i / n) for i in range(n)]


def melscale(f):
    return 64.875 * math.log10(1 + f / 17.5)


def inverse_melscale(m):
    return 17.5 * (10 ** (m / 64.875) - 1)


def triang(m):
    # scipy.signal.windows.triang for width m
    out = []
    n = np.arange(1, (m + 1) // 2 + 1)
    if m % 2 == 0:
        w = (2 * n - 1.0) / m
        w = np.concatenate([w, w[::-1]])
    else:
        w = 2 * n / (m + 1.0)
        w = np.concatenate([w, w[-2::-1]])
    return list(w)


def build_tables():
    """Tables that C would hold as constants."""
    t = {}
    t["w_psd"] = np.array(hann_symmetric(PSD_SEG))
    t["w_spg"] = np.array(hann_periodic(SPG_SEG))
    # mel filter bank on the 0.5 Hz spectrum (101 bins)
    lo, hi = melscale(0.0), melscale(25.0)
    mels = [lo + (hi - lo) * i / (N_FILT + 1) for i in range(N_FILT + 2)]
    freqs = [inverse_melscale(m) for m in mels]
    win_len = SPG_SEG   # what compute_mfccs derives: int(400 / (6 - 5*0.8))
    pts = [int(np.round(win_len / FS * f)) + 1 for f in freqs]
    fb = np.zeros((N_FILT, SPG_NFFT // 2 + 1))
    for j in range(N_FILT):
        tri = triang(pts[j + 2] - pts[j])
        fb[j, pts[j]:pts[j + 2]] = tri
        fb[j] /= FS / win_len * fb[j].sum()
    t["filters"] = fb
    dct = np.empty((N_COEF, N_FILT))
    dct[0] = 1.0 / math.sqrt(N_FILT)
    samples = [(2 * k + 1) * math.pi / (2.0 * N_FILT) for k in range(N_FILT)]
    for i in range(1, N_COEF):
        dct[i] = [math.cos(i * s) * math.sqrt(2.0 / N_FILT) for s in samples]
    t["dct"] = dct
    return t


def detect(window, model, t, dtype=np.float64):
    """window: (400, 3). model: dict of mean, scale, coef, intercept, threshold."""
    x = np.asarray(window, dtype=dtype)
    w_psd = t["w_psd"].astype(dtype)
    w_spg = t["w_spg"].astype(dtype)

    # 1. Fine spectrum: average of two 3 s slices, power per Hz, three axes added.
    psd = np.zeros(PSD_NFFT // 2 + 1, dtype=dtype)
    n_seg = (N - PSD_SEG) // PSD_STEP + 1
    scale = 1.0 / (FS * float((w_psd * w_psd).sum()))
    for axis in range(3):
        for s in range(n_seg):
            seg = x[s * PSD_STEP: s * PSD_STEP + PSD_SEG, axis] * w_psd
            spec = np.fft.rfft(seg, PSD_NFFT)
            p = (spec.real ** 2 + spec.imag ** 2) * scale
            p[1:-1] *= 2            # one-sided: fold negative frequencies in
            psd += p.astype(dtype) / n_seg
    f_psd = np.arange(PSD_NFFT // 2 + 1) * FS / PSD_NFFT

    # 2. Coarse spectrum: six 2 s slices, magnitude x 100, three axes added.
    n_sub = (N - SPG_SEG) // SPG_STEP + 1
    spg = np.zeros((n_sub, SPG_NFFT // 2 + 1), dtype=dtype)
    wsum = float(w_spg.sum())
    for axis in range(3):
        for s in range(n_sub):
            seg = x[s * SPG_STEP: s * SPG_STEP + SPG_SEG, axis] * w_spg
            spec = np.fft.rfft(seg, SPG_NFFT) / wsum
            spg[s] += (np.sqrt(spec.real ** 2 + spec.imag ** 2) * 100).astype(dtype)

    # 3. Twelve shape numbers: filter bank, log, cosine weights, average.
    fb = t["filters"].astype(dtype)
    dct = t["dct"].astype(dtype)
    mfcc = np.zeros(N_COEF, dtype=dtype)
    for s in range(n_sub):
        bands = fb @ spg[s]
        logb = np.log10(bands + dtype(1e-10))
        mfcc += (dct @ logb) / n_sub

    # 4. Score: standardise, weigh, add, squash to 0..1, compare.
    z = (mfcc - model["mean"]) / model["scale"]
    total = float(z @ model["coef"]) + model["intercept"]
    prob = 1.0 / (1.0 + math.exp(-total))
    logreg = prob >= model["threshold"]

    # 5. Two checks on the fine spectrum.
    band = (f_psd >= 1) & (f_psd <= 25)
    peak = f_psd[band][int(np.argmax(psd[band]))]
    below = (f_psd >= 0.5) & (f_psd < 3)
    below_power = 0.25 * float(psd[below].sum())
    at_rest = below_power <= 50
    tremor = logreg and 3 <= peak <= 7 and at_rest
    return dict(mfcc=mfcc, prob=prob, peak=peak, below=below_power,
                at_rest=at_rest, tremor=tremor)
