"""The last step after rebuilding: zips the rebuilt bible.db into the
package's data/bible.db.zip, the file that actually ships.

    python3 -m bible_connection.pipeline.pack
"""
from bible_connection.core.db import DB_PATH
from bible_connection.core.db_bootstrap import ZIP_PATH, pack_bible_db


def main() -> None:
    pack_bible_db()
    print(f"Packed {DB_PATH} ({DB_PATH.stat().st_size / 1e6:.0f} MB) "
          f"into {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
