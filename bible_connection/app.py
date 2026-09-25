import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from bible_connection.core import db_bootstrap
from bible_connection.core.db import get_user_connection
from bible_connection.core.reading_state import get_font_scale
from bible_connection.ui import fonts
from bible_connection.ui.main_window import MainWindow
from bible_connection.ui.theme import build_app_stylesheet, colors


def _extract_bible_db_with_notice(app: QApplication) -> None:
    """Shows a brief notice while the database extraction runs (first
    launch, and the first one after an update), so a slower disk
    doesn't make the app look frozen."""
    notice = QLabel("Setting up your Bible library -- only after installing or updating...")
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

