from __future__ import annotations

from typing import Dict


APP_THEMES: Dict[str, Dict[str, str]] = {
    "forge": {
        "label": "Forge Dark",
        "window": "#0f1118",
        "panel": "#171b24",
        "panel_alt": "#1d2430",
        "border": "#2a3445",
        "text": "#f3f7ff",
        "muted": "#a2b2cb",
        "accent": "#59d2ff",
        "accent_soft": "#17394c",
        "success": "#66c18c",
    },
    "linen": {
        "label": "Linen Light",
        "window": "#f4efe8",
        "panel": "#fffaf3",
        "panel_alt": "#f1e5d6",
        "border": "#d6c6b3",
        "text": "#2f241a",
        "muted": "#6b5c4d",
        "accent": "#e76a2f",
        "accent_soft": "#f7d7c8",
        "success": "#3d8e67",
    },
    "signal": {
        "label": "Signal",
        "window": "#0d0b16",
        "panel": "#161227",
        "panel_alt": "#201a37",
        "border": "#322b52",
        "text": "#f8efff",
        "muted": "#bba8d5",
        "accent": "#ff5fbf",
        "accent_soft": "#46213d",
        "success": "#5bddaa",
    },
    "obsidian": {
        "label": "Obsidian Cyan",
        "window": "#070a0f",
        "panel": "#0d141d",
        "panel_alt": "#142130",
        "border": "#243448",
        "text": "#ecf5ff",
        "muted": "#97abc2",
        "accent": "#44d8ff",
        "accent_soft": "#153446",
        "success": "#5fe0a8",
    },
    "ember": {
        "label": "Ember Noir",
        "window": "#100c0b",
        "panel": "#1a1312",
        "panel_alt": "#251a18",
        "border": "#3a2824",
        "text": "#fff1ea",
        "muted": "#d0ada0",
        "accent": "#ff875b",
        "accent_soft": "#4a2a20",
        "success": "#7fd089",
    },
    "neon-night": {
        "label": "Neon Night",
        "window": "#090812",
        "panel": "#111026",
        "panel_alt": "#1b1639",
        "border": "#30285c",
        "text": "#f4f0ff",
        "muted": "#b7abd9",
        "accent": "#7f7bff",
        "accent_soft": "#2a2752",
        "success": "#59d8c5",
    },
    "grove": {
        "label": "Grove",
        "window": "#e9efe8",
        "panel": "#f8fcf4",
        "panel_alt": "#dbe8dd",
        "border": "#c0d1c3",
        "text": "#203027",
        "muted": "#617064",
        "accent": "#357e5d",
        "accent_soft": "#cfe3d4",
        "success": "#2d7a56",
    },
}


def build_stylesheet(theme_name: str) -> str:
    theme = APP_THEMES.get(theme_name, APP_THEMES["forge"])
    return f"""
    QWidget {{
        background: {theme['window']};
        color: {theme['text']};
        font-family: 'Segoe UI';
        font-size: 10.5pt;
    }}
    QMainWindow {{
        background: {theme['window']};
    }}
    QLabel#titleLabel {{
        font-size: 18pt;
        font-weight: 700;
    }}
    QLabel#subtitleLabel {{
        color: {theme['muted']};
        font-size: 10pt;
    }}
    QLabel#sectionHeading {{
        font-size: 12pt;
        font-weight: 700;
    }}
    QLabel#eyebrowLabel {{
        color: {theme['accent']};
        font-size: 9pt;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }}
    QWidget[card='true'], QFrame[card='true'] {{
        background: {theme['panel']};
        border: 1px solid {theme['border']};
        border-radius: 18px;
    }}
    QPushButton {{
        background: {theme['panel_alt']};
        border: 1px solid {theme['border']};
        border-radius: 12px;
        padding: 10px 14px;
    }}
    QPushButton:hover {{
        border-color: {theme['accent']};
    }}
    QPushButton[variant='primary'] {{
        background: {theme['accent']};
        color: {theme['window']};
        font-weight: 700;
        border-color: {theme['accent']};
    }}
    QPushButton[variant='ghost'] {{
        background: transparent;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget, QTreeWidget, QTabWidget::pane {{
        background: {theme['panel']};
        border: 1px solid {theme['border']};
        border-radius: 12px;
        padding: 6px;
    }}
    QListWidget#navList {{
        padding: 10px;
    }}
    QListWidget#navList::item {{
        padding: 12px 14px;
        border-radius: 14px;
        margin: 4px 0;
        font-weight: 600;
    }}
    QListWidget#navList::item:selected {{
        background: {theme['accent_soft']};
        border: 1px solid {theme['accent']};
        color: {theme['text']};
    }}
    QListWidget::item {{
        padding: 8px;
        border-radius: 10px;
        margin: 3px;
    }}
    QListWidget::item:selected {{
        background: {theme['accent_soft']};
        border: 1px solid {theme['accent']};
    }}
    QTabBar::tab {{
        background: {theme['panel_alt']};
        border: 1px solid {theme['border']};
        border-bottom: none;
        padding: 10px 14px;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        margin-right: 4px;
    }}
    QTabBar::tab:selected {{
        background: {theme['panel']};
        color: {theme['accent']};
    }}
    QSplitter::handle {{
        background: {theme['window']};
    }}
    QSplitter::handle:horizontal {{
        width: 8px;
    }}
    QSplitter::handle:vertical {{
        height: 8px;
    }}
    QScrollBar:vertical {{
        width: 12px;
        background: {theme['window']};
        margin: 8px 0 8px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {theme['border']};
        border-radius: 6px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {theme['accent']};
    }}
    QStatusBar {{
        border-top: 1px solid {theme['border']};
    }}
    """
