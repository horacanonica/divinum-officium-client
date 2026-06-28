"""App-wide constants and defaults."""

APP_NAME = "Divinum Officium Client"
APP_VERSION = "0.1.3"

# GitHub repo that hosts the generated bundles
DEFAULT_GITHUB_REPO = "horacanonica/divinum-officium-FSSP-NorthAmerica"

# Fallback browse-only URL (upstream public site — no generation)
UPSTREAM_DO_URL = "https://divinumofficium.com"

BUNDLE_CACHE_DIR_NAME = ".do-client"
BUNDLE_FILENAME_TEMPLATE = "supplement-{year}.json"
RELEASE_TAG_TEMPLATE = "propers-{year}"

HORAS = ["Matutinum", "Laudes", "Prima", "Tertia", "Sexta", "Nona", "Vespera", "Completorium"]

# Kalendaria class field: 1=I class, 2=II class, 3=Double/III class
RANK_LABELS = {
    1: "I Class",
    2: "II Class",
    3: "Double (III Class)",
}

PDF_SINGLE_CSS = """
@page { size: letter; margin: 1in; }
body { font-family: "Palatino Linotype", Palatino, serif; font-size: 11pt; line-height: 1.5; }
h1 { font-size: 14pt; text-align: center; margin-top: 2em; border-top: 1px solid #888; padding-top: 0.5em; }
h2 { font-size: 12pt; text-align: center; color: #555; }
.rubric { color: #8b0000; }
.source-badge { font-size: 9pt; color: #555; font-style: italic; }
"""

PDF_BOOKLET_CSS = """
@page { size: letter; margin: 0.5in; }
body { font-family: "Palatino Linotype", Palatino, serif; font-size: 10pt; line-height: 1.4; }
h1 { font-size: 12pt; text-align: center; margin-top: 1.5em; border-top: 1px solid #888; padding-top: 0.4em; }
h2 { font-size: 10.5pt; text-align: center; color: #555; }
.rubric { color: #8b0000; }
.source-badge { font-size: 8pt; color: #555; font-style: italic; }
"""
