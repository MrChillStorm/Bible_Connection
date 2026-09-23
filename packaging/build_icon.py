"""Regenerates Bible Connection.app's icon from packaging/icon.svg --
run this after editing the SVG. Uses PySide6's QSvgRenderer (already a
project dependency, via desktop/cards.py's own _svg_icon()) rather than
pulling in Pillow or another image library just for this.

macOS only -- relies on the built-in `iconutil` command.
"""
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = Path(__file__).resolve().parent / "icon.svg"
ICONSET_DIR = Path(__file__).resolve().parent / "AppIcon.iconset"
ICNS_DEST = ROOT / "Bible Connection.app" / "Contents" / "Resources" / "AppIcon.icns"

# name -> pixel size, per Apple's required iconset naming convention
SIZES = {
    "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
}


def main() -> None:
    app = QApplication(sys.argv)
    svg_bytes = SVG_PATH.read_bytes()

    ICONSET_DIR.mkdir(exist_ok=True)
    for name, size in SIZES.items():
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        if not renderer.isValid():
            raise SystemExit(f"{SVG_PATH} failed to parse -- check for stray '--' inside XML comments")
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        pixmap.save(str(ICONSET_DIR / name))

    ICNS_DEST.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ICNS_DEST)], check=True)
    print(f"Wrote {ICNS_DEST}")


if __name__ == "__main__":
    main()
