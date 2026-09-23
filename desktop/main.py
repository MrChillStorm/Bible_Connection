import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtWidgets import QApplication

import fonts
from db import get_user_connection
from main_window import MainWindow
from reading_state import get_font_scale
from theme import build_app_stylesheet, colors


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # loaded before any widget is built, so the very first paint is
    # already at the user's last-chosen size, not a flash of 100% that
    # then jumps
    saved_scale = get_font_scale(get_user_connection())
    if saved_scale is not None:
        fonts.set_scale(saved_scale)

    app.setStyleSheet(build_app_stylesheet(colors()))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
