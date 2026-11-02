import sqlite3
import tempfile
import unittest
from pathlib import Path

from geo_reference.demo import create_demo


class QuarantineTest(unittest.TestCase):
    def test_nonmatched_cases_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            statuses = dict(connection.execute("SELECT status, COUNT(*) FROM quarantine_record GROUP BY status"))
            canonical_conflicts = connection.execute("SELECT COUNT(*) FROM source_normalization WHERE normalization_status='source_conflict' AND normalized_locality_id IS NOT NULL").fetchone()[0]
            connection.close()
            self.assertEqual(0, canonical_conflicts)
            self.assertGreaterEqual(statuses.get("source_conflict", 0), 1)
            self.assertGreaterEqual(statuses.get("unresolved", 0), 1)
            self.assertGreaterEqual(statuses.get("ambiguous", 0), 1)


if __name__ == "__main__":
    unittest.main()

