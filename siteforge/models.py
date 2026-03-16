from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
import copy
import uuid


PAGE_THEMES: Dict[str, Dict[str, str]] = {
    "midnight": {
        "label": "Midnight",
        "surface": "#0d1321",
        "surface_alt": "#171f33",
        "text": "#f5f7ff",
        "muted": "#aab8d6",
        "accent": "#58d6ff",
        "border": "#2a3a59",
        "hero": "linear-gradient(135deg, #12203b 0%, #101827 52%, #0b111d 100%)",
    },
    "paper": {
        "label": "Paper",
        "surface": "#f6f0e8",
        "surface_alt": "#fffaf4",
        "text": "#2b221a",
        "muted": "#6a5b4c",
        "accent": "#f0672f",
        "border": "#ddccb8",
        "hero": "linear-gradient(135deg, #fff6ea 0%, #f5e7d5 50%, #edd6bd 100%)",
    },
    "neon": {
        "label": "Neon Grid",
        "surface": "#0b0b16",
        "surface_alt": "#151529",
        "text": "#f8efff",
        "muted": "#b49dcd",
        "accent": "#ff5fbf",
        "border": "#322950",
        "hero": "linear-gradient(135deg, #1d1238 0%, #0d1023 45%, #07101c 100%)",
    },
    "sage": {
        "label": "Sage",
        "surface": "#eef3ec",
        "surface_alt": "#f7fbf5",
        "text": "#213127",
        "muted": "#617266",
        "accent": "#3b7f63",
        "border": "#c7d7cc",
        "hero": "linear-gradient(135deg, #f7fbf5 0%, #e1efe3 55%, #d3e4d6 100%)",
    },
}


DEFAULT_BLOCKS: Dict[str, Dict[str, Any]] = {
    "hero": {
        "name": "Hero",
        "type": "hero",
        "title": "Build pages without fighting CSS.",
        "body": "Create sections, cards, buttons, and polished landing pages. Import existing HTML or a live URL, tweak it visually, and export clean code.",
        "button_text": "Start Building",
        "button_url": "#next",
        "background": "",
        "color": "",
        "accent": "",
        "padding": 44,
        "margin": 16,
        "radius": 28,
        "align": "left",
        "min_height": 280,
        "width": -1,
        "height": -1,
        "font_size": -1,
        "font_family": "",
        "font_weight": "",
    },
    "section": {
        "name": "Section",
        "type": "section",
        "title": "Section Title",
        "body": "Use sections for feature groups, page breaks, or intro copy.",
        "button_text": "",
        "button_url": "",
        "background": "",
        "color": "",
        "accent": "",
        "padding": 28,
        "margin": 16,
        "radius": 20,
        "align": "left",
        "min_height": 0,
        "width": -1,
        "height": -1,
        "font_size": -1,
        "font_family": "",
        "font_weight": "",
    },
    "card": {
        "name": "Card",
        "type": "card",
        "title": "Feature Card",
        "body": "Cards are useful for services, stats, case studies, or about-page content.",
        "button_text": "Learn More",
        "button_url": "#",
        "background": "",
        "color": "",
        "accent": "",
        "padding": 24,
        "margin": 12,
        "radius": 22,
        "align": "left",
        "min_height": 0,
        "width": -1,
        "height": -1,
        "font_size": -1,
        "font_family": "",
        "font_weight": "",
    },
    "text": {
        "name": "Text",
        "type": "text",
        "title": "Short text block",
        "body": "Add supporting copy, paragraphs, or small callouts.",
        "button_text": "",
        "button_url": "",
        "background": "",
        "color": "",
        "accent": "",
        "padding": 18,
        "margin": 10,
        "radius": 14,
        "align": "left",
        "min_height": 0,
        "width": -1,
        "height": -1,
        "font_size": -1,
        "font_family": "",
        "font_weight": "",
    },
    "button": {
        "name": "Button",
        "type": "button",
        "title": "Primary Action",
        "body": "",
        "button_text": "Open Link",
        "button_url": "https://example.com",
        "background": "",
        "color": "",
        "accent": "",
        "padding": 16,
        "margin": 10,
        "radius": 999,
        "align": "left",
        "min_height": 0,
        "width": -1,
        "height": -1,
        "font_size": -1,
        "font_family": "",
        "font_weight": "",
    },
    "image": {
        "name": "Image",
        "type": "image",
        "title": "Image Caption",
        "body": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=1200&q=80",
        "button_text": "",
        "button_url": "",
        "background": "",
        "color": "",
        "accent": "",
        "padding": 12,
        "margin": 12,
        "radius": 24,
        "align": "left",
        "min_height": 220,
        "width": -1,
        "height": -1,
        "font_size": -1,
        "font_family": "",
        "font_weight": "",
    },
    "spacer": {
        "name": "Spacer",
        "type": "spacer",
        "title": "",
        "body": "",
        "button_text": "",
        "button_url": "",
        "background": "",
        "color": "",
        "accent": "",
        "padding": 0,
        "margin": 0,
        "radius": 0,
        "align": "left",
        "min_height": 72,
        "width": -1,
        "height": -1,
        "font_size": -1,
        "font_family": "",
        "font_weight": "",
    },
}


@dataclass
class Block:
    id: str
    type: str
    name: str
    title: str = ""
    body: str = ""
    button_text: str = ""
    button_url: str = ""
    background: str = ""
    color: str = ""
    accent: str = ""
    padding: int = 24
    margin: int = 12
    radius: int = 18
    align: str = "left"
    min_height: int = 0
    width: int = -1
    height: int = -1
    font_size: int = -1
    font_family: str = ""
    font_weight: str = ""

    def clone(self) -> "Block":
        data = self.to_dict()
        data["id"] = new_block_id()
        return Block.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "title": self.title,
            "body": self.body,
            "button_text": self.button_text,
            "button_url": self.button_url,
            "background": self.background,
            "color": self.color,
            "accent": self.accent,
            "padding": self.padding,
            "margin": self.margin,
            "radius": self.radius,
            "align": self.align,
            "min_height": self.min_height,
            "width": self.width,
            "height": self.height,
            "font_size": self.font_size,
            "font_family": self.font_family,
            "font_weight": self.font_weight,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        merged = copy.deepcopy(DEFAULT_BLOCKS.get(data.get("type", "text"), DEFAULT_BLOCKS["text"]))
        merged.update(data)
        merged.setdefault("id", new_block_id())
        return cls(**merged)


@dataclass
class ProjectDocument:
    title: str = "Untitled Project"
    page_theme: str = "midnight"
    app_theme: str = "forge"
    source_mode: str = "builder"
    source_path: str = ""
    source_url: str = ""
    raw_html: str = ""
    raw_css: str = ""
    custom_css: str = ""
    notes: str = ""
    blocks: List[Block] = field(default_factory=list)

    def ensure_defaults(self) -> None:
        if self.page_theme not in PAGE_THEMES:
            self.page_theme = "midnight"
        if not self.blocks:
            self.blocks = [make_block("hero"), make_block("card"), make_block("card")]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "page_theme": self.page_theme,
            "app_theme": self.app_theme,
            "source_mode": self.source_mode,
            "source_path": self.source_path,
            "source_url": self.source_url,
            "raw_html": self.raw_html,
            "raw_css": self.raw_css,
            "custom_css": self.custom_css,
            "notes": self.notes,
            "blocks": [block.to_dict() for block in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectDocument":
        project = cls(
            title=data.get("title", "Untitled Project"),
            page_theme=data.get("page_theme", "midnight"),
            app_theme=data.get("app_theme", "forge"),
            source_mode=data.get("source_mode", "builder"),
            source_path=data.get("source_path", ""),
            source_url=data.get("source_url", ""),
            raw_html=data.get("raw_html", ""),
            raw_css=data.get("raw_css", ""),
            custom_css=data.get("custom_css", ""),
            notes=data.get("notes", ""),
            blocks=[Block.from_dict(block) for block in data.get("blocks", [])],
        )
        project.ensure_defaults()
        return project


def new_block_id() -> str:
    return uuid.uuid4().hex[:8]


def make_block(block_type: str) -> Block:
    if block_type not in DEFAULT_BLOCKS:
        block_type = "text"
    data = copy.deepcopy(DEFAULT_BLOCKS[block_type])
    data["id"] = new_block_id()
    return Block.from_dict(data)


def make_portfolio_homepage() -> ProjectDocument:
    project = ProjectDocument(
        title="Portfolio Homepage",
        page_theme="midnight",
        app_theme="forge",
        source_mode="builder",
        notes="Generated from the built-in portfolio homepage template.",
        blocks=[
            Block.from_dict({
                **DEFAULT_BLOCKS["hero"],
                "id": new_block_id(),
                "title": "Design sharper pages faster.",
                "body": "SiteForge gives you a builder, importer, and live-site editor in one desktop app. Shape layouts, refine styling, and export code you can actually keep.",
                "button_text": "Launch a Project",
                "button_url": "#work",
                "min_height": 320,
            }),
            Block.from_dict({
                **DEFAULT_BLOCKS["section"],
                "id": new_block_id(),
                "title": "What you can do",
                "body": "Build from scratch, import an existing page, or load a live site URL and use it as the starting point for a cleaner version.",
                "padding": 30,
            }),
            Block.from_dict({
                **DEFAULT_BLOCKS["card"],
                "id": new_block_id(),
                "title": "Visual Builder",
                "body": "Add heroes, cards, buttons, text, images, and spacers. Reorder blocks with drag and drop and tune styling without digging through CSS.",
                "button_text": "Add Blocks",
                "button_url": "#builder",
            }),
            Block.from_dict({
                **DEFAULT_BLOCKS["card"],
                "id": new_block_id(),
                "title": "Import and Clean Up",
                "body": "Open local HTML or fetch a live URL, convert the main sections into editable blocks, and then refine the layout in one place.",
                "button_text": "Import Page",
                "button_url": "#import",
            }),
            Block.from_dict({
                **DEFAULT_BLOCKS["button"],
                "id": new_block_id(),
                "title": "Export Site",
                "button_text": "Export HTML and CSS",
                "button_url": "#export",
                "align": "center",
            }),
        ],
    )
    project.ensure_defaults()
    return project


def make_blank_project() -> ProjectDocument:
    project = ProjectDocument(title="Untitled Project")
    project.ensure_defaults()
    return project
