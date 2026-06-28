#!/usr/bin/env python3
"""Divinum Officium Client — cross-platform desktop app for generating parish propers."""

import json
import os
import sys
import threading
import webbrowser
from datetime import date
from io import BytesIO
from pathlib import Path

import customtkinter as ctk
import requests

import config

# ── Bundle / cache helpers ────────────────────────────────────────────────────

def bundle_cache_dir():
    return Path.home() / config.BUNDLE_CACHE_DIR_NAME

def settings_path():
    return bundle_cache_dir() / "settings.json"

def bundle_path(year):
    return bundle_cache_dir() / config.BUNDLE_FILENAME_TEMPLATE.format(year=year)

def load_settings():
    try:
        with open(settings_path()) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"github_repo": config.DEFAULT_GITHUB_REPO}

def save_settings(s):
    bundle_cache_dir().mkdir(parents=True, exist_ok=True)
    with open(settings_path(), "w") as f:
        json.dump(s, f, indent=2)

def load_bundle(year):
    p = bundle_path(year)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None

def latest_bundle_year():
    """Return the most recent year for which we have a cached bundle."""
    d = bundle_cache_dir()
    if not d.exists():
        return None
    candidates = []
    for p in d.glob("supplement-*.json"):
        try:
            candidates.append(int(p.stem.split("-")[1]))
        except (ValueError, IndexError):
            pass
    return max(candidates) if candidates else None

# ── GitHub release helpers ────────────────────────────────────────────────────

def fetch_latest_release_info(repo):
    url = f"https://api.github.com/repos/{repo}/releases"
    try:
        r = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        releases = r.json()
        propers = [rel for rel in releases if rel.get("tag_name", "").startswith("propers-")]
        if not propers:
            return None, None
        latest = propers[0]
        tag = latest["tag_name"]
        year = int(tag.split("-")[1])
        assets = latest.get("assets", [])
        expected_name = config.BUNDLE_FILENAME_TEMPLATE.format(year=year)
        asset = next((a for a in assets if a["name"] == expected_name), None)
        if not asset:
            return None, None
        return year, asset["browser_download_url"]
    except Exception:
        return None, None

def download_bundle(url, year, progress_cb=None):
    """Download bundle from URL and cache it. Returns True on success."""
    bundle_cache_dir().mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(url, timeout=120, stream=True)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        buf = BytesIO()
        for chunk in r.iter_content(chunk_size=65536):
            buf.write(chunk)
            downloaded += len(chunk)
            if progress_cb and total:
                progress_cb(downloaded / total)
        with open(bundle_path(year), "wb") as f:
            f.write(buf.getvalue())
        return True
    except Exception:
        return False

# ── Output generation ─────────────────────────────────────────────────────────

def build_html(feasts, solemn_only, include_latin, include_english, css):
    sections = []
    for feast in feasts:
        if solemn_only and feast.get("rank", 99) > 2:
            continue
        rank_lbl = feast.get("rank_label", "")
        source = feast.get("source", "")
        sections.append(
            f"<h1>{feast['name']}</h1>"
            f"<h2>{rank_lbl} <span class='source-badge'>({source})</span></h2>"
        )
        horas = feast.get("horas", {})
        for hora in config.HORAS:
            hora_data = horas.get(hora, {})
            parts = []
            if isinstance(hora_data, dict):
                if include_latin and hora_data.get("latin"):
                    parts.append(hora_data["latin"])
                if include_english and hora_data.get("english"):
                    parts.append(hora_data["english"])
            else:
                # legacy bundle format — single string, language already baked in
                parts.append(hora_data)
            content = "\n".join(parts)
            if content:
                sections.append(f"<h3>{hora}</h3><div class='hora-content'>{content}</div>")
    body = "\n".join(sections) if sections else "<p>No feasts found for the selected options.</p>"
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"

def generate_epub(html_content, output_path):
    from ebooklib import epub
    book = epub.EpubBook()
    book.set_title("Parish Propers")
    book.set_language("la")
    chapter = epub.EpubHtml(title="Propers", file_name="propers.xhtml", lang="la")
    chapter.content = html_content
    book.add_item(chapter)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]
    epub.write_epub(str(output_path), book)

def _html_to_pdf_bytes(html_content):
    from xhtml2pdf import pisa
    import io
    buf = io.BytesIO()
    pisa.CreatePDF(html_content, dest=buf)
    return buf.getvalue()

def generate_pdf_single(html_content, output_path):
    with open(output_path, "wb") as f:
        f.write(_html_to_pdf_bytes(html_content))

def generate_pdf_booklet(html_content, output_path):
    from pypdf import PdfWriter, PdfReader
    import io

    pdf_bytes = _html_to_pdf_bytes(html_content)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    n = len(reader.pages)

    # Pad to multiple of 4 for 2-up booklet imposition
    while n % 4 != 0:
        n += 1

    # Build imposition order for saddle-stitch: pages are printed in pairs
    # on letter paper, folded. Order for N-page booklet:
    order = []
    for i in range(n // 4):
        outer = (i, n - 1 - i)
        inner = (i + n // 2 - 1, n // 2 - i)
        order.extend([outer[0], outer[1], inner[1], inner[0]])

    # Write imposed PDF (simple 2-up, landscape letter)
    writer = PdfWriter()
    blank_page_bytes = HTML(string="<html><body></body></html>").write_pdf()
    blank_reader = PdfReader(io.BytesIO(blank_page_bytes))

    real_pages = len(reader.pages)
    for page_idx in order:
        if page_idx < real_pages:
            writer.add_page(reader.pages[page_idx])
        else:
            writer.add_page(blank_reader.pages[0])

    with open(output_path, "wb") as f:
        writer.write(f)

# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, settings, on_save):
        super().__init__(parent)
        self.title("Settings")
        self.resizable(False, False)
        self.on_save = on_save

        ctk.CTkLabel(self, text="GitHub source repo:", anchor="w").pack(padx=20, pady=(20, 4), fill="x")
        self.repo_var = ctk.StringVar(value=settings.get("github_repo", config.DEFAULT_GITHUB_REPO))
        ctk.CTkEntry(self, textvariable=self.repo_var, width=360).pack(padx=20)

        ctk.CTkLabel(self, text="Format: owner/repo  (where propers-YYYY releases are published)", font=ctk.CTkFont(size=11), text_color="gray").pack(padx=20, pady=(2, 12), anchor="w")

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(padx=20, pady=(0, 20), fill="x")
        ctk.CTkButton(frame, text="Save", command=self._save, width=100).pack(side="right")
        ctk.CTkButton(frame, text="Cancel", command=self.destroy, width=100, fg_color="gray").pack(side="right", padx=(0, 8))

        self.grab_set()

    def _save(self):
        self.on_save({"github_repo": self.repo_var.get().strip()})
        self.destroy()

# ── Main window ───────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(config.APP_NAME)
        self.geometry("520x560")
        self.resizable(False, False)

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.settings = load_settings()
        self.bundle = None
        self.bundle_year = None
        self._build_ui()
        self._load_best_bundle()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Title bar with gear icon
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(top, text=config.APP_NAME, font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="⚙", width=32, height=28, command=self._open_settings, fg_color="gray").pack(side="right")

        sep = ctk.CTkFrame(self, height=1, fg_color="gray70")
        sep.pack(fill="x", padx=20, pady=10)

        # Calendar selector
        ctk.CTkLabel(self, text="Calendar", anchor="w").pack(fill="x", padx=20, pady=(0, 4))
        self.calendar_var = ctk.StringVar(value="(loading...)")
        self.calendar_menu = ctk.CTkOptionMenu(self, variable=self.calendar_var, values=["(no bundle)"], width=460)
        self.calendar_menu.pack(padx=20)

        # Scope
        ctk.CTkLabel(self, text="Scope", anchor="w").pack(fill="x", padx=20, pady=(16, 4))
        self.scope_var = ctk.StringVar(value="all")
        ctk.CTkRadioButton(self, text="All Feasts  (all feasts in this calendar's supplement)", variable=self.scope_var, value="all").pack(anchor="w", padx=20)
        ctk.CTkRadioButton(self, text="I & II Class Only  (most solemn feasts)", variable=self.scope_var, value="solemn").pack(anchor="w", padx=20, pady=(4, 0))

        # Format
        ctk.CTkLabel(self, text="Format", anchor="w").pack(fill="x", padx=20, pady=(16, 4))
        self.format_var = ctk.StringVar(value="pdf-single")
        ctk.CTkRadioButton(self, text="EPUB", variable=self.format_var, value="epub").pack(anchor="w", padx=20)
        ctk.CTkRadioButton(self, text="PDF — Single Page  (letter, 1 in. margins)", variable=self.format_var, value="pdf-single").pack(anchor="w", padx=20, pady=(4, 0))
        ctk.CTkRadioButton(self, text="PDF — Booklet  (2-up imposed, for folded printing)", variable=self.format_var, value="pdf-booklet").pack(anchor="w", padx=20, pady=(4, 0))

        # Language
        ctk.CTkLabel(self, text="Language", anchor="w").pack(fill="x", padx=20, pady=(16, 4))
        lang_row = ctk.CTkFrame(self, fg_color="transparent")
        lang_row.pack(anchor="w", padx=20)
        self.lang_latin = ctk.BooleanVar(value=True)
        self.lang_english = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(lang_row, text="Latin", variable=self.lang_latin).pack(side="left")
        ctk.CTkCheckBox(lang_row, text="English", variable=self.lang_english).pack(side="left", padx=(16, 0))

        sep2 = ctk.CTkFrame(self, height=1, fg_color="gray70")
        sep2.pack(fill="x", padx=20, pady=14)

        # Generate button
        self.gen_btn = ctk.CTkButton(self, text="Generate", command=self._generate, height=38, font=ctk.CTkFont(size=14))
        self.gen_btn.pack(padx=20, fill="x")

        # Progress bar (hidden until needed)
        self.progress = ctk.CTkProgressBar(self, width=460)
        self.progress.set(0)

        # Status bar
        self.status_var = ctk.StringVar(value="")
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x", padx=20, pady=(10, 4))
        self.status_lbl = ctk.CTkLabel(status_row, textvariable=self.status_var, font=ctk.CTkFont(size=11), text_color="gray", anchor="w")
        self.status_lbl.pack(side="left", fill="x", expand=True)
        self.update_btn = ctk.CTkButton(status_row, text="Check for update", width=130, height=24, font=ctk.CTkFont(size=11), command=self._check_update_bg)
        self.update_btn.pack(side="right")

    # ── Bundle loading ────────────────────────────────────────────────────────

    def _load_best_bundle(self):
        year = latest_bundle_year()
        if year:
            self._apply_bundle(year)
        else:
            self._set_status("No bundle cached. Click 'Check for update' to download.")
            self.calendar_menu.configure(values=["(no bundle)"])

    def _apply_bundle(self, year):
        data = load_bundle(year)
        if not data:
            return
        self.bundle = data
        self.bundle_year = year
        calendars = list(data.get("calendars", {}).keys())
        if calendars:
            self.calendar_menu.configure(values=calendars)
            self.calendar_var.set(calendars[0])
        gen_date = data.get("generated", "?")
        self._set_status(f"Bundle {year} — generated {gen_date}")

    def _set_status(self, msg):
        self.status_var.set(msg)

    # ── Update check ──────────────────────────────────────────────────────────

    def _check_update_bg(self):
        self.update_btn.configure(state="disabled", text="Checking...")
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _check_update_worker(self):
        repo = self.settings.get("github_repo", config.DEFAULT_GITHUB_REPO)
        year, url = fetch_latest_release_info(repo)
        if not year:
            self.after(0, lambda: self._finish_update_check("Could not reach GitHub. Check connection."))
            return
        if bundle_path(year).exists():
            self.after(0, lambda: self._finish_update_check(f"Already have the latest bundle ({year})."))
            return
        # Offer download
        self.after(0, lambda: self._offer_download(year, url))

    def _finish_update_check(self, msg):
        self._set_status(msg)
        self.update_btn.configure(state="normal", text="Check for update")

    def _offer_download(self, year, url):
        self.update_btn.configure(state="normal", text="Check for update")
        answer = ctk.CTkInputDialog(text=f"Bundle {year} is available. Download now?", title="Update Available")
        # Use a simple top-level dialog approach
        dialog = ctk.CTkToplevel(self)
        dialog.title("Update Available")
        dialog.geometry("340x140")
        dialog.resizable(False, False)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=f"Bundle {year} is available.\nDownload now? (~5 MB)", font=ctk.CTkFont(size=13)).pack(pady=20)
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()
        ctk.CTkButton(btn_row, text="Download", command=lambda: (dialog.destroy(), self._download_bg(year, url))).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Later", command=dialog.destroy, fg_color="gray").pack(side="left", padx=8)

    def _download_bg(self, year, url):
        self.progress.pack(padx=20, pady=(0, 8), fill="x")
        self.progress.set(0)
        self._set_status(f"Downloading bundle {year}...")

        def worker():
            ok = download_bundle(url, year, lambda p: self.after(0, lambda: self.progress.set(p)))
            self.after(0, lambda: self._finish_download(year, ok))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_download(self, year, ok):
        self.progress.pack_forget()
        if ok:
            self._apply_bundle(year)
        else:
            self._set_status("Download failed. Check connection and try again.")

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        def on_save(new_settings):
            self.settings.update(new_settings)
            save_settings(self.settings)
        SettingsDialog(self, self.settings, on_save)

    # ── Generation ────────────────────────────────────────────────────────────

    def _generate(self):
        if not self.bundle:
            self._set_status("No bundle loaded. Use 'Check for update' to download one.")
            return

        calendar = self.calendar_var.get()
        cal_data = self.bundle.get("calendars", {}).get(calendar)
        if not cal_data:
            self._set_status(f"No data found for {calendar}.")
            return

        feasts = cal_data.get("feasts", [])
        fmt = self.format_var.get()
        solemn_only = self.scope_var.get() == "solemn"
        include_latin = self.lang_latin.get()
        include_english = self.lang_english.get()

        if fmt == "epub":
            ext = ".epub"
            css = ""
        elif fmt == "pdf-booklet":
            ext = ".pdf"
            css = config.PDF_BOOKLET_CSS
        else:
            ext = ".pdf"
            css = config.PDF_SINGLE_CSS

        cal_short = calendar.replace("Rubrics 1960 - ", "").replace(" ", "_")
        year = self.bundle_year or date.today().year
        filename = f"Propers_{cal_short}_{year}{ext}"
        out_path = Path.home() / "Desktop" / filename
        if not out_path.parent.exists():
            out_path = Path.home() / filename

        html = build_html(feasts, solemn_only, include_latin, include_english, css)

        self.gen_btn.configure(state="disabled", text="Generating...")
        self._set_status("Building document...")

        def worker():
            try:
                if fmt == "epub":
                    generate_epub(html, out_path)
                elif fmt == "pdf-booklet":
                    generate_pdf_booklet(html, out_path)
                else:
                    generate_pdf_single(html, out_path)
                self.after(0, lambda: self._finish_generate(out_path, None))
            except Exception as e:
                self.after(0, lambda: self._finish_generate(None, str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_generate(self, out_path, error):
        self.gen_btn.configure(state="normal", text="Generate")
        if error:
            self._set_status(f"Error: {error}")
        else:
            self._set_status(f"Saved: {out_path.name}")
            # Open the file
            if sys.platform == "win32":
                os.startfile(str(out_path))
            elif sys.platform == "darwin":
                os.system(f'open "{out_path}"')
            else:
                os.system(f'xdg-open "{out_path}"')


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
