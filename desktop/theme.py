"""Light/dark color tokens, chosen from the OS appearance setting."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPalette

import fonts

LIGHT = {
    "bg": "#faf7f0",
    "surface": "#ffffff",
    "border": "#e6ddc9",
    "ink": "#2a241c",
    "muted": "#8a7f6b",
    "curated": "#7a3b2e",
    "curated_hover": "#8a4a3c",
    "semantic": "#2e5c7a",
    "hover_bg": "#fff9ee",
    "highlight": "#fbe38a",
    "words_of_christ": "#c0392b",
    "scofield": "#2e7d4f",
}

DARK = {
    "bg": "#1c1a17",
    "surface": "#26221c",
    "border": "#42392c",
    "ink": "#ece6d9",
    "muted": "#a89d87",
    "curated": "#e0937a",
    "curated_hover": "#e8a794",
    "semantic": "#7fb3d8",
    "hover_bg": "#332c22",
    "highlight": "#6e5220",
    "words_of_christ": "#ff6b5e",
    "scofield": "#6fcf97",
}


def is_dark() -> bool:
    scheme = QGuiApplication.styleHints().colorScheme()
    if scheme != Qt.ColorScheme.Unknown:
        return scheme == Qt.ColorScheme.Dark
    # fall back to a luminance check on the default palette, in case the
    # platform doesn't report a color scheme directly
    window_color = QGuiApplication.palette().color(QPalette.ColorRole.Window)
    return window_color.lightnessF() < 0.5


def colors() -> dict:
    return DARK if is_dark() else LIGHT


def build_app_stylesheet(c: dict) -> str:
    """Lives here (not main.py) so main_window.py can re-apply it on a
    font-scale change without a circular import (main.py imports
    MainWindow from main_window.py)."""
    return f"""
    QMainWindow, QWidget {{ background: {c['bg']}; color: {c['ink']}; font-family: Georgia, "Times New Roman"; font-size: {fonts.px(14)}px; }}
    QComboBox, QLineEdit {{
        padding: 6px 8px; border: 1px solid {c['border']}; border-radius: 6px;
        background: {c['surface']}; color: {c['ink']};
    }}
    QPushButton {{ padding: 6px 14px; border: none; border-radius: 6px; background: {c['curated']}; color: white; }}
    QPushButton:hover {{ background: {c['curated_hover']}; }}
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{ padding: 8px 16px; background: transparent; color: {c['ink']}; }}
    QTabBar::tab:selected {{ font-weight: bold; color: {c['curated']}; }}
    QScrollArea {{ background: transparent; border: none; }}
    /* Explicit indicator rule: a broad QWidget background rule above
       otherwise makes Qt fall back to an unstyled (near-invisible)
       checkbox indicator. */
    QCheckBox::indicator {{
        width: 16px; height: 16px; border: 1px solid {c['border']};
        border-radius: 3px; background: {c['surface']};
    }}
    QCheckBox::indicator:checked {{ background: {c['curated']}; border-color: {c['curated']}; }}
    QCheckBox::indicator:hover {{ border-color: {c['curated']}; }}
    """
