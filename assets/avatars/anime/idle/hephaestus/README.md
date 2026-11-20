<!-- budget: 1400 words -->
# Heph idle loop from Google Vids

**Why.** klepsydra#388 wants each Kourai card to come alive with a short idle loop. This spike tested whether Google Vids (Omni, image to video) can make one for Heph, and scored every take.

**Open `index.html`:** each still beside its loop, at card height.

| Loop | Period | Breathing | Blink | Face SSIM | Verdict |
|---|---|---|---|---|---|
| Take 1, lit in post | 2.58 s | 0.62% | one, shut about 0.33 s | 0.79 | **recommended** |
| Take 4, lit still | 3.50 s | 1.56% | one, shut about 0.6 s | 0.48 | alternative |

Targets: loop 2.5 to 3.5 s, breathing near 1% of width, blink 100 to 400 ms; an untouched face scores SSIM 0.97.

Take 1 is the take AJ watched live and liked; it meets every target, blinks once at the loop point, and was lit frame by frame after generation. Take 4, from the lit still and prompt v2, runs about twice the target on blink and breathing.

**Status:** ready for AJ to judge the feel. Both loops come square and tall 3:5 (the card column), WebM and MP4, each under 0.7 MB.

<details><summary>All takes, measured</summary>

Scored by `tools/score.py` on the square crop (tall breathing after the slash). MAD is mean absolute difference, 0-255; a normal frame step is about 1.4. Best loop: the pair 2 to 4 s apart whose ±2-frame runs match best. Breathing: peak-to-peak torso shift over the whole clip, % of width, head dips included. Face SSIM: mean / worst, face window aligned. Blinks for takes 1 and 4 are counted from 12 fps eye strips; the rest are approximate.

| Take | Prompt | Input | Seam, last vs first | Best loop (period, window MAD) | Breathing % sq / tall | Face SSIM | Camera zoom | Notes |
|---|---|---|---|---|---|---|---|---|
| take1 | v1 | flat grey, 16:9 | 8.1 | 2.46 s (2.75-5.21), 5.7 | 2.19 / 3.65 | 0.63 / 0.23 | 1.00-1.00 | AJ liked it live ("it animated heph pretty well on the first try"); eyes shut about 2.1 s (0.83 to 2.9 s) |
| take2 | v1 | flat grey, 16:9 | 9.2 | 2.71 s (0.25-2.96), 4.5 | 2.03 / 3.39 | 0.64 / 0.26 | 1.00-1.00 | eyes shut about 2.3 s |
| take3 | v2 | lit, 16:9 | 13.8 | 2.25 s (0.96-3.21), 7.9 | 1.56 / 2.60 | 0.58 / 0.26 | 1.00-1.00 | hair grows longer from 1 s; eyes shut about 1.5 s; period below 2.5 s |
| take4 | v2 | lit, 16:9 | 9.9 | 2.54 s (2.67-5.21), 7.0 | 1.56 / 2.60 | 0.53 / 0.32 | 1.00-1.00 | one blink, eyes shut about 0.6 s (1.08 to 1.67 s) |
| take5 | v2 | lit, 9:16 | 15.0 | 3.42 s (0.38-3.79), 9.5 | 3.39 | 0.61 / 0.27 | 1.00-1.03 | camera pushes in during the first 0.5 s; visible mark over the forge |
| take6 | v2 | lit, 9:16 | 15.2 | 2.12 s (0.88-3.00), 9.7 | 2.86 | 0.66 / 0.36 | 1.00-1.03 | camera pushes in; eyes shut about 2 s; visible mark over the forge |
| AJ's download | v1 | Vids export of take 1 | 7.9 | 2.40 s (2.73-5.13), 5.7 | 2.19 / 3.65 | 0.63 / 0.23 | 1.00-1.00 | same picture as take 1 (MAD 3.7), re-timed to 30 fps, letterboxed |

The delivered loops, scored as files (square):

| Loop | Frames | Seam after crossfade vs mean step | Breathing | Face SSIM | Background motion |
|---|---|---|---|---|---|
| take1 lit, 3.00-5.58 s | 62 | 2.19 vs 1.41 | 0.62% | 0.79 / 0.66 | 1.19 |
| take1 as generated | 62 | 2.21 vs 1.41 | 0.78% | 0.79 / 0.66 | 1.38 |
| take4, 0.75-4.25 s | 84 | 1.90 vs 1.59 | 1.56% | 0.48 / 0.32 | 1.60 |

Each loop crossfades its last 6 frames into the frames before its start, so the wrap stays within 1.6x of a normal step. In take 1 those frames have the eyes shut, which makes its blink (`contacts/eyes-take1-loop-wrap.jpg`).

Heph's 0.28% centroid range for AJ's download is a whole-figure measure, which the still oar and anvil damp; the torso window carries the breathing. The scorer was checked on the still bobbing 1.85% on a 3 s sine: it read 1.88%, 3.00 s and face SSIM 0.97.

</details>

<details><summary>Prompts (verbatim)</summary>

Every take used Vids' Animate tab: Omni, 1080p, 6 s, Landscape (takes 1 to 4) or Portrait (takes 5 and 6).

**v1** (takes 1 and 2), `prompt_v1.txt`:

> Static locked-off camera, no camera movement, no cuts. Subtle idle animation of this exact illustration, like a 2D game character idle loop. The blacksmith breathes slowly and gently: his chest and shoulders rise and fall slightly, one breath every three seconds. His beard and hair sway very slightly. The purple smoke rising from the hammer undulates and curls upward continuously, a stylized painterly ribbon with one small sparkle. The forge embers under the anvil flicker softly. He keeps the same pose, the same face and expression, holds the hammer still on the anvil, and does not speak. The flat dark grey background stays perfectly still. No new objects, no text, no music. The motion is a seamless loop that returns exactly to the first frame.

**v2** (takes 3 to 6), `prompt_v2.txt`. It follows AJ's notes during the run: blinking is good, breathing too hard and blinking too long are bad.

> Static locked-off camera, no camera movement, no cuts. Subtle idle animation of this exact illustration, like a 2D game character idle loop. The blacksmith breathes very softly and shallowly: his chest and shoulders rise and fall only a tiny amount, barely visible, one slow calm breath every three seconds, never heaving. He blinks exactly once, a very quick natural blink: the eyes close and reopen in a fraction of a second, then stay open for the rest of the clip. His beard and hair sway very slightly. The purple smoke rising from the hammer undulates and curls upward continuously, a stylized painterly ribbon with one small sparkle. The forge embers under the anvil flicker softly. He keeps the same pose, the same face and expression, holds the hammer still on the anvil, and does not speak. The cool slate-blue backdrop and its soft glow stay perfectly still; the lighting never changes. No new objects, no text, no music. The motion is a seamless loop that returns exactly to the first frame.

</details>

<details><summary>Inputs and lighting</summary>

- Takes 1 to 4: the 640 px portrait padded onto 16:9 in its own flat grey (55); loops are cropped from the centre. Takes 5 and 6: the window x 236 to 620 with backdrop on top, as 9:16. The tall 3:5 loops use that window.
- Lighting matches the Last Asylum hero clips, described in words only: a slate radial backdrop, rgb(78,106,127) behind the head to rgb(47,62,83) at the edges, and a faint cool rim. No reference went to Vids.
- Frame 0 is the uploaded still, so prompted lighting would ramp in and break the seam. `tools/stage.py` bakes it into the still (takes 3 to 6) or into each frame after generation (take 1). The second order is better: the model never sees the lighting, and the backdrop can change per theme.

</details>

<details><summary>What Vids allowed</summary>

- Animate tab: one start image, no last-frame slot, so loops are cut from inside a take. Omni only; 720p or 1080p; Landscape or Portrait (no square). The slider ran 3 to 15 s ([Google's help page](https://support.google.com/docs/answer/16143507) says 3 to 10 s), and the page says off-ratio images get black bars, so the art was padded first.
- One Generate makes one take in one to two minutes; Recreate repeats a take's settings. One take failed and succeeded on Try again.
- Takes: 1920x1080 or 1080x1920, H.264, 24 fps, with an AAC track despite "no music". AJ's timeline download is a 30 fps, letterboxed re-encode; `aj-download-hephaestus-idle-silent.mp4` drops its audio.
- Quota: six takes and one retry, no count or warning shown; the help page gives most users up to 50 clips a month.

</details>

<details><summary>The visible sparkle mark</summary>

Every take carries Google's visible sparkle, fixed bottom right (about x 1739, y 898 on 1920x1080). The landscape crops leave it out by framing; the portrait takes keep it over the forge. The sparkles in the smoke are the prompted ones.

What Google says: its [Generative AI Prohibited Use Policy](https://policies.google.com/terms/generative-ai/use-policy) (updated 2024-12-17) bars misrepresenting the provenance of generated content by claiming it was created solely by a human, in order to deceive; it does not mention visible marks. Since August 2026, Gemini and Flow let users switch the visible mark off for Omni, Nano Banana and Lyria (Settings > Media Watermark), while the invisible SynthID watermark and C2PA metadata stay ([TechCrunch, 2026-08-14](https://techcrunch.com/2026/08/14/google-will-now-allow-users-to-remove-visible-watermark-from-its-ai-generations/)). No rule specific to Vids was found, and the Vids help page does not mention the mark. Google describes SynthID as built to survive cropping and re-encoding (not tested here). If the loops ship, the cards should say the motion is AI-generated.

</details>

<details><summary>Files</summary>

`loops/` (WebM VP9 and MP4, no audio), `stills/` (posters), `contacts/` (each take at 2 fps, eye strips), `scores/scores.json` (every number), `tools/` (`score.py`, `stage.py`, `loopcut.py` and helpers; `uv run --with numpy --with pillow --with scipy`).

</details>
