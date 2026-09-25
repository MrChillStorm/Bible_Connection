"""Smoke tests: the shipped database extracts, the queries the app makes
answer, and the window opens and reads a chapter. Runs offscreen, in a
throwaway data folder (BIBLE_CONNECTION_HOME), so your own reading
history is never touched:

    python3 -m unittest discover tests
"""
import importlib.util
import os
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

_home = tempfile.TemporaryDirectory()
os.environ["BIBLE_CONNECTION_HOME"] = _home.name  # before anything reads it
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from bible_connection.core import db, db_bootstrap
from bible_connection.core.chapters import get_chapter
from bible_connection.core.connections import find_verse, get_connections, search_text, verse_ref
from bible_connection.core.reading_state import get_font_scale
from bible_connection.core.strongs import get_entry

app = QApplication.instance() or QApplication([])


def setUpModule():
    db_bootstrap.extract_bible_db()


def tearDownModule():
    _home.cleanup()


class DatabaseTest(unittest.TestCase):
    def test_lives_in_the_data_folder(self):
        self.assertEqual(db.DB_PATH.parent, Path(_home.name))
        self.assertEqual(db.USER_DB_PATH.parent, Path(_home.name))
        self.assertTrue(db_bootstrap.bible_db_ready())

    def test_first_launch_without_reading_history(self):
        db.USER_DB_PATH.unlink(missing_ok=True)
        conn = db.get_user_connection()
        self.assertIsNone(get_font_scale(conn))  # what the app asks before its window exists
        conn.close()

    def test_a_new_zip_is_extracted_again(self):
        source = db_bootstrap.SOURCE_PATH.read_text()
        try:
            db_bootstrap.SOURCE_PATH.write_text("00000000 0\n")  # as if an update shipped another zip
            self.assertFalse(db_bootstrap.bible_db_ready())
            db_bootstrap.SOURCE_PATH.unlink()  # a database built by hand is left alone
            self.assertTrue(db_bootstrap.bible_db_ready())
        finally:
            db_bootstrap.SOURCE_PATH.write_text(source)
        self.assertTrue(db_bootstrap.bible_db_ready())

    def test_queries(self):
        conn = db.get_connection()
        row = find_verse(conn, "John 3:16")
        self.assertEqual(verse_ref(row), "John 3:16")
        self.assertIn("God so loved the world", row["text"])
        curated, semantic = get_connections(conn, row["id"], limit=5)
        self.assertTrue(curated and semantic)
        self.assertTrue(search_text(conn, "shepherd", limit=5))
        word = unicodedata.normalize("NFC", get_entry(conn, "G26")["original_word"])
        self.assertEqual(word, unicodedata.normalize("NFC", "ἀγάπη"))
        self.assertEqual(len(get_chapter(conn, "Psalms", 23)), 6)
        conn.close()


class WindowTest(unittest.TestCase):
    def test_opens_and_reads_a_chapter(self):
        from bible_connection.ui.main_window import MainWindow

        window = MainWindow()
        window.show()
        window._navigate_to("John", 3, 16)
        app.processEvents()
        self.assertEqual((window.reading_pane.book, window.reading_pane.chapter), ("John", 3))
        self.assertIn("God so loved the world", window.reading_pane.browser.toPlainText())
        window.close()
        window.conn.close()
        window.user_conn.close()


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "the web API is an optional extra")
class ApiTest(unittest.TestCase):
    def test_verse_and_stats(self):
        from bible_connection import api

        verse = api.api_verse(ref="Genesis 1:1", limit=3)
        self.assertEqual(verse["verse"]["ref"], "Genesis 1:1")
        self.assertGreater(api.api_stats()["verses"], 31000)


if __name__ == "__main__":
    unittest.main()
