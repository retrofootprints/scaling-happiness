"""Build a public-domain painting gallery from Wikipedia / Wikimedia Commons.

Steps:
  1. Wikipedia API (prop=pageimages) -> lead image filename for each article
  2. Commons API (prop=imageinfo) -> 500px thumb URL, license, artist, file page
  3. Keep only "Public domain" licensed images; report everything else
  4. Download thumbnails to ./thumbs/
  5. Write index.html (linked images) and gallery-embedded.html (base64 inline)
  6. Write credits.csv

Requires only `requests`.
"""

import base64
import csv
import html
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
THUMBS = ROOT / "thumbs"
WIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {
    "User-Agent": "PublicDomainGalleryBuilder/1.0 (static art gallery generator; python-requests)"
}
PAUSE = 0.5

# (Wikipedia article title, display title, artist, year)
PAINTINGS = [
    ("Mona Lisa", "Mona Lisa", "Leonardo da Vinci", "c. 1503–1519"),
    ("The Birth of Venus", "The Birth of Venus", "Sandro Botticelli", "c. 1484–1486"),
    ("The Creation of Adam", "The Creation of Adam", "Michelangelo", "c. 1508–1512"),
    ("The Garden of Earthly Delights", "The Garden of Earthly Delights", "Hieronymus Bosch", "c. 1490–1510"),
    ("Girl with a Pearl Earring", "Girl with a Pearl Earring", "Johannes Vermeer", "c. 1665"),
    ("The Night Watch", "The Night Watch", "Rembrandt", "1642"),
    ("Las Meninas", "Las Meninas", "Diego Velázquez", "1656"),
    ("The Great Wave off Kanagawa", "The Great Wave off Kanagawa", "Katsushika Hokusai", "c. 1831"),
    ("Wanderer above the Sea of Fog", "Wanderer above the Sea of Fog", "Caspar David Friedrich", "c. 1818"),
    ("The Third of May 1808", "The Third of May 1808", "Francisco Goya", "1814"),
    ("Liberty Leading the People", "Liberty Leading the People", "Eugène Delacroix", "1830"),
    ("The Fighting Temeraire", "The Fighting Temeraire", "J. M. W. Turner", "1839"),
    ("The Starry Night", "The Starry Night", "Vincent van Gogh", "1889"),
    ("Sunflowers (Van Gogh series)", "Sunflowers", "Vincent van Gogh", "1888–1889"),
    ("Water Lilies (Monet series)", "Water Lilies", "Claude Monet", "1906"),
    ("Impression, Sunrise", "Impression, Sunrise", "Claude Monet", "1872"),
    ("A Sunday Afternoon on the Island of La Grande Jatte",
     "A Sunday Afternoon on the Island of La Grande Jatte", "Georges Seurat", "1884–1886"),
    ("Bal du moulin de la Galette", "Bal du moulin de la Galette", "Pierre-Auguste Renoir", "1876"),
    ("The Card Players", "The Card Players", "Paul Cézanne", "1890s"),
    ("The Kiss (Klimt)", "The Kiss", "Gustav Klimt", "1907–1908"),
    ("The Scream", "The Scream", "Edvard Munch", "1893"),
    ("Broadway Boogie Woogie", "Broadway Boogie Woogie", "Piet Mondrian", "1942–1943"),
    ("Composition VIII", "Composition VIII", "Wassily Kandinsky", "1923"),
]

# English Wikipedia has no article for these titles, so use a named Commons file
# instead. The public-domain license check still applies, and each use is reported.
COMMONS_FALLBACK = {
    "Composition VIII": "Wassily Kandinsky Composition VIII.jpg",
}

# Articles whose lead image is not a straight-on view of the canvas: always use
# this Commons file instead (license check still applies; reported each run).
COMMONS_OVERRIDE = {
    # lead image is a photo of the MoMA triptych installation, walls and floor included
    "Water Lilies (Monet series)": "Claude Monet - Water Lilies - 1906, Ryerson.jpg",
}

session = requests.Session()
session.headers.update(HEADERS)


def polite_get(url, params=None, retries=6):
    """GET with a pause after every request and backoff on 429/5xx."""
    delay = 5.0
    for attempt in range(retries + 1):
        r = session.get(url, params=params, timeout=60)
        time.sleep(PAUSE)
        if r.status_code == 429 or r.status_code >= 500:
            if attempt == retries:
                r.raise_for_status()
            wait = float(r.headers.get("Retry-After") or delay)
            print(f"[HTTP {r.status_code}, waiting {wait:.0f}s] ", end="", flush=True)
            time.sleep(wait)
            delay = min(delay * 2, 120)
            continue
        r.raise_for_status()
        return r


def api_get(url, params):
    params = {"format": "json", "formatversion": "2", **params}
    return polite_get(url, params).json()


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def strip_html(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def lead_image(title):
    data = api_get(WIKI_API, {
        "action": "query", "prop": "pageimages", "piprop": "original|name",
        "titles": title, "redirects": "1",
    })
    page = data["query"]["pages"][0]
    if page.get("missing"):
        raise LookupError("Wikipedia article not found")
    name = page.get("pageimage")
    if not name:
        raise LookupError("article has no lead image (pageimage)")
    return name


def commons_info(filename):
    data = api_get(COMMONS_API, {
        "action": "query", "prop": "imageinfo", "titles": f"File:{filename}",
        "iiprop": "url|extmetadata", "iiurlwidth": "500",
    })
    page = data["query"]["pages"][0]
    if page.get("missing") and "imageinfo" not in page:
        raise LookupError(f"File:{filename} not found on Commons (may be a local en.wikipedia file)")
    info = page["imageinfo"][0]
    meta = info.get("extmetadata", {})
    return {
        "thumb_url": info["thumburl"],
        "page_url": info["descriptionurl"],
        "license": strip_html(meta.get("LicenseShortName", {}).get("value", "")),
        "commons_artist": strip_html(meta.get("Artist", {}).get("value", "")),
    }


def collect():
    kept, problems = [], []
    for article, title, artist, year in PAINTINGS:
        print(f"- {article} ... ", end="", flush=True)
        try:
            try:
                if article in COMMONS_OVERRIDE:
                    filename = COMMONS_OVERRIDE[article]
                    print("[override] ", end="")
                    problems.append((article, f"NOTE (kept): lead image overridden with {filename!r}"))
                else:
                    filename = lead_image(article)
            except LookupError as e:
                if article not in COMMONS_FALLBACK:
                    raise
                filename = COMMONS_FALLBACK[article]
                print(f"[{e}; using Commons fallback] ", end="")
                problems.append((article, f"NOTE (kept): {e}; used Commons file {filename!r}"))
            info = commons_info(filename)
        except Exception as e:  # report, never skip silently
            print(f"FAILED: {e}")
            problems.append((article, f"lookup failed: {e}"))
            continue
        if "public domain" not in info["license"].lower():
            print(f"REJECTED: license is {info['license']!r} ({filename})")
            problems.append((article, f"license {info['license']!r} for {filename}"))
            continue
        slug = slugify(title)
        ext = Path(info["thumb_url"].split("?")[0]).suffix.lower() or ".jpg"
        local = THUMBS / f"{slug}{ext}"
        if not local.exists() or local.stat().st_size == 0:
            try:
                local.write_bytes(polite_get(info["thumb_url"]).content)
            except Exception as e:
                print(f"FAILED download: {e}")
                problems.append((article, f"thumbnail download failed: {e}"))
                continue
        print(f"ok ({filename}, {info['license']})")
        kept.append({
            "article": article, "title": title, "artist": artist, "year": year,
            "filename": filename, "thumb": f"thumbs/{local.name}", **info,
        })
    return kept, problems


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Public Domain Masterpieces</title>
<style>
  :root {{ --bg:#f6f3ee; --card:#fff; --ink:#1d1b18; --muted:#6b645a; --line:#e4ddd2; --accent:#8a4b2a; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#151412; --card:#1f1d1a; --ink:#eee8df; --muted:#a39a8d; --line:#33302b; --accent:#e0a070; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font:16px/1.45 Georgia, "Times New Roman", serif; }}
  header {{ max-width:1280px; margin:0 auto; padding:32px 16px 24px; }}
  nav {{ display:flex; gap:18px; flex-wrap:wrap; font-family:system-ui,sans-serif; font-size:.9rem; margin-bottom:28px; }}
  nav a {{ color:var(--muted); text-decoration:none; padding-bottom:2px; border-bottom:2px solid transparent; }}
  nav a[aria-current] {{ color:var(--ink); border-color:var(--accent); }}
  h1 {{ font-size:clamp(1.8rem,4vw,2.8rem); margin:0 0 8px; font-weight:normal; letter-spacing:.01em; }}
  header p {{ margin:0; color:var(--muted); font-family:system-ui,sans-serif; font-size:.95rem; }}
  main {{ max-width:1280px; margin:0 auto; padding:0 16px 64px;
         display:grid; gap:20px; grid-template-columns:repeat(4,1fr); }}
  @media (max-width:1000px) {{ main {{ grid-template-columns:repeat(3,1fr); }} }}
  @media (max-width:700px)  {{ main {{ grid-template-columns:repeat(2,1fr); gap:12px; }} }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:6px; overflow:hidden;
          display:flex; flex-direction:column; }}
  .frame {{ position:relative; aspect-ratio:4/5; background:#0001; overflow:hidden; }}
  .frame img {{ position:absolute; inset:0; width:100%; height:100%; object-fit:contain; display:block; }}
  .meta {{ padding:12px 14px 14px; display:flex; flex-direction:column; gap:2px; flex:1; }}
  .meta h2 {{ font-size:1.02rem; margin:0; font-weight:bold; line-height:1.25; }}
  .meta .by {{ color:var(--muted); font-family:system-ui,sans-serif; font-size:.85rem; }}
  .meta a {{ margin-top:auto; padding-top:8px; color:var(--accent); font-family:system-ui,sans-serif;
            font-size:.82rem; text-decoration:none; }}
  .meta a:hover {{ text-decoration:underline; }}
  footer {{ text-align:center; color:var(--muted); font-family:system-ui,sans-serif; font-size:.8rem; padding:0 16px 40px; }}
</style>
</head>
<body>
<header>
  <nav><a href="index.html" aria-current="page">Gallery</a><a href="colors.html">Average colour</a><a href="pigments.html">Pigments</a></nav>
  <h1>Public Domain Masterpieces</h1>
  <p>{count} paintings · images from Wikimedia Commons, all public domain · select a link for the full-resolution file</p>
</header>
<main>
{cards}
</main>
<footer>Thumbnails via Wikimedia Commons. See credits.csv for per-file sources and licenses.</footer>
</body>
</html>
"""

CARD = """  <article class="card">
    <div class="frame"><img src="{src}" alt="{alt}" loading="lazy" decoding="async"></div>
    <div class="meta">
      <h2>{title}</h2>
      <span class="by">{artist} · {year}</span>
      <a href="{page}" target="_blank" rel="noopener">Full resolution on Commons ↗</a>
    </div>
  </article>"""


def data_uri(path):
    mime = {".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}.get(path.suffix, "image/jpeg")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def render(items, embed):
    cards = []
    for it in items:
        src = data_uri(ROOT / it["thumb"]) if embed else it["thumb"]
        e = html.escape
        cards.append(CARD.format(
            src=src, alt=e(f"{it['title']} by {it['artist']}"), title=e(it["title"]),
            artist=e(it["artist"]), year=e(it["year"]), page=e(it["page_url"]),
        ))
    return PAGE.format(count=len(items), cards="\n".join(cards))


def main():
    THUMBS.mkdir(exist_ok=True)
    kept, problems = collect()

    (ROOT / "gallery.json").write_text(json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "index.html").write_text(render(kept, embed=False), encoding="utf-8")
    (ROOT / "gallery-embedded.html").write_text(render(kept, embed=True), encoding="utf-8")
    with open(ROOT / "credits.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "artist", "commons_url", "license", "commons_artist_field", "file"])
        for it in kept:
            w.writerow([it["title"], it["artist"], it["page_url"], it["license"],
                        it["commons_artist"], it["filename"]])

    print(f"\nKept {len(kept)}/{len(PAINTINGS)} paintings.")
    if problems:
        print("NEEDS REVIEW:")
        for article, why in problems:
            print(f"  * {article}: {why}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
