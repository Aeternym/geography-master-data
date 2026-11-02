import sqlite3
import tempfile
import unittest
from pathlib import Path

from geo_reference.import_excel import initialize_database
from geo_reference.models import ALLOWED_NORMALIZATION_STATUSES, SPEC_BY_TABLE
from geo_reference.sql_checks import run_sql_checks_connection


class SchemaTest(unittest.TestCase):
    def test_required_tables_and_columns_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            connection = sqlite3.connect(Path(tmp) / "schema.db")
            initialize_database(connection)
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue(set(SPEC_BY_TABLE).issubset(tables))
            for table, spec in SPEC_BY_TABLE.items():
                columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
                self.assertTrue(set(spec.columns).issubset(columns), table)
            status_rules = {row[0] for row in connection.execute("SELECT status FROM normalization_status_rule")}
            self.assertEqual(ALLOWED_NORMALIZATION_STATUSES, status_rules)
            connection.close()

    def test_sql_and_python_normalization_status_rules_are_consistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "demo.db"
            from geo_reference.demo import create_demo

            create_demo(database)
            connection = sqlite3.connect(database)
            connection.execute(
                """INSERT INTO source_normalization(
                       mapping_id, source_system, entity_type, normalized_country_id,
                       normalized_region_id, normalized_locality_id, normalization_status
                   ) VALUES (999, 'test', 'locality', 101, NULL, 10001, 'matched_country_region_unresolved')"""
            )
            result = run_sql_checks_connection(connection)
            invalid = next(item for item in result["checks"] if item["check"] == "invalid_normalization_status")
            unresolved_region = next(item for item in result["checks"] if item["check"] == "region_unresolved_status_inconsistent")
            rules = {row[0] for row in connection.execute("SELECT status FROM normalization_status_rule")}
            connection.close()
            self.assertEqual(ALLOWED_NORMALIZATION_STATUSES, rules)
            self.assertEqual(0, invalid["count"])
            self.assertEqual(0, unresolved_region["count"])


if __name__ == "__main__":
    unittest.main()

