"""clipboard_tool: the system's wl-paste first, else Akousousin's bundled copy."""
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import logos_plasma as lp  # noqa: E402


class TestClipboardTool(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.helpers = Path(folder.name) / "helpers"

    def bundle(self):
        exe = self.helpers / "wl-paste" / "bin" / "wl-paste"
        exe.parent.mkdir(parents=True)
        (self.helpers / "wl-paste" / "lib").mkdir()
        exe.write_text("#!/bin/sh\n")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
        return exe

    def test_system_copy_wins(self):
        self.bundle()
        with mock.patch.object(lp, "AKOUSOUSIN_HELPERS", self.helpers), \
                mock.patch.object(lp.shutil, "which", return_value="/usr/bin/wl-paste"):
            self.assertEqual(lp.clipboard_tool("wl-paste"), ("/usr/bin/wl-paste", None))

    def test_akousousin_copy_when_system_has_none(self):
        exe = self.bundle()
        with mock.patch.object(lp, "AKOUSOUSIN_HELPERS", self.helpers), \
                mock.patch.object(lp.shutil, "which", return_value=None):
            path, env = lp.clipboard_tool("wl-paste")
        self.assertEqual(path, str(exe))
        self.assertEqual(env["LD_LIBRARY_PATH"], str(self.helpers / "wl-paste" / "lib"))

    def test_neither(self):
        with mock.patch.object(lp, "AKOUSOUSIN_HELPERS", self.helpers), \
                mock.patch.object(lp.shutil, "which", return_value=None):
            self.assertEqual(lp.clipboard_tool("wl-paste"), (None, None))


if __name__ == "__main__":
    unittest.main()
