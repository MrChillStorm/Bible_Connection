import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

import db_bootstrap
import fonts
from db import get_user_connection
from main_window import MainWindow
from reading_state import get_font_scale
from theme import build_app_stylesheet, colors


def _extract_bible_db_with_notice(app: QApplication) -> None:
    """Shows a brief notice while the one-time database extraction
    runs, so a slower disk doesn't make the app look frozen on its
    very first launch."""
    notice = QLabel("Setting up your Bible library -- this only happens once...")
    notice.setWindowFlag(Qt.FramelessWindowHint)
    notice.setAlignment(Qt.AlignCenter)
    notice.setStyleSheet(
        "background: #2b2b2b; color: white; padding: 24px; font-size: 14px;"
    )
    notice.adjustSize()
    screen = app.primaryScreen().geometry()
    notice.move(
        screen.center().x() - notice.width() // 2,
        screen.center().y() - notice.height() // 2,
    )
    notice.show()
    app.processEvents()

    try:
        db_bootstrap.extract_bible_db()
    except Exception as exc:
        notice.close()
        QMessageBox.critical(None, "Bible Connection", f"Couldn't set up the Bible database:\n\n{exc}")
        sys.exit(1)

    notice.close()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    if not db_bootstrap.bible_db_ready():
        _extract_bible_db_with_notice(app)

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
