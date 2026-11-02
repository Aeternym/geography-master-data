from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path

from .models import ALLOWED_NORMALIZATION_STATUSES, SPECS


FORBIDDEN_OUTPUT_SUFFIXES = {
    ".xlsx", ".xls", ".xlsm", ".xlsb", ".ods", ".rar", ".zip", ".7z"
}


def _canonical_row(values):
    encoded = []
    for value in values:
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        if value is None:
            encoded.append(["null", None])
        elif isinstance(value, bool):
            encoded.append(["bool", value])
        elif isinstance(value, int):
            encoded.append(["int", value])
        elif isinstance(value, float):
            encoded.append(["float", repr(value)])
        else:
            encoded.append(["text", str(value)])
    return json.dumps(encoded, ensure_ascii=False, separators=(",", ":"))


def _sqlite_value(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def initialize_database(connection: sqlite3.Connection) -> None:
    schema = (project_root() / "sql" / "schema.sql").read_text(encoding="utf-8")
    indexes = (project_root() / "sql" / "indexes.sql").read_text(encoding="utf-8")
    connection.executescript(schema)
    connection.executescript(indexes)


def _cleanup_sqlite_files(database: Path) -> None:
    for path in (database, Path(f"{database}-wal"), Path(f"{database}-shm")):
        if path.exists():
            path.unlink()


def _same_physical_file(source: Path, output: Path) -> bool:
    """Compare existing files by identity and non-existing paths canonically."""
    if output.exists():
        try:
            return os.path.samefile(source, output)
        except OSError:
            # Fall through to canonical path comparison when the platform cannot
            # obtain file identities. This still covers relative paths and links.
            pass
    return source.resolve(strict=True) == output.resolve(strict=False)


def _validate_import_paths(source: Path, output: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Workbook not found: {source}")
    if output.exists() and not output.is_file():
        raise ValueError(f"Output path is not a file: {output}")
    if _same_physical_file(source, output):
        raise ValueError("Input workbook and output database must be different physical files")
    if output.suffix.lower() in FORBIDDEN_OUTPUT_SUFFIXES:
        raise ValueError(
            f"Unsafe output extension {output.suffix!r}. Use a SQLite extension such as .db, .sqlite, or .sqlite3."
        )


def _load_workbook_to_database(source: Path, database: Path, openpyxl) -> dict:
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=False)
    expected_sheets = tuple(spec.sheet for spec in SPECS)
    actual_sheets = tuple(workbook.sheetnames)
    if actual_sheets != expected_sheets:
        workbook.close()
        raise ValueError(f"Unexpected sheet sequence. Expected {expected_sheets}; got {actual_sheets}")

    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    initialize_database(connection)
    manifest = {}
    try:
        for spec in SPECS:
            worksheet = workbook[spec.sheet]
            rows = worksheet.iter_rows(values_only=True)
            headers = tuple(next(rows, ()))
            if headers != spec.columns:
                raise ValueError(f"Unexpected columns in {spec.sheet}: {headers}")
            placeholders = ",".join("?" for _ in spec.columns)
            columns_sql = ",".join(f'"{column}"' for column in spec.columns)
            insert_sql = f'INSERT INTO "{spec.table}" ({columns_sql}) VALUES ({placeholders})'
            batch = []
            row_count = 0
            digest = hashlib.sha256()
            for row in rows:
                values = list(row[: len(spec.columns)])
                if len(values) < len(spec.columns):
                    values.extend([None] * (len(spec.columns) - len(values)))
                if all(value is None for value in values):
                    continue
                digest.update(_canonical_row(values).encode("utf-8"))
                digest.update(b"\n")
                batch.append(tuple(_sqlite_value(value) for value in values))
                row_count += 1
                if len(batch) >= 1000:
                    connection.executemany(insert_sql, batch)
                    batch.clear()
            if batch:
                connection.executemany(insert_sql, batch)
            sheet_hash = digest.hexdigest()
            connection.execute(
                "INSERT INTO import_manifest(sheet_name, table_name, source_rows, source_sha256) VALUES (?, ?, ?, ?)",
                (spec.sheet, spec.table, row_count, sheet_hash),
            )
            manifest[spec.sheet] = {"table": spec.table, "rows": row_count, "sha256": sheet_hash}
        connection.execute(
            "INSERT INTO import_run(source_path, source_file_sha256, source_size_bytes) VALUES (?, ?, ?)",
            (str(source.resolve()), source_sha256, source.stat().st_size),
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode = DELETE")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        workbook.close()
    return {"source_sha256": source_sha256, "database": str(database), "sheets": manifest}


def _verify_import_database(database: Path) -> dict:
    connection = sqlite3.connect(database)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise RuntimeError(f"Imported database has {len(foreign_keys)} foreign-key violations")
        manifest = {
            row[0]: {"table": row[1], "rows": row[2], "sha256": row[3]}
            for row in connection.execute("SELECT sheet_name, table_name, source_rows, source_sha256 FROM import_manifest")
        }
        if set(manifest) != {spec.sheet for spec in SPECS}:
            raise RuntimeError("Import manifest does not contain every expected sheet")
        for spec in SPECS:
            actual_columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{spec.table}")')]
            if [name for name in actual_columns if name in spec.columns] != list(spec.columns):
                raise RuntimeError(f"Imported table {spec.table} has an unexpected source-column sequence")
            actual_rows = connection.execute(f'SELECT COUNT(*) FROM "{spec.table}"').fetchone()[0]
            if actual_rows != manifest[spec.sheet]["rows"]:
                raise RuntimeError(f"Row count differs from import manifest for {spec.sheet}")
        status_rules = {row[0] for row in connection.execute("SELECT status FROM normalization_status_rule")}
        if status_rules != ALLOWED_NORMALIZATION_STATUSES:
            raise RuntimeError("Database normalization status rules differ from Python rules")
        return {"sqlite_integrity": integrity, "foreign_key_violations": 0, "manifest_sheets": len(manifest)}
    finally:
        connection.close()


def import_workbook(source: Path, output: Path, replace: bool = False) -> dict:
    source = Path(source)
    output = Path(output)
    _validate_import_paths(source, output)
    if output.exists() and not replace:
        raise FileExistsError(f"Output already exists: {output}. Use --replace to replace it explicitly.")

    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("Full import requires openpyxl. Install the project dependencies first.") from exc

    output.parent.mkdir(parents=True, exist_ok=True)

    temporary = output.parent / f".{output.name}.import-{uuid.uuid4().hex}.tmp"
    try:
        result = _load_workbook_to_database(source, temporary, openpyxl)
        result["pre_swap_verification"] = _verify_import_database(temporary)

        # Re-read both artifacts independently before replacing an existing
        # database. This catches value/type/hash mismatches not covered by the
        # structural import manifest.
        from .parity import verify_parity

        parity = verify_parity(source, temporary)
        if parity["verdict"] != "PASS":
            raise RuntimeError(f"Pre-swap Excel/SQLite parity failed for: {parity['failed_tables']}")
        result["pre_swap_parity"] = {
            "verdict": parity["verdict"],
            "tables": len(parity["tables"]),
            "failed_tables": parity["failed_tables"],
            "foreign_key_violations": parity["relations"]["sqlite_foreign_key_violations"],
        }

        # Repeat the identity check immediately before replacement to protect
        # against path changes while a long import is running.
        _validate_import_paths(source, output)

        # Existing WAL/SHM files can represent uncheckpointed changes or an open
        # connection. Refuse the swap instead of risking silent data loss.
        active_sidecars = [path for path in (Path(f"{output}-wal"), Path(f"{output}-shm")) if path.exists()]
        if active_sidecars:
            raise RuntimeError(f"Refusing to replace a database with active SQLite sidecar files: {active_sidecars}")

        os.replace(temporary, output)
        result["database"] = str(output)
        result["replacement"] = "atomic_after_successful_import_and_structural_verification"
        return result
    finally:
        _cleanup_sqlite_files(temporary)
