"""Cut a seamless loop from a take and encode WebM (VP9) and MP4 (H.264).

usage: loopcut.py VIDEO --crop W:H:X:Y --size WxH --start F --end F [--xfade K] --out PREFIX
Frames [start, end) form the loop. With --xfade K, the last K frames are blended
toward the K frames just before `start` (or, when start < K, the first K frames
toward the K frames just after `end`), so the last frame flows into the first.
"""

import argparse
import os
import subprocess

import numpy as np


def read(path, crop, w, h):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"crop={crop},scale={w}:{h}:flags=lanczos",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def loop(F, s, e, k):
    seg = F[s:e].astype(np.float32).copy()
    if k:
        a = ((np.arange(1, k + 1)) / (k + 1)).astype(np.float32)[:, None, None, None]
        if s >= k:  # end -> blend toward frames that precede start
            seg[-k:] = seg[-k:] * (1 - a) + F[s - k:s].astype(np.float32) * a
        elif e + k <= len(F):  # start <- blend from frames that follow end
            seg[:k] = F[e:e + k].astype(np.float32) * (1 - a) + seg[:k] * a
        else:
            raise SystemExit("no room for the crossfade")
    return np.clip(seg.round(), 0, 255).astype(np.uint8)


def encode(frames, fps, w, h, out, args):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", *args, out],
                         stdin=subprocess.PIPE)
    p.stdin.write(frames.tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit(f"ffmpeg failed for {out}")
    return os.path.getsize(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--crop", required=True)
    ap.add_argument("--size", required=True)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--xfade", type=int, default=0)
    ap.add_argument("--fps", type=float, default=24)
    ap.add_argument("--webm-crf", type=int, default=36)
    ap.add_argument("--mp4-crf", type=int, default=24)
    ap.add_argument("--stage", action="store_true", help="apply stage.py lighting to every frame")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    F = read(a.video, a.crop, w, h)
    L = loop(F, a.start, a.end, a.xfade)
    if a.stage:
        from stage import stage
        L = np.stack([np.clip(stage(f.astype(np.float32))[0], 0, 255).round().astype(np.uint8) for f in L])
    seam = float(np.abs(L[-1].astype(np.int16) - L[0].astype(np.int16)).mean())
    step = float(np.mean([np.abs(L[i + 1].astype(np.int16) - L[i].astype(np.int16)).mean()
                          for i in range(len(L) - 1)]))
    wb = encode(L, a.fps, w, h, a.out + ".webm",
                ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str(a.webm_crf), "-row-mt", "1",
                 "-pix_fmt", "yuv420p", "-an"])
    mp = encode(L, a.fps, w, h, a.out + ".mp4",
                ["-c:v", "libx264", "-preset", "slow", "-crf", str(a.mp4_crf), "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", "-an"])
    print(f"frames {len(L)} ({len(L) / a.fps:.3f} s), seam mad {seam:.2f}, "
          f"mean step mad {step:.2f}, webm {wb / 1e6:.2f} MB, mp4 {mp / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
