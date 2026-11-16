"""The logos_databases switch: off means no Logos database is opened, and the
features built on them return nothing instead of failing."""
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "logos_plasma", Path(__file__).resolve().parent.parent / "backend" / "logos_plasma.py")
lp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lp)


class DataSwitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        docs = Path(self.tmp.name) / "Documents" / "u1"
        (docs / "LayoutManager").mkdir(parents=True)
        with sqlite3.connect(docs / "LayoutManager" / "layouts.db") as db:
            db.execute("CREATE TABLE Layouts (Title TEXT, CreatedDate TEXT, IsDeleted INTEGER)")
            db.executemany("INSERT INTO Layouts VALUES (?, '2026-11-16', 0)",
                           [("Sermon prep",), ("Application Closed",), ("Greek",)])
        self.lib = lp.Library()
        self.lib.docs_dir = docs
        self.lib.data_dir = Path(self.tmp.name) / "Data" / "u1"
        lp.LOGOS_DATA["enabled"] = True

    def tearDown(self):
        lp.LOGOS_DATA["enabled"] = True
        self.tmp.cleanup()

    def test_on_reads_layouts(self):
        self.assertEqual(self.lib.layouts(), ["Greek", "Sermon prep"])

    def test_off_returns_nothing(self):
        lp.LOGOS_DATA["enabled"] = False
        self.assertEqual(self.lib.layouts(), [])
        self.assertEqual(self.lib.reading_plans("logosres:{logosres}"), [])
        self.assertIsNone(self.lib.sermon_passage())
        self.assertEqual(self.lib.showcase(), [])

    def test_off_never_opens_a_database(self):
        lp.LOGOS_DATA["enabled"] = False
        with self.assertRaises(lp.LogosDataOff):
            lp.ro_connect(self.lib.docs_dir / "LayoutManager" / "layouts.db")

    def test_off_refresh_clears_bibles(self):
        lp.LOGOS_DATA["enabled"] = False
        self.lib.bibles = ["x"]
        self.lib.refresh()
        self.assertEqual(self.lib.bibles, [])
        self.assertIn("turned off", self.lib.error)

    def test_setting_controls_switch(self):
        cfg = lp.Config()
        cfg.settings = {**lp.DEFAULTS["settings"], "logos_databases": False}
        lp.LOGOS_DATA["enabled"] = bool(cfg.settings["logos_databases"])
        self.assertFalse(lp.LOGOS_DATA["enabled"])
        self.assertIn("logos_databases", lp.DEFAULTS["settings"])


if __name__ == "__main__":
    unittest.main()
