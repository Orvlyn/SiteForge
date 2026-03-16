from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Tag
from PySide6.QtCore import QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--enable-smooth-scrolling --enable-gpu-rasterization --enable-zero-copy --ignore-gpu-blocklist --disable-logging --log-level=3",
)

try:
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEB_ENGINE = True
except Exception:
    QWebEnginePage = None
    QWebEngineSettings = None
    QWebEngineView = None
    HAS_WEB_ENGINE = False

from .exporter import build_css, build_html, export_project
from .color_lab import ColorLabWorkspace
from .models import DEFAULT_BLOCKS, PAGE_THEMES, Block, ProjectDocument, make_blank_project, make_block, make_portfolio_homepage
from .parser import html_to_document, load_html_file, load_url
from .themes import APP_THEMES, build_stylesheet
from .website_tools import apply_text_change, build_rule_css, extract_targets, inject_override_css, sanitize_html_for_preview


def base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_VERSION = "1.1.0"
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/Orvlyn/SiteForge/main/version.json"
ICON_CACHE_PATH = base_dir() / ".siteforge_icon_cache.ico"
ICON_GITHUB_URL = "https://raw.githubusercontent.com/Orvlyn/SiteForge/main/SiteForge.ico"


def get_cached_icon() -> QIcon:
    local_icon = base_dir() / "siteforge.ico"
    if local_icon.exists():
        icon = QIcon(str(local_icon))
        if not icon.isNull():
            return icon
    if ICON_CACHE_PATH.exists():
        icon = QIcon(str(ICON_CACHE_PATH))
        if not icon.isNull():
            return icon
    try:
        urllib.request.urlretrieve(ICON_GITHUB_URL, str(ICON_CACHE_PATH))
        icon = QIcon(str(ICON_CACHE_PATH))
        if not icon.isNull():
            return icon
    except Exception:
        pass
    return QIcon()


def card_frame() -> QFrame:
    frame = QFrame()
    frame.setProperty("card", True)
    frame.setFrameShape(QFrame.StyledPanel)
    return frame


def copy_to_clipboard(text: str) -> None:
    QApplication.clipboard().setText(text)


class GradientPickerDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, initial: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Gradient Picker")
        self.resize(620, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setVerticalSpacing(8)

        self.gradient_type = QComboBox()
        self.gradient_type.addItems(["linear", "radial"])

        self.stop_count = QComboBox()
        for value in range(2, 9):
            self.stop_count.addItem(f"{value} colors", value)

        self.stop_rows: list[tuple[QWidget, QLineEdit, QSpinBox]] = []
        stop_defaults = [
            ("#5ee7df", 0),
            ("#b490ca", 100),
            ("#f6d365", 25),
            ("#fda085", 40),
            ("#84fab0", 55),
            ("#8fd3f4", 70),
            ("#cfd9df", 85),
            ("#fbc2eb", 100),
        ]
        stops_widget = QWidget()
        stops_layout = QVBoxLayout(stops_widget)
        stops_layout.setContentsMargins(0, 0, 0, 0)
        stops_layout.setSpacing(8)
        for index, (color_value, stop_value) in enumerate(stop_defaults, start=1):
            color_edit = QLineEdit(color_value)
            pick_button = QPushButton("Pick")
            stop_spin = QSpinBox()
            stop_spin.setRange(0, 100)
            stop_spin.setValue(stop_value)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_label = QLabel(f"Stop {index}")
            row_label.setMinimumWidth(44)
            percent_label = QLabel("%")
            row_layout.addWidget(row_label)
            row_layout.addWidget(color_edit, 1)
            row_layout.addWidget(pick_button)
            row_layout.addWidget(stop_spin)
            row_layout.addWidget(percent_label)
            stops_layout.addWidget(row)
            pick_button.clicked.connect(lambda checked=False, target=color_edit: self._pick_color(target))
            color_edit.textChanged.connect(self._update_preview)
            stop_spin.valueChanged.connect(self._update_preview)
            self.stop_rows.append((row, color_edit, stop_spin))

        self.angle_spin = QSpinBox()
        self.angle_spin.setRange(0, 360)
        self.angle_spin.setValue(135)

        self.preview_css = QPlainTextEdit()
        self.preview_css.setReadOnly(True)
        self.preview_css.setMinimumHeight(100)

        form.addRow("Type", self.gradient_type)
        form.addRow("Stops", self.stop_count)
        form.addRow("Angle", self.angle_spin)
        form.addRow("Colors", stops_widget)
        form.addRow("CSS", self.preview_css)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root.addLayout(form)
        root.addWidget(buttons)

        self.stop_count.currentIndexChanged.connect(self._update_stop_visibility)
        self.gradient_type.currentIndexChanged.connect(self._update_preview)
        self.angle_spin.valueChanged.connect(self._update_preview)

        if initial.strip().startswith("linear-gradient"):
            self.gradient_type.setCurrentText("linear")
        elif initial.strip().startswith("radial-gradient"):
            self.gradient_type.setCurrentText("radial")
        self.stop_count.setCurrentIndex(2)
        self._update_stop_visibility()
        self._update_preview()

    def _field_row(self, line_edit: QLineEdit, button: QPushButton, extra_button: Optional[QPushButton] = None) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        if extra_button is not None:
            layout.addWidget(extra_button)
        return widget

    def _pick_color(self, target: QLineEdit) -> None:
        initial = QColor(target.text()) if target.text().strip() else QColor("#ffffff")
        color = QColorDialog.getColor(initial, self, "Pick Color")
        if color.isValid():
            target.setText(color.name())

    def _update_preview(self) -> None:
        self.preview_css.setPlainText(self.gradient_value())

    def _update_stop_visibility(self) -> None:
        active_count = int(self.stop_count.currentData() or 2)
        for index, (row, _, _) in enumerate(self.stop_rows, start=1):
            row.setVisible(index <= active_count)
        self._update_preview()

    def gradient_value(self) -> str:
        active_count = int(self.stop_count.currentData() or 2)
        stops = []
        for index, (_row, color_edit, stop_spin) in enumerate(self.stop_rows[:active_count], start=1):
            color_value = color_edit.text().strip() or "#ffffff"
            stop_value = stop_spin.value()
            stops.append(f"{color_value} {stop_value}%")
        if not stops:
            stops = ["#5ee7df 0%", "#b490ca 100%"]
        if self.gradient_type.currentText() == "radial":
            return f"radial-gradient(circle, {', '.join(stops)})"
        angle = self.angle_spin.value()
        return f"linear-gradient({angle}deg, {', '.join(stops)})"


class BlockListWidget(QListWidget):
    orderChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAlternatingRowColors(False)

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        self.orderChanged.emit()


class PreviewPane(QWidget):
    jsMessageReceived = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.interaction_mode = "none"
        self.desired_viewport_width = 0
        self._last_zoom_factor = -1.0
        self._last_html = ""
        self._last_base_url = ""
        self._last_mode_loaded = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if HAS_WEB_ENGINE:
            self.browser = QWebEngineView()
            self.page = _WebBridgePage(self.browser)
            self.browser.setPage(self.page)
            if QWebEngineSettings is not None:
                settings = self.browser.settings()
                settings.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
                settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            self.page.bridgeMessage.connect(self.jsMessageReceived)
            self.browser.loadFinished.connect(self._inject_interaction)
        else:
            self.browser = QPlainTextEdit()
            self.browser.setReadOnly(True)
        layout.addWidget(self.browser)

    def set_html(self, html: str, base_url: Optional[QUrl] = None) -> None:
        if HAS_WEB_ENGINE:
            base_value = (base_url.toString() if isinstance(base_url, QUrl) else "") if base_url else ""
            if (
                html == self._last_html
                and self.interaction_mode == self._last_mode_loaded
                and base_value == self._last_base_url
            ):
                self._apply_zoom()
                return
            self._last_html = html
            self._last_base_url = base_value
            self._last_mode_loaded = self.interaction_mode
            self.browser.setHtml(html, base_url or QUrl())
            QTimer.singleShot(0, self._apply_zoom)
        else:
            self.browser.setPlainText(html)

    def set_interaction_mode(self, mode: str) -> None:
        self.interaction_mode = mode

    def set_desired_viewport_width(self, width: int) -> None:
        self.desired_viewport_width = max(int(width or 0), 0)
        self._apply_zoom()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        if not HAS_WEB_ENGINE:
            return
        if self.desired_viewport_width <= 0:
            if abs(self._last_zoom_factor - 1.0) > 0.001:
                self.browser.setZoomFactor(1.0)
                self._last_zoom_factor = 1.0
            return
        available = max(self.browser.width() - 24, 320)
        zoom = available / float(self.desired_viewport_width)
        zoom = max(0.2, min(2.0, zoom))
        if abs(self._last_zoom_factor - zoom) > 0.001:
            self.browser.setZoomFactor(zoom)
            self._last_zoom_factor = zoom

    def _inject_interaction(self, ok: bool) -> None:
        if not ok or not HAS_WEB_ENGINE:
            return
        self.page.runJavaScript(
            """
            (function() {
              if (window.__sfSmoothStylesBound) return;
              window.__sfSmoothStylesBound = true;
              var style = document.createElement('style');
              style.textContent = 'html, body { scroll-behavior: smooth !important; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }';
              (document.head || document.documentElement).appendChild(style);
            })();
            """
        )
        if self.interaction_mode == "builder":
            script = """
            (function() {
              if (window.__sfBuilderBound) return;
              window.__sfBuilderBound = true;
                            function selectorFor(el) {
                                if (el.id) return '#' + el.id;
                                if (el.classList && el.classList.length) {
                                    return el.tagName.toLowerCase() + '.' + Array.from(el.classList).join('.');
                                }
                                let index = 1;
                                let sibling = el;
                                while ((sibling = sibling.previousElementSibling) != null) {
                                    if (sibling.tagName === el.tagName) index += 1;
                                }
                                return el.tagName.toLowerCase() + ':nth-of-type(' + index + ')';
                            }
              document.addEventListener('click', function(ev) {
                const block = ev.target.closest('[data-block-id]');
                ev.preventDefault();
                ev.stopPropagation();
                                if (block) {
                                    console.log('__sf__builder:' + block.getAttribute('data-block-id'));
                                    return;
                                }
                                const el = ev.target;
                                if (!el) return;
                                const styles = window.getComputedStyle(el);
                                const payload = {
                                    selector: selectorFor(el),
                                    snippet: (el.outerHTML || '').slice(0, 500),
                                    text: (el.innerText || '').slice(0, 1000),
                                    backgroundImage: styles.backgroundImage || '',
                                    backgroundFull: styles.background || '',
                                    color: styles.color || '',
                                    background: styles.backgroundImage && styles.backgroundImage !== 'none' ? styles.backgroundImage : (styles.backgroundColor || ''),
                                    paddingFull: styles.padding || '',
                                    marginFull: styles.margin || '',
                                    radiusFull: styles.borderRadius || '',
                                    boxShadow: styles.boxShadow || '',
                                    display: styles.display || '',
                                    position: styles.position || '',
                                    padding: styles.paddingTop || '',
                                    margin: styles.marginTop || '',
                                    radius: styles.borderTopLeftRadius || '',
                                    width: Math.round(el.getBoundingClientRect().width || 0),
                                    height: Math.round(el.getBoundingClientRect().height || 0),
                                    fontSize: styles.fontSize || '',
                                    fontFamily: styles.fontFamily || '',
                                    fontWeight: styles.fontWeight || '',
                                    borderWidth: styles.borderTopWidth || '',
                                    borderStyle: styles.borderTopStyle || '',
                                    borderColor: styles.borderTopColor || ''
                                };
                                console.log('__sf__buildersource:' + JSON.stringify(payload));
              }, true);
            })();
            """
            self.page.runJavaScript(script)
            return
        if self.interaction_mode == "website":
            script = """
            (function() {
              if (window.__sfWebsiteBound) return;
              function selectorFor(el) {
                if (el.id) return '#' + el.id;
                if (el.classList && el.classList.length) {
                  return el.tagName.toLowerCase() + '.' + Array.from(el.classList).join('.');
                }
                let index = 1;
                let sibling = el;
                while ((sibling = sibling.previousElementSibling) != null) {
                  if (sibling.tagName === el.tagName) index += 1;
                }
                const tag = el.tagName.toLowerCase();
                return tag + ':nth-of-type(' + index + ')';
              }
              window.__sfWebsiteBound = true;
              document.addEventListener('click', function(ev) {
                const el = ev.target;
                if (!el) return;
                ev.preventDefault();
                ev.stopPropagation();
                const styles = window.getComputedStyle(el);
                const payload = {
                  selector: selectorFor(el),
                  snippet: (el.outerHTML || '').slice(0, 500),
                                    text: (el.innerText || '').slice(0, 1000),
                                    backgroundImage: styles.backgroundImage || '',
                                    backgroundFull: styles.background || '',
                  background: styles.backgroundColor || '',
                  color: styles.color || '',
                                    marginFull: styles.margin || '',
                                    paddingFull: styles.padding || '',
                                    radiusFull: styles.borderRadius || '',
                                    boxShadow: styles.boxShadow || '',
                                    display: styles.display || '',
                                    position: styles.position || '',
                  padding: styles.paddingTop || '',
                  margin: styles.marginTop || '',
                  radius: styles.borderTopLeftRadius || '',
                  width: Math.round(el.getBoundingClientRect().width || 0),
                  height: Math.round(el.getBoundingClientRect().height || 0),
                  fontSize: styles.fontSize || '',
                  fontFamily: styles.fontFamily || ''
                                    ,fontWeight: styles.fontWeight || ''
                                    ,borderWidth: styles.borderTopWidth || ''
                                    ,borderStyle: styles.borderTopStyle || ''
                                    ,borderColor: styles.borderTopColor || ''
                };
                if (window.__sfPrevSelected) {
                  window.__sfPrevSelected.style.outline = '';
                  window.__sfPrevSelected.style.outlineOffset = '';
                }
                el.style.outline = '3px solid #4ecbff';
                el.style.outlineOffset = '2px';
                window.__sfPrevSelected = el;
                console.log('__sf__website:' + JSON.stringify(payload));
              }, true);
            })();
            """
            self.page.runJavaScript(script)


if HAS_WEB_ENGINE:
    class _WebBridgePage(QWebEnginePage):
        bridgeMessage = Signal(str)

        _IGNORED_CONSOLE_PATTERNS = (
            "has been blocked by CORS policy",
            "No 'Access-Control-Allow-Origin' header is present",
            "Cannot read properties of null (reading 'offsetHeight')",
        )

        def javaScriptConsoleMessage(self, level, message, line_number, source_id):
            if message.startswith("__sf__"):
                self.bridgeMessage.emit(message[6:])
                return
            lowered = (message or "").strip()
            if any(pattern in lowered for pattern in self._IGNORED_CONSOLE_PATTERNS):
                return
            super().javaScriptConsoleMessage(level, message, line_number, source_id)


class HomeWorkspace(QWidget):
    newBlankRequested = Signal()
    newHomepageRequested = Signal()
    importHtmlRequested = Signal()
    openProjectRequested = Signal()
    loadUrlRequested = Signal(str)
    recentProjectRequested = Signal(str)
    goEditorRequested = Signal()
    goExportRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(24)

        # ── Hero ──────────────────────────────────────────────────────────
        hero = card_frame()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(40, 36, 40, 36)
        hero_layout.setSpacing(18)

        eyebrow = QLabel("Design Workflow")
        eyebrow.setObjectName("eyebrowLabel")
        title = QLabel("SiteForge")
        title.setObjectName("titleLabel")
        subtitle = QLabel(
            "Build pages in Editor · Inspect imported HTML or live URLs · Copy and export finished code from Export."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)

        hero_actions = QHBoxLayout()
        hero_actions.setSpacing(12)
        homepage_button = QPushButton("New Homepage")
        homepage_button.setProperty("variant", "primary")
        blank_button = QPushButton("Blank Project")
        import_button = QPushButton("Import HTML")
        open_button = QPushButton("Open Project")
        for btn in [homepage_button, blank_button, import_button, open_button]:
            btn.setMinimumHeight(44)
            btn.setMinimumWidth(148)
            hero_actions.addWidget(btn)
        hero_actions.addStretch(1)

        url_row = QHBoxLayout()
        url_row.setSpacing(10)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com  — import a live URL into the Editor")
        self.url_input.setMinimumHeight(38)
        url_button = QPushButton("Import URL")
        url_button.setMinimumHeight(38)
        url_button.setMinimumWidth(120)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(url_button)

        jump_row = QHBoxLayout()
        jump_row.setSpacing(10)
        editor_jump = QPushButton("Go to Editor →")
        export_jump = QPushButton("Go to Export →")
        editor_jump.setMinimumHeight(36)
        export_jump.setMinimumHeight(36)
        jump_row.addWidget(editor_jump)
        jump_row.addWidget(export_jump)
        jump_row.addStretch(1)

        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addSpacing(6)
        hero_layout.addLayout(hero_actions)
        hero_layout.addLayout(url_row)
        hero_layout.addLayout(jump_row)

        # ── Lower cards grid ────────────────────────────────────────────
        lower_splitter = QSplitter(Qt.Horizontal)
        lower_splitter.setChildrenCollapsible(False)
        lower_splitter.setHandleWidth(10)

        recent = card_frame()
        recent_layout = QVBoxLayout(recent)
        recent_layout.setContentsMargins(28, 26, 28, 26)
        recent_layout.setSpacing(14)
        recent_heading = QLabel("Recent Projects")
        recent_heading.setObjectName("sectionHeading")
        self.recent_container = QVBoxLayout()
        self.recent_container.setSpacing(10)
        recent_layout.addWidget(recent_heading)
        recent_layout.addLayout(self.recent_container)
        recent_layout.addStretch(1)

        info = card_frame()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(28, 26, 28, 26)
        info_layout.setSpacing(20)

        workflow_heading = QLabel("Workflow")
        workflow_heading.setObjectName("sectionHeading")
        workflow_body = QLabel(
            "Homepage · Start a new or existing project.\n"
            "Editor · Build with blocks, import HTML or a URL, inspect elements, and tweak styles.\n"
            "Export · Copy or save the final HTML and CSS output."
        )
        workflow_body.setObjectName("subtitleLabel")
        workflow_body.setWordWrap(True)

        tips_heading = QLabel("Tips")
        tips_heading.setObjectName("sectionHeading")
        tips_body = QLabel(
            "Switch to Source Preview in the Editor and click any element to auto-fill the Inspect panel.\n"
            "Drag blocks in the Page Blocks list to reorder them.\n"
            "Use the Code tab to copy builder output at any time."
        )
        tips_body.setObjectName("subtitleLabel")
        tips_body.setWordWrap(True)

        info_layout.addWidget(workflow_heading)
        info_layout.addWidget(workflow_body)
        info_layout.addSpacing(4)
        info_layout.addWidget(tips_heading)
        info_layout.addWidget(tips_body)
        credit = QLabel("made by Orvlyn")
        credit.setObjectName("subtitleLabel")
        credit.setAlignment(Qt.AlignRight)
        info_layout.addWidget(credit)
        info_layout.addStretch(1)

        lower_splitter.addWidget(recent)
        lower_splitter.addWidget(info)
        lower_splitter.setSizes([480, 800])

        root.addWidget(hero)
        root.addWidget(lower_splitter, 1)

        homepage_button.clicked.connect(self.newHomepageRequested)
        blank_button.clicked.connect(self.newBlankRequested)
        import_button.clicked.connect(self.importHtmlRequested)
        open_button.clicked.connect(self.openProjectRequested)
        editor_jump.clicked.connect(self.goEditorRequested)
        export_jump.clicked.connect(self.goExportRequested)
        url_button.clicked.connect(self._emit_url)
        self.url_input.returnPressed.connect(self._emit_url)

    def _emit_url(self) -> None:
        value = self.url_input.text().strip()
        if value:
            self.loadUrlRequested.emit(value)

    def _clear_recent(self) -> None:
        while self.recent_container.count():
            item = self.recent_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_recent_projects(self, paths: list[str]) -> None:
        self._clear_recent()
        if not paths:
            label = QLabel("No saved projects yet.")
            label.setObjectName("subtitleLabel")
            self.recent_container.addWidget(label)
            return
        for path in paths[:5]:
            button = QPushButton(path)
            button.clicked.connect(lambda checked=False, value=path: self.recentProjectRequested.emit(value))
            self.recent_container.addWidget(button)


class EditorWorkspace(QWidget):
    projectChanged = Signal()
    projectTitleChanged = Signal(str)
    projectLoaded = Signal(object)
    importFileRequested = Signal()
    loadUrlRequested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project = make_blank_project()
        self._updating = False
        self._base_url = QUrl()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._flush_pending_refresh)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._pending_refresh = False
        self._pending_list_refresh = False
        self.source_field_dirty: dict[str, bool] = {}
        self._visual_syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ── HEADER ──────────────────────────────────────────────────────────
        header = card_frame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(18)

        identity = QVBoxLayout()
        identity.setSpacing(3)
        eyebrow = QLabel("Editor")
        eyebrow.setObjectName("eyebrowLabel")
        self.project_title = QLineEdit()
        self.project_title.setPlaceholderText("Page title")
        self.project_title.setMinimumHeight(30)
        self.source_label = QLabel("Source: Builder")
        self.source_label.setObjectName("subtitleLabel")
        identity.addWidget(eyebrow)
        identity.addWidget(self.project_title)
        identity.addWidget(self.source_label)

        # Controls grid — 2 rows × 3 cols (matching screenshot)
        controls = QGridLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(8)

        self.page_theme = QComboBox()
        for key, value in PAGE_THEMES.items():
            self.page_theme.addItem(value["label"], key)
        self.preview_viewport_combo = QComboBox()
        self.preview_viewport_combo.addItem("Viewport: Auto", 0)
        self.preview_viewport_combo.addItem("Viewport: 1366", 1366)
        self.preview_viewport_combo.addItem("Viewport: 1600", 1600)
        self.preview_viewport_combo.addItem("Viewport: 1920", 1920)
        self.preview_mode_combo = QComboBox()
        self.preview_mode_combo.addItem("Builder", "builder")
        self.preview_mode_combo.addItem("Source Preview", "source")
        self.preview_mode_combo.addItem("Source (Full)", "source-full")

        self.live_preview_button = QPushButton("Live")
        self.live_preview_button.setCheckable(True)
        self.live_preview_button.setChecked(True)
        self.refresh_preview_button = QPushButton("Refresh")
        self.inspect_clicks_button = QPushButton("Inspect Click")
        self.inspect_clicks_button.setCheckable(True)
        self.inspect_clicks_button.setChecked(True)
        preview_wide_button = QPushButton("Preview Wide")
        preview_reset_button = QPushButton("Reset Layout")
        import_file_button = QPushButton("Import HTML")
        paste_code_button = QPushButton("Paste Code")
        import_code_button = QPushButton("Convert to Blocks")

        for widget in [
            self.preview_viewport_combo, self.inspect_clicks_button,
            self.refresh_preview_button, self.preview_mode_combo,
            preview_reset_button, import_file_button,
        ]:
            widget.setMinimumHeight(30)

        # Row 0: Viewport | Inspect Click | Refresh
        controls.addWidget(self.preview_viewport_combo, 0, 0)
        controls.addWidget(self.inspect_clicks_button, 0, 1)
        controls.addWidget(self.refresh_preview_button, 0, 2)
        # Row 1: Builder/Source | Reset Layout | Import HTML
        controls.addWidget(self.preview_mode_combo, 1, 0)
        controls.addWidget(preview_reset_button, 1, 1)
        controls.addWidget(import_file_button, 1, 2)

        header_layout.addLayout(identity, 1)
        header_layout.addLayout(controls, 2)
        root.addWidget(header)

        # ── MAIN 3-COLUMN SPLITTER ───────────────────────────────────────────
        self.editor_splitter = QSplitter(Qt.Horizontal)
        self.editor_splitter.setChildrenCollapsible(False)
        self.editor_splitter.setOpaqueResize(True)
        self.editor_splitter.setHandleWidth(2)
        self.editor_splitter.setStyleSheet(
            "QSplitter::handle { background: palette(mid); }"
            " QSplitter::handle:hover { background: palette(highlight); }"
        )

        # ── LEFT COLUMN: block library + page blocks ─────────────────────────
        left_column = card_frame()
        left_column.setMinimumWidth(180)
        left_column.setMaximumWidth(280)
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(10, 12, 10, 12)
        left_layout.setSpacing(8)

        library_heading = QLabel("Block Library")
        library_heading.setObjectName("sectionHeading")
        left_layout.addWidget(library_heading)

        library_grid = QGridLayout()
        library_grid.setHorizontalSpacing(6)
        library_grid.setVerticalSpacing(5)
        for _idx, block_type in enumerate(DEFAULT_BLOCKS.keys()):
            btn = QPushButton(DEFAULT_BLOCKS[block_type]["name"])
            btn.setMinimumHeight(28)
            btn.clicked.connect(lambda checked=False, value=block_type: self.add_block(value))
            library_grid.addWidget(btn, _idx, 0)
        left_layout.addLayout(library_grid)

        left_sep = QFrame()
        left_sep.setFrameShape(QFrame.HLine)
        left_sep.setFrameShadow(QFrame.Sunken)
        left_layout.addWidget(left_sep)

        blocks_heading = QLabel("Page Blocks")
        blocks_heading.setObjectName("sectionHeading")
        left_layout.addWidget(blocks_heading)

        self.block_list = BlockListWidget()
        self.block_list.currentRowChanged.connect(self._on_block_selected)
        self.block_list.orderChanged.connect(self._apply_block_order)
        left_layout.addWidget(self.block_list, 1)

        block_actions = QHBoxLayout()
        duplicate_button = QPushButton("Duplicate")
        delete_button = QPushButton("Delete")
        duplicate_button.clicked.connect(self.duplicate_selected_block)
        delete_button.clicked.connect(self.delete_selected_block)
        block_actions.addWidget(duplicate_button)
        block_actions.addWidget(delete_button)
        left_layout.addLayout(block_actions)

        # ── CENTER COLUMN ────────────────────────────────────────────────────
        center_panel = card_frame()
        center_panel.setMinimumWidth(500)
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # ── BLOCK EDITOR PANEL (used inside Block Editor tab) ───────────────
        block_editor_panel = QWidget()
        block_editor_panel_layout = QVBoxLayout(block_editor_panel)
        block_editor_panel_layout.setContentsMargins(14, 10, 14, 10)
        block_editor_panel_layout.setSpacing(8)

        self.block_name_label = QLabel("Select a block from the list to edit its properties")
        self.block_name_label.setObjectName("subtitleLabel")
        block_editor_panel_layout.addWidget(self.block_name_label)

        inspector_scroll = QScrollArea()
        inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setFrameShape(QFrame.NoFrame)
        inspector_inner = QWidget()
        inspector_layout = QVBoxLayout(inspector_inner)
        inspector_layout.setContentsMargins(0, 0, 4, 0)
        inspector_layout.setSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(12)

        self.title_edit = QLineEdit()
        self.body_edit = QTextEdit()
        self.body_edit.setMinimumHeight(90)
        self.body_edit.setAcceptRichText(False)
        body_buttons = QHBoxLayout()
        strong_button = QPushButton("Strong")
        em_button = QPushButton("Em")
        link_button = QPushButton("Link")
        break_button = QPushButton("BR")
        clear_markup_button = QPushButton("Strip Tags")
        for button in [strong_button, em_button, link_button, break_button, clear_markup_button]:
            button.setMinimumHeight(26)
            body_buttons.addWidget(button)
        body_buttons.addStretch(1)
        body_editor_widget = QWidget()
        body_editor_layout_inner = QVBoxLayout(body_editor_widget)
        body_editor_layout_inner.setContentsMargins(0, 0, 0, 0)
        body_editor_layout_inner.setSpacing(3)
        body_editor_layout_inner.addLayout(body_buttons)
        body_editor_layout_inner.addWidget(self.body_edit)

        self.button_text_edit = QLineEdit()
        self.button_url_edit = QLineEdit()
        self.background_edit = QLineEdit()
        self.color_edit = QLineEdit()
        self.accent_edit = QLineEdit()
        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(0, 320)
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 240)
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(0, 999)
        self.min_height_spin = QSpinBox()
        self.min_height_spin.setRange(0, 2400)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(-1, 2600)
        self.width_spin.setSpecialValueText("auto")
        self.height_spin = QSpinBox()
        self.height_spin.setRange(-1, 2600)
        self.height_spin.setSpecialValueText("auto")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(-1, 180)
        self.font_size_spin.setSpecialValueText("theme")
        self.font_family_edit = QLineEdit()
        self.font_family_edit.setPlaceholderText("Inter, system-ui, sans-serif")
        self.align_combo = QComboBox()
        self.align_combo.addItems(["left", "center", "right"])
        self.background_pick = QPushButton("Pick")
        self.background_gradient_pick = QPushButton("Gradient")
        self.color_pick = QPushButton("Pick")
        self.accent_pick = QPushButton("Pick")

        form.addRow("Title", self.title_edit)
        form.addRow("Body HTML", body_editor_widget)
        form.addRow("Button Text", self.button_text_edit)
        form.addRow("Link / Source", self.button_url_edit)
        form.addRow("Background", self._field_row(self.background_edit, self.background_pick, self.background_gradient_pick))
        form.addRow("Text Color", self._field_row(self.color_edit, self.color_pick))
        form.addRow("Accent", self._field_row(self.accent_edit, self.accent_pick))
        form.addRow("Padding", self.padding_spin)
        form.addRow("Margin", self.margin_spin)
        form.addRow("Radius", self.radius_spin)
        form.addRow("Min Height", self.min_height_spin)
        form.addRow("Width", self.width_spin)
        form.addRow("Height", self.height_spin)
        form.addRow("Font Size", self.font_size_spin)
        form.addRow("Font Family", self.font_family_edit)
        form.addRow("Alignment", self.align_combo)

        inspector_layout.addLayout(form)
        inspector_layout.addStretch(1)
        inspector_scroll.setWidget(inspector_inner)
        block_editor_panel_layout.addWidget(inspector_scroll, 1)

        # ── LOWER TABS ───────────────────────────────────────────────────────
        # Tab indices: 0=Block Editor, 1=Inspect, 2=Paste Code, 3=Visual Text, 4=Code
        self.lower_tabs = QTabWidget()
        self.lower_tabs.setDocumentMode(True)

        block_editor_tab = QWidget()
        block_editor_tab_layout = QVBoxLayout(block_editor_tab)
        block_editor_tab_layout.setContentsMargins(0, 0, 0, 0)
        block_editor_tab_layout.setSpacing(0)
        block_editor_splitter = QSplitter(Qt.Horizontal)
        block_editor_splitter.setChildrenCollapsible(False)
        block_editor_splitter.setOpaqueResize(True)
        block_editor_splitter.setHandleWidth(2)
        block_editor_splitter.setStyleSheet(
            "QSplitter::handle { background: palette(mid); }"
            " QSplitter::handle:hover { background: palette(highlight); }"
        )
        left_column.setParent(None)
        left_column.setMinimumWidth(220)
        left_column.setMaximumWidth(330)
        block_editor_splitter.addWidget(left_column)
        block_editor_splitter.addWidget(block_editor_panel)
        block_editor_splitter.setStretchFactor(0, 0)
        block_editor_splitter.setStretchFactor(1, 1)
        block_editor_splitter.setSizes([280, 900])
        block_editor_tab_layout.addWidget(block_editor_splitter, 1)

        # --- TAB 0: Inspect (source inspector - form top, elements bottom) ---
        inspect_tab = QWidget()
        inspect_layout = QVBoxLayout(inspect_tab)
        inspect_layout.setContentsMargins(0, 0, 0, 0)
        inspect_layout.setSpacing(0)

        # Vertical splitter: inspector form (top) | elements tree (bottom)
        inspect_splitter = QSplitter(Qt.Vertical)
        inspect_splitter.setChildrenCollapsible(False)
        inspect_splitter.setOpaqueResize(True)
        inspect_splitter.setHandleWidth(3)
        inspect_splitter.setStyleSheet(
            "QSplitter::handle { background: palette(mid); }"
            " QSplitter::handle:hover { background: palette(highlight); }"
        )
        self.source_workbench_splitter = inspect_splitter  # kept for compatibility

        # Top: source inspector form
        source_inspector_card = QWidget()
        source_inspector_layout = QVBoxLayout(source_inspector_card)
        source_inspector_layout.setContentsMargins(14, 12, 14, 10)
        source_inspector_layout.setSpacing(8)

        source_form = QFormLayout()
        source_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        source_form.setVerticalSpacing(8)
        source_form.setHorizontalSpacing(12)

        self.source_selector_edit = QLineEdit()
        self.source_selector_edit.setPlaceholderText("Auto-filled from click in source preview")
        self.source_text_edit = QPlainTextEdit()
        self.source_text_edit.setMinimumHeight(60)
        self.source_text_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.source_color_edit = QLineEdit()
        self.source_color_pick = QPushButton("Pick")
        self.source_bg_edit = QLineEdit()
        self.source_bg_pick = QPushButton("Pick")
        self.source_bg_gradient_pick = QPushButton("Gradient")
        self.source_padding_spin = QSpinBox()
        self.source_padding_spin.setRange(-1, 400)
        self.source_padding_spin.setSpecialValueText("unchanged")
        self.source_margin_spin = QSpinBox()
        self.source_margin_spin.setRange(-1, 400)
        self.source_margin_spin.setSpecialValueText("unchanged")
        self.source_radius_spin = QSpinBox()
        self.source_radius_spin.setRange(-1, 400)
        self.source_radius_spin.setSpecialValueText("unchanged")
        self.source_width_spin = QSpinBox()
        self.source_width_spin.setRange(-1, 2400)
        self.source_width_spin.setSpecialValueText("unchanged")
        self.source_height_spin = QSpinBox()
        self.source_height_spin.setRange(-1, 2400)
        self.source_height_spin.setSpecialValueText("unchanged")
        self.source_font_size_spin = QSpinBox()
        self.source_font_size_spin.setRange(-1, 180)
        self.source_font_size_spin.setSpecialValueText("unchanged")
        self.source_font_family_edit = QLineEdit()
        self.source_font_weight_edit = QLineEdit()
        self.source_font_weight_edit.setPlaceholderText("400, 600, bold...")
        self.source_border_width_spin = QSpinBox()
        self.source_border_width_spin.setRange(-1, 80)
        self.source_border_width_spin.setSpecialValueText("unchanged")
        self.source_border_style_combo = QComboBox()
        self.source_border_style_combo.addItems(["unchanged", "none", "solid", "dashed", "dotted", "double"])
        self.source_border_color_edit = QLineEdit()
        self.source_border_color_pick = QPushButton("Pick")
        self.source_box_shadow_edit = QLineEdit()
        self.source_box_shadow_edit.setPlaceholderText("0 20px 60px rgba(0,0,0,0.18) or none")
        self.source_box_shadow_preset_combo = QComboBox()
        self.source_box_shadow_preset_combo.addItem("unchanged", "")
        self.source_box_shadow_preset_combo.addItem("none", "none")
        self.source_box_shadow_preset_combo.addItem("soft", "0 8px 24px rgba(0, 0, 0, 0.16)")
        self.source_box_shadow_preset_combo.addItem("medium", "0 16px 40px rgba(0, 0, 0, 0.20)")
        self.source_box_shadow_preset_combo.addItem("glow", "0 0 0 1px rgba(0, 236, 184, 0.24), 0 12px 36px rgba(0, 236, 184, 0.18)")
        self.source_display_combo = QComboBox()
        self.source_display_combo.addItems(["unchanged", "block", "inline", "inline-block", "flex", "grid", "none"])
        self.source_position_combo = QComboBox()
        self.source_position_combo.addItems(["unchanged", "static", "relative", "absolute", "fixed", "sticky"])
        self.source_extra_css_edit = QPlainTextEdit()
        self.source_extra_css_edit.setMinimumHeight(70)
        self.source_extra_css_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.source_extra_css_edit.setPlaceholderText("box-shadow: 0 20px 60px rgba(0,0,0,0.18);")
        self.source_detected_css_view = QPlainTextEdit()
        self.source_detected_css_view.setReadOnly(True)
        self.source_detected_css_view.setMinimumHeight(80)
        self.source_detected_css_view.setLineWrapMode(QPlainTextEdit.WidgetWidth)

        source_form.addRow("Selector", self.source_selector_edit)
        source_form.addRow("Text", self.source_text_edit)
        source_form.addRow("Text Color", self._field_row(self.source_color_edit, self.source_color_pick))
        source_form.addRow("Background", self._field_row(self.source_bg_edit, self.source_bg_pick, self.source_bg_gradient_pick))
        source_form.addRow("Padding", self.source_padding_spin)
        source_form.addRow("Margin", self.source_margin_spin)
        source_form.addRow("Radius", self.source_radius_spin)
        source_form.addRow("Width", self.source_width_spin)
        source_form.addRow("Height", self.source_height_spin)
        source_form.addRow("Font Size", self.source_font_size_spin)
        source_form.addRow("Font Family", self.source_font_family_edit)
        source_form.addRow("Font Weight", self.source_font_weight_edit)
        source_form.addRow("Border Width", self.source_border_width_spin)
        source_form.addRow("Border Style", self.source_border_style_combo)
        source_form.addRow("Border Color", self._field_row(self.source_border_color_edit, self.source_border_color_pick))
        source_form.addRow("Box Shadow", self.source_box_shadow_edit)
        source_form.addRow("Shadow Preset", self.source_box_shadow_preset_combo)
        source_form.addRow("Display", self.source_display_combo)
        source_form.addRow("Position", self.source_position_combo)
        source_form.addRow("Extra CSS", self.source_extra_css_edit)
        source_form.addRow("Detected CSS", self.source_detected_css_view)

        source_actions = QHBoxLayout()
        source_apply_style = QPushButton("Apply Style")
        source_apply_text = QPushButton("Apply Text")
        source_reset = QPushButton("Reset Changes")
        source_actions.addWidget(source_apply_style)
        source_actions.addWidget(source_apply_text)
        source_actions.addWidget(source_reset)
        source_actions.addStretch(1)
        source_inspector_layout.addLayout(source_form)

        source_actions_bar = QWidget()
        source_actions_bar_layout = QHBoxLayout(source_actions_bar)
        source_actions_bar_layout.setContentsMargins(14, 8, 14, 8)
        source_actions_bar_layout.setSpacing(8)
        source_actions_bar_layout.addWidget(source_apply_style)
        source_actions_bar_layout.addWidget(source_apply_text)
        source_actions_bar_layout.addWidget(source_reset)
        source_actions_bar_layout.addStretch(1)

        source_inspector_scroll = QScrollArea()
        source_inspector_scroll.setWidgetResizable(True)
        source_inspector_scroll.setFrameShape(QFrame.NoFrame)
        source_inspector_scroll.setWidget(source_inspector_card)

        # Bottom: elements tree
        source_elements_card = QWidget()
        source_elements_layout = QVBoxLayout(source_elements_card)
        source_elements_layout.setContentsMargins(14, 10, 14, 10)
        source_elements_layout.setSpacing(8)

        source_elements_heading = QLabel("Elements")
        source_elements_heading.setObjectName("sectionHeading")
        source_elements_note = QLabel("Select an element from the tree, or click in Source Preview.")
        source_elements_note.setObjectName("subtitleLabel")
        source_elements_note.setWordWrap(True)
        self.source_filter_input = QLineEdit()
        self.source_filter_input.setPlaceholderText("Filter elements (tag, id, class, or text)...")
        self.source_target_tree = QTreeWidget()
        self.source_target_tree.setColumnCount(1)
        self.source_target_tree.setHeaderLabels(["Element"])
        self.source_target_tree.setHeaderHidden(True)
        self.source_target_tree.setRootIsDecorated(False)
        self.source_target_tree.setIndentation(10)
        self.source_target_tree.setAlternatingRowColors(False)
        self.source_target_tree.setUniformRowHeights(True)
        self.source_target_tree.setStyleSheet(
            "QTreeView::branch { background: transparent; border: none; }"
            " QTreeView::item { padding: 4px 6px; border: none; }"
        )
        self.source_target_tree.header().setStretchLastSection(True)
        self.source_target_snippet = QPlainTextEdit()
        self.source_target_snippet.setReadOnly(True)
        self.source_target_snippet.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.source_target_snippet.setPlaceholderText("Selected element HTML snippet...")
        self.source_target_snippet.setMinimumHeight(80)
        refresh_elements_button = QPushButton("Refresh Elements")
        copy_selected_html_button = QPushButton("Copy Selected HTML")
        elem_btn_row = QHBoxLayout()
        elem_btn_row.addWidget(refresh_elements_button)
        elem_btn_row.addWidget(copy_selected_html_button)
        source_elements_layout.addWidget(source_elements_heading)
        source_elements_layout.addWidget(source_elements_note)
        source_elements_layout.addWidget(self.source_filter_input)
        source_elements_layout.addLayout(elem_btn_row)
        source_elements_layout.addWidget(self.source_target_tree, 2)
        source_elements_layout.addWidget(self.source_target_snippet, 1)

        inspect_splitter.addWidget(source_inspector_scroll)
        inspect_splitter.addWidget(source_elements_card)
        inspect_splitter.setStretchFactor(0, 3)
        inspect_splitter.setStretchFactor(1, 2)
        inspect_splitter.setSizes([600, 400])

        inspect_layout.addWidget(source_actions_bar, 0)
        inspect_layout.addWidget(inspect_splitter, 1)

        # --- TAB 1: Paste Code ---
        source_tab = QWidget()
        source_layout = QVBoxLayout(source_tab)
        source_layout.setContentsMargins(14, 14, 14, 14)
        source_layout.setSpacing(10)
        source_note = QLabel("Paste HTML, import a file, or load from a URL.")
        source_note.setObjectName("subtitleLabel")
        source_note.setWordWrap(True)
        import_row = QGridLayout()
        import_row.setHorizontalSpacing(8)
        import_row.setVerticalSpacing(8)
        self.source_url_input = QLineEdit()
        self.source_url_input.setPlaceholderText("https://example.com")
        source_load_url = QPushButton("Import URL")
        source_file = QPushButton("Open HTML File")
        source_use_paste = QPushButton("Use as Source")
        source_convert = QPushButton("Convert Pasted HTML")
        for button in [source_load_url, source_file, source_use_paste, source_convert]:
            button.setMinimumHeight(34)
        import_row.addWidget(self.source_url_input, 0, 0, 1, 3)
        import_row.addWidget(source_load_url, 0, 3)
        import_row.addWidget(source_file, 1, 0)
        import_row.addWidget(source_use_paste, 1, 1)
        import_row.addWidget(source_convert, 1, 2)

        source_paste_card = card_frame()
        source_paste_layout = QVBoxLayout(source_paste_card)
        source_paste_layout.setContentsMargins(10, 10, 10, 10)
        source_paste_layout.setSpacing(8)
        source_paste_heading = QLabel("Paste HTML Here")
        source_paste_heading.setObjectName("sectionHeading")
        source_paste_hint = QLabel("Paste copied HTML below, then click Use as Source or Convert Pasted HTML.")
        source_paste_hint.setObjectName("subtitleLabel")
        source_paste_hint.setWordWrap(True)
        self.source_paste_edit = QPlainTextEdit()
        self.source_paste_edit.setPlaceholderText("Paste your HTML code here...")
        source_paste_layout.addWidget(source_paste_heading)
        source_paste_layout.addWidget(source_paste_hint)
        source_paste_layout.addWidget(self.source_paste_edit, 1)

        source_layout.addWidget(source_note)
        source_layout.addLayout(import_row)
        source_layout.addWidget(source_paste_card, 1)

        # --- TAB 3: Visual Text ---
        visual_tab = QWidget()
        visual_layout = QVBoxLayout(visual_tab)
        visual_layout.setContentsMargins(12, 12, 12, 12)
        visual_layout.setSpacing(8)
        visual_note = QLabel("Edit selected element content visually, then apply it back to the source HTML.")
        visual_note.setObjectName("subtitleLabel")
        visual_note.setWordWrap(True)
        visual_layout.addWidget(visual_note)

        visual_actions = QVBoxLayout()
        visual_actions.setSpacing(8)
        visual_actions_row1 = QHBoxLayout()
        visual_actions_row1.setSpacing(8)
        visual_actions_row2 = QHBoxLayout()
        visual_actions_row2.setSpacing(8)
        load_selected_visual_button = QPushButton("Load Element")
        apply_selected_visual_button = QPushButton("Apply Element")
        visual_sync_from_html_button = QPushButton("Sync HTML")
        visual_bold_button = QPushButton("Bold")
        visual_italic_button = QPushButton("Italic")
        visual_link_button = QPushButton("Link")
        visual_color_button = QPushButton("Text Color")
        visual_accent_button = QPushButton("Accent")
        self.visual_color_palette_combo = QComboBox()
        self.visual_color_palette_combo.addItem("Palette", "")
        self.visual_apply_palette_color_button = QPushButton("Apply Color")
        visual_clear_button = QPushButton("Clear")
        for button in [
            load_selected_visual_button,
            apply_selected_visual_button,
            visual_sync_from_html_button,
            visual_bold_button,
            visual_italic_button,
            visual_link_button,
            visual_color_button,
            visual_accent_button,
            self.visual_apply_palette_color_button,
            visual_clear_button,
        ]:
            button.setMinimumHeight(32)
            button.setMinimumWidth(128)
        self.visual_color_palette_combo.setMinimumHeight(32)
        self.visual_color_palette_combo.setMinimumWidth(220)

        visual_actions_row1.addWidget(load_selected_visual_button)
        visual_actions_row1.addWidget(apply_selected_visual_button)
        visual_actions_row1.addWidget(visual_sync_from_html_button)
        visual_actions_row1.addWidget(visual_bold_button)
        visual_actions_row1.addWidget(visual_italic_button)
        visual_actions_row1.addWidget(visual_link_button)
        visual_actions_row1.addWidget(visual_clear_button)
        visual_actions_row1.addStretch(1)

        visual_actions_row2.addWidget(visual_color_button)
        visual_actions_row2.addWidget(visual_accent_button)
        visual_actions_row2.addWidget(self.visual_color_palette_combo)
        visual_actions_row2.addWidget(self.visual_apply_palette_color_button)
        visual_actions_row2.addStretch(1)

        visual_actions.addLayout(visual_actions_row1)
        visual_actions.addLayout(visual_actions_row2)
        visual_layout.addLayout(visual_actions)

        self.visual_text_edit = QTextEdit()
        self.visual_text_edit.setAcceptRichText(True)
        self.visual_text_edit.setPlaceholderText("Visual text editor for selected element...")
        self.visual_text_edit.setMinimumHeight(240)

        visual_html_heading = QLabel("HTML Output")
        visual_html_heading.setObjectName("sectionHeading")
        self.visual_html_edit = QPlainTextEdit()
        self.visual_html_edit.setPlaceholderText("HTML generated from visual editor...")
        self.visual_html_edit.setMinimumHeight(200)

        visual_layout.addWidget(self.visual_text_edit, 2)
        visual_layout.addWidget(visual_html_heading)
        visual_layout.addWidget(self.visual_html_edit, 1)

        # --- TAB 4: Code ---
        code_tab = QWidget()
        code_layout = QVBoxLayout(code_tab)
        code_layout.setContentsMargins(8, 8, 8, 8)
        code_layout.setSpacing(8)
        self.code_splitter = QSplitter(Qt.Horizontal)
        self.code_splitter.setChildrenCollapsible(False)
        self.code_splitter.setOpaqueResize(True)
        self.code_splitter.setHandleWidth(2)
        self.code_splitter.setStyleSheet(
            "QSplitter::handle { background: palette(mid); }"
            " QSplitter::handle:hover { background: palette(highlight); }"
        )
        self.code_primary_tabs = QTabWidget()
        self.code_secondary_tabs = QTabWidget()
        self.html_view = QPlainTextEdit()
        self.html_view.setReadOnly(True)
        self.css_view = QPlainTextEdit()
        self.css_view.setReadOnly(True)
        self.custom_css_view = QPlainTextEdit()
        self.notes_view = QPlainTextEdit()
        self.code_primary_tabs.addTab(self.html_view, "Generated HTML")
        self.code_primary_tabs.addTab(self.css_view, "Generated CSS")
        self.source_html_view = QPlainTextEdit()
        self.source_html_view.setReadOnly(True)
        self.code_secondary_tabs.addTab(self.custom_css_view, "Inspector CSS")
        self.code_secondary_tabs.addTab(self.source_html_view, "Source HTML")
        self.code_secondary_tabs.addTab(self.notes_view, "Notes")
        self.code_splitter.addWidget(self.code_primary_tabs)
        self.code_splitter.addWidget(self.code_secondary_tabs)
        self.code_splitter.setStretchFactor(0, 1)
        self.code_splitter.setStretchFactor(1, 1)
        self.code_splitter.setSizes([780, 780])
        code_actions = QHBoxLayout()
        copy_left_code_button = QPushButton("Copy Left Tab")
        copy_right_code_button = QPushButton("Copy Right Tab")
        copy_all_code_button = QPushButton("Copy All")
        code_actions.addStretch(1)
        code_actions.addWidget(copy_left_code_button)
        code_actions.addWidget(copy_right_code_button)
        code_actions.addWidget(copy_all_code_button)
        code_layout.addWidget(self.code_splitter, 1)
        code_layout.addLayout(code_actions)

        # Tab indices: 0=Block Editor, 1=Inspect, 2=Paste Code, 3=Visual Text, 4=Code
        self.lower_tabs.addTab(block_editor_tab, "Block Editor")
        self.lower_tabs.addTab(inspect_tab, "Inspect")
        self.lower_tabs.addTab(source_tab, "Paste Code")
        self.lower_tabs.addTab(visual_tab, "Visual Text")
        self.lower_tabs.addTab(code_tab, "Code")
        center_layout.addWidget(self.lower_tabs, 1)

        # ── RIGHT COLUMN: live preview ───────────────────────────────────────
        preview_card = card_frame()
        preview_card.setMinimumWidth(480)
        self.preview_card = preview_card
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)
        preview_heading = QLabel("Live Preview")
        preview_heading.setObjectName("sectionHeading")
        self.preview = PreviewPane()
        self.preview.setMinimumWidth(420)
        self.preview.set_interaction_mode("builder")
        preview_layout.addWidget(preview_heading)
        preview_layout.addWidget(self.preview, 1)

        self.editor_splitter.addWidget(center_panel)
        self.editor_splitter.addWidget(preview_card)
        self.editor_splitter.setStretchFactor(0, 4)
        self.editor_splitter.setStretchFactor(1, 3)
        self.editor_splitter.setSizes([1260, 960])
        root.addWidget(self.editor_splitter, 1)

        # ── SIGNAL WIRING ────────────────────────────────────────────────────
        import_file_button.clicked.connect(self.importFileRequested)
        paste_code_button.clicked.connect(self.open_source_import)
        import_code_button.clicked.connect(self.import_pasted_html)

        self.project_title.editingFinished.connect(self._update_project_title)
        self.page_theme.currentIndexChanged.connect(self._update_page_theme)
        self.preview_mode_combo.currentIndexChanged.connect(self._schedule_preview_refresh)
        self.preview_viewport_combo.currentIndexChanged.connect(self._schedule_preview_refresh)
        self.inspect_clicks_button.toggled.connect(self._schedule_preview_refresh)
        self.live_preview_button.toggled.connect(self._live_preview_toggled)
        self.refresh_preview_button.clicked.connect(self._force_preview_refresh)
        preview_wide_button.clicked.connect(self._set_preview_wide_layout)
        preview_reset_button.clicked.connect(self._reset_editor_layout)
        self.title_edit.editingFinished.connect(self._sync_current_block)
        self.button_text_edit.editingFinished.connect(self._sync_current_block)
        self.button_url_edit.editingFinished.connect(self._sync_current_block)
        self.background_edit.editingFinished.connect(self._sync_current_block)
        self.color_edit.editingFinished.connect(self._sync_current_block)
        self.accent_edit.editingFinished.connect(self._sync_current_block)
        self.body_edit.textChanged.connect(self._sync_current_block)
        self.padding_spin.valueChanged.connect(self._sync_current_block)
        self.margin_spin.valueChanged.connect(self._sync_current_block)
        self.radius_spin.valueChanged.connect(self._sync_current_block)
        self.min_height_spin.valueChanged.connect(self._sync_current_block)
        self.width_spin.valueChanged.connect(self._sync_current_block)
        self.height_spin.valueChanged.connect(self._sync_current_block)
        self.font_size_spin.valueChanged.connect(self._sync_current_block)
        self.font_family_edit.editingFinished.connect(self._sync_current_block)
        self.align_combo.currentIndexChanged.connect(self._sync_current_block)
        self.background_pick.clicked.connect(lambda: self._pick_color(self.background_edit, self._sync_current_block))
        self.background_gradient_pick.clicked.connect(lambda: self._pick_gradient(self.background_edit, self._sync_current_block))
        self.color_pick.clicked.connect(lambda: self._pick_color(self.color_edit, self._sync_current_block))
        self.accent_pick.clicked.connect(lambda: self._pick_color(self.accent_edit, self._sync_current_block))
        strong_button.clicked.connect(lambda: self._wrap_body_selection("<strong>", "</strong>"))
        em_button.clicked.connect(lambda: self._wrap_body_selection("<em>", "</em>"))
        link_button.clicked.connect(self._insert_body_link)
        break_button.clicked.connect(lambda: self._insert_body_snippet("<br>"))
        clear_markup_button.clicked.connect(self._strip_body_markup)
        self.custom_css_view.textChanged.connect(self._update_project_text_fields)
        self.notes_view.textChanged.connect(self._update_project_text_fields)
        source_convert.clicked.connect(self.import_pasted_html)
        source_file.clicked.connect(self.importFileRequested)
        source_use_paste.clicked.connect(self.use_pasted_source)
        source_load_url.clicked.connect(self._emit_source_url)
        self.source_url_input.returnPressed.connect(self._emit_source_url)
        refresh_elements_button.clicked.connect(self._refresh_source_targets)
        copy_selected_html_button.clicked.connect(self.copy_selected_element_html)
        source_apply_style.clicked.connect(self.apply_source_style)
        source_apply_text.clicked.connect(self.apply_source_text)
        source_reset.clicked.connect(self._reset_source_field_changes)
        self.source_bg_pick.clicked.connect(lambda: self._pick_color(self.source_bg_edit))
        self.source_bg_gradient_pick.clicked.connect(lambda: self._pick_gradient(self.source_bg_edit))
        self.source_color_pick.clicked.connect(lambda: self._pick_color(self.source_color_edit))
        self.source_border_color_pick.clicked.connect(lambda: self._pick_color(self.source_border_color_edit))
        load_selected_visual_button.clicked.connect(self._load_visual_from_selected_element)
        apply_selected_visual_button.clicked.connect(self._apply_visual_to_selected_element)
        visual_sync_from_html_button.clicked.connect(self._visual_load_html_changes)
        visual_bold_button.clicked.connect(lambda: self._visual_wrap_selection("<strong>", "</strong>"))
        visual_italic_button.clicked.connect(lambda: self._visual_wrap_selection("<em>", "</em>"))
        visual_link_button.clicked.connect(self._visual_insert_link)
        visual_color_button.clicked.connect(self._visual_pick_text_color)
        visual_accent_button.clicked.connect(self._visual_apply_accent)
        self.visual_apply_palette_color_button.clicked.connect(self._visual_apply_palette_color)
        visual_clear_button.clicked.connect(self._visual_clear_formatting)
        self.visual_text_edit.textChanged.connect(self._sync_visual_html_from_editor)
        copy_left_code_button.clicked.connect(lambda: self.copy_current_code("left"))
        copy_right_code_button.clicked.connect(lambda: self.copy_current_code("right"))
        copy_all_code_button.clicked.connect(lambda: self.copy_current_code("all"))
        self.preview.jsMessageReceived.connect(self._handle_preview_message)
        self.source_target_tree.currentItemChanged.connect(self._populate_source_target)
        self.source_filter_input.textChanged.connect(self._filter_source_targets)
        self.lower_tabs.currentChanged.connect(self._on_lower_tab_changed)
        self._wire_source_dirty_tracking()

        self.set_project(make_blank_project())
        self.lower_tabs.setCurrentIndex(1)  # Inspect tab by default

    def _field_row(self, line_edit: QLineEdit, button: QPushButton, extra_button: Optional[QPushButton] = None) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        if extra_button is not None:
            layout.addWidget(extra_button)
        return widget

    def set_base_url(self, value: str) -> None:
        self._base_url = QUrl.fromUserInput(value) if value else QUrl()

    def set_source_url_value(self, value: str) -> None:
        self.source_url_input.setText(value or "")

    def open_source_import(self) -> None:
        self.lower_tabs.setCurrentIndex(2)  # Paste Code tab
        mode = "source-full" if self._looks_like_elementor(self.project.raw_html) or self.project.source_mode == "live-url" else "source"
        self.preview_mode_combo.setCurrentIndex(max(self.preview_mode_combo.findData(mode), 0))
        self.preview_viewport_combo.setCurrentIndex(max(self.preview_viewport_combo.findData(1366), 0))
        self._set_preview_wide_layout()
        self.source_paste_edit.setFocus()

    def _looks_like_elementor(self, html: str) -> bool:
        lowered = (html or "").lower()
        return "elementor" in lowered or "data-element_type" in lowered or "data-widget_type" in lowered

    def _refresh_source_targets(self) -> None:
        current_selector = self.source_selector_edit.text().strip()
        self.source_target_tree.blockSignals(True)
        self.source_target_tree.clear()
        html = self.project.raw_html.strip()
        if html:
            try:
                soup = BeautifulSoup(html, "html.parser")
                root = soup.body or soup
                self._populate_tree_recursive(root, None, depth=0, max_depth=7, remaining=[600])
            except Exception:
                pass
        self.source_target_tree.blockSignals(False)
        if self.source_target_tree.topLevelItemCount() == 0:
            self.source_target_snippet.clear()
            return
        self.source_target_tree.expandToDepth(1)
        target_item = None
        if current_selector:
            target_item = self._find_tree_item_by_selector(current_selector)
        if target_item is None:
            target_item = self.source_target_tree.topLevelItem(0)
        if target_item is not None:
            self.source_target_tree.setCurrentItem(target_item)
        self._filter_source_targets(self.source_filter_input.text())

    def _selector_for_tag(self, element: Tag) -> str:
        if element.get("id"):
            return f"#{element.get('id')}"
        classes = [value for value in element.get("class", []) if value]
        if classes:
            return f"{element.name}." + ".".join(classes[:2])
        parent = element.parent if isinstance(element.parent, Tag) else None
        if not parent:
            return element.name or "div"
        siblings = [node for node in parent.find_all(element.name, recursive=False)]
        if len(siblings) <= 1:
            return element.name or "div"
        return f"{element.name}:nth-of-type({siblings.index(element) + 1})"

    def _populate_tree_recursive(
        self,
        parent_tag: Tag,
        parent_item: Optional[QTreeWidgetItem],
        *,
        depth: int,
        max_depth: int,
        remaining: list[int],
    ) -> None:
        if depth > max_depth or remaining[0] <= 0:
            return
        for child in parent_tag.find_all(True, recursive=False):
            if not isinstance(child, Tag):
                continue
            if child.name in {"script", "style", "noscript", "meta", "link"}:
                continue
            selector = self._selector_for_tag(child)
            text = " ".join(child.get_text(" ", strip=True).split())
            if len(text) > 70:
                text = text[:67].rstrip() + "..."
            classes = ".".join(child.get("class", [])[:2])
            display = child.name
            if child.get("id"):
                display += f"#{child.get('id')}"
            elif classes:
                display += f".{classes}"
            text_preview = text or "(no text)"
            if len(text_preview) > 90:
                text_preview = text_preview[:87].rstrip() + "..."
            item = QTreeWidgetItem([display])
            item.setData(0, Qt.UserRole, selector)
            item.setData(0, Qt.UserRole + 1, str(child)[:700])
            item.setData(0, Qt.UserRole + 2, text_preview)
            item.setToolTip(0, f"{display}\n{selector}\n{text_preview}")
            self.source_target_tree.addTopLevelItem(item)
            remaining[0] -= 1
            if remaining[0] <= 0:
                return
            self._populate_tree_recursive(child, None, depth=depth + 1, max_depth=max_depth, remaining=remaining)

    def _find_tree_item_by_selector(self, selector: str) -> Optional[QTreeWidgetItem]:
        if not selector:
            return None
        stack = [self.source_target_tree.topLevelItem(i) for i in range(self.source_target_tree.topLevelItemCount())]
        while stack:
            item = stack.pop()
            if not item:
                continue
            if item.data(0, Qt.UserRole) == selector:
                return item
            for i in range(item.childCount()):
                stack.append(item.child(i))
        return None

    def _filter_source_targets(self, value: str) -> None:
        needle = (value or "").strip().lower()
        for i in range(self.source_target_tree.topLevelItemCount()):
            self._filter_tree_item(self.source_target_tree.topLevelItem(i), needle)

    def _filter_tree_item(self, item: Optional[QTreeWidgetItem], needle: str) -> bool:
        if item is None:
            return False
        selector = (item.data(0, Qt.UserRole) or "").lower()
        label = (item.text(0) or "").lower()
        snippet = (item.data(0, Qt.UserRole + 1) or "").lower()
        own_match = not needle or needle in selector or needle in label or needle in snippet
        child_match = False
        for i in range(item.childCount()):
            child_match = self._filter_tree_item(item.child(i), needle) or child_match
        visible = own_match or child_match
        item.setHidden(not visible)
        return visible

    def _clean_css_value(self, value: str) -> str:
        text = (value or "").strip()
        return text if text else "(none)"

    def _normalize_html_fragment(self, html: str) -> str:
        parsed = BeautifulSoup(html or "", "html.parser")
        if parsed.body is not None:
            fragment = "".join(str(child) for child in parsed.body.contents)
        else:
            fragment = html or ""

        # Strip Qt-specific rich-text styles that can shrink or distort site typography.
        soup = BeautifulSoup(fragment, "html.parser")
        allowed_style_keys = {"color", "font-weight", "font-style", "text-decoration", "background-color"}
        for tag in soup.find_all(True):
            style = tag.get("style")
            if not style:
                continue
            declarations = []
            for part in style.split(";"):
                if ":" not in part:
                    continue
                key, value = [piece.strip() for piece in part.split(":", 1)]
                if key.lower() in allowed_style_keys and value:
                    declarations.append(f"{key}: {value}")
            if declarations:
                tag["style"] = "; ".join(declarations)
            else:
                del tag["style"]

        fragment = "".join(str(child) for child in (soup.body.contents if soup.body is not None else soup.contents))

        # For headings, avoid wrapping content in block-level containers from rich editor.
        heading_wrapped = BeautifulSoup(f"<root>{fragment}</root>", "html.parser")
        root = heading_wrapped.find("root")
        if root is not None and len(root.contents) == 1 and getattr(root.contents[0], "name", None) in {"p", "div"}:
            inner = root.contents[0]
            return "".join(str(child) for child in inner.contents)

        return fragment

    def _extract_color_tokens(self, text: str) -> list[str]:
        if not text:
            return []
        pattern = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b|rgba?\([^\)]+\)|hsla?\([^\)]+\)")
        seen: list[str] = []
        for match in pattern.findall(text):
            value = match.strip()
            if value and value not in seen:
                seen.append(value)
        return seen

    def _refresh_visual_color_palette(self, fragment: str) -> None:
        colors = self._extract_color_tokens(fragment)
        defaults = ["#f5f7fa", "#a9b5c4", "#00ecb8", "#ffffff", "#0f1319"]
        for color in defaults:
            if color not in colors:
                colors.insert(0, color)
        self.visual_color_palette_combo.blockSignals(True)
        self.visual_color_palette_combo.clear()
        self.visual_color_palette_combo.addItem("Palette", "")
        for color in colors[:16]:
            self.visual_color_palette_combo.addItem(color, color)
        self.visual_color_palette_combo.blockSignals(False)

    def _sync_visual_html_from_editor(self) -> None:
        if self._visual_syncing:
            return
        self._visual_syncing = True
        html = self._normalize_html_fragment(self.visual_text_edit.toHtml())
        self.visual_html_edit.setPlainText(html)
        self._refresh_visual_color_palette(html)
        self._visual_syncing = False

    def _sync_visual_editor_from_html(self) -> None:
        if self._visual_syncing:
            return
        self._visual_syncing = True
        self.visual_text_edit.setHtml(self.visual_html_edit.toPlainText())
        self._visual_syncing = False

    def _visual_load_html_changes(self) -> None:
        if self._visual_syncing:
            return
        self._visual_syncing = True
        self.visual_text_edit.setHtml(self.visual_html_edit.toPlainText())
        self._refresh_visual_color_palette(self.visual_html_edit.toPlainText())
        self._visual_syncing = False

    def _visual_selected_cursor(self) -> tuple[str, Optional[QTextCursor]]:
        rich_cursor = self.visual_text_edit.textCursor()
        if rich_cursor.hasSelection():
            return "rich", rich_cursor
        html_cursor = self.visual_html_edit.textCursor()
        if html_cursor.hasSelection():
            return "html", html_cursor
        if self.visual_text_edit.hasFocus():
            return "rich", self.visual_text_edit.textCursor()
        return "html", self.visual_html_edit.textCursor()

    def _visual_wrap_selection(self, open_tag: str, close_tag: str) -> None:
        target, cursor = self._visual_selected_cursor()
        if target == "rich":
            if cursor is None or not cursor.hasSelection():
                QMessageBox.information(self, "SiteForge", "Highlight text in Visual Text editor first.")
                return
            if open_tag == "<strong>":
                self._visual_apply_char_format(font_weight=QFont.Bold)
                return
            if open_tag == "<em>":
                self._visual_apply_char_format(italic=True)
                return
        if cursor is None or not cursor.hasSelection():
            QMessageBox.information(self, "SiteForge", "Highlight text in Visual Text editor or HTML Output first.")
            return
        selected = cursor.selectedText().replace("\u2029", "\n")
        cursor.insertText(f"{open_tag}{selected}{close_tag}")
        self._visual_load_html_changes()

    def _visual_apply_char_format(
        self,
        *,
        color: Optional[QColor] = None,
        font_weight: Optional[int] = None,
        italic: Optional[bool] = None,
    ) -> None:
        editor = self.visual_text_edit
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            return
        fmt = QTextCharFormat()
        if color is not None:
            fmt.setForeground(color)
        if font_weight is not None:
            fmt.setFontWeight(font_weight)
        if italic is not None:
            fmt.setFontItalic(italic)
        cursor.mergeCharFormat(fmt)
        editor.mergeCurrentCharFormat(fmt)
        self._sync_visual_html_from_editor()

    def _visual_insert_link(self) -> None:
        target, cursor = self._visual_selected_cursor()
        if cursor is None or not cursor.hasSelection():
            QMessageBox.information(self, "SiteForge", "Highlight text before inserting a link.")
            return
        selected = cursor.selectedText().replace("\u2029", " ").strip() or "Link"
        if target == "rich":
            cursor.insertHtml(f"<a href='https://example.com'>{selected}</a>")
            self.visual_text_edit.setTextCursor(cursor)
            self._sync_visual_html_from_editor()
            return
        cursor.insertText(f"<a href='https://example.com'>{selected}</a>")
        self._visual_load_html_changes()

    def _visual_wrap_with_style(self, style: str) -> None:
        target, cursor = self._visual_selected_cursor()
        if target == "rich":
            if cursor is None or not cursor.hasSelection():
                QMessageBox.information(self, "SiteForge", "Highlight text in Visual Text editor first.")
                return
            parts = [segment.strip() for segment in style.split(";") if segment.strip()]
            color_value = None
            weight_value = None
            italic_value = None
            for part in parts:
                if ":" not in part:
                    continue
                key, value = [s.strip().lower() for s in part.split(":", 1)]
                if key == "color":
                    color_value = QColor(value)
                elif key == "font-weight" and value in {"700", "bold"}:
                    weight_value = QFont.Bold
                elif key == "font-style" and value in {"italic", "oblique"}:
                    italic_value = True
            self._visual_apply_char_format(color=color_value, font_weight=weight_value, italic=italic_value)
            return
        if cursor is None or not cursor.hasSelection():
            QMessageBox.information(self, "SiteForge", "Highlight text in Visual Text editor or HTML Output first.")
            return
        selected = cursor.selectedText().replace("\u2029", " ").strip()
        cursor.insertText(f"<span style=\"{style}\">{selected}</span>")
        self._visual_load_html_changes()

    def _visual_pick_text_color(self) -> None:
        color = QColorDialog.getColor(QColor("#ffffff"), self, "Pick Text Color")
        if not color.isValid():
            return
        self._visual_wrap_with_style(f"color:{color.name()};")

    def _visual_apply_palette_color(self) -> None:
        value = (self.visual_color_palette_combo.currentData() or "").strip()
        if not value:
            QMessageBox.information(self, "SiteForge", "Choose a color from Palette first.")
            return
        self._visual_wrap_with_style(f"color:{value};")

    def _visual_apply_accent(self) -> None:
        self._visual_wrap_with_style("color:#00ecb8;font-weight:700;")

    def _visual_clear_formatting(self) -> None:
        target, cursor = self._visual_selected_cursor()
        if target == "rich":
            if cursor is None or not cursor.hasSelection():
                QMessageBox.information(self, "SiteForge", "Highlight text in Visual Text editor first.")
                return
            plain = cursor.selectedText().replace("\u2029", "\n")
            cursor.insertText(plain)
            self.visual_text_edit.setTextCursor(cursor)
            self._sync_visual_html_from_editor()
            return
        if cursor is None or not cursor.hasSelection():
            stripped = re.sub(r"<[^>]+>", "", self.visual_html_edit.toPlainText())
            self.visual_html_edit.setPlainText(stripped)
            return
        selected = cursor.selectedText().replace("\u2029", "\n")
        selected = re.sub(r"<[^>]+>", "", selected)
        cursor.insertText(selected)
        self._visual_load_html_changes()

    def _load_visual_from_selected_element(self) -> None:
        selector = self.source_selector_edit.text().strip()
        html = self.project.raw_html or ""
        if not selector or not html:
            QMessageBox.information(self, "SiteForge", "Select an element in Inspect first.")
            return
        try:
            soup = BeautifulSoup(html, "html.parser")
            node = soup.select_one(selector)
        except Exception:
            node = None
        if node is None:
            QMessageBox.information(self, "SiteForge", "Could not find the selected element in source HTML.")
            return
        fragment = node.decode_contents()
        self._refresh_visual_color_palette(fragment)
        self._visual_syncing = True
        self.visual_html_edit.setPlainText(fragment)
        self.visual_text_edit.setHtml(fragment)
        self._visual_syncing = False
        self.lower_tabs.setCurrentIndex(3)  # Visual Text tab

    def _apply_visual_to_selected_element(self) -> None:
        selector = self.source_selector_edit.text().strip()
        html = self.project.raw_html or ""
        if not selector or not html:
            QMessageBox.information(self, "SiteForge", "Select an element in Inspect first.")
            return
        fragment = self.visual_html_edit.toPlainText().strip()
        if not fragment:
            QMessageBox.information(self, "SiteForge", "Visual Text editor is empty.")
            return
        try:
            soup = BeautifulSoup(html, "html.parser")
            node = soup.select_one(selector)
        except Exception:
            node = None
        if node is None:
            QMessageBox.information(self, "SiteForge", "Could not find the selected element in source HTML.")
            return
        tag_name = (node.name or "").lower()
        normalized_fragment = self._normalize_html_fragment(fragment)
        if tag_name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            plain = BeautifulSoup(normalized_fragment, "html.parser").get_text(" ", strip=True)
            node.clear()
            node.append(plain)
        else:
            node.clear()
            fragment_soup = BeautifulSoup(normalized_fragment, "html.parser")
            container = fragment_soup.body if fragment_soup.body is not None else fragment_soup
            for child in list(container.contents):
                node.append(child)
        self.project.raw_html = str(soup)
        self.source_paste_edit.setPlainText(self.project.raw_html)
        self._refresh_source_targets()
        self._refresh_preview()
        self._refresh_code()
        self.projectChanged.emit()

    def _populate_source_target(self, item: Optional[QTreeWidgetItem], _previous: Optional[QTreeWidgetItem] = None) -> None:
        if not item:
            return
        self.source_target_snippet.setPlainText(item.data(0, Qt.UserRole + 1) or "")
        self.source_selector_edit.setText(item.data(0, Qt.UserRole) or "")

    def _upsert_source_target_item(self, selector: str, snippet: str) -> None:
        if not selector:
            return
        item = self._find_tree_item_by_selector(selector)
        if item is None:
            item = QTreeWidgetItem([selector, "(preview click)"])
            item.setData(0, Qt.UserRole, selector)
            item.setData(0, Qt.UserRole + 1, snippet)
            self.source_target_tree.insertTopLevelItem(0, item)
        else:
            item.setData(0, Qt.UserRole + 1, snippet)
        self.source_target_tree.setCurrentItem(item)
        self.source_target_snippet.setPlainText(snippet)

    def set_project(self, project: ProjectDocument) -> None:
        self.project = project
        self.project.ensure_defaults()
        if self.project.raw_css.strip() and not self.project.custom_css.strip():
            self.project.custom_css = self.project.raw_css
        self._updating = True
        self.project_title.setText(self.project.title)
        theme_index = self.page_theme.findData(self.project.page_theme)
        self.page_theme.setCurrentIndex(max(theme_index, 0))
        self.custom_css_view.setPlainText(self.project.custom_css)
        self.notes_view.setPlainText(self.project.notes)
        self.source_paste_edit.setPlainText(self.project.raw_html)
        self.source_url_input.setText(self.project.source_url)
        if self.project.raw_html and self.project.source_mode != "builder":
            mode = "source-full" if self._looks_like_elementor(self.project.raw_html) or self.project.source_mode == "live-url" else "source"
            self.preview_mode_combo.setCurrentIndex(max(self.preview_mode_combo.findData(mode), 0))
        else:
            self.preview_mode_combo.setCurrentIndex(max(self.preview_mode_combo.findData("builder"), 0))
        self.source_label.setText(f"Source: {self.project.source_url or self.project.source_path or 'Builder'}")
        self._updating = False
        self._reset_source_field_changes()
        self.refresh_everything(select_first=True)

    def _emit_source_url(self) -> None:
        value = self.source_url_input.text().strip()
        if value:
            self.loadUrlRequested.emit(value)

    def _set_preview_wide_layout(self) -> None:
        self.editor_splitter.setSizes([920, 1280])

    def _reset_editor_layout(self) -> None:
        self.editor_splitter.setSizes([1080, 1160])

    def _apply_workspace_layout(self, index: int) -> None:
        # Tab 0 = Block Editor, 1 = Inspect, 2 = Paste Code, 3 = Visual Text, 4 = Code
        if index == 0:  # Block Editor
            self.editor_splitter.setSizes([1160, 1080])
            return
        if index == 1:  # Inspect
            self.editor_splitter.setSizes([1080, 1160])
            return
        if index == 2:  # Paste Code
            self.editor_splitter.setSizes([1040, 1200])
            return
        if index == 3:  # Visual Text
            self.editor_splitter.setSizes([1100, 1140])
            return
        if index == 4:  # Code
            self.editor_splitter.setSizes([1020, 1220])
            return

    def _live_preview_toggled(self, checked: bool) -> None:
        self.refresh_preview_button.setEnabled(not checked)
        if checked:
            self._refresh_preview()

    def _force_preview_refresh(self) -> None:
        self._refresh_preview()
        if self.lower_tabs.currentIndex() == 4:  # Code tab
            self._refresh_code()

    def _schedule_refresh(self, *, list_refresh: bool = False) -> None:
        if list_refresh:
            self._pending_list_refresh = True
        self._pending_refresh = True
        self._refresh_timer.start(300)

    def _flush_pending_refresh(self) -> None:
        if not self._pending_refresh:
            return
        self._pending_refresh = False
        refresh_list = self._pending_list_refresh
        if self._pending_list_refresh:
            self._refresh_block_list()
            self._pending_list_refresh = False
        if self.live_preview_button.isChecked():
            self._schedule_preview_refresh()
        if refresh_list or self.lower_tabs.currentIndex() == 4:  # Code tab
            self._refresh_code()
        self.projectChanged.emit()

    def _on_lower_tab_changed(self, index: int) -> None:
        self._apply_workspace_layout(index)
        if index == 4:  # Code tab
            self._refresh_code()

    def _wrap_body_selection(self, open_tag: str, close_tag: str) -> None:
        cursor = self.body_edit.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        if selected:
            cursor.insertText(f"{open_tag}{selected}{close_tag}")
        else:
            cursor.insertText(f"{open_tag}{close_tag}")
            cursor.movePosition(cursor.Left, cursor.MoveAnchor, len(close_tag))
            self.body_edit.setTextCursor(cursor)
        self._sync_current_block()

    def _insert_body_snippet(self, snippet: str) -> None:
        cursor = self.body_edit.textCursor()
        cursor.insertText(snippet)
        self._sync_current_block()

    def _insert_body_link(self) -> None:
        cursor = self.body_edit.textCursor()
        selected = cursor.selectedText().replace("\u2029", " ").strip() or "Link"
        cursor.insertText(f"<a href='https://example.com'>{selected}</a>")
        self._sync_current_block()

    def _strip_body_markup(self) -> None:
        cleaned = re.sub(r"<[^>]+>", "", self.body_edit.toPlainText())
        self.body_edit.setPlainText(cleaned)
        self._sync_current_block()

    def _wire_source_dirty_tracking(self) -> None:
        self.source_field_dirty = {
            "background": False,
            "color": False,
            "padding": False,
            "margin": False,
            "radius": False,
            "width": False,
            "height": False,
            "font_size": False,
            "font_family": False,
            "font_weight": False,
            "border_width": False,
            "border_style": False,
            "border_color": False,
            "box_shadow": False,
            "display": False,
            "position": False,
            "extra_css": False,
            "text": False,
        }
        self.source_bg_edit.textChanged.connect(lambda: self._mark_source_dirty("background"))
        self.source_color_edit.textChanged.connect(lambda: self._mark_source_dirty("color"))
        self.source_padding_spin.valueChanged.connect(lambda: self._mark_source_dirty("padding"))
        self.source_margin_spin.valueChanged.connect(lambda: self._mark_source_dirty("margin"))
        self.source_radius_spin.valueChanged.connect(lambda: self._mark_source_dirty("radius"))
        self.source_width_spin.valueChanged.connect(lambda: self._mark_source_dirty("width"))
        self.source_height_spin.valueChanged.connect(lambda: self._mark_source_dirty("height"))
        self.source_font_size_spin.valueChanged.connect(lambda: self._mark_source_dirty("font_size"))
        self.source_font_family_edit.textChanged.connect(lambda: self._mark_source_dirty("font_family"))
        self.source_font_weight_edit.textChanged.connect(lambda: self._mark_source_dirty("font_weight"))
        self.source_border_width_spin.valueChanged.connect(lambda: self._mark_source_dirty("border_width"))
        self.source_border_style_combo.currentIndexChanged.connect(lambda: self._mark_source_dirty("border_style"))
        self.source_border_color_edit.textChanged.connect(lambda: self._mark_source_dirty("border_color"))
        self.source_box_shadow_edit.textChanged.connect(lambda: self._mark_source_dirty("box_shadow"))
        self.source_box_shadow_preset_combo.currentIndexChanged.connect(self._on_box_shadow_preset_changed)
        self.source_display_combo.currentIndexChanged.connect(lambda: self._mark_source_dirty("display"))
        self.source_position_combo.currentIndexChanged.connect(lambda: self._mark_source_dirty("position"))
        self.source_extra_css_edit.textChanged.connect(lambda: self._mark_source_dirty("extra_css"))
        self.source_text_edit.textChanged.connect(lambda: self._mark_source_dirty("text"))

    def _mark_source_dirty(self, key: str) -> None:
        if self._updating:
            return
        self.source_field_dirty[key] = True

    def _reset_source_field_changes(self) -> None:
        for key in self.source_field_dirty.keys():
            self.source_field_dirty[key] = False

    def _on_box_shadow_preset_changed(self) -> None:
        if self._updating:
            return
        value = (self.source_box_shadow_preset_combo.currentData() or "").strip()
        if not value and self.source_box_shadow_preset_combo.currentText() == "unchanged":
            return
        self.source_box_shadow_edit.setText(value or "none")
        self._mark_source_dirty("box_shadow")

    def current_block(self) -> Optional[Block]:
        row = self.block_list.currentRow()
        if row < 0 or row >= len(self.project.blocks):
            return None
        return self.project.blocks[row]

    def refresh_everything(self, select_first: bool = False) -> None:
        self._refresh_block_list(select_first=select_first)
        self._refresh_preview()
        self._refresh_code()
        self._refresh_source_targets()
        self._populate_inspector()

    def _refresh_block_list(self, select_first: bool = False) -> None:
        current_id = self.current_block().id if self.current_block() else None
        self.block_list.blockSignals(True)
        self.block_list.clear()
        for index, block in enumerate(self.project.blocks, start=1):
            item = QListWidgetItem(f"{index}. {block.name} - {block.title or block.type.title()}")
            item.setData(Qt.UserRole, block.id)
            self.block_list.addItem(item)
        self.block_list.blockSignals(False)

        if not self.project.blocks:
            return
        if select_first:
            self.block_list.setCurrentRow(0)
            return
        if current_id:
            for row in range(self.block_list.count()):
                if self.block_list.item(row).data(Qt.UserRole) == current_id:
                    self.block_list.setCurrentRow(row)
                    return
        self.block_list.setCurrentRow(0)

    def _schedule_preview_refresh(self, *_args) -> None:
        self._preview_timer.start(420)

    def _refresh_preview(self, _index: int = -1) -> None:
        mode = self.preview_mode_combo.currentData()
        if mode in {"source", "source-full"} and self.project.raw_html.strip():
            source_html = sanitize_html_for_preview(self.project.raw_html, keep_scripts=(mode == "source-full"))
            html = inject_override_css(source_html, self.project.custom_css)
        else:
            selected = self.current_block()
            html = build_html(self.project, selected_id=selected.id if selected else None)
        self.preview.set_desired_viewport_width(int(self.preview_viewport_combo.currentData() or 0))
        self.preview.set_interaction_mode("builder" if self.inspect_clicks_button.isChecked() else "none")
        self.preview.set_html(html, self._base_url)

    def _refresh_code(self) -> None:
        self.html_view.setPlainText(build_html(self.project, inline_css=True))
        self.css_view.setPlainText(build_css(self.project))
        self.source_html_view.setPlainText(self.project.raw_html)

    def _populate_inspector(self) -> None:
        block = self.current_block()
        self._updating = True
        if not block:
            self.block_name_label.setText("No block selected")
            for widget in [self.title_edit, self.button_text_edit, self.button_url_edit, self.background_edit, self.color_edit, self.accent_edit]:
                widget.clear()
            self.body_edit.clear()
            self.padding_spin.setValue(0)
            self.margin_spin.setValue(0)
            self.radius_spin.setValue(0)
            self.min_height_spin.setValue(0)
            self.width_spin.setValue(-1)
            self.height_spin.setValue(-1)
            self.font_size_spin.setValue(-1)
            self.font_family_edit.clear()
            self.align_combo.setCurrentText("left")
            self._updating = False
            return
        self.block_name_label.setText(f"Editing {block.name} ({block.type})")
        self.title_edit.setText(block.title)
        self.body_edit.setPlainText(block.body)
        self.button_text_edit.setText(block.button_text)
        self.button_url_edit.setText(block.body if block.type == "image" else block.button_url)
        self.background_edit.setText(block.background)
        self.color_edit.setText(block.color)
        self.accent_edit.setText(block.accent)
        self.padding_spin.setValue(block.padding)
        self.margin_spin.setValue(block.margin)
        self.radius_spin.setValue(block.radius)
        self.min_height_spin.setValue(block.min_height)
        self.width_spin.setValue(getattr(block, "width", -1))
        self.height_spin.setValue(getattr(block, "height", -1))
        self.font_size_spin.setValue(getattr(block, "font_size", -1))
        self.font_family_edit.setText(getattr(block, "font_family", ""))
        align_index = self.align_combo.findText(block.align)
        self.align_combo.setCurrentIndex(max(align_index, 0))
        self._updating = False

    def add_block(self, block_type: str) -> None:
        block = make_block(block_type)
        self.project.blocks.append(block)
        self.refresh_everything()
        self._select_block(block.id)
        self.projectChanged.emit()

    def duplicate_selected_block(self) -> None:
        block = self.current_block()
        if not block:
            return
        clone = block.clone()
        index = self.project.blocks.index(block) + 1
        self.project.blocks.insert(index, clone)
        self.refresh_everything()
        self._select_block(clone.id)
        self.projectChanged.emit()

    def delete_selected_block(self) -> None:
        block = self.current_block()
        if not block:
            return
        if len(self.project.blocks) == 1:
            QMessageBox.information(self, "SiteForge", "Keep at least one block in the layout.")
            return
        self.project.blocks = [entry for entry in self.project.blocks if entry.id != block.id]
        self.refresh_everything(select_first=True)
        self.projectChanged.emit()

    def _select_block(self, block_id: str) -> None:
        for row in range(self.block_list.count()):
            if self.block_list.item(row).data(Qt.UserRole) == block_id:
                self.block_list.setCurrentRow(row)
                return

    def _on_block_selected(self) -> None:
        self._populate_inspector()
        self._refresh_preview()
        if self.lower_tabs.currentIndex() not in (1, 4):
            self.lower_tabs.setCurrentIndex(0)  # Block Editor tab

    def _update_project_title(self) -> None:
        if self._updating:
            return
        self.project.title = self.project_title.text().strip() or "Untitled Project"
        self._refresh_preview()
        self._refresh_code()
        self.projectTitleChanged.emit(self.project.title)
        self.projectChanged.emit()

    def _update_page_theme(self) -> None:
        if self._updating:
            return
        self.project.page_theme = self.page_theme.currentData()
        self._refresh_preview()
        self._refresh_code()
        self.projectChanged.emit()

    def _update_project_text_fields(self) -> None:
        if self._updating:
            return
        self.project.custom_css = self.custom_css_view.toPlainText()
        self.project.raw_css = self.project.custom_css
        self.project.notes = self.notes_view.toPlainText()
        self._schedule_refresh()

    def _sync_current_block(self) -> None:
        if self._updating:
            return
        block = self.current_block()
        if not block:
            return
        old_title = block.title
        block.title = self.title_edit.text().strip()
        block.body = self.body_edit.toPlainText().strip()
        block.button_text = self.button_text_edit.text().strip()
        if block.type == "image":
            block.body = self.button_url_edit.text().strip() or block.body
        else:
            block.button_url = self.button_url_edit.text().strip()
        block.background = self.background_edit.text().strip()
        block.color = self.color_edit.text().strip()
        block.accent = self.accent_edit.text().strip()
        block.padding = self.padding_spin.value()
        block.margin = self.margin_spin.value()
        block.radius = self.radius_spin.value()
        block.min_height = self.min_height_spin.value()
        block.width = self.width_spin.value()
        block.height = self.height_spin.value()
        block.font_size = self.font_size_spin.value()
        block.font_family = self.font_family_edit.text().strip()
        block.align = self.align_combo.currentText()
        self._schedule_refresh(list_refresh=(old_title != block.title))

    def _pick_color(self, target: QLineEdit, on_change=None) -> None:
        initial = QColor(target.text()) if target.text().strip() else QColor("#ffffff")
        color = QColorDialog.getColor(initial, self, "Pick Color")
        if color.isValid():
            target.setText(color.name())
            if on_change is not None:
                on_change()

    def _pick_gradient(self, target: QLineEdit, on_change=None) -> None:
        dialog = GradientPickerDialog(self, initial=target.text().strip())
        if dialog.exec() == QDialog.Accepted:
            target.setText(dialog.gradient_value())
            if on_change is not None:
                on_change()

    def _apply_block_order(self) -> None:
        ordered_ids = []
        for row in range(self.block_list.count()):
            ordered_ids.append(self.block_list.item(row).data(Qt.UserRole))
        current_by_id = {block.id: block for block in self.project.blocks}
        self.project.blocks = [current_by_id[block_id] for block_id in ordered_ids if block_id in current_by_id]
        self._refresh_preview()
        self._refresh_code()
        self.projectChanged.emit()

    def _handle_preview_message(self, payload: str) -> None:
        if payload.startswith("builder:"):
            block_id = payload.split(":", 1)[1].strip()
            if not block_id:
                return
            self._select_block(block_id)
            return
        if payload.startswith("buildersource:"):
            raw = payload.split(":", 1)[1]
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return
            self._updating = True
            self.source_selector_edit.setText(data.get("selector", ""))
            snippet = data.get("snippet", "")
            self.source_target_snippet.setPlainText(snippet)
            self._upsert_source_target_item(data.get("selector", ""), snippet)
            self.source_text_edit.setPlainText(data.get("text", ""))
            self.source_color_edit.setText(data.get("color", ""))
            background_image = data.get("backgroundImage", "")
            self.source_bg_edit.setText(background_image if background_image and background_image != "none" else data.get("background", ""))
            self.source_padding_spin.setValue(self._px_to_int(data.get("padding", "")))
            self.source_margin_spin.setValue(self._px_to_int(data.get("margin", "")))
            self.source_radius_spin.setValue(self._px_to_int(data.get("radius", "")))
            self.source_width_spin.setValue(self._safe_int(data.get("width", -1)))
            self.source_height_spin.setValue(self._safe_int(data.get("height", -1)))
            self.source_font_size_spin.setValue(self._px_to_int(data.get("fontSize", "")))
            self.source_font_family_edit.setText(data.get("fontFamily", ""))
            self.source_font_weight_edit.setText(data.get("fontWeight", ""))
            self.source_border_width_spin.setValue(self._px_to_int(data.get("borderWidth", "")))
            border_style = data.get("borderStyle", "").strip() or "unchanged"
            style_index = self.source_border_style_combo.findText(border_style)
            self.source_border_style_combo.setCurrentIndex(style_index if style_index >= 0 else 0)
            self.source_border_color_edit.setText(data.get("borderColor", ""))
            shadow_value = data.get("boxShadow", "")
            self.source_box_shadow_edit.setText(shadow_value)
            preset_index = self.source_box_shadow_preset_combo.findData(shadow_value)
            self.source_box_shadow_preset_combo.setCurrentIndex(preset_index if preset_index >= 0 else 0)
            display_value = (data.get("display", "") or "").strip() or "unchanged"
            display_index = self.source_display_combo.findText(display_value)
            self.source_display_combo.setCurrentIndex(display_index if display_index >= 0 else 0)
            position_value = (data.get("position", "") or "").strip() or "unchanged"
            position_index = self.source_position_combo.findText(position_value)
            self.source_position_combo.setCurrentIndex(position_index if position_index >= 0 else 0)
            detected_lines = [
                "Detected values (editable via fields above):",
                f"selector: {self._clean_css_value(data.get('selector', ''))}",
                f"background: {self._clean_css_value(data.get('backgroundImage') if data.get('backgroundImage') and data.get('backgroundImage') != 'none' else data.get('background'))}",
                f"text color: {self._clean_css_value(data.get('color', ''))}",
                f"padding: {self._clean_css_value(data.get('padding', ''))}",
                f"margin: {self._clean_css_value(data.get('margin', ''))}",
                f"radius: {self._clean_css_value(data.get('radius', ''))}",
                f"font size: {self._clean_css_value(data.get('fontSize', ''))}",
                f"font family: {self._clean_css_value(data.get('fontFamily', ''))}",
                f"font weight: {self._clean_css_value(data.get('fontWeight', ''))}",
                f"border width: {self._clean_css_value(data.get('borderWidth', ''))}",
                f"border style: {self._clean_css_value(data.get('borderStyle', ''))}",
                f"border color: {self._clean_css_value(data.get('borderColor', ''))}",
                f"box shadow: {self._clean_css_value(data.get('boxShadow', ''))}",
                f"display: {self._clean_css_value(data.get('display', ''))}",
                f"position: {self._clean_css_value(data.get('position', ''))}",
            ]
            self.source_detected_css_view.setPlainText("\n".join(detected_lines))
            self._updating = False
            self._reset_source_field_changes()

    def copy_selected_element_html(self) -> None:
        selector = self.source_selector_edit.text().strip()
        html = self.project.raw_html or ""
        if not selector or not html:
            snippet = self.source_target_snippet.toPlainText().strip()
            if snippet:
                copy_to_clipboard(snippet)
                return
            QMessageBox.information(self, "SiteForge", "Select an element first.")
            return
        try:
            soup = BeautifulSoup(html, "html.parser")
            node = soup.select_one(selector)
        except Exception:
            node = None
        if node is None:
            snippet = self.source_target_snippet.toPlainText().strip()
            if snippet:
                copy_to_clipboard(snippet)
                return
            QMessageBox.information(self, "SiteForge", "Could not resolve selector in source HTML.")
            return
        copy_to_clipboard(str(node))

    def _px_to_int(self, value: str) -> int:
        cleaned = (value or "").replace("px", "").strip()
        try:
            return max(int(float(cleaned)), -1)
        except ValueError:
            return -1

    def _safe_int(self, value) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return -1

    def apply_source_text(self) -> None:
        selector = self.source_selector_edit.text().strip()
        text_value = self.source_text_edit.toPlainText().strip()
        if not selector or not self.source_field_dirty.get("text") or not text_value:
            QMessageBox.information(self, "SiteForge", "Select a source element and change its text first.")
            return
        self.project.raw_html = apply_text_change(self.project.raw_html, selector, text_value)
        self.source_paste_edit.setPlainText(self.project.raw_html)
        self._refresh_source_targets()
        self._refresh_preview()
        self._refresh_code()
        self._reset_source_field_changes()
        self.projectChanged.emit()

    def apply_source_style(self) -> None:
        selector = self.source_selector_edit.text().strip()
        if not selector:
            QMessageBox.information(self, "SiteForge", "Select a source element first.")
            return
        background = self.source_bg_edit.text().strip() if self.source_field_dirty.get("background") else None
        color = self.source_color_edit.text().strip() if self.source_field_dirty.get("color") else None
        padding = self.source_padding_spin.value() if self.source_field_dirty.get("padding") else None
        margin = self.source_margin_spin.value() if self.source_field_dirty.get("margin") else None
        radius = self.source_radius_spin.value() if self.source_field_dirty.get("radius") else None
        width = self.source_width_spin.value() if self.source_field_dirty.get("width") else None
        height = self.source_height_spin.value() if self.source_field_dirty.get("height") else None
        font_size = self.source_font_size_spin.value() if self.source_field_dirty.get("font_size") else None
        font_family = self.source_font_family_edit.text().strip() if self.source_field_dirty.get("font_family") else None
        font_weight = self.source_font_weight_edit.text().strip() if self.source_field_dirty.get("font_weight") else None
        border_width = self.source_border_width_spin.value() if self.source_field_dirty.get("border_width") else None
        border_style = self.source_border_style_combo.currentText() if self.source_field_dirty.get("border_style") else None
        border_color = self.source_border_color_edit.text().strip() if self.source_field_dirty.get("border_color") else None
        box_shadow = self.source_box_shadow_edit.text().strip() if self.source_field_dirty.get("box_shadow") else None
        display_value = self.source_display_combo.currentText() if self.source_field_dirty.get("display") else None
        position_value = self.source_position_combo.currentText() if self.source_field_dirty.get("position") else None
        extra_css = self.source_extra_css_edit.toPlainText().strip() if self.source_field_dirty.get("extra_css") else None
        extra_parts = []
        if font_weight:
            extra_parts.append(f"font-weight: {font_weight};")
        if border_width is not None:
            extra_parts.append(f"border-width: {border_width}px;")
        if border_style and border_style != "unchanged":
            extra_parts.append(f"border-style: {border_style};")
        if border_color:
            extra_parts.append(f"border-color: {border_color};")
        if box_shadow is not None:
            box_shadow = box_shadow or "none"
            extra_parts.append(f"box-shadow: {box_shadow};")
        if display_value and display_value != "unchanged":
            extra_parts.append(f"display: {display_value};")
        if position_value and position_value != "unchanged":
            extra_parts.append(f"position: {position_value};")
        if extra_css:
            extra_parts.append(extra_css)
        if not any(value is not None for value in [background, color, padding, margin, radius, width, height, font_size, font_family, box_shadow, display_value, position_value]) and not extra_parts:
            QMessageBox.information(self, "SiteForge", "No changed style fields detected. Adjust one or more inspector fields first.")
            return
        rule = build_rule_css(
            selector,
            background,
            color,
            padding,
            margin,
            radius,
            width,
            height,
            font_size,
            font_family,
            "\n".join(extra_parts) if extra_parts else None,
        )
        existing = self.project.custom_css.strip()
        pattern = re.compile(rf"(?ms){re.escape(selector)}\s*\{{.*?\}}")
        if pattern.search(existing):
            self.project.custom_css = pattern.sub(rule, existing)
        elif existing:
            self.project.custom_css = existing + "\n\n" + rule
        else:
            self.project.custom_css = rule
        self.project.raw_css = self.project.custom_css
        self.custom_css_view.setPlainText(self.project.custom_css)
        self._refresh_preview()
        self._refresh_code()
        self._reset_source_field_changes()
        self.projectChanged.emit()

    def import_pasted_html(self) -> None:
        html = self.source_paste_edit.toPlainText().strip()
        if not html:
            QMessageBox.information(self, "SiteForge", "Paste some HTML first.")
            return
        try:
            project = html_to_document(html, title="Pasted HTML", source_mode="paste")
        except Exception as exc:
            QMessageBox.critical(self, "Convert Failed", str(exc))
            return
        self.projectLoaded.emit(project)

    def use_pasted_source(self) -> None:
        html = self.source_paste_edit.toPlainText().strip()
        if not html:
            QMessageBox.information(self, "SiteForge", "Paste some HTML first.")
            return
        self.project.raw_html = html
        self.project.source_mode = "paste"
        self.project.source_path = ""
        self.project.source_url = ""
        self.source_url_input.clear()
        self.set_base_url("")
        self.source_label.setText("Source: Pasted HTML")
        mode = "source-full" if self._looks_like_elementor(html) else "source"
        self.preview_mode_combo.setCurrentIndex(max(self.preview_mode_combo.findData(mode), 0))
        self.preview_viewport_combo.setCurrentIndex(max(self.preview_viewport_combo.findData(1366), 0))
        self._set_preview_wide_layout()
        self._refresh_source_targets()
        self._refresh_preview()
        self._refresh_code()
        self.projectChanged.emit()

    def copy_current_code(self, target: str = "left") -> None:
        if target == "all":
            bundle = "\n\n".join(
                [
                    "--- Generated HTML ---\n" + self.html_view.toPlainText(),
                    "--- Generated CSS ---\n" + self.css_view.toPlainText(),
                    "--- Inspector CSS ---\n" + self.custom_css_view.toPlainText(),
                    "--- Original Source HTML ---\n" + self.source_html_view.toPlainText(),
                    "--- Notes ---\n" + self.notes_view.toPlainText(),
                ]
            )
            copy_to_clipboard(bundle)
            return
        if target == "right":
            current = self.code_secondary_tabs.currentWidget()
        else:
            current = self.code_primary_tabs.currentWidget()
        if isinstance(current, QPlainTextEdit):
            copy_to_clipboard(current.toPlainText())


class WebsiteWorkspace(QWidget):
    websiteChanged = Signal()
    loadUrlRequested = Signal(str)
    openHtmlRequested = Signal()
    useProjectHtmlRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.current_html = ""
        self.original_html = ""
        self.current_source_url = ""
        self.current_source_kind = "project"
        self._base_url = QUrl()
        self._updating = False
        self.keep_scripts = False
        self.field_dirty: dict[str, bool] = {}
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh_outputs)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Compact topbar ─────────────────────────────────────────────
        topbar = card_frame()
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 10, 16, 10)
        topbar_layout.setSpacing(20)

        id_col = QVBoxLayout()
        id_col.setSpacing(3)
        eyebrow = QLabel("Website")
        eyebrow.setObjectName("eyebrowLabel")
        heading = QLabel("Inspect-Style Workspace")
        heading.setObjectName("sectionHeading")
        description = QLabel("Load a website or HTML, target selectors, layer override CSS, watch the preview update instantly.")
        description.setObjectName("subtitleLabel")
        description.setWordWrap(True)
        id_col.addWidget(eyebrow)
        id_col.addWidget(heading)
        id_col.addWidget(description)

        url_col = QVBoxLayout()
        url_col.setSpacing(8)
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.setMinimumHeight(34)
        load_button = QPushButton("Load Website")
        load_button.setMinimumHeight(34)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(load_button)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        open_html_button = QPushButton("Open HTML File")
        use_project_button = QPushButton("Use Project HTML")
        self.preview_mode_combo = QComboBox()
        self.preview_mode_combo.addItem("Smooth Preview", False)
        self.preview_mode_combo.addItem("Full Preview (scripts)", True)
        refresh_targets_button = QPushButton("Refresh Targets")
        for btn in [open_html_button, use_project_button, refresh_targets_button]:
            btn.setMinimumHeight(32)
        self.preview_mode_combo.setMinimumHeight(32)
        btn_row.addWidget(open_html_button)
        btn_row.addWidget(use_project_button)
        btn_row.addWidget(self.preview_mode_combo)
        btn_row.addWidget(refresh_targets_button)
        btn_row.addStretch(1)
        url_col.addLayout(url_row)
        url_col.addLayout(btn_row)

        topbar_layout.addLayout(id_col, 1)
        topbar_layout.addLayout(url_col, 2)
        root.addWidget(topbar)

        # ── Main 3-panel splitter: targets | preview | rule editor ─────
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setOpaqueResize(False)
        main_splitter.setHandleWidth(10)

        # ── LEFT: Detected Targets ──────────────────────────────────────
        targets_card = card_frame()
        targets_card.setMinimumWidth(200)
        targets_layout = QVBoxLayout(targets_card)
        targets_layout.setContentsMargins(14, 14, 14, 14)
        targets_layout.setSpacing(10)
        target_heading = QLabel("Detected Targets")
        target_heading.setObjectName("sectionHeading")
        target_note = QLabel("Pick a selector to edit its styles.")
        target_note.setObjectName("subtitleLabel")
        target_note.setWordWrap(True)
        self.target_list = QListWidget()
        self.target_snippet = QPlainTextEdit()
        self.target_snippet.setReadOnly(True)
        self.target_snippet.setPlaceholderText("Selected element snippet...")
        self.target_snippet.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.target_snippet.setMaximumHeight(120)
        targets_layout.addWidget(target_heading)
        targets_layout.addWidget(target_note)
        targets_layout.addWidget(self.target_list, 1)
        targets_layout.addWidget(self.target_snippet)

        # ── CENTER: Large Website Preview ──────────────────────────────
        preview_card = card_frame()
        preview_card.setMinimumWidth(680)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(8)
        preview_heading = QLabel("Website Preview")
        preview_heading.setObjectName("sectionHeading")
        self.website_source_label = QLabel("Source: Project HTML")
        self.website_source_label.setObjectName("subtitleLabel")
        self.preview = PreviewPane()
        self.preview.setMinimumWidth(660)
        self.preview.set_interaction_mode("website")
        preview_layout.addWidget(preview_heading)
        preview_layout.addWidget(self.website_source_label)
        preview_layout.addWidget(self.preview, 1)

        # ── RIGHT: Rule Editor (scrollable) ────────────────────────────
        rule_card = card_frame()
        rule_card.setMinimumWidth(260)
        rule_outer_layout = QVBoxLayout(rule_card)
        rule_outer_layout.setContentsMargins(0, 0, 0, 0)
        rule_outer_layout.setSpacing(0)

        rule_scroll = QScrollArea()
        rule_scroll.setWidgetResizable(True)
        rule_scroll.setFrameShape(QFrame.NoFrame)
        rule_inner = QWidget()
        rule_layout = QVBoxLayout(rule_inner)
        rule_layout.setContentsMargins(14, 14, 14, 14)
        rule_layout.setSpacing(12)

        re_heading = QLabel("Rule Editor")
        re_heading.setObjectName("sectionHeading")
        rule_layout.addWidget(re_heading)

        rule_form = QFormLayout()
        rule_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        rule_form.setVerticalSpacing(10)
        rule_form.setHorizontalSpacing(12)
        self.selector_edit = QLineEdit()
        self.selector_edit.setPlaceholderText(".card or #hero")
        self.rule_background_edit = QLineEdit()
        self.rule_color_edit = QLineEdit()
        self.rule_background_pick = QPushButton("Pick")
        self.rule_color_pick = QPushButton("Pick")
        self.rule_padding_spin = QSpinBox()
        self.rule_padding_spin.setRange(-1, 400)
        self.rule_padding_spin.setSpecialValueText("unchanged")
        self.rule_margin_spin = QSpinBox()
        self.rule_margin_spin.setRange(-1, 400)
        self.rule_margin_spin.setSpecialValueText("unchanged")
        self.rule_radius_spin = QSpinBox()
        self.rule_radius_spin.setRange(-1, 400)
        self.rule_radius_spin.setSpecialValueText("unchanged")
        self.rule_width_spin = QSpinBox()
        self.rule_width_spin.setRange(-1, 2400)
        self.rule_width_spin.setSpecialValueText("unchanged")
        self.rule_height_spin = QSpinBox()
        self.rule_height_spin.setRange(-1, 2400)
        self.rule_height_spin.setSpecialValueText("unchanged")
        self.rule_font_size_spin = QSpinBox()
        self.rule_font_size_spin.setRange(-1, 160)
        self.rule_font_size_spin.setSpecialValueText("unchanged")
        self.rule_font_family_edit = QLineEdit()
        self.rule_font_family_edit.setPlaceholderText("Inter, system-ui, sans-serif")
        self.rule_font_weight_edit = QLineEdit()
        self.rule_font_weight_edit.setPlaceholderText("400, 700, bold...")
        self.rule_border_width_spin = QSpinBox()
        self.rule_border_width_spin.setRange(-1, 80)
        self.rule_border_width_spin.setSpecialValueText("unchanged")
        self.rule_border_style_combo = QComboBox()
        self.rule_border_style_combo.addItems(["unchanged", "none", "solid", "dashed", "dotted", "double"])
        self.rule_border_color_edit = QLineEdit()
        self.rule_border_color_pick = QPushButton("Pick")
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Edit selected element text...")
        self.text_edit.setFixedHeight(90)
        self.gradient_start_edit = QLineEdit()
        self.gradient_start_pick = QPushButton("Pick")
        self.gradient_end_edit = QLineEdit()
        self.gradient_end_pick = QPushButton("Pick")
        self.gradient_angle_spin = QSpinBox()
        self.gradient_angle_spin.setRange(0, 360)
        self.gradient_angle_spin.setValue(135)
        self.gradient_type_combo = QComboBox()
        self.gradient_type_combo.addItems(["linear", "radial"])
        gradient_apply_button = QPushButton("Use Gradient as Background")
        gradient_apply_button.setMinimumHeight(34)
        self.rule_extra_css = QPlainTextEdit()
        self.rule_extra_css.setPlaceholderText("box-shadow: 0 20px 60px rgba(0,0,0,0.25);")
        self.rule_extra_css.setFixedHeight(90)
        self.detected_css_view = QPlainTextEdit()
        self.detected_css_view.setReadOnly(True)
        self.detected_css_view.setPlaceholderText("Detected CSS from selected element...")
        self.detected_css_view.setFixedHeight(130)
        self.detected_css_view.setLineWrapMode(QPlainTextEdit.WidgetWidth)

        rule_form.addRow("Selector", self.selector_edit)
        rule_form.addRow("Background", self._field_row(self.rule_background_edit, self.rule_background_pick))
        rule_form.addRow("Text Color", self._field_row(self.rule_color_edit, self.rule_color_pick))
        rule_form.addRow("Padding", self.rule_padding_spin)
        rule_form.addRow("Margin", self.rule_margin_spin)
        rule_form.addRow("Radius", self.rule_radius_spin)
        rule_form.addRow("Width", self.rule_width_spin)
        rule_form.addRow("Height", self.rule_height_spin)
        rule_form.addRow("Font Size", self.rule_font_size_spin)
        rule_form.addRow("Font Family", self.rule_font_family_edit)
        rule_form.addRow("Font Weight", self.rule_font_weight_edit)
        rule_form.addRow("Border Width", self.rule_border_width_spin)
        rule_form.addRow("Border Style", self.rule_border_style_combo)
        rule_form.addRow("Border Color", self._field_row(self.rule_border_color_edit, self.rule_border_color_pick))
        rule_form.addRow("Text Content", self.text_edit)
        rule_form.addRow("Gradient Start", self._field_row(self.gradient_start_edit, self.gradient_start_pick))
        rule_form.addRow("Gradient End", self._field_row(self.gradient_end_edit, self.gradient_end_pick))
        rule_form.addRow("Gradient Angle", self.gradient_angle_spin)
        rule_form.addRow("Gradient Type", self.gradient_type_combo)
        rule_form.addRow("Gradient", gradient_apply_button)
        rule_form.addRow("Extra CSS", self.rule_extra_css)
        rule_form.addRow("Detected CSS", self.detected_css_view)

        rule_actions = QHBoxLayout()
        rule_actions.setSpacing(8)
        apply_rule_button = QPushButton("Apply Rule")
        apply_text_button = QPushButton("Apply Text")
        reset_changes_button = QPushButton("Reset Changes")
        remove_rule_button = QPushButton("Remove Rule")
        for btn in [apply_rule_button, apply_text_button, reset_changes_button, remove_rule_button]:
            btn.setMinimumHeight(34)
            rule_actions.addWidget(btn)

        rule_layout.addLayout(rule_form)
        rule_layout.addLayout(rule_actions)
        rule_layout.addStretch(1)

        # Code output tabs at bottom of right panel
        code_heading = QLabel("Code Output")
        code_heading.setObjectName("sectionHeading")
        rule_layout.addWidget(code_heading)
        self.lower_tabs = QTabWidget()
        self.lower_tabs.setDocumentMode(True)
        self.website_code_tabs = QTabWidget()
        self.override_css_edit = QPlainTextEdit()
        self.final_html_view = QPlainTextEdit()
        self.final_html_view.setReadOnly(True)
        self.original_html_view = QPlainTextEdit()
        self.original_html_view.setReadOnly(True)
        self.website_code_tabs.addTab(self.override_css_edit, "Override CSS")
        self.website_code_tabs.addTab(self.final_html_view, "Final HTML")
        self.website_code_tabs.addTab(self.original_html_view, "Original HTML")
        self.website_code_tabs.setMinimumHeight(220)
        code_copy_row = QHBoxLayout()
        copy_website_code_button = QPushButton("Copy Current Tab")
        copy_website_code_button.setMinimumHeight(32)
        code_copy_row.addStretch(1)
        code_copy_row.addWidget(copy_website_code_button)
        rule_layout.addWidget(self.website_code_tabs)
        rule_layout.addLayout(code_copy_row)

        rule_scroll.setWidget(rule_inner)
        rule_outer_layout.addWidget(rule_scroll)

        main_splitter.addWidget(targets_card)
        main_splitter.addWidget(preview_card)
        main_splitter.addWidget(rule_card)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setStretchFactor(2, 2)
        main_splitter.setSizes([260, 980, 560])
        root.addWidget(main_splitter, 1)

        load_button.clicked.connect(self._emit_url)
        self.url_input.returnPressed.connect(self._emit_url)
        open_html_button.clicked.connect(self.openHtmlRequested)
        use_project_button.clicked.connect(self.useProjectHtmlRequested)
        refresh_targets_button.clicked.connect(self._refresh_targets)
        self.preview_mode_combo.currentIndexChanged.connect(self._change_preview_mode)
        apply_rule_button.clicked.connect(self.apply_rule)
        apply_text_button.clicked.connect(self.apply_text_change)
        reset_changes_button.clicked.connect(self._reset_field_changes)
        remove_rule_button.clicked.connect(self.remove_rule)
        copy_website_code_button.clicked.connect(self.copy_current_code)
        self.target_list.currentRowChanged.connect(self._populate_target)
        self.override_css_edit.textChanged.connect(self._override_css_changed)
        self.preview.jsMessageReceived.connect(self._handle_preview_message)
        self.rule_background_pick.clicked.connect(lambda: self._pick_color(self.rule_background_edit))
        self.rule_color_pick.clicked.connect(lambda: self._pick_color(self.rule_color_edit))
        self.rule_border_color_pick.clicked.connect(lambda: self._pick_color(self.rule_border_color_edit))
        self.gradient_start_pick.clicked.connect(lambda: self._pick_color(self.gradient_start_edit))
        self.gradient_end_pick.clicked.connect(lambda: self._pick_color(self.gradient_end_edit))
        gradient_apply_button.clicked.connect(self._apply_gradient_to_background)
        self._wire_dirty_tracking()
        self._reset_field_changes()


    def _field_row(self, line_edit: QLineEdit, button: QPushButton) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return widget

    def _pick_color(self, target: QLineEdit) -> None:
        initial = QColor(target.text()) if target.text().strip() else QColor("#ffffff")
        color = QColorDialog.getColor(initial, self, "Pick Color")
        if color.isValid():
            target.setText(color.name())

    def _wire_dirty_tracking(self) -> None:
        self.field_dirty = {
            "background": False,
            "color": False,
            "padding": False,
            "margin": False,
            "radius": False,
            "width": False,
            "height": False,
            "font_size": False,
            "font_family": False,
            "font_weight": False,
            "border_width": False,
            "border_style": False,
            "border_color": False,
            "extra_css": False,
            "text": False,
        }
        self.rule_background_edit.textChanged.connect(lambda: self._mark_dirty("background"))
        self.rule_color_edit.textChanged.connect(lambda: self._mark_dirty("color"))
        self.rule_padding_spin.valueChanged.connect(lambda: self._mark_dirty("padding"))
        self.rule_margin_spin.valueChanged.connect(lambda: self._mark_dirty("margin"))
        self.rule_radius_spin.valueChanged.connect(lambda: self._mark_dirty("radius"))
        self.rule_width_spin.valueChanged.connect(lambda: self._mark_dirty("width"))
        self.rule_height_spin.valueChanged.connect(lambda: self._mark_dirty("height"))
        self.rule_font_size_spin.valueChanged.connect(lambda: self._mark_dirty("font_size"))
        self.rule_font_family_edit.textChanged.connect(lambda: self._mark_dirty("font_family"))
        self.rule_font_weight_edit.textChanged.connect(lambda: self._mark_dirty("font_weight"))
        self.rule_border_width_spin.valueChanged.connect(lambda: self._mark_dirty("border_width"))
        self.rule_border_style_combo.currentIndexChanged.connect(lambda: self._mark_dirty("border_style"))
        self.rule_border_color_edit.textChanged.connect(lambda: self._mark_dirty("border_color"))
        self.rule_extra_css.textChanged.connect(lambda: self._mark_dirty("extra_css"))
        self.text_edit.textChanged.connect(lambda: self._mark_dirty("text"))

    def _mark_dirty(self, key: str) -> None:
        if self._updating:
            return
        self.field_dirty[key] = True

    def _schedule_refresh(self) -> None:
        self._refresh_timer.start(120)

    def _change_preview_mode(self, _index: int = -1) -> None:
        self.keep_scripts = bool(self.preview_mode_combo.currentData())
        self.current_html = sanitize_html_for_preview(self.original_html, keep_scripts=self.keep_scripts)
        self._refresh_targets()
        self.refresh_outputs()

    def _reset_field_changes(self) -> None:
        for key in self.field_dirty.keys():
            self.field_dirty[key] = False

    def _build_gradient_value(self) -> str:
        start = self.gradient_start_edit.text().strip()
        end = self.gradient_end_edit.text().strip()
        if not start or not end:
            return ""
        if self.gradient_type_combo.currentText() == "radial":
            return f"radial-gradient(circle, {start} 0%, {end} 100%)"
        angle = self.gradient_angle_spin.value()
        return f"linear-gradient({angle}deg, {start} 0%, {end} 100%)"

    def _apply_gradient_to_background(self) -> None:
        gradient = self._build_gradient_value()
        if not gradient:
            QMessageBox.information(self, "SiteForge", "Pick both gradient colors first.")
            return
        self.rule_background_edit.setText(gradient)
        self.field_dirty["background"] = True

    def _emit_url(self) -> None:
        value = self.url_input.text().strip()
        if value:
            self.loadUrlRequested.emit(value)

    def is_project_bound(self) -> bool:
        return self.current_source_kind == "project"

    def set_source(self, html: str, *, source_url: str = "", source_label: str = "", source_kind: str = "website") -> None:
        self.original_html = html or ""
        self.current_html = sanitize_html_for_preview(self.original_html, keep_scripts=self.keep_scripts)
        self.current_source_url = source_url
        self.current_source_kind = source_kind
        self._base_url = QUrl.fromUserInput(source_url) if source_url else QUrl()
        self.website_source_label.setText(f"Source: {source_label or source_url or 'Imported HTML'}")
        if source_url and source_url.startswith(("http://", "https://")):
            self.url_input.setText(source_url)
        self.original_html_view.setPlainText(self.original_html)
        self._refresh_targets()
        self.refresh_outputs()

    def sync_from_project(self, project: ProjectDocument) -> None:
        html = project.raw_html or build_html(project, inline_css=True)
        label = project.source_url or project.source_path or "Current Project"
        self._updating = True
        self.override_css_edit.setPlainText(project.raw_css)
        self._updating = False
        self.set_source(html, source_url=project.source_url, source_label=label, source_kind="project")

    def _refresh_targets(self) -> None:
        current_selector = self.selector_edit.text().strip()
        self.target_list.blockSignals(True)
        self.target_list.clear()
        for target in extract_targets(self.current_html):
            item = QListWidgetItem(target.label)
            item.setData(Qt.UserRole, target.selector)
            item.setData(Qt.UserRole + 1, target.snippet)
            self.target_list.addItem(item)
        self.target_list.blockSignals(False)
        if self.target_list.count() > 0:
            self.target_list.setCurrentRow(0)
            if current_selector:
                for row in range(self.target_list.count()):
                    if self.target_list.item(row).data(Qt.UserRole) == current_selector:
                        self.target_list.setCurrentRow(row)
                        break
        else:
            self.target_snippet.clear()

    def _populate_target(self) -> None:
        item = self.target_list.currentItem()
        if not item:
            return
        self._updating = True
        self.selector_edit.setText(item.data(Qt.UserRole))
        self.target_snippet.setPlainText(item.data(Qt.UserRole + 1))
        self.text_edit.setPlainText("")
        self._updating = False
        self._reset_field_changes()

    def _upsert_rule(self, selector: str, rule_css: str) -> None:
        existing = self.override_css_edit.toPlainText().strip()
        pattern = re.compile(rf"(?ms){re.escape(selector)}\s*\{{.*?\}}")
        if pattern.search(existing):
            updated = pattern.sub(rule_css, existing)
        elif existing:
            updated = existing.rstrip() + "\n\n" + rule_css
        else:
            updated = rule_css
        self._updating = True
        self.override_css_edit.setPlainText(updated)
        self._updating = False
        self.refresh_outputs()

    def apply_rule(self) -> None:
        selector = self.selector_edit.text().strip()
        if not selector:
            QMessageBox.information(self, "SiteForge", "Select or enter a selector first.")
            return

        background = self.rule_background_edit.text().strip() if self.field_dirty.get("background") else None
        color = self.rule_color_edit.text().strip() if self.field_dirty.get("color") else None
        padding = self.rule_padding_spin.value() if self.field_dirty.get("padding") else None
        margin = self.rule_margin_spin.value() if self.field_dirty.get("margin") else None
        radius = self.rule_radius_spin.value() if self.field_dirty.get("radius") else None
        width = self.rule_width_spin.value() if self.field_dirty.get("width") else None
        height = self.rule_height_spin.value() if self.field_dirty.get("height") else None
        font_size = self.rule_font_size_spin.value() if self.field_dirty.get("font_size") else None
        font_family = self.rule_font_family_edit.text().strip() if self.field_dirty.get("font_family") else None
        font_weight = self.rule_font_weight_edit.text().strip() if self.field_dirty.get("font_weight") else None
        border_width = self.rule_border_width_spin.value() if self.field_dirty.get("border_width") else None
        border_style = self.rule_border_style_combo.currentText() if self.field_dirty.get("border_style") else None
        border_color = self.rule_border_color_edit.text().strip() if self.field_dirty.get("border_color") else None
        extra_css = self.rule_extra_css.toPlainText() if self.field_dirty.get("extra_css") else None

        extra_parts = []
        if font_weight:
            extra_parts.append(f"font-weight: {font_weight};")
        if border_width is not None:
            extra_parts.append(f"border-width: {border_width}px;")
        if border_style and border_style != "unchanged":
            extra_parts.append(f"border-style: {border_style};")
        if border_color:
            extra_parts.append(f"border-color: {border_color};")
        if extra_css:
            extra_parts.append(extra_css)
        combined_extra = "\n".join(extra_parts) if extra_parts else None

        if not any(value is not None for value in [background, color, padding, margin, radius, width, height, font_size, font_family, combined_extra]):
            QMessageBox.information(self, "SiteForge", "No changed style fields detected. Adjust one or more fields first.")
            return

        rule_css = build_rule_css(
            selector,
            background,
            color,
            padding,
            margin,
            radius,
            width,
            height,
            font_size,
            font_family,
            combined_extra,
        )
        self._upsert_rule(selector, rule_css)
        self._reset_field_changes()
        self.websiteChanged.emit()

    def apply_text_change(self) -> None:
        selector = self.selector_edit.text().strip()
        text_value = self.text_edit.toPlainText().strip()
        if not selector:
            QMessageBox.information(self, "SiteForge", "Select a target first.")
            return
        if not text_value:
            QMessageBox.information(self, "SiteForge", "Enter the replacement text first.")
            return
        self.original_html = apply_text_change(self.original_html, selector, text_value)
        self.current_html = sanitize_html_for_preview(self.original_html, keep_scripts=self.keep_scripts)
        self._refresh_targets()
        self.refresh_outputs()
        self.detected_css_view.setPlainText("")
        self.websiteChanged.emit()

    def remove_rule(self) -> None:
        selector = self.selector_edit.text().strip()
        if not selector:
            return
        existing = self.override_css_edit.toPlainText()
        pattern = re.compile(rf"(?ms)\s*{re.escape(selector)}\s*\{{.*?\}}\s*")
        updated = pattern.sub("\n", existing).strip()
        self._updating = True
        self.override_css_edit.setPlainText(updated)
        self._updating = False
        self.refresh_outputs()
        self.websiteChanged.emit()

    def _override_css_changed(self) -> None:
        if self._updating:
            return
        self._schedule_refresh()
        self.websiteChanged.emit()

    def refresh_outputs(self) -> None:
        merged = inject_override_css(self.current_html, self.override_css_edit.toPlainText()) if self.current_html else ""
        self.preview.set_interaction_mode("website")
        self.preview.set_html(merged or "<html><body></body></html>", self._base_url)
        self.final_html_view.setPlainText(merged)
        self.original_html_view.setPlainText(self.original_html)

    def _px_to_int(self, value: str) -> int:
        cleaned = (value or "").replace("px", "").strip()
        try:
            return max(int(float(cleaned)), 0)
        except ValueError:
            return -1

    def _safe_int(self, value) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return -1

    def _upsert_target_item(self, selector: str, snippet: str) -> None:
        for row in range(self.target_list.count()):
            item = self.target_list.item(row)
            if item.data(Qt.UserRole) == selector:
                self.target_list.setCurrentRow(row)
                self.target_snippet.setPlainText(snippet)
                return
        item = QListWidgetItem(selector)
        item.setData(Qt.UserRole, selector)
        item.setData(Qt.UserRole + 1, snippet)
        self.target_list.insertItem(0, item)
        self.target_list.setCurrentRow(0)

    def _handle_preview_message(self, payload: str) -> None:
        if not payload.startswith("website:"):
            return
        raw = payload.split(":", 1)[1]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        selector = data.get("selector", "").strip()
        if not selector:
            return
        self._updating = True
        self.selector_edit.setText(selector)
        snippet = data.get("snippet", "")
        self.target_snippet.setPlainText(snippet)
        self._upsert_target_item(selector, snippet)
        self.rule_background_edit.setText(data.get("background", ""))
        background_image = data.get("backgroundImage", "")
        if background_image and background_image != "none":
            self.rule_background_edit.setText(background_image)
        self.rule_color_edit.setText(data.get("color", ""))
        self.rule_padding_spin.setValue(self._px_to_int(data.get("padding", "")))
        self.rule_margin_spin.setValue(self._px_to_int(data.get("margin", "")))
        self.rule_radius_spin.setValue(self._px_to_int(data.get("radius", "")))
        self.rule_width_spin.setValue(self._safe_int(data.get("width", -1)))
        self.rule_height_spin.setValue(self._safe_int(data.get("height", -1)))
        self.rule_font_size_spin.setValue(self._px_to_int(data.get("fontSize", "")))
        self.rule_font_family_edit.setText(data.get("fontFamily", ""))
        self.rule_font_weight_edit.setText(data.get("fontWeight", ""))
        self.rule_border_width_spin.setValue(self._px_to_int(data.get("borderWidth", "")))
        border_style = data.get("borderStyle", "").strip() or "unchanged"
        style_index = self.rule_border_style_combo.findText(border_style)
        self.rule_border_style_combo.setCurrentIndex(style_index if style_index >= 0 else 0)
        self.rule_border_color_edit.setText(data.get("borderColor", ""))
        self.text_edit.setPlainText(data.get("text", ""))
        detected_lines = [
            f"background: {data.get('backgroundFull', '')};",
            f"background-image: {data.get('backgroundImage', '')};",
            f"color: {data.get('color', '')};",
            f"padding: {data.get('paddingFull', '')};",
            f"margin: {data.get('marginFull', '')};",
            f"border-radius: {data.get('radiusFull', '')};",
            f"font-size: {data.get('fontSize', '')};",
            f"font-family: {data.get('fontFamily', '')};",
            f"font-weight: {data.get('fontWeight', '')};",
            f"border-width: {data.get('borderWidth', '')};",
            f"border-style: {data.get('borderStyle', '')};",
            f"border-color: {data.get('borderColor', '')};",
            f"box-shadow: {data.get('boxShadow', '')};",
            f"display: {data.get('display', '')};",
            f"position: {data.get('position', '')};",
        ]
        self.detected_css_view.setPlainText("\n".join(detected_lines))
        self._updating = False
        self._reset_field_changes()
        if hasattr(self, "lower_tabs"):
            self.lower_tabs.setCurrentIndex(0)

    def get_override_css(self) -> str:
        return self.override_css_edit.toPlainText()

    def get_final_html(self) -> str:
        return self.final_html_view.toPlainText()

    def copy_current_code(self) -> None:
        current = self.website_code_tabs.currentWidget()
        if isinstance(current, QPlainTextEdit):
            copy_to_clipboard(current.toPlainText())


class ExportWorkspace(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(20)

        header = card_frame()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(36, 30, 36, 30)
        header_layout.setSpacing(8)
        eyebrow = QLabel("Export")
        eyebrow.setObjectName("eyebrowLabel")
        heading = QLabel("Copy or Export Final Code")
        heading.setObjectName("sectionHeading")
        subtitle = QLabel(
            "Copy builder or import output directly, or export both to disk."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        header_layout.addWidget(eyebrow)
        header_layout.addWidget(heading)
        header_layout.addWidget(subtitle)
        root.addWidget(header)

        body = card_frame()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(10)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.builder_html_view = QPlainTextEdit()
        self.builder_html_view.setReadOnly(True)
        self.builder_css_view = QPlainTextEdit()
        self.builder_css_view.setReadOnly(True)
        self.import_html_view = QPlainTextEdit()
        self.import_html_view.setReadOnly(True)
        self.import_css_view = QPlainTextEdit()
        self.import_css_view.setReadOnly(True)
        self.import_original_view = QPlainTextEdit()
        self.import_original_view.setReadOnly(True)
        self.tabs.addTab(self.builder_html_view, "Builder HTML")
        self.tabs.addTab(self.builder_css_view, "Builder CSS")
        self.tabs.addTab(self.import_html_view, "Imported Final HTML")
        self.tabs.addTab(self.import_css_view, "Inspector CSS")
        self.tabs.addTab(self.import_original_view, "Original Source HTML")
        actions = QHBoxLayout()
        actions.setSpacing(8)
        copy_button = QPushButton("Copy Current Tab")
        copy_button.setMinimumHeight(36)
        copy_button.setMinimumWidth(160)
        actions.addStretch(1)
        actions.addWidget(copy_button)
        body_layout.addWidget(self.tabs, 1)
        body_layout.addLayout(actions)
        root.addWidget(body, 1)

        copy_button.clicked.connect(self.copy_current_tab)


    def set_builder_output(self, html: str, css: str) -> None:
        self.builder_html_view.setPlainText(html)
        self.builder_css_view.setPlainText(css)

    def set_import_output(self, final_html: str, override_css: str, original_html: str) -> None:
        self.import_html_view.setPlainText(final_html)
        self.import_css_view.setPlainText(override_css)
        self.import_original_view.setPlainText(original_html)

    def copy_current_tab(self) -> None:
        current = self.tabs.currentWidget()
        if isinstance(current, QPlainTextEdit):
            copy_to_clipboard(current.toPlainText())


class MainWindow(QMainWindow):
    updateCheckFinished = Signal(dict, str)

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("Orvlyn", "SiteForge")
        self.current_project_path = ""
        self.dirty = False
        self.project = make_portfolio_homepage()

        self.setWindowTitle("SiteForge")
        self.resize(1920, 1080)
        self._update_check_inflight = False
        app_icon = get_cached_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        topbar = card_frame()
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(18, 12, 18, 12)
        topbar_layout.setSpacing(10)

        title = QLabel("SiteForge")
        title.setObjectName("titleLabel")

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Enter URL")
        self.url_bar.setMinimumWidth(260)
        self.url_bar.setMinimumHeight(32)

        self.load_url_button = QPushButton("Load URL")
        self.load_url_button.setMinimumHeight(32)

        self.open_button = QPushButton("Open")
        self.save_button = QPushButton("Save")
        self.export_button = QPushButton("Export")
        self.export_button.setProperty("variant", "primary")
        self.update_button = QPushButton("Check Updates")
        self.app_theme_combo = QComboBox()
        for key, value in APP_THEMES.items():
            self.app_theme_combo.addItem(value["label"], key)

        # Hidden/secondary buttons — still wired up
        self.new_blank_button = QPushButton("Blank")
        self.new_homepage_button = QPushButton("Homepage")
        self.import_button = QPushButton("Import HTML")
        self.paste_code_button = QPushButton("Paste Code")

        for widget in [self.open_button, self.save_button, self.export_button, self.update_button, self.app_theme_combo,
                       self.new_blank_button, self.new_homepage_button, self.import_button, self.paste_code_button]:
            widget.setMinimumHeight(32)

        # Secondary actions row (hidden initially, accessible via keyboard / menus if needed)
        secondary_actions = QHBoxLayout()
        secondary_actions.setSpacing(6)
        secondary_actions.addWidget(self.new_blank_button)
        secondary_actions.addWidget(self.new_homepage_button)
        secondary_actions.addWidget(self.import_button)
        secondary_actions.addWidget(self.paste_code_button)

        topbar_layout.addWidget(title)
        topbar_layout.addStretch(1)
        topbar_layout.addWidget(self.url_bar)
        topbar_layout.addWidget(self.load_url_button)
        topbar_layout.addSpacing(8)
        topbar_layout.addLayout(secondary_actions)
        topbar_layout.addSpacing(8)
        topbar_layout.addWidget(self.open_button)
        topbar_layout.addWidget(self.save_button)
        topbar_layout.addWidget(self.export_button)
        topbar_layout.addWidget(self.update_button)
        topbar_layout.addWidget(self.app_theme_combo)
        root.addWidget(topbar)

        content = QSplitter(Qt.Horizontal)
        content.setChildrenCollapsible(False)
        content.setOpaqueResize(False)

        nav_card = card_frame()
        nav_layout = QVBoxLayout(nav_card)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_heading = QLabel("Workspace")
        nav_heading.setObjectName("sectionHeading")
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        for label in ["Homepage", "Editor", "Color Lab", "Export"]:
            self.nav_list.addItem(label)
        nav_layout.addWidget(nav_heading)
        nav_layout.addWidget(self.nav_list, 1)

        self.pages = QStackedWidget()
        self.home_page = HomeWorkspace()
        self.editor_page = EditorWorkspace()
        self.color_lab_page = ColorLabWorkspace()
        self.export_page = ExportWorkspace()
        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.editor_page)
        self.pages.addWidget(self.color_lab_page)
        self.pages.addWidget(self.export_page)

        content.addWidget(nav_card)
        content.addWidget(self.pages)
        content.setSizes([140, 1600])
        root.addWidget(content, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        self.nav_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav_list.setCurrentRow(0)

        self.new_blank_button.clicked.connect(self.new_blank_project)
        self.new_homepage_button.clicked.connect(self.new_homepage_project)
        self.import_button.clicked.connect(self.import_html_into_editor)
        self.paste_code_button.clicked.connect(self.open_paste_code)
        self.load_url_button.clicked.connect(self._load_url_from_bar)
        self.url_bar.returnPressed.connect(self._load_url_from_bar)
        self.open_button.clicked.connect(self.open_project)
        self.save_button.clicked.connect(self.save_project)
        self.export_button.clicked.connect(self.export_current_project)
        self.update_button.clicked.connect(self.check_for_updates)
        self.app_theme_combo.currentIndexChanged.connect(self._apply_selected_theme)

        self.home_page.newBlankRequested.connect(self.new_blank_project)
        self.home_page.newHomepageRequested.connect(self.new_homepage_project)
        self.home_page.importHtmlRequested.connect(self.import_html_into_editor)
        self.home_page.openProjectRequested.connect(self.open_project)
        self.home_page.loadUrlRequested.connect(self.load_url_from_value)
        self.home_page.recentProjectRequested.connect(self.open_recent_project)
        self.home_page.goEditorRequested.connect(lambda: self.nav_list.setCurrentRow(1))
        self.home_page.goExportRequested.connect(lambda: self.nav_list.setCurrentRow(3))

        self.editor_page.importFileRequested.connect(self.import_html_into_editor)
        self.editor_page.loadUrlRequested.connect(self.load_url_from_value)
        self.editor_page.projectChanged.connect(self._handle_editor_changed)
        self.editor_page.projectTitleChanged.connect(self._update_window_title)
        self.editor_page.projectLoaded.connect(self._load_project_from_editor)
        self.updateCheckFinished.connect(self._on_update_check_result)

        self._load_settings()
        self._apply_selected_theme()
        self._set_project(self.project, project_path="")

    def _load_settings(self) -> None:
        recent = self.settings.value("recent_projects", [], type=list)
        self.home_page.set_recent_projects(recent if isinstance(recent, list) else [])
        saved_theme = self.settings.value("app_theme", "forge")
        index = self.app_theme_combo.findData(saved_theme)
        self.app_theme_combo.setCurrentIndex(max(index, 0))

    def _save_recent(self, path: str) -> None:
        if not path:
            return
        recent = self.settings.value("recent_projects", [], type=list)
        recent = recent if isinstance(recent, list) else []
        normalized = str(Path(path))
        recent = [entry for entry in recent if entry != normalized]
        recent.insert(0, normalized)
        recent = recent[:6]
        self.settings.setValue("recent_projects", recent)
        self.home_page.set_recent_projects(recent)

    def _apply_selected_theme(self) -> None:
        theme_name = self.app_theme_combo.currentData() or "forge"
        self.settings.setValue("app_theme", theme_name)
        self.setStyleSheet(build_stylesheet(theme_name))
        self.project.app_theme = theme_name
        accent = APP_THEMES.get(theme_name, APP_THEMES["forge"]).get("accent", "")
        if hasattr(self, "color_lab_page"):
            self.color_lab_page.set_theme_accent(accent)

    def _version_tuple(self, value: str) -> tuple[int, ...]:
        parts = [int(part) for part in re.findall(r"\d+", value or "")]
        return tuple(parts) if parts else (0,)

    def _is_remote_newer(self, remote: str, current: str) -> bool:
        left = list(self._version_tuple(remote))
        right = list(self._version_tuple(current))
        size = max(len(left), len(right))
        left.extend([0] * (size - len(left)))
        right.extend([0] * (size - len(right)))
        return tuple(left) > tuple(right)

    def check_for_updates(self) -> None:
        if self._update_check_inflight:
            self.statusBar().showMessage("Update check already running", 3000)
            return
        self._update_check_inflight = True
        self.update_button.setEnabled(False)
        self.statusBar().showMessage("Checking for updates...", 3000)

        def _worker() -> None:
            result: dict[str, str] = {}
            error_message = ""
            try:
                with urllib.request.urlopen(UPDATE_CHECK_URL, timeout=8) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                result = payload if isinstance(payload, dict) else {}
            except Exception as exc:
                error_message = str(exc)
            self.updateCheckFinished.emit(result, error_message)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_update_check_result(self, result: dict, error_message: str) -> None:
        self._update_check_inflight = False
        self.update_button.setEnabled(True)
        if error_message:
            self.statusBar().showMessage("Update check failed", 3000)
            QMessageBox.warning(self, "Update Check", f"Could not check updates.\n\n{error_message}")
            return

        remote_version = str(result.get("version") or "").strip()
        download_url = str(result.get("download_url") or "").strip()
        notes = str(result.get("notes") or "").strip()

        if remote_version and self._is_remote_newer(remote_version, APP_VERSION):
            message = [
                f"Current version: {APP_VERSION}",
                f"Latest version: {remote_version}",
            ]
            if notes:
                message.extend(["", "Release notes:", notes])
            if download_url:
                message.extend(["", f"Download: {download_url}"])
            QMessageBox.information(self, "Update Available", "\n".join(message))
            self.statusBar().showMessage(f"Update available: {remote_version}", 4000)
        else:
            QMessageBox.information(self, "Up To Date", f"You are on the latest version ({APP_VERSION}).")
            self.statusBar().showMessage("You are on the latest version", 3000)

    def _set_project(self, project: ProjectDocument, project_path: str = "") -> None:
        self.project = project
        self.current_project_path = project_path
        self.dirty = False
        self.editor_page.set_project(project)
        if project.source_path:
            self.editor_page.set_base_url(Path(project.source_path).parent.as_uri() + "/")
        elif project.source_url:
            self.editor_page.set_base_url(project.source_url)
        else:
            self.editor_page.set_base_url("")
        self.editor_page.set_source_url_value(project.source_url)
        self._refresh_export_views()
        self._update_window_title(project.title)
        self.statusBar().showMessage("Project loaded", 3000)

    def _refresh_export_views(self) -> None:
        self.export_page.set_builder_output(build_html(self.project, inline_css=True), build_css(self.project))
        final_import_html = inject_override_css(self.project.raw_html, self.project.custom_css or self.project.raw_css) if self.project.raw_html.strip() else ""
        self.export_page.set_import_output(final_import_html, self.project.custom_css or self.project.raw_css, self.project.raw_html)

    def _update_window_title(self, title: str) -> None:
        suffix = " *" if self.dirty else ""
        path = f" - {self.current_project_path}" if self.current_project_path else ""
        self.setWindowTitle(f"SiteForge - {title}{path}{suffix}")

    def _mark_dirty(self) -> None:
        self.dirty = True
        self._update_window_title(self.project.title)

    def _handle_editor_changed(self) -> None:
        self.project = self.editor_page.project
        self._refresh_export_views()
        self._mark_dirty()

    def _load_project_from_editor(self, project: ProjectDocument) -> None:
        self._set_project(project)
        self.nav_list.setCurrentRow(1)

    def new_blank_project(self) -> None:
        self._set_project(make_blank_project())
        self.nav_list.setCurrentRow(1)
        self.statusBar().showMessage("Started blank project", 3000)

    def new_homepage_project(self) -> None:
        self._set_project(make_portfolio_homepage())
        self.nav_list.setCurrentRow(1)
        self.statusBar().showMessage("Loaded homepage starter", 3000)

    def open_paste_code(self) -> None:
        self.nav_list.setCurrentRow(1)
        self.editor_page.open_source_import()
        self.statusBar().showMessage("Paste code into the Editor source panel", 3000)

    def import_html_into_editor(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import HTML", str(base_dir()), "HTML Files (*.html *.htm)")
        if not path:
            return
        try:
            project = load_html_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))
            return
        self._set_project(project)
        self.nav_list.setCurrentRow(1)
        self.editor_page.open_source_import()
        self.statusBar().showMessage("HTML imported into Editor", 3000)

    def _load_url_from_bar(self) -> None:
        self.load_url_from_value(self.url_bar.text().strip())

    def load_url_dialog(self) -> None:
        seed = self.home_page.url_input.text().strip() or self.editor_page.source_url_input.text().strip()
        self.load_url_from_value(seed)

    def load_url_from_value(self, value: str) -> None:
        url = value.strip()
        if not url:
            QMessageBox.information(self, "SiteForge", "Enter a website URL first.")
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.home_page.url_input.setText(url)
        self.editor_page.set_source_url_value(url)
        try:
            project = load_url(url)
        except Exception as exc:
            QMessageBox.critical(self, "Load URL Failed", str(exc))
            return
        self._set_project(project)
        self.nav_list.setCurrentRow(1)
        self.editor_page.open_source_import()
        self.statusBar().showMessage("URL loaded into Editor source mode", 3000)

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open SiteForge Project", str(base_dir()), "SiteForge Project (*.siteforge *.json)")
        if path:
            self.open_recent_project(path)

    def open_recent_project(self, path: str) -> None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            project = ProjectDocument.from_dict(data)
        except Exception as exc:
            QMessageBox.critical(self, "Open Failed", str(exc))
            return
        self._set_project(project, project_path=path)
        self._save_recent(path)
        self.nav_list.setCurrentRow(1)

    def save_project(self) -> None:
        self.project = self.editor_page.project
        self.project.raw_css = self.project.custom_css
        if self.current_project_path:
            path = self.current_project_path
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Save SiteForge Project", str(base_dir() / "project.siteforge"), "SiteForge Project (*.siteforge)")
            if not path:
                return
            if not path.endswith(".siteforge"):
                path += ".siteforge"
        try:
            Path(path).write_text(json.dumps(self.project.to_dict(), indent=2), encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return
        self.current_project_path = path
        self.dirty = False
        self._save_recent(path)
        self._update_window_title(self.project.title)
        self.statusBar().showMessage("Project saved", 3000)

    def export_current_project(self) -> None:
        target_dir = QFileDialog.getExistingDirectory(self, "Export SiteForge Output", str(base_dir() / "exports"))
        if not target_dir:
            return
        builder_dir = Path(target_dir) / "Builder"
        import_dir = Path(target_dir) / "Imported"
        try:
            builder_html, builder_css, builder_json = export_project(self.project, str(builder_dir))
            import_dir.mkdir(parents=True, exist_ok=True)
            (import_dir / "import-preview.html").write_text(inject_override_css(self.project.raw_html, self.project.custom_css), encoding="utf-8")
            (import_dir / "inspector-overrides.css").write_text(self.project.custom_css, encoding="utf-8")
            (import_dir / "import-source.html").write_text(self.project.raw_html, encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported Builder to {builder_html.parent} and imported source files to {import_dir}",
            6000,
        )
        self.nav_list.setCurrentRow(3)


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SiteForge")
    app.setOrganizationName("Orvlyn")
    app_icon = get_cached_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    window = MainWindow()
    window.show()
    return app.exec()