import hashlib
import io
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import openpyxl

from geo_reference.cli import main as cli_main
from geo_reference.import_excel import import_workbook
from geo_reference.models import SPECS
from geo_reference.parity import verify_parity


def create_minimal_workbook(path: Path) -> None:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for spec in SPECS:
        sheet = workbook.create_sheet(spec.sheet)
        sheet.append(spec.columns)
        if spec.sheet == "README":
            sheet.append(("fixture", "original"))
    workbook.save(path)
    workbook.close()


class ImportAndParityTest(unittest.TestCase):
    def test_same_input_and_output_is_rejected_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "fixture.xlsx"
            create_minimal_workbook(source)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            with patch("geo_reference.import_excel._load_workbook_to_database") as loader:
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = cli_main([
                        "import-excel",
                        "--input", str(source),
                        "--output", str(source),
                        "--replace",
                    ])
                self.assertEqual(2, exit_code)
                self.assertIn("different physical files", output.getvalue())
                loader.assert_not_called()
            self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_relative_and_absolute_paths_to_same_file_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.xlsx"
            create_minimal_workbook(source)
            previous = Path.cwd()
            try:
                os.chdir(root)
                with self.assertRaisesRegex(ValueError, "different physical files"):
                    import_workbook(Path("fixture.xlsx"), source.resolve(), replace=True)
            finally:
                os.chdir(previous)

    def test_hard_link_to_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.xlsx"
            output = root / "alias.db"
            create_minimal_workbook(source)
            try:
                os.link(source, output)
            except OSError as exc:
                self.skipTest(f"Hard links are unavailable: {exc}")
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "different physical files"):
                import_workbook(source, output, replace=True)
            self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_symbolic_link_to_input_is_rejected_when_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.xlsx"
            output = root / "alias.db"
            create_minimal_workbook(source)
            try:
                output.symlink_to(source)
            except OSError as exc:
                self.skipTest(f"Symbolic links are unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "different physical files"):
                import_workbook(source, output, replace=True)

    def test_unsafe_output_extension_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.xlsx"
            output = root / "database.zip"
            create_minimal_workbook(source)
            with patch("geo_reference.import_excel._load_workbook_to_database") as loader:
                with self.assertRaisesRegex(ValueError, "Unsafe output extension"):
                    import_workbook(source, output, replace=True)
                loader.assert_not_called()
            self.assertFalse(output.exists())

    def test_mutated_sqlite_row_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.xlsx"
            database = root / "fixture.db"
            create_minimal_workbook(source)
            import_workbook(source, database)
            self.assertEqual("PASS", verify_parity(source, database)["verdict"])
            connection = sqlite3.connect(database)
            connection.execute("UPDATE workbook_readme SET value='changed' WHERE topic='fixture'")
            connection.commit()
            connection.close()
            report = verify_parity(source, database)
            self.assertEqual("FAIL", report["verdict"])
            self.assertIn("README", report["failed_tables"])

    def test_corrupted_excel_does_not_replace_existing_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "broken.xlsx"
            source.write_bytes(b"not an xlsx archive")
            database = root / "existing.db"
            database.write_bytes(b"existing database sentinel")
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with self.assertRaises(Exception):
                import_workbook(source, database, replace=True)
            self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
            self.assertEqual([], list(root.glob(".existing.db.import-*.tmp*")))

    def test_failed_pre_swap_verification_preserves_existing_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.xlsx"
            create_minimal_workbook(source)
            database = root / "existing.db"
            database.write_bytes(b"previous valid artifact")
            before = database.read_bytes()
            with patch("geo_reference.import_excel._verify_import_database", side_effect=RuntimeError("forced verification failure")):
                with self.assertRaisesRegex(RuntimeError, "forced verification failure"):
                    import_workbook(source, database, replace=True)
            self.assertEqual(before, database.read_bytes())
            self.assertEqual([], list(root.glob(".existing.db.import-*.tmp*")))

    def test_failed_pre_swap_parity_preserves_existing_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.xlsx"
            create_minimal_workbook(source)
            database = root / "existing.db"
            database.write_bytes(b"previous valid artifact")
            before = database.read_bytes()
            with patch("geo_reference.parity.verify_parity", return_value={
                "verdict": "FAIL",
                "failed_tables": ["README"],
                "tables": [],
                "relations": {"sqlite_foreign_key_violations": 0},
            }):
                with self.assertRaisesRegex(RuntimeError, "parity failed"):
                    import_workbook(source, database, replace=True)
            self.assertEqual(before, database.read_bytes())
            self.assertEqual([], list(root.glob(".existing.db.import-*.tmp*")))

    def test_repeat_import_requires_replace_and_then_succeeds_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.xlsx"
            database = root / "fixture.db"
            create_minimal_workbook(source)
            import_workbook(source, database)
            with self.assertRaises(FileExistsError):
                import_workbook(source, database)
            result = import_workbook(source, database, replace=True)
            self.assertEqual("atomic_after_successful_import_and_structural_verification", result["replacement"])
            self.assertEqual("PASS", verify_parity(source, database)["verdict"])

    def test_active_output_wal_prevents_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.xlsx"
            database = root / "fixture.db"
            create_minimal_workbook(source)
            import_workbook(source, database)
            before = database.read_bytes()
            Path(f"{database}-wal").write_bytes(b"active")
            with self.assertRaisesRegex(RuntimeError, "sidecar"):
                import_workbook(source, database, replace=True)
            self.assertEqual(before, database.read_bytes())
            self.assertEqual([], list(root.glob(".fixture.db.import-*.tmp*")))


if __name__ == "__main__":
    unittest.main()
