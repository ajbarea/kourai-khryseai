import sys
import numpy as np
argv, sys.argv = sys.argv[1:], sys.argv[:1]
import score as S

def best(video, crop, w, h, smin, smax, emin, pmin=2.5, pmax=3.5, K=2):
    _, _, fps = S.probe(video)
    F = S.frames(video, crop, w, h)[:, ::4, ::4]
    n = len(F); memo = {}
    def pm(a, b):
        if (a, b) not in memo: memo[(a, b)] = S.mad(F[a], F[b])
        return memo[(a, b)]
    out = []
    for i in range(max(K, int(smin * fps)), min(n - K, int(smax * fps) + 1)):
        for j in range(i + int(pmin * fps), min(n - K, i + int(pmax * fps) + 1)):
            if j / fps < emin: continue
            out.append((sum(pm(i + k, j + k) for k in range(-K, K + 1)) / (2 * K + 1), i, j))
    out.sort()
    step = np.mean([S.mad(F[i], F[i + 1]) for i in range(n - 1)])
    return fps, out[:3], step

for spec in argv:
    name, video, crop, wh, smin, smax, emin = spec.split("|")
    w, h = map(int, wh.split("x"))
    fps, top, step = best(video, crop, w, h, float(smin), float(smax), float(emin))
    print(name, f"step {step:.2f}", [(round(c, 2), round(i / fps, 3), round(j / fps, 3), round((j - i) / fps, 3), i, j) for c, i, j in top])
