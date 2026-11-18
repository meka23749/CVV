# Portfolio – Steve Meka

Persönliche Portfolio-Website (Embedded Software Engineering), veröffentlicht mit GitHub Pages:
**https://meka23749.github.io/CVV/**

Reines HTML/CSS ohne Build-Schritt und ohne Framework.

## Struktur

```
index.html                    Startseite
embedded.html                 Projektübersicht
weitere.html                  Weitere Projekte
*.html                        Projektseiten
css/base.css                  Gemeinsame Basis: Farben, Reset, Navigation (alle Seiten)
css/cards.css                 Kartenraster für index, embedded und weitere
css/project.css               Layout und Komponenten der Projektseiten
images/                       Abbildungen (PNG, optimiert) und github.svg
favicon.svg
```

Projektseiten laden `css/base.css` und `css/project.css`. Seitenspezifische Regeln
(z. B. Farben eines SVG-Diagramms) stehen in einem kurzen `<style>`-Block im `<head>`
der jeweiligen Seite.

## Lokal ansehen

```bash
python3 -m http.server 8000
# dann http://localhost:8000 öffnen
```

## Neue Projektseite

1. Eine bestehende Projektseite (z. B. `mqtt-iot.html`) kopieren und den Inhalt ersetzen.
2. Titel und `<meta name="description">` anpassen.
3. Eine Karte in `embedded.html` oder `weitere.html` ergänzen.

Verfügbare Komponenten in `css/project.css`: `.hcard`, `.btn-github`, `.skills-row`/`.skill-tag`,
`.context-grid`, `.metrics-grid`/`.metric-card`, `.grid2`, `.ausblick-list`, Hinweisboxen
(`.success`, `.warn`, `.warn-note`, `.limit-note`), `.img-light` für Diagramme mit transparentem
Hintergrund und Abstände `.mt-8` … `.mt-22`.

## Bilder

- Bilder lokal in `images/` ablegen, nicht von anderen Domains einbinden.
- draw.io-Diagramme **ohne** „Include a copy of my diagram“ exportieren – sonst steckt die
  komplette Diagrammquelle in der PNG-Datei (mehrere MB).
- Vor dem Hochladen komprimieren, z. B. mit [Squoosh](https://squoosh.app) oder `oxipng`.
