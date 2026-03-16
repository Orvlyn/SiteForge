from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import List, Optional

from bs4 import BeautifulSoup, Tag


@dataclass
class WebsiteTarget:
    selector: str
    label: str
    snippet: str


def _best_selector(element: Tag) -> str:
    if element.get("id"):
        return f"#{element.get('id')}"

    def simple_selector(tag: Tag) -> str:
        name = tag.name or "div"
        classes = [value for value in tag.get("class", []) if value]
        if classes:
            return f"{name}." + ".".join(classes[:2])
        parent = tag.parent if isinstance(tag.parent, Tag) else None
        if not parent:
            return name
        siblings = [node for node in parent.find_all(name, recursive=False)]
        if len(siblings) <= 1:
            return name
        position = siblings.index(tag) + 1
        return f"{name}:nth-of-type({position})"

    parts: List[str] = []
    current: Optional[Tag] = element
    depth = 0
    while current and current.name and depth < 4:
        parts.append(simple_selector(current))
        if current.get("id"):
            parts[-1] = f"#{current.get('id')}"
            break
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
        depth += 1
    return " > ".join(reversed(parts)) if parts else (element.name or "div")


def _target_label(element: Tag, selector: str) -> str:
    text = element.get_text(" ", strip=True)
    text = " ".join(text.split())
    if len(text) > 72:
        text = text[:69].rstrip() + "..."
    if not text:
        text = element.get("aria-label") or element.get("alt") or element.name
    classes = element.get("class", [])
    class_hint = ""
    if classes:
        class_hint = f" [{'.'.join(classes[:2])}]"
    return f"{selector}{class_hint} - {text}"


def extract_targets(html: str, limit: int = 180) -> List[WebsiteTarget]:
    soup = BeautifulSoup(html, "html.parser")
    targets: List[WebsiteTarget] = []
    structural_tags = {
        "section", "article", "div", "header", "footer", "nav", "main", "aside", "button", "a",
        "img", "p", "h1", "h2", "h3", "h4", "h5", "span", "li", "ul", "ol", "figure", "iframe"
    }

    def include_element(element: Tag) -> bool:
        if element.name in structural_tags:
            return True
        classes = " ".join(element.get("class", []))
        if "elementor" in classes:
            return True
        if element.get("data-element_type") or element.get("data-widget_type"):
            return True
        return False

    for element in soup.find_all(True):
        if not isinstance(element, Tag):
            continue
        if not include_element(element):
            continue
        selector = _best_selector(element)
        snippet = str(element)[:420]
        targets.append(WebsiteTarget(selector=selector, label=_target_label(element, selector), snippet=snippet))
        if len(targets) >= limit:
            break
    return targets
def sanitize_html_for_preview(html: str, *, keep_scripts: bool = False) -> str:
    if keep_scripts:
        return html or ""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all("script"):
        script_type = (tag.get("type") or "").strip().lower()
        if script_type == "application/ld+json":
            continue
        tag.decompose()
    for tag in soup.find_all(True):
        for key in list(tag.attrs.keys()):
            if key.lower().startswith("on"):
                tag.attrs.pop(key, None)
    return str(soup)


def build_rule_css(
    selector: str,
    background: Optional[str],
    color: Optional[str],
    padding: Optional[int],
    margin: Optional[int],
    radius: Optional[int],
    width: Optional[int],
    height: Optional[int],
    font_size: Optional[int],
    font_family: Optional[str],
    extra_css: Optional[str],
) -> str:
    def strong(decl: str) -> str:
        if decl.endswith("!important;"):
            return decl
        return decl[:-1] + " !important;"

    parts = []
    if background:
        parts.append(strong(f"background: {background};"))
    if color:
        parts.append(strong(f"color: {color};"))
    if padding is not None:
        parts.append(strong(f"padding: {padding}px;"))
    if margin is not None:
        parts.append(strong(f"margin: {margin}px;"))
    if radius is not None:
        parts.append(strong(f"border-radius: {radius}px;"))
    if width is not None:
        parts.append(strong(f"width: {width}px;"))
    if height is not None:
        parts.append(strong(f"height: {height}px;"))
    if font_size is not None:
        parts.append(strong(f"font-size: {font_size}px;"))
    if font_family and font_family.strip():
        parts.append(strong(f"font-family: {font_family.strip()};"))
    if extra_css and extra_css.strip():
        cleaned = extra_css.strip()
        if not cleaned.endswith(";"):
            cleaned += ";"
        parts.append(cleaned)
    declarations = "\n    ".join(parts)
    if not declarations:
        declarations = "/* no overrides */"
    return f"{selector} {{\n    {declarations}\n}}"


def inject_override_css(html: str, css: str) -> str:
    if not css.strip():
        return html
    style_tag = f"<style id='siteforge-overrides'>\n{css}\n</style>"
    lower = html.lower()
    head_index = lower.find("</head>")
    if head_index != -1:
        return html[:head_index] + style_tag + html[head_index:]
    body_index = lower.find("<body")
    if body_index != -1:
        body_start = html.find(">", body_index)
        if body_start != -1:
            insertion_point = body_start + 1
            return html[:insertion_point] + style_tag + html[insertion_point:]
    return style_tag + html


def apply_text_change(html: str, selector: str, text_value: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    target = soup.select_one(selector)
    if target is None:
        return html
    target.clear()
    if "<" in text_value and ">" in text_value:
        fragment = BeautifulSoup(f"<div>{text_value}</div>", "html.parser")
        wrapper = fragment.div
        if wrapper is not None:
            for child in list(wrapper.contents):
                target.append(child)
        else:
            target.append(text_value)
    else:
        target.append(text_value)
    return str(soup)


def build_targets_html(targets: List[WebsiteTarget]) -> str:
    rows = []
    for target in targets:
        rows.append(
            f"<div class='sf-target-row'><strong>{escape(target.selector)}</strong><span>{escape(target.label)}</span></div>"
        )
    return "\n".join(rows)
