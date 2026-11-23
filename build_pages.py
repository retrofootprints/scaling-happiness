"""Build colors.html (average canvas colour) and pigments.html (likely palette).

Reads gallery.json + thumbs/ produced by build_gallery.py; no network access.
Requires Pillow.

Average colour: mean of every pixel of the painted surface only, computed in
linear light (sRGB decoded, averaged, re-encoded), i.e. the colour you would see
if the whole painting were optically blurred into one tone. Frames and photo
margins are excluded via CANVAS_REGIONS / a small default inset.
"""

import csv
import html
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent

# Default: trim 1% from each edge (photo edge artefacts, thin scan margins).
DEFAULT_INSET = 0.01

# Explicit painted-surface rectangles, in pixels of the 500px-wide thumbnail,
# for images whose photo includes a frame. Found by scanning for dark frame strips.
CANVAS_REGIONS = {
    # triptych photographed in its black frame: average the three panels only
    "the-garden-of-earthly-delights": [(5, 6, 115, 280), (123, 6, 379, 280), (386, 6, 495, 280)],
}

# --- Pigments -----------------------------------------------------------------
# Approximate masstone colour of each pigment (for the swatch).
PIGMENTS = {
    "Lead white": "#F2EFE6", "Zinc white": "#F8F8F3", "Lime white": "#F3F0E4",
    "Yellow ochre": "#C9962E", "Red ochre": "#9E3B26", "Green earth": "#7C8A63",
    "Raw umber": "#5E4A33", "Burnt umber": "#6B3D24",
    "Bone black": "#1E1C1B", "Ivory black": "#1B1A19", "Carbon black": "#232323", "Sumi ink": "#1F1F1F",
    "Vermilion": "#D8342B", "Red lake": "#9E1B32", "Madder lake": "#B0263F",
    "Geranium lake": "#E24B6E", "Alizarin crimson": "#8E1A2E", "Cadmium red": "#D52B1E",
    "Lead-tin yellow": "#E8C84A", "Naples yellow": "#F0C66A", "Orpiment / pararealgar": "#E9B53A",
    "Chrome yellow": "#F2B705", "Zinc yellow": "#F2E24A", "Cadmium yellow": "#F5C400",
    "Indian yellow": "#E3A82B", "Weld (yellow lake)": "#CFB43A",
    "Natural ultramarine (lapis lazuli)": "#2A3F9E", "Synthetic ultramarine": "#2B3BA8",
    "Azurite": "#2F5DA0", "Smalt": "#4A62A6", "Prussian blue": "#1E2F5A", "Indigo": "#2E3355",
    "Cobalt blue": "#0047AB", "Cerulean blue": "#2A7AB0",
    "Verdigris / copper green": "#3E8F7A", "Emerald green": "#2EB872", "Viridian": "#2C7A63",
    "Cobalt violet": "#9B4F96", "Gold leaf": "#D4AF37", "Silver leaf": "#C0C0C0",
}

# Per painting: (pigment, basis) where basis is
#   "D" = reported in published technical / conservation studies (or, for Monet,
#         his own stated palette), and
#   "L" = likely: consistent with the artist's known palette and the period,
#         and with the colours visible in the painting.
D, L = "D", "L"
PALETTES = {
    "Mona Lisa": [("Lead white", D), ("Vermilion", D), ("Yellow ochre", D), ("Raw umber", D),
                  ("Verdigris / copper green", L), ("Red lake", L),
                  ("Natural ultramarine (lapis lazuli)", L), ("Bone black", L)],
    "The Birth of Venus": [("Lead white", L), ("Natural ultramarine (lapis lazuli)", L), ("Azurite", L),
                           ("Vermilion", L), ("Red lake", L), ("Yellow ochre", L),
                           ("Verdigris / copper green", L), ("Green earth", L), ("Gold leaf", D)],
    "The Creation of Adam": [("Lime white", D), ("Yellow ochre", D), ("Red ochre", D), ("Green earth", D),
                             ("Carbon black", D), ("Raw umber", L), ("Burnt umber", L), ("Smalt", L)],
    "The Garden of Earthly Delights": [("Lead white", D), ("Azurite", D), ("Vermilion", D), ("Red lake", D),
                                       ("Verdigris / copper green", D), ("Lead-tin yellow", L),
                                       ("Natural ultramarine (lapis lazuli)", L), ("Yellow ochre", L),
                                       ("Bone black", L)],
    "Girl with a Pearl Earring": [("Natural ultramarine (lapis lazuli)", D), ("Lead white", D),
                                  ("Yellow ochre", D), ("Vermilion", D), ("Red lake", D), ("Indigo", D),
                                  ("Weld (yellow lake)", D), ("Raw umber", D), ("Bone black", D),
                                  ("Carbon black", D)],
    "The Night Watch": [("Lead white", D), ("Lead-tin yellow", D), ("Yellow ochre", D), ("Red ochre", D),
                        ("Vermilion", D), ("Red lake", D), ("Smalt", D), ("Orpiment / pararealgar", D),
                        ("Raw umber", D), ("Bone black", D), ("Azurite", L)],
    "Las Meninas": [("Lead white", D), ("Vermilion", D), ("Red lake", D), ("Azurite", D), ("Red ochre", D),
                    ("Carbon black", D), ("Smalt", L), ("Yellow ochre", L), ("Raw umber", L)],
    "The Great Wave off Kanagawa": [("Prussian blue", D), ("Indigo", D), ("Sumi ink", D)],
    "Wanderer above the Sea of Fog": [("Lead white", L), ("Prussian blue", L), ("Yellow ochre", L),
                                      ("Red ochre", L), ("Raw umber", L), ("Burnt umber", L),
                                      ("Vermilion", L), ("Bone black", L)],
    "The Third of May 1808": [("Lead white", L), ("Vermilion", L), ("Red ochre", L), ("Yellow ochre", L),
                              ("Naples yellow", L), ("Prussian blue", L), ("Raw umber", L), ("Bone black", L)],
    "Liberty Leading the People": [("Lead white", L), ("Vermilion", L), ("Red lake", L), ("Prussian blue", L),
                                   ("Cobalt blue", L), ("Yellow ochre", L), ("Naples yellow", L),
                                   ("Chrome yellow", L), ("Emerald green", L), ("Red ochre", L),
                                   ("Raw umber", L), ("Bone black", L)],
    "The Fighting Temeraire": [("Lead white", D), ("Chrome yellow", D), ("Vermilion", D), ("Red lake", L),
                               ("Cobalt blue", L), ("Synthetic ultramarine", L), ("Indian yellow", L),
                               ("Naples yellow", L), ("Yellow ochre", L), ("Bone black", L)],
    "The Starry Night": [("Synthetic ultramarine", D), ("Cobalt blue", D), ("Chrome yellow", D),
                         ("Emerald green", D), ("Zinc white", D), ("Prussian blue", L), ("Lead white", L),
                         ("Viridian", L)],
    "Sunflowers": [("Chrome yellow", D), ("Emerald green", D), ("Synthetic ultramarine", D),
                   ("Geranium lake", D), ("Vermilion", D), ("Zinc white", D), ("Lead white", D),
                   ("Yellow ochre", L), ("Prussian blue", L)],
    "Water Lilies": [("Lead white", D), ("Cadmium yellow", D), ("Vermilion", D), ("Madder lake", D),
                     ("Cobalt blue", D), ("Emerald green", D), ("Synthetic ultramarine", L),
                     ("Viridian", L), ("Cobalt violet", L), ("Chrome yellow", L)],
    "Impression, Sunrise": [("Lead white", L), ("Cobalt blue", L), ("Synthetic ultramarine", L),
                            ("Vermilion", L), ("Red lake", L), ("Chrome yellow", L),
                            ("Emerald green", L), ("Viridian", L)],
    "A Sunday Afternoon on the Island of La Grande Jatte": [
        ("Zinc yellow", D), ("Chrome yellow", D), ("Emerald green", D), ("Cobalt blue", D),
        ("Synthetic ultramarine", D), ("Vermilion", D), ("Red lake", D), ("Zinc white", D),
        ("Lead white", D), ("Viridian", L)],
    "Bal du moulin de la Galette": [("Lead white", L), ("Cobalt blue", L), ("Synthetic ultramarine", L),
                                    ("Vermilion", L), ("Madder lake", L), ("Chrome yellow", L),
                                    ("Naples yellow", L), ("Viridian", L), ("Emerald green", L),
                                    ("Ivory black", L)],
    "The Card Players": [("Lead white", L), ("Prussian blue", L), ("Synthetic ultramarine", L),
                         ("Cobalt blue", L), ("Emerald green", L), ("Viridian", L), ("Vermilion", L),
                         ("Red lake", L), ("Chrome yellow", L), ("Yellow ochre", L), ("Red ochre", L),
                         ("Ivory black", L)],
    "The Kiss": [("Gold leaf", D), ("Silver leaf", D), ("Lead white", L), ("Zinc white", L),
                 ("Cadmium yellow", L), ("Yellow ochre", L), ("Synthetic ultramarine", L), ("Viridian", L),
                 ("Vermilion", L), ("Red lake", L), ("Ivory black", L)],
    "The Scream": [("Cadmium yellow", D), ("Vermilion", D), ("Synthetic ultramarine", D), ("Viridian", L),
                   ("Red ochre", L), ("Zinc white", L)],
    "Broadway Boogie Woogie": [("Cadmium yellow", L), ("Cadmium red", L), ("Synthetic ultramarine", L),
                               ("Cobalt blue", L), ("Lead white", L), ("Zinc white", L)],
    "Composition VIII": [("Cadmium yellow", L), ("Cadmium red", L), ("Synthetic ultramarine", L),
                         ("Cobalt blue", L), ("Cerulean blue", L), ("Viridian", L), ("Alizarin crimson", L),
                         ("Cobalt violet", L), ("Yellow ochre", L), ("Zinc white", L), ("Lead white", L),
                         ("Ivory black", L)],
}

# --- Average colour -------------------------------------------------------------
TO_LIN = [((v / 255) / 12.92) if v / 255 <= 0.04045 else (((v / 255) + 0.055) / 1.055) ** 2.4
          for v in range(256)]


def to_srgb(c):
    c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return max(0, min(255, round(c * 255)))


def regions_for(slug, size):
    if slug in CANVAS_REGIONS:
        return CANVAS_REGIONS[slug]
    w, h = size
    dx, dy = round(w * DEFAULT_INSET), round(h * DEFAULT_INSET)
    return [(dx, dy, w - dx, h - dy)]


def average_color(path):
    im = Image.open(path).convert("RGB")
    sums, n = [0.0, 0.0, 0.0], 0
    for box in regions_for(path.stem, im.size):
        hist = im.crop(box).histogram()  # 3 x 256 bins
        for ch in range(3):
            bins = hist[ch * 256:(ch + 1) * 256]
            sums[ch] += sum(cnt * TO_LIN[v] for v, cnt in enumerate(bins))
        n += (box[2] - box[0]) * (box[3] - box[1])
    rgb = tuple(to_srgb(s / n) for s in sums)
    return rgb, "#{:02X}{:02X}{:02X}".format(*rgb)


def text_on(rgb):
    lum = sum(TO_LIN[c] * k for c, k in zip(rgb, (0.2126, 0.7152, 0.0722)))
    return "#111" if lum > 0.18 else "#fff"


# --- HTML -------------------------------------------------------------------------
NAV = [("index.html", "Gallery"), ("colors.html", "Average colour"), ("pigments.html", "Pigments")]

SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --bg:#f6f3ee; --card:#fff; --ink:#1d1b18; --muted:#6b645a; --line:#e4ddd2; --accent:#8a4b2a; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#151412; --card:#1f1d1a; --ink:#eee8df; --muted:#a39a8d; --line:#33302b; --accent:#e0a070; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.45 Georgia, "Times New Roman", serif; }}
  header {{ max-width:1280px; margin:0 auto; padding:32px 16px 24px; }}
  nav {{ display:flex; gap:18px; flex-wrap:wrap; font-family:system-ui,sans-serif; font-size:.9rem; margin-bottom:28px; }}
  nav a {{ color:var(--muted); text-decoration:none; padding-bottom:2px; border-bottom:2px solid transparent; }}
  nav a[aria-current] {{ color:var(--ink); border-color:var(--accent); }}
  h1 {{ font-size:clamp(1.8rem,4vw,2.8rem); margin:0 0 8px; font-weight:normal; }}
  header p {{ margin:0; color:var(--muted); font-family:system-ui,sans-serif; font-size:.95rem; max-width:70ch; }}
  main {{ max-width:1280px; margin:0 auto; padding:0 16px 64px; display:grid; gap:20px;
         grid-template-columns:repeat(4,1fr); }}
  @media (max-width:1000px) {{ main {{ grid-template-columns:repeat(3,1fr); }} }}
  @media (max-width:700px)  {{ main {{ grid-template-columns:repeat(2,1fr); gap:12px; }} }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:6px; overflow:hidden;
          display:flex; flex-direction:column; }}
  .meta {{ padding:12px 14px 14px; display:flex; flex-direction:column; gap:2px; }}
  .meta h2 {{ font-size:1.02rem; margin:0; line-height:1.25; }}
  .by {{ color:var(--muted); font-family:system-ui,sans-serif; font-size:.85rem; }}
  footer {{ max-width:1280px; margin:0 auto; color:var(--muted); font-family:system-ui,sans-serif;
           font-size:.8rem; padding:0 16px 40px; }}
{extra_css}
</style>
</head>
<body>
<header>
  <nav>{nav}</nav>
  <h1>{h1}</h1>
  <p>{intro}</p>
</header>
<main>
{cards}
</main>
<footer>{footer}</footer>
</body>
</html>
"""


def nav_html(current):
    return "".join(f'<a href="{href}"{" aria-current=\"page\"" if href == current else ""}>{label}</a>'
                   for href, label in NAV)


def meta_html(it):
    e = html.escape
    return (f'<div class="meta"><h2>{e(it["title"])}</h2>'
            f'<span class="by">{e(it["artist"])} · {e(it["year"])}</span>')


COLORS_CSS = """
  .swatch { aspect-ratio:1; display:flex; align-items:flex-end; justify-content:space-between;
            padding:12px 14px; font-family:ui-monospace,Consolas,monospace; font-size:.82rem; }
  .swatch img { width:44px; height:44px; object-fit:cover; border-radius:3px;
                box-shadow:0 0 0 1px #0002; }
"""

PIGMENTS_CSS = """
  .chips { list-style:none; margin:0; padding:12px 14px 16px; display:grid;
           grid-template-columns:repeat(auto-fill,minmax(70px,1fr)); gap:10px 8px; flex:1; align-content:start;
           border-bottom:1px solid var(--line); }
  .chips li { display:flex; flex-direction:column; gap:4px; font-family:system-ui,sans-serif;
              font-size:.7rem; line-height:1.15; }
  .chips i { display:block; height:34px; border-radius:4px; box-shadow:inset 0 0 0 1px #0002; }
  .chips li.L i { outline:2px dashed var(--muted); outline-offset:2px; }
  .chips li.L span { color:var(--muted); }
  .legend { display:flex; gap:18px; margin-top:12px; flex-wrap:wrap; }
  .legend i { display:inline-block; width:14px; height:14px; vertical-align:-2px; margin-right:6px;
              border-radius:3px; background:#b08850; }
  .legend .L i { outline:2px dashed var(--muted); outline-offset:1px; }
"""


def build_colors(items):
    cards, rows = [], []
    for it in items:
        rgb, hexv = average_color(ROOT / it["thumb"])
        it["avg_hex"], it["avg_rgb"] = hexv, rgb
        rows.append([it["title"], it["artist"], it["year"], hexv, *rgb])
        e = html.escape
        cards.append(
            f'  <article class="card">\n'
            f'    <div class="swatch" style="background:{hexv};color:{text_on(rgb)}">'
            f'<span>{hexv}<br>rgb({rgb[0]}, {rgb[1]}, {rgb[2]})</span>'
            f'<img src="{e(it["thumb"])}" alt="" loading="lazy" decoding="async"></div>\n'
            f'    {meta_html(it)}</div>\n  </article>')
    page = SHELL.format(
        title="Average Colours", nav=nav_html("colors.html"), h1="Average colour of each canvas",
        intro=("One colour per painting: the mean of every pixel of the painted surface, averaged in "
               "linear light (what the painting looks like blurred into a single tone). Frames, scan "
               "margins and museum surroundings are excluded."),
        cards="\n".join(cards), extra_css=COLORS_CSS,
        footer=("Computed from 500px Wikimedia Commons reproductions; photography and colour "
                "calibration differ between sources, so treat values as approximate. Data: colors.csv."))
    (ROOT / "colors.html").write_text(page, encoding="utf-8")
    with open(ROOT / "colors.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "artist", "year", "hex", "r", "g", "b"])
        w.writerows(rows)


def build_pigments(items):
    cards, rows = [], []
    for it in items:
        palette = PALETTES[it["title"]]
        chips = []
        for name, basis in palette:
            chips.append(f'<li class="{basis}"><i style="background:{PIGMENTS[name]}"></i>'
                         f'<span>{html.escape(name)}</span></li>')
            rows.append([it["title"], it["artist"], name, PIGMENTS[name],
                         "documented" if basis == D else "likely"])
        cards.append(f'  <article class="card">\n    <ul class="chips">{"".join(chips)}</ul>\n'
                     f'    {meta_html(it)}</div>\n  </article>')
    page = SHELL.format(
        title="Painters' Pigments", nav=nav_html("pigments.html"), h1="The pigments behind each painting",
        intro=("The paints each artist most likely used. Solid swatches are pigments reported in "
               "technical and conservation studies of the work (for Monet, his own stated palette); "
               "dashed swatches are likely, based on the artist's known palette, the period and the colours "
               "visible in the painting."
               '<span class="legend"><span><i></i>Documented</span><span class="L"><i></i>Likely</span></span>'),
        cards="\n".join(cards), extra_css=PIGMENTS_CSS,
        footer=("Swatches show each pigment's approximate pure colour, not how it appears in the painting. "
                "Compiled from general knowledge of the conservation literature, not from per-pigment "
                "citations; verify before quoting. Data: pigments.csv."))
    (ROOT / "pigments.html").write_text(page, encoding="utf-8")
    with open(ROOT / "pigments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "artist", "pigment", "swatch_hex", "basis"])
        w.writerows(rows)


def main():
    items = json.loads((ROOT / "gallery.json").read_text(encoding="utf-8"))
    missing = [it["title"] for it in items if it["title"] not in PALETTES]
    if missing:
        raise SystemExit(f"No palette defined for: {missing}")
    build_colors(items)
    build_pigments(items)
    for it in items:
        print(f'{it["avg_hex"]}  {it["title"]}')


if __name__ == "__main__":
    main()
