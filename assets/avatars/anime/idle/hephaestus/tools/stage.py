"""Shared stage lighting for Kourai portraits on a flat background.

usage: stage.py IN.png OUT.png [--bg 55] [--rim 0.22]
Replaces the flat background (only the region connected to the border) with a
cool slate radial glow brighter behind the head, and adds a faint cool rim
along the silhouette. Edge pixels blended with the old grey are shifted by
(1 - a) * (new - old), so anti-aliased hair and smoke keep no grey fringe.
"""

import argparse

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

CENTER = np.array([78, 106, 127], np.float32)  # behind the head
EDGE = np.array([47, 62, 83], np.float32)  # lower edges
RIM = np.array([150, 185, 225], np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--bg", type=float, default=55)
    ap.add_argument("--rim", type=float, default=0.22)
    ap.add_argument("--backdrop-out")
    a = ap.parse_args()

    im = np.asarray(Image.open(a.src).convert("RGB")).astype(np.float32)
    out, backdrop, bgreg, g = stage(im, a.bg, a.rim)
    if a.backdrop_out:
        Image.fromarray(np.clip(backdrop, 0, 255).round().astype(np.uint8)).save(a.backdrop_out)
    Image.fromarray(np.clip(out, 0, 255).round().astype(np.uint8)).save(a.dst)
    print(f"bg px {bgreg.mean():.1%}, edge band {((g > 0) & (g < 1)).mean():.2%}")


def stage(im, bg=55.0, rim_amt=0.22):
    """Return (lit image, backdrop, background mask, grey-likeness) for a float RGB array."""
    h, w, _ = im.shape
    diff = np.abs(im - bg).max(-1)

    # background = near-grey pixels connected to the border
    near = diff <= 10
    lab, _ = ndimage.label(near)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    bgreg = np.isin(lab, border[border > 0])
    band = ndimage.binary_dilation(bgreg, iterations=3)
    # grey-likeness: 1 on pure grey, 0 at diff >= 40, only inside the band
    g = np.clip((40 - diff) / 36, 0, 1) * band
    g[bgreg] = 1.0
    # smoke zone: purple ribbons let the old grey show through and enclose grey holes
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    purple = ((R + B) / 2 - G > 25) & (B > G + 15)
    zone = ndimage.binary_dilation(purple, iterations=10)
    sat = im.max(-1) - im.min(-1)
    gz = np.clip((40 - diff) / 36, 0, 1) * np.clip((30 - sat) / 20, 0, 1)
    # translucent smoke: shift by how much grey is mixed in (hue-preserving)
    mix = np.clip(1 - (sat / 90), 0, 1) * np.clip((70 - diff) / 60, 0, 1)
    g = np.where(zone, np.maximum(g, np.maximum(gz, mix * purple)), g)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    m = min(w, h)
    r = np.sqrt(((xx - 0.5 * w) / (0.62 * m)) ** 2 + ((yy - 0.27 * h) / (0.78 * m)) ** 2)
    t = np.clip(r, 0, 1)[..., None] ** 1.4
    backdrop = CENTER * (1 - t) + EDGE * t

    out = im + g[..., None] * (backdrop - bg)

    # faint cool rim: inside edge of the figure, stronger toward the top
    fig = ~bgreg
    edge = fig & ~ndimage.binary_erosion(fig, iterations=4)
    rim = np.asarray(Image.fromarray((edge * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(3))).astype(np.float32) / 255
    rim *= fig * np.clip(1.2 - yy / h, 0, 1) * rim_amt
    out = out + rim[..., None] * (RIM - out) * 0.6
    return out, backdrop, bgreg, g


if __name__ == "__main__":
    main()
