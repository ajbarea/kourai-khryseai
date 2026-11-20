"""Blink timing from eye-window brightness vs the take's own frame 0, face-aligned."""
import json, sys
import numpy as np
sys.argv, args = sys.argv[:1], sys.argv[1:]
import score as S
from PIL import Image

def run(video, ref, crop, off):
    ox, oy = off
    face = (S.FACE[0]-ox, S.FACE[1]-oy, S.FACE[2]-ox, S.FACE[3]-oy)
    eyes = (S.EYES[0]-ox, S.EYES[1]-oy, S.EYES[2]-ox, S.EYES[3]-oy)
    P = np.asarray(Image.open(ref).convert("RGB")); rh, rw = P.shape[:2]
    _, _, fps = S.probe(video)
    F = S.frames(video, crop, rw, rh)
    lum = []
    for f in F:
        _, (dy, dx) = S.face_aligned(f, F[0], face)
        lum.append(S.gray(S.crop(np.roll(f, (dy, dx), (0, 1)), eyes)).mean())
    lum = np.array(lum) - lum[0]
    closed = lum > 8.0  # lids brighter than open sockets by 8 grey levels
    runs, i = [], 0
    while i < len(F):
        if closed[i]:
            j = i
            while j + 1 < len(F) and closed[j + 1]: j += 1
            if j - i + 1 >= 2:
                runs.append({"start_s": round(i / fps, 3), "end_s": round((j + 1) / fps, 3), "ms": round((j - i + 1) / fps * 1000)})
            i = j + 1
        else: i += 1
    return {"blinks": runs, "lum_rise_max": round(float(lum.max()), 1), "lum_curve": [round(float(x), 1) for x in lum]}

out = {}
for spec in args:
    name, video, ref, crop, off = spec.split("|")
    out[name] = run(video, ref, crop, tuple(int(v) for v in off.split(",")))
    print(name, out[name]["blinks"], "max rise", out[name]["lum_rise_max"])
json.dump(out, open("scores/eyes.json", "w"), indent=1)
