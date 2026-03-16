from __future__ import annotations

import colorsys
import random
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ColorLabWorkspace(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._initial_theme_load = True
        self.locked: Dict[int, str] = {}
        self.edited: Dict[int, str] = {}
        self.palette: List[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)
        self.setFocusPolicy(Qt.StrongFocus)

        heading = QLabel("Color Lab")
        heading.setObjectName("sectionHeading")
        subtitle = QLabel("HEX Tool with lockable swatches, randomizer, and export actions.")
        subtitle.setObjectName("subtitleLabel")
        root.addWidget(heading)
        root.addWidget(subtitle)

        top = QHBoxLayout()
        top.addWidget(QLabel("HEX"))
        self.hex_input = QLineEdit("#00ecb8")
        self.hex_input.setPlaceholderText("#00ecb8")
        self.count_combo = QComboBox()
        self.count_combo.addItems(["3", "4", "5", "6", "7", "8", "9", "10"])
        pick_btn = QPushButton("Pick")
        random_btn = QPushButton("Random")
        top.addWidget(self.hex_input, 1)
        top.addWidget(QLabel("Count"))
        top.addWidget(self.count_combo)
        top.addWidget(pick_btn)
        top.addWidget(random_btn)
        root.addLayout(top)

        self.color_preview = QLabel()
        self.color_preview.setMinimumHeight(34)
        self.color_preview.setAlignment(Qt.AlignCenter)
        self.color_preview.setCursor(Qt.PointingHandCursor)
        self.color_preview.mousePressEvent = lambda _event: self.pick_color()
        root.addWidget(self.color_preview)

        info = QHBoxLayout()
        self.rgb_label = QLabel("RGB:")
        self.hsl_label = QLabel("HSL:")
        info.addWidget(self.rgb_label)
        info.addWidget(self.hsl_label)
        info.addStretch(1)
        root.addLayout(info)

        actions = QHBoxLayout()
        self.contrast_btn = QPushButton("Contrast Check")
        self.dark_variant_btn = QPushButton("Dark Variant")
        self.copy_all_btn = QPushButton("Copy HEX List")
        self.copy_css_btn = QPushButton("Copy CSS Vars")
        self.copy_gradient_btn = QPushButton("Copy Gradient")
        self.export_png_btn = QPushButton("Export PNG")
        self.export_txt_btn = QPushButton("Export TXT")
        actions.addWidget(self.contrast_btn)
        actions.addWidget(self.dark_variant_btn)
        actions.addWidget(self.copy_all_btn)
        actions.addWidget(self.copy_css_btn)
        actions.addWidget(self.copy_gradient_btn)
        actions.addWidget(self.export_png_btn)
        actions.addWidget(self.export_txt_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        self.swatch_widget = QWidget()
        self.swatch_layout = QGridLayout(self.swatch_widget)
        self.swatch_layout.setContentsMargins(0, 0, 0, 0)
        self.swatch_layout.setHorizontalSpacing(0)
        self.swatch_layout.setVerticalSpacing(0)
        root.addWidget(self.swatch_widget, 1)

        self.hex_input.textChanged.connect(self.refresh_palette)
        self.count_combo.currentIndexChanged.connect(self.refresh_palette)
        pick_btn.clicked.connect(self.pick_color)
        random_btn.clicked.connect(self.randomize_base)
        self.contrast_btn.clicked.connect(self.contrast_check)
        self.dark_variant_btn.clicked.connect(self.apply_dark_variant)
        self.copy_all_btn.clicked.connect(self.copy_all_hex)
        self.copy_css_btn.clicked.connect(self.copy_css_vars)
        self.copy_gradient_btn.clicked.connect(self.copy_gradient)
        self.export_png_btn.clicked.connect(self.export_png)
        self.export_txt_btn.clicked.connect(self.export_txt)

        self.refresh_palette()

    def set_theme_accent(self, accent: str) -> None:
        if not accent:
            return
        if self._initial_theme_load:
            self.hex_input.setText(accent)
            self._initial_theme_load = False

    def _hex_to_rgb(self, value: str) -> tuple[int, int, int]:
        value = value.strip().lstrip("#")
        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)
        if len(value) != 6:
            raise ValueError("Invalid HEX")
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, rgb: tuple[float, float, float]) -> str:
        r = max(0, min(255, int(round(rgb[0] * 255))))
        g = max(0, min(255, int(round(rgb[1] * 255))))
        b = max(0, min(255, int(round(rgb[2] * 255))))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _rgb_to_hsl(self, rgb: tuple[int, int, int]) -> tuple[float, float, float]:
        return colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)

    def _hsl_to_hex(self, h: float, l: float, s: float) -> str:
        return self._rgb_to_hex(colorsys.hls_to_rgb(h, l, s))

    def _random_variation(self, hex_color: str) -> str:
        rgb = self._hex_to_rgb(hex_color)
        h, l, s = self._rgb_to_hsl(rgb)
        h = (h + random.uniform(-0.08, 0.08)) % 1.0
        l = max(0.0, min(1.0, l + random.uniform(-0.1, 0.1)))
        s = max(0.0, min(1.0, s + random.uniform(-0.1, 0.1)))
        return self._hsl_to_hex(h, l, s)

    def _build_palette(self, base_hex: str, count: int) -> List[str]:
        r, g, b = self._hex_to_rgb(base_hex)
        h, l, s = self._rgb_to_hsl((r, g, b))
        palette: List[str] = []

        if count == 3:
            palette.append(self._hsl_to_hex(h, max(0.08, l * 0.35), s))
            palette.append(self._hsl_to_hex(h, l, s))
            palette.append(self._hsl_to_hex(h, min(0.95, l + 0.3), min(1.0, s * 0.8)))
        elif count == 4:
            palette.append(self._hsl_to_hex(h, max(0.1, l * 0.3), s))
            palette.append(self._hsl_to_hex(h, l, s))
            palette.append(self._hsl_to_hex(h, min(0.95, l + 0.3), min(1.0, s * 0.8)))
            comp_h = (h + 0.5) % 1.0
            comp_l = 0.5 if l < 0.3 else (0.65 if l < 0.7 else l)
            palette.append(self._hsl_to_hex(comp_h, comp_l, min(1.0, s * 1.15)))
        elif count == 5:
            palette.append(self._hsl_to_hex(h, min(0.95, l + 0.3), min(0.6, s * 0.6)))
            palette.append(self._hsl_to_hex(h, l, s))
            palette.append(self._hsl_to_hex(h, max(0.15, l * 0.45), min(1.0, s * 1.1)))
            comp_h = (h + 0.5) % 1.0
            comp_l = 0.5 if l < 0.35 else (0.6 if l < 0.7 else l - 0.1)
            palette.append(self._hsl_to_hex(comp_h, comp_l, min(1.0, s * 1.2)))
            ana_h = (h + 0.083) % 1.0
            palette.append(self._hsl_to_hex(ana_h, l, min(1.0, s * 1.05)))
        else:
            palette.append(self._hsl_to_hex(h, min(0.98, l + 0.35), min(0.5, s * 0.6)))
            palette.append(self._hsl_to_hex(h, min(0.9, l + 0.2), s))
            palette.append(self._hsl_to_hex(h, l, s))
            palette.append(self._hsl_to_hex(h, max(0.15, l * 0.55), min(1.0, s * 1.1)))
            palette.append(self._hsl_to_hex(h, max(0.08, l * 0.25), s))
            comp_h = (h + 0.5) % 1.0
            comp_l = 0.5 if l < 0.35 else (0.6 if l < 0.7 else l - 0.1)
            palette.append(self._hsl_to_hex(comp_h, comp_l, min(1.0, s * 1.2)))
            if count >= 7:
                warm_h = (h + 0.083) % 1.0
                palette.append(self._hsl_to_hex(warm_h, l, min(1.0, s * 1.1)))
            if count >= 8:
                cool_h = (h - 0.083) % 1.0
                palette.append(self._hsl_to_hex(cool_h, l, min(1.0, s * 1.05)))
            if count >= 9:
                tri_h = (h + 0.333) % 1.0
                palette.append(self._hsl_to_hex(tri_h, l, min(1.0, s * 0.95)))
            if count >= 10:
                tri2_h = (h + 0.667) % 1.0
                palette.append(self._hsl_to_hex(tri2_h, l, min(1.0, s * 0.95)))
        return palette[:count]

    def _clear_swatches(self) -> None:
        while self.swatch_layout.count():
            item = self.swatch_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        for col in range(max(1, self.swatch_layout.columnCount())):
            self.swatch_layout.setColumnStretch(col, 0)
        self.swatch_layout.setRowStretch(0, 0)

    def _create_swatch(self, color: str, index: int) -> QWidget:
        container = QWidget()
        container.setFocusPolicy(Qt.NoFocus)
        container.setStyleSheet(f"background-color: {color};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setAlignment(Qt.AlignCenter)

        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 8, 8, 8)
        controls_layout.setSpacing(6)

        lock_btn = QPushButton("Lock")
        up_btn = QPushButton("+")
        down_btn = QPushButton("-")
        for button in (lock_btn, up_btn, down_btn):
            button.setMinimumHeight(26)
            button.setFocusPolicy(Qt.NoFocus)

        if index in self.locked:
            lock_btn.setText("Unlock")
            color = self.locked[index]
            container.setStyleSheet(f"background-color: {color};")

        def update_overlay(value: str) -> None:
            qcolor = QColor(value)
            overlay = qcolor.darker(120)
            overlay.setAlpha(int(255 * 0.6))
            controls.setStyleSheet(f"background-color: {overlay.name(QColor.HexArgb)}; border-radius: 8px;")

        update_overlay(color)

        controls_layout.addWidget(lock_btn)
        controls_layout.addWidget(up_btn)
        controls_layout.addWidget(down_btn)
        layout.addWidget(controls)
        controls.setVisible(False)

        container.enterEvent = lambda event: (controls.setVisible(True), event.accept())
        container.leaveEvent = lambda event: (controls.setVisible(False), event.accept())

        def toggle_lock() -> None:
            nonlocal color
            if index in self.locked:
                self.locked.pop(index, None)
                lock_btn.setText("Lock")
            else:
                current = self.edited.get(index, color)
                self.locked[index] = current
                lock_btn.setText("Unlock")

        def adjust(amount: float) -> None:
            nonlocal color
            current = self.locked.get(index, self.edited.get(index, color))
            rgb = self._hex_to_rgb(current)
            h, l, s = self._rgb_to_hsl(rgb)
            l = max(0.0, min(1.0, l + amount))
            new_color = self._hsl_to_hex(h, l, s)
            container.setStyleSheet(f"background-color: {new_color};")
            color = new_color
            if index in self.locked:
                self.locked[index] = new_color
            else:
                self.edited[index] = new_color
            update_overlay(new_color)

        def _copy_current_color(_event) -> None:
            QApplication.clipboard().setText(color)

        container.mousePressEvent = _copy_current_color
        lock_btn.clicked.connect(toggle_lock)
        up_btn.clicked.connect(lambda: adjust(0.05))
        down_btn.clicked.connect(lambda: adjust(-0.05))
        return container

    def refresh_palette(self) -> None:
        raw = self.hex_input.text().strip()
        if not raw.startswith("#"):
            raw = "#" + raw
        try:
            rgb = self._hex_to_rgb(raw)
        except Exception:
            return

        count = int(self.count_combo.currentText())
        self.palette = self._build_palette(raw, count)

        self.locked = {k: v for k, v in self.locked.items() if k < count}
        self.edited = {k: v for k, v in self.edited.items() if k < count}
        for idx in range(len(self.palette)):
            if idx in self.locked:
                self.palette[idx] = self.locked[idx]
            elif idx in self.edited:
                self.palette[idx] = self.edited[idx]

        self.color_preview.setStyleSheet(f"background:{raw}; border-radius:8px;")
        self.color_preview.setText(raw)
        self.rgb_label.setText(f"RGB: {rgb[0]}, {rgb[1]}, {rgb[2]}")
        h, l, s = self._rgb_to_hsl(rgb)
        self.hsl_label.setText(f"HSL: {int(h * 360)}°, {int(s * 100)}%, {int(l * 100)}%")

        self._clear_swatches()
        for idx, color in enumerate(self.palette):
            swatch = self._create_swatch(color, idx)
            self.swatch_layout.addWidget(swatch, 0, idx)
        for col in range(len(self.palette)):
            self.swatch_layout.setColumnStretch(col, 1)
        self.swatch_layout.setRowStretch(0, 1)

    def pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.hex_input.text().strip() or "#00ecb8"), self, "Pick Base Color")
        if color.isValid():
            self.hex_input.setText(color.name())

    def randomize_base(self) -> None:
        rgb = tuple(random.randint(20, 235) for _ in range(3))
        self.hex_input.setText(f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}")

    def copy_all_hex(self) -> None:
        if not self.palette:
            return
        QApplication.clipboard().setText("\n".join(self.palette))

    def copy_css_vars(self) -> None:
        if not self.palette:
            return
        css = "\n".join(f"--color-{i+1}: {hex_value};" for i, hex_value in enumerate(self.palette))
        QApplication.clipboard().setText(css)

    def copy_gradient(self) -> None:
        if not self.palette:
            return
        n = len(self.palette)
        stops = [f"{hex_value} {int(i / max(1, n - 1) * 100)}%" for i, hex_value in enumerate(self.palette)]
        gradient = f"background: linear-gradient(90deg, {', '.join(stops)});"
        QApplication.clipboard().setText(gradient)

    def export_txt(self) -> None:
        if not self.palette:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export HEX Palette", "palette.txt", "Text Files (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(self.palette) + "\n")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def export_png(self) -> None:
        if not self.palette:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Palette PNG", "palette.png", "PNG Images (*.png)")
        if not path:
            return
        swatch_width = 160
        height = 120
        width = swatch_width * len(self.palette)
        image = QImage(width, height, QImage.Format_RGB32)
        painter = QPainter(image)
        for idx, value in enumerate(self.palette):
            painter.fillRect(idx * swatch_width, 0, swatch_width, height, QColor(value))
        painter.end()
        if not image.save(path):
            QMessageBox.warning(self, "Export Failed", "Could not save PNG file.")

    def contrast_check(self) -> None:
        raw = self.hex_input.text().strip()
        if not raw.startswith("#"):
            raw = "#" + raw
        try:
            rgb = self._hex_to_rgb(raw)
        except Exception:
            return

        def luminance(color: tuple[int, int, int]) -> float:
            values = []
            for channel in color:
                value = channel / 255.0
                if value <= 0.03928:
                    values.append(value / 12.92)
                else:
                    values.append(((value + 0.055) / 1.055) ** 2.4)
            return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]

        def ratio(a: float, b: float) -> float:
            hi, lo = (a, b) if a > b else (b, a)
            return (hi + 0.05) / (lo + 0.05)

        base = luminance(rgb)
        white = luminance((255, 255, 255))
        black = luminance((0, 0, 0))
        QMessageBox.information(
            self,
            "Contrast Check",
            f"Contrast vs white: {ratio(base, white):.1f}\nContrast vs black: {ratio(base, black):.1f}",
        )

    def apply_dark_variant(self) -> None:
        raw = self.hex_input.text().strip()
        if not raw.startswith("#"):
            raw = "#" + raw
        try:
            rgb = self._hex_to_rgb(raw)
        except Exception:
            return
        h, l, s = self._rgb_to_hsl(rgb)
        dark = self._hsl_to_hex(h, 1.0 - l, s)
        QApplication.clipboard().setText(dark)
        QMessageBox.information(self, "Dark Variant", f"Copied: {dark}")

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space:
            count = int(self.count_combo.currentText())
            base = self.hex_input.text().strip()
            if not base.startswith("#"):
                base = "#" + base
            self.locked = {k: v for k, v in self.locked.items() if k < count}
            palette = self._build_palette(base, count)
            for idx in range(count):
                if idx in self.locked:
                    palette[idx] = self.locked[idx]
                else:
                    palette[idx] = self._random_variation(palette[idx])
            self.edited = {k: v for k, v in self.edited.items() if k in self.locked}
            self.palette = palette
            self._clear_swatches()
            for idx, color in enumerate(self.palette):
                swatch = self._create_swatch(color, idx)
                self.swatch_layout.addWidget(swatch, 0, idx)
            for col in range(len(self.palette)):
                self.swatch_layout.setColumnStretch(col, 1)
            self.swatch_layout.setRowStretch(0, 1)
            event.accept()
            return
        super().keyPressEvent(event)
