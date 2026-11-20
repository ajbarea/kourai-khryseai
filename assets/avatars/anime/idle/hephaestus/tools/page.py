"""Build the side-by-side review page from manifest.json.

manifest: {"title": str, "note": str, "rows": [{"label": str, "caption": str,
           "still": "file.png", "webm": "file.webm", "mp4": "file.mp4",
           "aspect": "3 / 5"}]}
"""

import html
import json
import sys

m = json.load(open(sys.argv[1]))
out = sys.argv[2]
e = html.escape

rows = []
for r in m["rows"]:
    rows.append(f"""
  <section class="row">
    <header><h2>{e(r["label"])}</h2><p>{e(r["caption"])}</p></header>
    <div class="pair" style="--ar: {r["aspect"]}">
      <figure><img src="{e(r["still"])}" alt="Still portrait"><figcaption>Still</figcaption></figure>
      <figure><video autoplay loop muted playsinline poster="{e(r["still"])}">
        <source src="{e(r["webm"])}" type="video/webm"><source src="{e(r["mp4"])}" type="video/mp4"></video>
        <figcaption>Loop</figcaption></figure>
    </div>
  </section>""")

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Heph idle loop</title>
<style>
:root {{ --bg: #14171c; --fg: #e8e6e1; --muted: #a8a49c; --card: #1d2128; --line: #2c313a; }}
@media (prefers-color-scheme: light) {{ :root:not([data-theme="dark"]) {{
  --bg: #f4f2ee; --fg: #1d1b18; --muted: #5c5850; --card: #ffffff; --line: #ddd8cf; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 1880px; margin: 0 auto; padding: 24px 16px 48px; }}
h1 {{ font-size: 1.6rem; margin: 0 0 4px; }}
.note {{ color: var(--muted); margin: 0 0 24px; max-width: 80ch; }}
.row {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 16px; margin-bottom: 20px; }}
.row header h2 {{ font-size: 1.1rem; margin: 0; }}
.row header p {{ color: var(--muted); margin: 2px 0 12px; }}
.pair {{ display: flex; gap: 16px; flex-wrap: wrap; }}
figure {{ margin: 0; flex: 0 1 auto; }}
figure img, figure video {{ display: block; height: min(78vh, 900px); width: auto;
  max-width: 100%; aspect-ratio: var(--ar); object-fit: cover; border-radius: 8px; background: #000; }}
figcaption {{ color: var(--muted); font-size: .9rem; margin-top: 4px; }}
@media (max-width: 700px) {{ figure img, figure video {{ height: auto; width: 100%; }} figure {{ flex: 1 1 100%; }} }}
</style>
</head>
<body><main>
  <h1>{e(m["title"])}</h1>
  <p class="note">{e(m["note"])}</p>
  {"".join(rows)}
</main></body>
</html>
"""
open(out, "w").write(page)
print(out)
