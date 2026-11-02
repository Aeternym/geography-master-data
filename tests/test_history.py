import sqlite3
import tempfile
import unittest
from pathlib import Path

from geo_reference.demo import create_demo
from geo_reference.history import history_violations


class HistoryTest(unittest.TestCase):
    def test_valid_demo_history_has_no_violations(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            self.assertEqual([], history_violations(connection))
            connection.close()


if __name__ == "__main__":
    unittest.main()

