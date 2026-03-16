from __future__ import annotations

from html import unescape
from pathlib import Path
from typing import Dict, Iterable, Optional
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag

from .models import Block, ProjectDocument, make_blank_project, new_block_id


HEADERS = {
    "User-Agent": "SiteForge/0.1 (+desktop-editor)",
}


def parse_style_attribute(value: str) -> Dict[str, str]:
    styles: Dict[str, str] = {}
    for entry in value.split(";"):
        if ":" not in entry:
            continue
        key, raw_value = entry.split(":", 1)
        styles[key.strip().lower()] = raw_value.strip()
    return styles


def _px_to_int(value: str, default: int) -> int:
    cleaned = value.strip().lower().replace("px", "")
    try:
        return int(float(cleaned))
    except ValueError:
        return default


def _first_text(*values: Optional[str]) -> str:
    for value in values:
        if value and value.strip():
            return unescape(value.strip())
    return ""


def _extract_link(element: Tag) -> tuple[str, str]:
    link = element.find("a", href=True)
    if not link:
        return "", ""
    return _first_text(link.get_text(" ", strip=True), "Open"), link.get("href", "")


def _block_from_element(element: Tag, base_url: str = "") -> Optional[Block]:
    if element.name in {"script", "style", "noscript"}:
        return None

    styles = parse_style_attribute(element.get("style", ""))
    classes = " ".join(element.get("class", []))
    title = ""
    body = ""
    button_text = ""
    button_url = ""
    block_type = "text"

    if element.name in {"section", "article"}:
        block_type = "section"
    elif element.name == "img":
        block_type = "image"
    elif element.name in {"a", "button"}:
        block_type = "button"
    elif element.name in {"div", "aside"}:
        block_type = "card" if any(word in classes.lower() for word in ["card", "panel", "feature", "tile"]) else "section"
    elif element.name in {"h1", "h2", "h3", "h4"}:
        block_type = "section"
    elif element.name == "p":
        block_type = "text"

    if element.name == "img":
        src = element.get("src", "")
        if base_url:
            src = urljoin(base_url, src)
        return Block(
            id=new_block_id(),
            type="image",
            name="Imported Image",
            title=_first_text(element.get("alt"), "Imported image"),
            body=src,
            padding=12,
            margin=12,
            radius=20,
            min_height=220,
            background=styles.get("background", ""),
            color=styles.get("color", ""),
            accent="",
            width=_px_to_int(styles.get("width", "-1"), -1),
            height=_px_to_int(styles.get("height", "-1"), -1),
            font_size=_px_to_int(styles.get("font-size", "-1"), -1),
            font_family=styles.get("font-family", ""),
            font_weight=styles.get("font-weight", ""),
        )

    if element.name in {"a", "button"}:
        button_text = _first_text(element.get_text(" ", strip=True), "Open")
        button_url = element.get("href", "")
        if base_url:
            button_url = urljoin(base_url, button_url)
        return Block(
            id=new_block_id(),
            type="button",
            name="Imported Button",
            title=button_text,
            button_text=button_text,
            button_url=button_url,
            padding=_px_to_int(styles.get("padding", "16"), 16),
            margin=_px_to_int(styles.get("margin", "10"), 10),
            radius=_px_to_int(styles.get("border-radius", "999"), 999),
            background=styles.get("background", ""),
            color=styles.get("color", ""),
            accent=styles.get("background", ""),
            width=_px_to_int(styles.get("width", "-1"), -1),
            height=_px_to_int(styles.get("height", "-1"), -1),
            font_size=_px_to_int(styles.get("font-size", "-1"), -1),
            font_family=styles.get("font-family", ""),
            font_weight=styles.get("font-weight", ""),
        )

    heading = element.find(["h1", "h2", "h3", "h4"])
    paragraph = element.find("p")
    button_text, button_url = _extract_link(element)

    title = _first_text(
        element.get_text(" ", strip=True) if element.name in {"h1", "h2", "h3", "h4"} else "",
        heading.get_text(" ", strip=True) if heading else "",
        element.get("aria-label", ""),
        classes.replace("-", " ").title(),
        "Imported Block",
    )
    body = _first_text(
        paragraph.get_text(" ", strip=True) if paragraph else "",
        element.get_text(" ", strip=True) if element.name == "p" else "",
        "Imported from HTML",
    )

    if len(body) > 360:
        body = body[:357].rstrip() + "..."

    return Block(
        id=new_block_id(),
        type=block_type,
        name=f"Imported {block_type.title()}",
        title=title,
        body=body,
        button_text=button_text,
        button_url=button_url,
        background=styles.get("background", ""),
        color=styles.get("color", ""),
        accent=styles.get("border-color", styles.get("background", "")),
        padding=_px_to_int(styles.get("padding", "24"), 24),
        margin=_px_to_int(styles.get("margin", "12"), 12),
        radius=_px_to_int(styles.get("border-radius", "18"), 18),
        width=_px_to_int(styles.get("width", "-1"), -1),
        height=_px_to_int(styles.get("height", "-1"), -1),
        font_size=_px_to_int(styles.get("font-size", "-1"), -1),
        font_family=styles.get("font-family", ""),
        font_weight=styles.get("font-weight", ""),
    )


def _pick_candidates(soup: BeautifulSoup) -> Iterable[Tag]:
    body = soup.body or soup
    candidates = []
    seen_signatures: set[str] = set()

    for element in body.find_all(True):
        if not isinstance(element, Tag):
            continue
        if element.name in {"script", "style", "noscript"}:
            continue

        classes = " ".join(element.get("class", []))
        has_text = bool(element.get_text(" ", strip=True))
        important = (
            element.name in {"section", "article", "header", "main", "footer", "aside", "h1", "h2", "h3", "h4", "p", "a", "button", "img"}
            or "elementor" in classes
            or element.get("data-widget_type")
            or element.get("data-element_type")
            or (element.name == "div" and has_text)
        )
        if not important:
            continue

        signature = f"{element.name}|{element.get('id','')}|{classes[:80]}|{element.get_text(' ', strip=True)[:60]}"
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        candidates.append(element)
        if len(candidates) >= 60:
            break

    return candidates


def html_to_document(html: str, *, title: str = "Imported Page", source_mode: str = "import", source_path: str = "", source_url: str = "", base_url: str = "") -> ProjectDocument:
    soup = BeautifulSoup(html, "html.parser")
    page_title = title
    if soup.title and soup.title.string:
        page_title = soup.title.string.strip()

    project = make_blank_project()
    project.title = page_title or "Imported Page"
    project.source_mode = source_mode
    project.source_path = source_path
    project.source_url = source_url
    project.raw_html = html
    project.blocks.clear()

    for element in _pick_candidates(soup):
        block = _block_from_element(element, base_url=base_url)
        if block:
            project.blocks.append(block)

    if not project.blocks:
        project.ensure_defaults()
    return project


def load_html_file(path: str) -> ProjectDocument:
    file_path = Path(path)
    html = file_path.read_text(encoding="utf-8", errors="ignore")
    return html_to_document(
        html,
        title=file_path.stem.replace("_", " ").title(),
        source_mode="import",
        source_path=str(file_path),
        base_url=file_path.parent.as_uri() + "/",
    )


def load_url(url: str) -> ProjectDocument:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=12) as response:
        html = response.read().decode("utf-8", errors="ignore")
    return html_to_document(html, source_mode="live-url", source_url=url, base_url=url)
