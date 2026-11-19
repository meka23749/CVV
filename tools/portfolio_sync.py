#!/usr/bin/env python3
"""portfolio_sync.py

Erstellt automatisch Projektkarten und Projektseiten fuer die Portfolio-Website
aus allen GitHub-Repositories mit dem Topic "portfolio".

Ablauf (laeuft in GitHub Actions, siehe .github/workflows/portfolio-sync.yml):
  1. Alle oeffentlichen Repos von OWNER mit dem Topic TOPIC holen.
  2. Optional portfolio.yml im Projekt-Repo lesen (Titel, Beschreibung, Tags, Farbe ...).
  3. Aus der README des Projekts eine Projektseite <slug>.html im Stil der Website erzeugen.
  4. Die Karten zwischen den Markern AUTO-PROJEKTE in embedded.html bzw. weitere.html eintragen.

Von Hand gebaute Seiten und Karten werden nie veraendert.
Testmodus ohne GitHub:  python tools/portfolio_sync.py --local <ordner>
  (<ordner>/repos.json und <ordner>/<repo>/README.md, <ordner>/<repo>/portfolio.yml)
"""
import argparse
import base64
import html
import json
import os
import posixpath
import re
import urllib.error
import urllib.request

import markdown
import yaml

OWNER = os.environ.get("PORTFOLIO_OWNER", "meka23749")
TOPIC = os.environ.get("PORTFOLIO_TOPIC", "portfolio")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START, END = "<!-- AUTO-PROJEKTE:START -->", "<!-- AUTO-PROJEKTE:END -->"
GEN = '<meta name="generator" content="portfolio-sync">'
PAGES = {"portfolio": "embedded.html", "weitere": "weitere.html"}
FARBEN = {"embedded", "devops", "web", "sim"}

# Schreibweise bekannter GitHub-Topics auf den Karten
NAMEN = {
    "python": "Python", "c": "C", "cpp": "C++", "c-plus-plus": "C++", "bash": "Bash", "cmake": "CMake",
    "linux": "Linux", "embedded": "Embedded", "embedded-linux": "Embedded Linux", "yocto": "Yocto",
    "arm": "ARM", "cortex-m": "ARM Cortex-M", "bare-metal": "Bare-Metal", "stm32": "STM32",
    "raspberry-pi": "Raspberry Pi", "beagley": "BeagleY", "device-tree": "Device Tree", "qemu": "QEMU",
    "freertos": "FreeRTOS", "zephyr": "Zephyr", "firmware": "Firmware", "can": "CAN", "can-fd": "CAN-FD",
    "mqtt": "MQTT", "modbus": "Modbus", "modbus-tcp": "Modbus TCP", "iot": "IoT", "iiot": "IIoT",
    "qt": "Qt", "ros2": "ROS2", "sensors": "Sensors", "docker": "Docker", "kubernetes": "Kubernetes",
    "kafka": "Kafka", "github-actions": "GitHub Actions", "ci-cd": "CI/CD", "devops": "DevOps",
    "robot-framework": "Robot Framework", "pytest": "pytest", "sil": "SIL", "hil": "HIL",
    "unit-tests": "Unit Tests", "testing": "Tests", "matlab": "MATLAB", "simulink": "Simulink",
    "machine-learning": "Machine Learning", "deep-learning": "Deep Learning", "computer-vision": "Computer Vision",
    "yolo": "YOLO", "rag": "RAG", "llm": "LLM", "fastapi": "FastAPI", "angular": "Angular",
    "typescript": "TypeScript", "javascript": "JavaScript", "mbse": "MBSE",
}
EMBEDDED = {"embedded", "embedded-linux", "linux", "yocto", "arm", "cortex-m", "bare-metal", "stm32",
            "raspberry-pi", "beagley", "firmware", "device-tree", "can", "can-fd", "iot", "iiot", "mqtt",
            "sensors", "ros2", "qt", "freertos", "zephyr", "robotics"}
WEB = {"machine-learning", "deep-learning", "computer-vision", "yolo", "rag", "llm", "ai", "ml",
       "web", "angular", "fastapi", "typescript", "javascript", "data"}
SIM = {"simulation", "matlab", "simulink", "mbse"}

PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {gen}
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="icon" href="favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="css/base.css">
  <link rel="stylesheet" href="css/project.css">
</head>

<body>
<nav class="site-nav">
  <ul>
    <li><a class="active" href="{back}">Portfolio</a></li>
  </ul>
</nav>

<header>
  <h1>{title}</h1>
  <p class="muted lead">{lead}</p>
{art}  <a class="btn-github" href="{repo_url}" target="_blank" rel="noopener">GitHub Repository</a>
</header>

<main>
{sections}
</main>

<footer>© <span id="year"></span> Steve Meka · All rights reserved.</footer>
<script>document.getElementById("year").textContent = new Date().getFullYear();</script>
</body>
</html>
"""

CARD = """      <a class="project-card" href="{href}"{target}>
        <div class="project-media">
          <div class="tech-bg bg-{farbe}">
            <div class="tech-grid">
{pills}
            </div>
          </div>
          <div class="project-caption">
            <h3 class="project-title">{title}</h3>
          </div>
        </div>
      </a>
"""


class GitHub:
    def __init__(self, token):
        self.token = token

    def _get(self, url):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "portfolio-sync",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
            return json.load(r)

    def repos(self):
        out, page = [], 1
        while True:
            batch = self._get(f"https://api.github.com/users/{OWNER}/repos?type=owner&per_page=100&page={page}")
            out += batch
            if len(batch) < 100:
                return out
            page += 1

    def file(self, repo, path, ref):
        try:
            d = self._get(f"https://api.github.com/repos/{OWNER}/{repo}/contents/{path}?ref={ref}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        if isinstance(d, list) or "content" not in d:
            return None
        return base64.b64decode(d["content"]).decode("utf-8", "replace")

    def readme(self, repo, ref):
        try:
            d = self._get(f"https://api.github.com/repos/{OWNER}/{repo}/readme?ref={ref}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, "README.md"
            raise
        return base64.b64decode(d["content"]).decode("utf-8", "replace"), d.get("path", "README.md")


class Local:
    """Testmodus: liest Repos aus einem lokalen Ordner statt von GitHub."""

    def __init__(self, base):
        self.base = base

    def repos(self):
        with open(os.path.join(self.base, "repos.json"), encoding="utf-8") as f:
            return json.load(f)

    def file(self, repo, path, ref):
        p = os.path.join(self.base, repo, path)
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as f:
            return f.read()

    def readme(self, repo, ref):
        return self.file(repo, "README.md", ref), "README.md"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_if_changed(path, text):
    if os.path.exists(path) and read(path) == text:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def nice(tag):
    t = str(tag).strip()
    return NAMEN.get(t.lower(), t.replace("-", " ").title() if t.islower() else t)


def guess_farbe(topics):
    s = {str(t).lower().replace(" ", "-") for t in topics}
    if s & EMBEDDED:
        return "embedded"
    if s & WEB:
        return "web"
    if s & SIM:
        return "sim"
    return "devops"


BADGE = re.compile(r"(shields\.io|badge\.svg|badgen\.net)", re.I)


def clean_md(md):
    """Entfernt Badges und die erste H1 (der Titel steht im Seitenkopf)."""
    lines = [line for line in md.splitlines() if not BADGE.search(line)]
    for i, line in enumerate(lines):
        if line.strip():
            if re.match(r"#\s+", line):
                title = line.lstrip("#").strip()
                del lines[i]
                return "\n".join(lines), title
            break
    return "\n".join(lines), None


def split_sections(md):
    """Teilt die README an den ##-Ueberschriften in Abschnitte."""
    intro, secs, cur, in_code = [], [], None, False
    for line in md.splitlines():
        if line.strip().startswith(("```", "~~~")):
            in_code = not in_code
        m = None if in_code else re.match(r"##\s+(.+?)\s*#*\s*$", line)
        if m:
            cur = [m.group(1), []]
            secs.append(cur)
        elif cur is None:
            intro.append(line)
        else:
            cur[1].append(line)
    return "\n".join(intro).strip(), [(h, "\n".join(b).strip()) for h, b in secs]


def first_paragraph(text):
    for block in re.split(r"\n\s*\n", text):
        b = block.strip()
        if b and not b.startswith(("#", "!", "|", "```", "~~~", "<", "- ", "* ", ">")):
            plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", b)
            plain = re.sub(r"[*_`]", "", plain)
            return block, " ".join(plain.split())
    return None, ""


def md_html(text, repo, ref, base_dir):
    out = markdown.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])

    def fix(m):
        attr, url = m.group(1), m.group(2)
        if re.match(r"^(https?:|mailto:|#|data:)", url):
            return m.group(0)
        path = url.lstrip("/") if url.startswith("/") else posixpath.normpath(posixpath.join(base_dir or ".", url))
        if attr == "src":
            new = f"https://raw.githubusercontent.com/{OWNER}/{repo}/{ref}/{path}"
        else:
            new = f"https://github.com/{OWNER}/{repo}/blob/{ref}/{path}"
        return f'{attr}="{new}"'

    out = re.sub(r'(src|href)="([^"]+)"', fix, out)
    # Codebloecke wie auf den bestehenden Seiten: nur <pre>, ohne <code>
    out = re.sub(r"<pre><code[^>]*>", "<pre>", out).replace("</code></pre>", "</pre>")
    return out.replace("<img ", '<img loading="lazy" ')


def handmade_text(root):
    """Text aller von Hand gebauten Seiten (ohne automatische Bloecke)."""
    parts = []
    for f in sorted(os.listdir(root)):
        if f.endswith(".html"):
            t = read(os.path.join(root, f))
            if GEN in t:
                continue
            parts.append(re.sub(re.escape(START) + ".*?" + re.escape(END), "", t, flags=re.S))
    return "\n".join(parts)


def ensure_markers(txt, fname):
    if START in txt:
        return txt
    ins = f"      {START}\n      {END}\n\n"
    i = txt.find('<a class="project-card" href="weitere.html"')
    if i != -1:
        ls = txt.rfind("\n", 0, i) + 1
        return txt[:ls] + ins + txt[ls:]
    j = txt.find("</main>")
    k = txt.rfind("</a>", 0, j)
    if k == -1:
        raise SystemExit(f"Kein Kartenraster in {fname} gefunden")
    k = txt.find("\n", k) + 1
    return txt[:k] + f"\n      {START}\n      {END}\n" + txt[k:]


def build(src, root):
    handmade = handmade_text(root)
    cards = {b: [] for b in PAGES}
    keep, changed = set(), []
    repos = sorted(src.repos(), key=lambda r: r.get("created_at", ""), reverse=True)
    for r in repos:
        topics = [str(t) for t in r.get("topics", [])]
        if r.get("fork") or r.get("archived") or r.get("private") or TOPIC not in topics:
            continue
        name, ref = r["name"], r.get("default_branch") or "main"
        repo_url = r.get("html_url") or f"https://github.com/{OWNER}/{name}"
        if re.search(rf"github\.com/{re.escape(OWNER)}/{re.escape(name)}(?=[\"'/#?\s<]|$)", handmade, re.I):
            print(f"= {name}: schon von Hand auf der Website, wird nicht angefasst")
            continue
        cfg = yaml.safe_load(src.file(name, "portfolio.yml", ref) or "") or {}
        if not isinstance(cfg, dict):
            cfg = {}
        if cfg.get("anzeigen") is False:
            continue
        readme, readme_path = src.readme(name, ref)
        md, h1 = clean_md(readme or "")
        intro, secs = split_sections(md)
        title = str(cfg.get("titel") or h1 or name.replace("-", " ").replace("_", " ").title())
        lead = str(cfg.get("beschreibung") or r.get("description") or "").strip()
        if not lead:
            block, lead = first_paragraph(intro)
            if block:
                intro = intro.replace(block, "", 1).strip()
        tags = cfg.get("tags") or [nice(t) for t in topics if t != TOPIC]
        tags = [str(t) for t in tags][:6]
        farbe = cfg.get("farbe") if cfg.get("farbe") in FARBEN else guess_farbe(topics + tags)
        bereich = cfg.get("bereich") if cfg.get("bereich") in PAGES else "portfolio"
        slug = re.sub(r"[^a-z0-9-]+", "-", str(cfg.get("slug") or name).lower()).strip("-")
        seite = cfg.get("seite", True) is not False and bool(secs or intro)
        page_file = slug + ".html"
        page_path = os.path.join(root, page_file)
        if seite and os.path.exists(page_path) and GEN not in read(page_path):
            print(f"! {name}: {page_file} existiert schon (von Hand). Karte verlinkt auf GitHub.")
            seite = False

        if seite:
            base_dir = posixpath.dirname(readme_path)
            parts = []
            if intro:
                parts.append(("Überblick", intro))
            parts += secs
            html_secs = "\n".join(
                f'<section class="hcard">\n  <h2>{html.escape(h)}</h2>\n{md_html(b, name, ref, base_dir)}\n</section>\n'
                for h, b in parts)
            art = f'  <p class="muted">{html.escape(str(cfg["art"]))}</p>\n' if cfg.get("art") else ""
            page = PAGE.format(gen=GEN, title=html.escape(title), desc=html.escape(lead, quote=True),
                               lead=html.escape(lead), art=art, repo_url=html.escape(repo_url, quote=True),
                               back=PAGES[bereich], sections=html_secs)
            if write_if_changed(page_path, page):
                changed.append(page_file)
            keep.add(page_file)
            href, target = page_file, ""
        else:
            href, target = repo_url, ' target="_blank" rel="noopener"'

        pills = "\n".join(f'              <div class="tech-pill">{html.escape(t)}</div>' for t in tags)
        cards[bereich].append(CARD.format(href=html.escape(href, quote=True), target=target, farbe=farbe,
                                          pills=pills, title=html.escape(title)))
        print(f"+ {name}: Karte in {PAGES[bereich]}" + (f", Seite {page_file}" if seite else ", Link auf GitHub"))

    for bereich, fname in PAGES.items():
        p = os.path.join(root, fname)
        if not os.path.exists(p):
            continue
        old = read(p)
        txt = ensure_markers(old, fname)
        inner = "".join(c + "\n" for c in cards[bereich])
        block = START + "\n" + ("\n" if cards[bereich] else "") + inner + "      " + END
        txt = re.sub(re.escape(START) + ".*?" + re.escape(END), lambda m: block, txt, flags=re.S)
        if write_if_changed(p, txt):
            changed.append(fname)

    for f in sorted(os.listdir(root)):
        if f.endswith(".html") and f not in keep and GEN in read(os.path.join(root, f)):
            os.remove(os.path.join(root, f))
            changed.append(f + " (entfernt)")
            print(f"- {f}: Repo hat das Topic '{TOPIC}' nicht mehr, Seite entfernt")

    print("Geändert:", ", ".join(changed) if changed else "nichts")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", help="Testordner statt GitHub-API")
    ap.add_argument("--root", default=ROOT, help="Ordner der Website (Standard: Repo-Wurzel)")
    a = ap.parse_args()
    build(Local(a.local) if a.local else GitHub(os.environ.get("GITHUB_TOKEN")), a.root)
