import sqlite3
import tempfile
import unittest
from pathlib import Path

from geo_reference.demo import create_demo
from geo_reference.normalization import resolve_locality


class NormalizationTest(unittest.TestCase):
    def test_all_synthetic_cases_have_expected_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            result = create_demo(output)
            unexpected = [case for case in result["cases"] if case["status"] != case["expected"]]
            self.assertEqual([], unexpected)

    def test_same_name_different_fias_guids_is_not_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            rows = connection.execute("SELECT locality_id, fias_object_guid FROM locality_external_ids WHERE locality_id IN (10004,10005)").fetchall()
            connection.close()
            self.assertEqual(2, len(rows))
            self.assertEqual(2, len({row[1] for row in rows}))

    def test_conflicting_fias_guid_and_oktmo_returns_source_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            result = resolve_locality(connection, {
                "source_fias_guid": "11111111-1111-4111-8111-111111111111",
                "source_external_code": "00100000102",
            })
            connection.close()
            self.assertEqual("source_conflict", result.status)
            self.assertIsNone(result.locality_id)
            self.assertIsNone(result.country_id)
            self.assertIsNone(result.region_id)

    def test_external_code_and_different_country_returns_source_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            result = resolve_locality(connection, {
                "source_external_code": "00100000102",
                "source_country_value": "BB",
            })
            connection.close()
            self.assertEqual("source_conflict", result.status)
            self.assertIsNone(result.locality_id)

    def test_unknown_guid_is_not_ignored_in_favour_of_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            result = resolve_locality(connection, {
                "source_fias_guid": "99999999-9999-4999-8999-999999999999",
                "source_country_value": "AA",
                "source_region_value": "AA-NO",
                "source_locality_value": "Североград",
            })
            connection.close()
            self.assertEqual("unresolved", result.status)
            self.assertIsNone(result.locality_id)


if __name__ == "__main__":
    unittest.main()

