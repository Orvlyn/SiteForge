from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Optional
import warnings
import re

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

from .models import Block, PAGE_THEMES, ProjectDocument


def _text_align(value: str) -> str:
    return value if value in {"left", "center", "right"} else "left"


def _block_style(block: Block) -> str:
    parts = [
        f"padding:{max(block.padding, 0)}px",
        f"margin:{max(block.margin, 0)}px 0",
        f"border-radius:{max(block.radius, 0)}px",
        f"text-align:{_text_align(block.align)}",
    ]
    if block.background:
        parts.append(f"background:{block.background}")
    if block.color:
        parts.append(f"color:{block.color}")
    if block.min_height:
        parts.append(f"min-height:{max(block.min_height, 0)}px")
    if getattr(block, "width", -1) >= 0:
        parts.append(f"width:{max(block.width, 0)}px")
    if getattr(block, "height", -1) >= 0:
        parts.append(f"height:{max(block.height, 0)}px")
    if getattr(block, "font_size", -1) >= 0:
        parts.append(f"font-size:{max(block.font_size, 0)}px")
    if getattr(block, "font_family", "").strip():
        parts.append(f"font-family:{block.font_family.strip()}")
    if getattr(block, "font_weight", "").strip():
        parts.append(f"font-weight:{block.font_weight.strip()}")
    return "; ".join(parts)


def _render_button(text: str, url: str, accent: str) -> str:
    label = escape(text or "Open")
    href = escape(url or "#")
    style = f" style='--button-accent:{escape(accent)}'" if accent else ""
    return f"<a class='sf-button' href='{href}'{style}>{label}</a>"


def _safe_inline_html(value: str) -> str:
    if not value.strip():
        return ""
    normalized = value.strip()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://\S+$", normalized):
        return escape(value)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MarkupResemblesLocatorWarning)
        soup = BeautifulSoup(value, "html.parser")
    allowed = {"strong", "em", "b", "i", "u", "span", "br", "a", "small", "mark", "code"}
    for tag in soup.find_all(True):
        if tag.name not in allowed:
            tag.unwrap()
            continue
        for attr in list(tag.attrs.keys()):
            if tag.name == "a" and attr in {"href", "target", "rel"}:
                continue
            if tag.name == "span" and attr == "style":
                continue
            tag.attrs.pop(attr, None)
    return str(soup)


def render_block(block: Block, selected_id: Optional[str] = None) -> str:
    selected_class = " is-selected" if block.id == selected_id else ""
    style = escape(_block_style(block), quote=True)
    heading = escape(block.title)
    body = _safe_inline_html(block.body).replace("\n", "<br>")

    if block.type == "hero":
        button_html = _render_button(block.button_text, block.button_url, block.accent) if block.button_text else ""
        return f"""
        <section class='sf-block sf-hero{selected_class}' data-block-id='{block.id}' style='{style}'>
            <div class='sf-eyebrow'>Homepage</div>
            <h1>{heading}</h1>
            <p>{body}</p>
            {button_html}
        </section>
        """

    if block.type == "section":
        button_html = _render_button(block.button_text, block.button_url, block.accent) if block.button_text else ""
        return f"""
        <section class='sf-block sf-section{selected_class}' data-block-id='{block.id}' style='{style}'>
            <h2>{heading}</h2>
            <p>{body}</p>
            {button_html}
        </section>
        """

    if block.type == "card":
        button_html = _render_button(block.button_text, block.button_url, block.accent) if block.button_text else ""
        return f"""
        <article class='sf-block sf-card{selected_class}' data-block-id='{block.id}' style='{style}'>
            <h3>{heading}</h3>
            <p>{body}</p>
            {button_html}
        </article>
        """

    if block.type == "button":
        return f"""
        <div class='sf-block sf-button-wrap{selected_class}' data-block-id='{block.id}' style='{style}'>
            {_render_button(block.button_text or block.title, block.button_url, block.accent or block.background)}
        </div>
        """

    if block.type == "image":
        image_src = escape(block.body, quote=True)
        alt = heading or "Image"
        return f"""
        <figure class='sf-block sf-image{selected_class}' data-block-id='{block.id}' style='{style}'>
            <img src='{image_src}' alt='{escape(alt, quote=True)}' />
            <figcaption>{heading}</figcaption>
        </figure>
        """

    if block.type == "spacer":
        return f"<div class='sf-block sf-spacer{selected_class}' data-block-id='{block.id}' style='{style}'></div>"

    return f"""
    <div class='sf-block sf-text{selected_class}' data-block-id='{block.id}' style='{style}'>
        <p><strong>{heading}</strong></p>
        <p>{body}</p>
    </div>
    """


def build_css(project: ProjectDocument) -> str:
    palette = PAGE_THEMES.get(project.page_theme, PAGE_THEMES["midnight"])
    return f"""
:root {{
    --sf-surface: {palette['surface']};
    --sf-surface-alt: {palette['surface_alt']};
    --sf-text: {palette['text']};
    --sf-muted: {palette['muted']};
    --sf-accent: {palette['accent']};
    --sf-border: {palette['border']};
    --sf-hero: {palette['hero']};
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    background: var(--sf-surface);
    color: var(--sf-text);
}}
.sf-shell {{
    max-width: 1180px;
    margin: 0 auto;
    padding: 36px 20px 72px;
}}
.sf-topbar {{
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: center;
    margin-bottom: 18px;
}}
.sf-topbar h1 {{
    margin: 0;
    font-size: clamp(2rem, 4vw, 3rem);
}}
.sf-topbar p {{
    margin: 6px 0 0;
    color: var(--sf-muted);
}}
.sf-meta {{
    color: var(--sf-muted);
    font-size: 0.95rem;
}}
.sf-canvas {{
    display: grid;
    gap: 18px;
}}
.sf-block {{
    border: 1px solid var(--sf-border);
    background: var(--sf-surface-alt);
    box-shadow: 0 18px 50px rgba(0, 0, 0, 0.16);
}}
.sf-hero {{
    background: var(--sf-hero);
    padding-top: 58px !important;
    padding-bottom: 58px !important;
}}
.sf-hero h1, .sf-section h2, .sf-card h3 {{ margin-top: 0; }}
.sf-hero p, .sf-section p, .sf-card p, .sf-text p {{
    color: var(--sf-muted);
    line-height: 1.65;
}}
.sf-eyebrow {{
    display: inline-block;
    margin-bottom: 12px;
    padding: 6px 10px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    color: var(--sf-accent);
    font-size: 0.85rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}}
.sf-card {{
    backdrop-filter: blur(12px);
}}
.sf-button-wrap {{
    display: flex;
    justify-content: center;
}}
.sf-button {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    padding: 12px 18px;
    min-width: 140px;
    border-radius: 999px;
    background: var(--button-accent, var(--sf-accent));
    color: #06111c;
    font-weight: 700;
}}
.sf-image img {{
    width: 100%;
    display: block;
    border-radius: inherit;
    object-fit: cover;
    min-height: 220px;
    max-height: 480px;
}}
.sf-image figcaption {{
    padding-top: 10px;
    color: var(--sf-muted);
}}
.sf-spacer {{
    background: transparent;
    border-style: dashed;
    box-shadow: none;
}}
.is-selected {{
    outline: 3px solid var(--sf-accent);
    outline-offset: 2px;
}}
{project.custom_css}
""".strip()


def build_html(project: ProjectDocument, selected_id: Optional[str] = None, *, inline_css: bool = True) -> str:
    css = build_css(project)
    blocks_html = "\n".join(render_block(block, selected_id=selected_id) for block in project.blocks)
    stylesheet = f"<style>{css}</style>" if inline_css else "<link rel='stylesheet' href='styles.css'>"
    subtitle = escape(project.notes or "Built with SiteForge")
    source_value = project.source_url or project.source_path or "Builder"
    return f"""
<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='utf-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>{escape(project.title)}</title>
    {stylesheet}
</head>
<body>
    <div class='sf-shell'>
        <header class='sf-topbar'>
            <div>
                <h1>{escape(project.title)}</h1>
                <p>{subtitle}</p>
            </div>
            <div class='sf-meta'>Source: {escape(source_value)}</div>
        </header>
        <main class='sf-canvas'>
            {blocks_html}
        </main>
    </div>
</body>
</html>
    """.strip()


def export_project(project: ProjectDocument, target_dir: str) -> tuple[Path, Path, Path]:
    root = Path(target_dir)
    root.mkdir(parents=True, exist_ok=True)
    html_path = root / "index.html"
    css_path = root / "styles.css"
    json_path = root / "siteforge_project.json"

    html_path.write_text(build_html(project, inline_css=False), encoding="utf-8")
    css_path.write_text(build_css(project), encoding="utf-8")
    json_path.write_text(__import__("json").dumps(project.to_dict(), indent=2), encoding="utf-8")
    return html_path, css_path, json_path
