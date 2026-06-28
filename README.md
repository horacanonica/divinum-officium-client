# Divinum Officium Client

A cross-platform desktop application for generating **parish propers** — supplement booklets containing the Divine Office texts for feasts specific to FSSP North America parishes — in PDF or EPUB format. No server, no subscription, no internet connection required after the annual bundle is downloaded.

---

## What It Does

The Traditional Latin Mass calendar used by FSSP parishes contains feasts not found in the standard 1960 rubrics: patronal feasts, diocesan observances, and approved additions. Each parish has its own Kalendarium that laymen and schola directors need in a printable, portable format.

This app:
1. **Downloads a pre-generated bundle** (once per year, ~8 MB) from GitHub containing all Office texts for every feast in every supported parish calendar.
2. **Lets you pick your parish** and the scope of what to include (your parish's unique feasts only, or the full FSSP USA supplement, or all 1960-rubric calendars).
3. **Generates a PDF or EPUB locally** — formatted for letter-size printing or for reading in an e-reader.

---

## Supported Calendars

| Calendar | Type |
|---|---|
| Rubrics 1960 | Standard (upstream) |
| Rubrics 1960 — USA 1960 | Standard (upstream) |
| Rubrics 1960 — FSSP | FSSP universal |
| Rubrics 1960 — FSSP USA | FSSP North America |
| Rubrics 1960 — Nashua | Parish (St. Augustine, Nashua NH) |
| Rubrics 1960 — Arlington | Parish (FSSP Arlington) |
| Rubrics 1960 — Chesapeake | Parish |
| Rubrics 1960 — Sacramento | Parish |
| Rubrics 1960 — Guadalajara | Parish |

---

## Architecture

Nothing runs on a private server. Everything is either GitHub or your own machine.

```
[GitHub: divinum-officium-FSSP-NorthAmerica]
    │  GitHub Actions runs Perl scripts on Nov 1 each year
    │  Generates all feast Office texts for all parish calendars
    │  Uploads supplement-YYYY.json to GitHub Releases (public, free CDN)
    ▼
[GitHub Releases — supplement-YYYY.json, ~8 MB]
    ▼
[This app — runs entirely on your machine]
    │  Downloads bundle once, caches it locally
    │  You pick calendar + scope + output format
    │  Generates PDF or EPUB locally (no internet needed)
    │  Opens the file in your default viewer
```

The generation step uses the Perl scripts from the DO Fork repo (`standalone/tools/epubgen2/EofficiumXhtml.pl`), run by GitHub's free CI infrastructure. The desktop app never touches a live server.

---

## Output Formats

| Format | Description |
|---|---|
| **PDF — Single Page** | Letter-size, 1-inch margins, Palatino serif, red rubrics |
| **PDF — Booklet** | Half-inch margins, 2-up imposition for folded printing |
| **EPUB** | EPUB3, one chapter per feast, suitable for Kindle or Calibre |

---

## Installation

Download the binary for your platform from the [latest release](https://github.com/horacanonica/divinum-officium-client/releases/latest). No Python or dependencies required.

| Platform | File |
|---|---|
| macOS | `DO-Client-macos.zip` — unzip, then right-click `DO-Client.app` → Open |
| Windows | `DO-Client-windows.exe` |
| Linux | `DO-Client-linux` — `chmod +x` then run |

**macOS note:** The app is not notarized. On first launch, right-click → Open (instead of double-clicking) to bypass Gatekeeper, then confirm in the security dialog.

### First run

On first launch the app will prompt you to download the bundle for the current liturgical year. This is a one-time ~8 MB download. After that the app works fully offline until you check for a new bundle (available each November 1).

---

## Building From Source

```bash
pip install -r requirements.txt
python app.py
```

To build a binary:

```bash
pip install pyinstaller
pyinstaller --windowed --name DO-Client --add-data "config.py:." app.py
```

**Dependencies:** `customtkinter`, `requests`, `xhtml2pdf`, `ebooklib`, `pypdf`

---

## How the Bundle Is Generated

See the companion repo: [divinum-officium-FSSP-NorthAmerica](https://github.com/horacanonica/divinum-officium-FSSP-NorthAmerica).

A GitHub Actions workflow (`.github/workflows/generate-propers.yml`) runs automatically on November 1 each year. It:
1. Checks out the full DO Fork (which contains all Perl scripts and Kalendaria data files)
2. Reads each parish's Kalendarium file to identify feasts unique to that calendar vs. its parent
3. Calls `EofficiumXhtml.pl` for each feast × 8 canonical hours in Latin and English
4. Assembles `supplement-YYYY.json` and publishes it as a GitHub Release

Feast rank labels map to class numbers from the Kalendaria files: `1 = I Class`, `2 = II Class`, `3 = Double (III Class)`.

The workflow can also be triggered manually from the GitHub Actions tab (useful for testing or re-generating after calendar changes).

---

## Related

- [divinum-officium-FSSP-NorthAmerica](https://github.com/horacanonica/divinum-officium-FSSP-NorthAmerica) — the DO Fork containing all parish Kalendaria and the generation workflow
- [divinumofficium.com](https://divinumofficium.com) — the upstream public Divinum Officium project (browse-only option in app settings)
