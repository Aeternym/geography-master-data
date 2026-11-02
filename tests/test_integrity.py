import sqlite3
import tempfile
import unittest
from pathlib import Path

from geo_reference.demo import create_demo
from geo_reference.validation import validate_database


class IntegrityTest(unittest.TestCase):
    def test_demo_passes_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            report = validate_database(output)
            self.assertEqual("PASS", report["verdict"], report["issues"])

    def test_database_rejects_orphan_locality(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            connection.execute("PRAGMA foreign_keys=ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO geo_locality(locality_id,country_id,region_id,is_active) VALUES (99999,101,99999,1)")
            connection.close()

    def test_missing_timezone_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            connection.execute("UPDATE geo_locality SET timezone_name=NULL WHERE locality_id=10001")
            connection.commit()
            connection.close()
            report = validate_database(output)
            self.assertTrue(any(item["check"] == "locality_without_timezone" for item in report["issues"]))

    def test_country_region_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            connection.execute("UPDATE geo_locality SET country_id=102 WHERE locality_id=10001")
            connection.commit()
            connection.close()
            report = validate_database(output)
            self.assertTrue(any(item["check"] == "locality_region_country_mismatch" for item in report["issues"]))

    def test_invalid_external_code_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            connection.execute("UPDATE locality_external_ids SET okato_code='12X' WHERE locality_id=10001")
            connection.commit()
            connection.close()
            report = validate_database(output)
            self.assertTrue(any(item["check"] == "invalid_okato_code" for item in report["issues"]))

    def test_history_overlap_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            connection.execute("UPDATE history_locality SET valid_to='2025-01-01' WHERE locality_history_id=1")
            connection.commit()
            connection.close()
            report = validate_database(output)
            self.assertTrue(any(item["check"] == "locality_history_overlap" for item in report["issues"]))

    def test_inconsistent_status_rules_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("DELETE FROM normalization_status_rule WHERE status='matched_existing'")
            connection.commit()
            connection.close()
            report = validate_database(output)
            self.assertTrue(any(item["check"] == "normalization_status_rule_consistency" for item in report["issues"]))

    def test_quarantine_payload_problem_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo.db"
            create_demo(output)
            connection = sqlite3.connect(output)
            connection.execute("UPDATE quarantine_record SET payload_json='' WHERE quarantine_id=(SELECT MIN(quarantine_id) FROM quarantine_record)")
            connection.commit()
            connection.close()
            report = validate_database(output)
            self.assertTrue(any(item["check"] == "quarantine_missing_payload_or_reason" for item in report["issues"]))

    def test_incomplete_database_does_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "incomplete.db"
            connection = sqlite3.connect(output)
            connection.execute("CREATE TABLE geo_country(country_id INTEGER PRIMARY KEY)")
            connection.commit()
            connection.close()
            report = validate_database(output)
            self.assertEqual("NOT_READY", report["verdict"])
            self.assertTrue(any(item["check"] == "required_tables" for item in report["issues"]))


if __name__ == "__main__":
    unittest.main()

