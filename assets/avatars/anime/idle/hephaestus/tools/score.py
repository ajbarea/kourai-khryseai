"""Score an idle-loop take against the still portrait.

usage: score.py VIDEO REF.png [--crop W:H:X:Y] [--backdrop BG.png] [--offset X,Y] [--json OUT]
REF is the still the take should match, already cut to the same window as --crop.
Frames are cropped and scaled to REF's size. Box coordinates are in the 640 px
square portrait; --offset is where REF's window starts in that square.
All diffs are mean absolute differences on a 0-255 scale.
"""

import argparse
import json
import subprocess

import numpy as np
from PIL import Image

N = 640
BG = 55  # flat background grey of the portrait
FACE = (262, 50, 390, 210)  # x0, y0, x1, y1 in 640 coords
TORSO = (150, 90, 500, 340)
EYES = (292, 106, 368, 132)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate,nb_frames", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return s["width"], s["height"], float(num) / float(den)


def frames(path, crop, w, h):
    vf = (f"crop={crop}," if crop else "") + f"scale={w}:{h}:flags=lanczos"
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", vf, "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def gray(a):
    return a[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)


def box_filter(x, r):
    k = 2 * r + 1
    p = np.pad(x, r + 1, mode="edge")
    c = p.cumsum(0).cumsum(1)
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s[: x.shape[0], : x.shape[1]] / (k * k)


def ssim(a, b, r=3):
    a, b = gray(a), gray(b)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    ma, mb = box_filter(a, r), box_filter(b, r)
    va = box_filter(a * a, r) - ma * ma
    vb = box_filter(b * b, r) - mb * mb
    cov = box_filter(a * b, r) - ma * mb
    m = ((2 * ma * mb + c1) * (2 * cov + c2)) / ((ma * ma + mb * mb + c1) * (va + vb + c2))
    return float(m.mean())


def mad(a, b, mask=None):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).mean(-1)
    return float(d[mask].mean() if mask is not None else d.mean())


def phase_shift(a, b):
    """Sub-pixel-free translation of b relative to a (dy, dx) by phase correlation."""
    A, B = np.fft.fft2(gray(a)), np.fft.fft2(gray(b))
    R = A * np.conj(B)
    R /= np.abs(R) + 1e-9
    r = np.abs(np.fft.ifft2(R))
    dy, dx = np.unravel_index(np.argmax(r), r.shape)
    h, w = r.shape
    return (dy - h if dy > h // 2 else dy), (dx - w if dx > w // 2 else dx)


def unzoom(f, s, fill):
    """Shrink (s > 1) or grow frame f about its centre by 1/s, filling with `fill`."""
    h, w = f.shape[:2]
    nw, nh = max(1, round(w / s)), max(1, round(h / s))
    im = np.asarray(Image.fromarray(f).resize((nw, nh), Image.LANCZOS))
    out = fill.copy()
    y0, x0 = (h - nh) // 2, (w - nw) // 2
    sy0, sx0 = max(0, -y0), max(0, -x0)
    dy0, dx0 = max(0, y0), max(0, x0)
    hh, ww = min(nh - sy0, h - dy0), min(nw - sx0, w - dx0)
    out[dy0:dy0 + hh, dx0:dx0 + ww] = im[sy0:sy0 + hh, sx0:sx0 + ww]
    return out


def register(f, ref, fill):
    """Zoom s and shift (dy, dx) that best map frame f back onto ref."""
    best = None
    for s in np.arange(0.90, 1.305, 0.01):
        u = unzoom(f, s, fill)
        dy, dx = phase_shift(ref, u)
        v = np.roll(u, (dy, dx), (0, 1))
        m = mad(v[20:-20, 20:-20], ref[20:-20, 20:-20])
        if best is None or m < best[0]:
            best = (m, float(s), int(dy), int(dx))
    return best


def warp(f, reg, fill):
    _, s, dy, dx = reg
    return np.roll(unzoom(f, s, fill), (dy, dx), (0, 1))


def face_aligned(f, ref, box, pad=24):
    """Crop `box` from f after matching f's face window to ref's (head may move)."""
    h, w = f.shape[:2]
    x0, y0, x1, y1 = box
    X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)
    dy, dx = phase_shift(ref[Y0:Y1, X0:X1], f[Y0:Y1, X0:X1])
    ax0, ay0 = min(max(0, x0 - dx), w - (x1 - x0)), min(max(0, y0 - dy), h - (y1 - y0))
    return f[ay0:ay0 + (y1 - y0), ax0:ax0 + (x1 - x0)], (dy, dx)


def crop(a, b):
    x0, y0, x1, y1 = b
    return a[y0:y1, x0:x1]


def erode(m, r):
    return box_filter(m.astype(np.float32), r) > 0.999


def minima(d, fps, lo_s=1.0):
    out = []
    for i in range(int(lo_s * fps), len(d) - 1):
        if d[i] < d[i - 1] and d[i] <= d[i + 1]:
            out.append((round(i / fps, 3), round(float(d[i]), 2), i))
    return out


def score(video, portrait, crop_spec, backdrop=None, offset=(0, 0)):
    global FACE, EYES, TORSO
    ox, oy = offset
    FACE, EYES, TORSO = ((b[0] - ox, b[1] - oy, b[2] - ox, b[3] - oy) for b in (FACE, EYES, TORSO))
    w, h, fps = probe(video)
    P = np.asarray(Image.open(portrait).convert("RGB"))
    rh, rw = P.shape[:2]
    FACE, EYES, TORSO = ((max(0, b[0]), max(0, b[1]), min(rw, b[2]), min(rh, b[3]))
                         for b in (FACE, EYES, TORSO))
    F = frames(video, crop_spec, rw, rh)
    n = len(F)
    BGI = (np.asarray(Image.open(backdrop).convert("RGB")).astype(np.int16)
           if backdrop else np.full_like(P, BG, dtype=np.int16))
    fill = BGI.astype(np.uint8)
    step = max(1, int(round(fps / 2)))
    zoom_track = [(round(i / fps, 2),) + register(F[i], P, fill)[1:] for i in range(0, n, step)]
    reg = register(F[n // 2], P, fill)
    W = np.stack([warp(f, reg, fill) for f in F]) if abs(reg[1] - 1) > 0.005 or reg[2] or reg[3] else F
    pg = np.abs(P.astype(np.int16) - BGI).max(-1)
    bg_mask = erode(pg <= 6, 8)  # background, kept 8 px clear of the figure

    d0 = np.array([mad(f, F[0]) for f in F])
    small = F[:, ::4, ::4]
    # best loop pair with period 2.0-4.0 s
    # pair cost over frames i-2..i+2 vs j-2..j+2, so position AND velocity must match
    K = 2
    pair = {}

    def pm(a, b):
        if (a, b) not in pair:
            pair[(a, b)] = mad(small[a], small[b])
        return pair[(a, b)]

    best = None
    for i in range(K, n - K):
        for j in range(i + int(2.0 * fps), min(n - K, i + int(4.0 * fps) + 1)):
            v = sum(pm(i + k, j + k) for k in range(-K, K + 1)) / (2 * K + 1)
            if best is None or v < best[0]:
                best = (v, i, j)
    bi, bj = best[1], best[2]
    best_full = mad(F[bi], F[bj])

    # amplitude: foreground centroid and torso translation
    cents = []
    for f in F:
        g = np.abs(f.astype(np.int16) - BGI).max(-1) > 12
        ys, xs = np.nonzero(g)
        cents.append((xs.mean(), ys.mean()))
    cents = np.array(cents)
    shifts = np.array([phase_shift(crop(W[0], TORSO), crop(f, TORSO)) for f in W])

    face_p = crop(P, FACE)
    aligned = [face_aligned(f, P, FACE) for f in W]
    face_mad = [mad(c, face_p) for c, _ in aligned]
    face_ssim = [ssim(c, face_p) for c, _ in aligned]
    head = np.array([d for _, d in aligned])
    eye_p = crop(P, EYES)
    eye = np.array([mad(crop(np.roll(f, tuple(head[i]), (0, 1)), EYES), eye_p)
                    for i, f in enumerate(W)])
    base = float(np.median(eye))
    closed = eye > max(base * 1.6, base + 6)
    blinks, i = [], 0
    while i < n:
        if closed[i]:
            j = i
            while j + 1 < n and closed[j + 1]:
                j += 1
            blinks.append({"start_s": round(i / fps, 3), "frames": int(j - i + 1),
                           "ms": round((j - i + 1) / fps * 1000), "peak_mad": round(float(eye[i:j + 1].max()), 1)})
            i = j + 1
        else:
            i += 1
    bg_motion = [mad(f, W[n // 2], bg_mask) for f in W[step:]]
    bg_vs_portrait = [mad(f, P, bg_mask) for f in W]

    return {
        "video": video, "src_size": [w, h], "scored_size": [rw, rh], "fps": fps, "frames": n,
        "duration_s": round(n / fps, 3), "crop": crop_spec,
        "registration_mid": {"scale": round(reg[1], 3), "dy": reg[2], "dx": reg[3], "mad": round(reg[0], 2)},
        "zoom_track": [[t, round(z, 3), dy, dx] for t, z, dy, dx in zoom_track],
        "frame0_vs_portrait_mad": round(mad(F[0], P), 2),
        "frame0_vs_portrait_ssim": round(ssim(F[0], P), 4),
        "seam_last_vs_first_mad": round(float(d0[-1]), 2),
        "d0_minima": [m[:2] for m in minima(d0, fps)][:8],
        "d0_max": round(float(d0.max()), 2),
        "best_loop": {"start_s": round(bi / fps, 3), "end_s": round(bj / fps, 3),
                      "period_s": round((bj - bi) / fps, 3), "mad": round(best_full, 2),
                      "window_mad": round(best[0], 2),
                      "start_frame": int(bi), "end_frame": int(bj)},
        "centroid_range_pct_w": [round(float(np.ptp(cents[:, 0])) / rw * 100, 2),
                                 round(float(np.ptp(cents[:, 1])) / rw * 100, 2)],
        "torso_shift_px_range": [int(np.ptp(shifts[:, 0])), int(np.ptp(shifts[:, 1]))],
        "torso_shift_pct_w": round(float(np.ptp(shifts[:, 0])) / rw * 100, 2),
        "head_shift_px_range": [int(np.ptp(head[:, 0])), int(np.ptp(head[:, 1]))],
        "face_mad": {"frame0": round(face_mad[0], 2), "mean": round(float(np.mean(face_mad)), 2),
                     "worst": round(float(np.max(face_mad)), 2)},
        "face_ssim": {"frame0": round(face_ssim[0], 4), "mean": round(float(np.mean(face_ssim)), 4),
                      "worst": round(float(np.min(face_ssim)), 4)},
        "eye_mad_median": round(base, 2),
        "blinks": blinks,
        "bg_motion_vs_mid": {"mean": round(float(np.mean(bg_motion)), 2),
                                "max": round(float(np.max(bg_motion)), 2)},
        "bg_vs_portrait_max": round(float(np.max(bg_vs_portrait)), 2),
        "d0_curve": [round(float(x), 2) for x in d0],
        "eye_curve": [round(float(x), 2) for x in eye],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("portrait")
    ap.add_argument("--crop", default="1080:1080:420:0")
    ap.add_argument("--backdrop")
    ap.add_argument("--offset", default="0,0")
    ap.add_argument("--json")
    a = ap.parse_args()
    off = tuple(int(v) for v in a.offset.split(","))
    r = score(a.video, a.portrait, a.crop or None, a.backdrop, off)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(r, fh, indent=1)
    short = {k: v for k, v in r.items() if not k.endswith("_curve")}
    print(json.dumps(short, indent=1))
