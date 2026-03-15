# SiteForge

SiteForge is a Python desktop app for building and tweaking website layouts with a clearer workflow split across dedicated modes.

## What it does

- Left-side navigation for `Homepage`, `Editor`, `Color Lab`, and `Export`
- `Editor` mode with drag-and-drop block reordering, live preview, inspector controls, and generated code views
- HTML import from file or pasted code, converted into editable blocks
- `Color Lab` workspace for HEX palette generation, CSS variables, gradient snippets, and TXT export
- Copyable output tabs for generated builder HTML/CSS and website-mode final HTML/CSS
- Export folders for both builder output and website-mode output
- Switch app themes and page themes
- Built-in update check button in the top bar

## Stack

- Python 3.10+
- PySide6
- Beautiful Soup 4

## Install

```powershell
cd [FOLDER]\SiteForge
python -m pip install -r requirements.txt
```

## Run

```powershell
cd [FOLDER]\SiteForge
python main.py
```

## Notes

- URL import works best on landing pages, portfolios, and other content-heavy pages with clean HTML.
- Source preview/editing is a local inspect-style workflow. It does not permanently edit remote websites.
- If `QtWebEngine` is unavailable, SiteForge falls back to a code preview instead of a rendered browser preview.
