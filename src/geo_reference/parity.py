from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from .models import SPECS


BOOLEAN_COLUMNS = {"is_active", "is_current", "release_blocker"}
STABLE_KEY_COLUMNS = {
    "workbook_readme": "topic",
    "geo_country": "country_id",
    "geo_region": "region_id",
    "geo_locality": "locality_id",
    "source_normalization": "mapping_id",
    "history_country": "country_history_id",
    "history_region": "region_history_id",
    "history_locality": "locality_history_id",
    "source_registry": "source_code",
    "dq_backlog": "issue_id",
    "quarantine_summary": "gar_region_code",
}


def _normalize(column: str, value):
    if value is None:
        return ["null", None]
    if column in BOOLEAN_COLUMNS:
        return ["bool", bool(value)]
    if isinstance(value, (datetime, date)):
        return ["text", value.isoformat()]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, float):
        return ["float", repr(value)]
    return ["text", str(value)]


def _canonical(columns: tuple[str, ...], values) -> str:
    return json.dumps(
        [_normalize(column, value) for column, value in zip(columns, values)],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _type_name(column: str, value) -> str:
    return _normalize(column, value)[0]


def _hash_keys(values) -> str:
    digest = hashlib.sha256()
    for value in sorted((json.dumps(value, ensure_ascii=False, default=str) for value in values)):
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def verify_parity(source: Path, database: Path) -> dict:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("Parity verification requires openpyxl") from exc

    source = Path(source)
    database = Path(database)
    if not source.is_file():
        raise FileNotFoundError(f"Workbook not found: {source}")
    if not database.is_file():
        raise FileNotFoundError(f"Database not found: {database}")

    workbook = openpyxl.load_workbook(source, read_only=True, data_only=False)
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    table_results = []
    try:
        actual_sheets = tuple(workbook.sheetnames)
        expected_sheets = tuple(spec.sheet for spec in SPECS)
        sheet_sequence_match = actual_sheets == expected_sheets
        database_tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}

        for spec in SPECS:
            result = {
                "sheet": spec.sheet,
                "table": spec.table,
                "source_columns": [],
                "database_source_columns": [],
                "database_extra_columns": [],
                "columns_match": False,
                "source_rows": 0,
                "database_rows": 0,
                "row_count_match": False,
                "source_sha256": None,
                "database_sha256": None,
                "content_hash_match": False,
                "value_mismatch_samples": [],
                "source_types": {},
                "database_types": {},
                "leading_zero_values": 0,
                "leading_zero_mismatches": 0,
                "stable_key_match": None,
            }
            if spec.sheet not in workbook.sheetnames or spec.table not in database_tables:
                result["error"] = "Source sheet or database table is missing"
                table_results.append(result)
                continue

            sheet_rows = workbook[spec.sheet].iter_rows(values_only=True)
            source_columns = tuple(next(sheet_rows, ()))
            all_db_columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{spec.table}")')]
            database_source_columns = tuple(name for name in all_db_columns if name in spec.columns)
            result["source_columns"] = list(source_columns)
            result["database_source_columns"] = list(database_source_columns)
            result["database_extra_columns"] = [name for name in all_db_columns if name not in spec.columns]
            result["columns_match"] = source_columns == spec.columns == database_source_columns
            if not result["columns_match"]:
                table_results.append(result)
                continue

            quoted = ",".join(f'"{column}"' for column in spec.columns)
            database_rows = connection.execute(f'SELECT {quoted} FROM "{spec.table}" ORDER BY rowid')
            source_digest = hashlib.sha256()
            database_digest = hashlib.sha256()
            source_type_counts = {column: Counter() for column in spec.columns}
            database_type_counts = {column: Counter() for column in spec.columns}
            source_keys = []
            database_keys = []
            key_column = STABLE_KEY_COLUMNS.get(spec.table)
            key_index = spec.columns.index(key_column) if key_column else None

            row_number = 0
            while True:
                source_row = next(sheet_rows, None)
                while source_row is not None and all(value is None for value in source_row[: len(spec.columns)]):
                    source_row = next(sheet_rows, None)
                database_row = database_rows.fetchone()
                if source_row is None and database_row is None:
                    break
                row_number += 1
                if source_row is not None:
                    source_row = tuple(source_row[: len(spec.columns)])
                    source_digest.update(_canonical(spec.columns, source_row).encode("utf-8") + b"\n")
                    result["source_rows"] += 1
                    for column, value in zip(spec.columns, source_row):
                        source_type_counts[column][_type_name(column, value)] += 1
                    if key_index is not None:
                        source_keys.append(_normalize(key_column, source_row[key_index]))
                if database_row is not None:
                    database_digest.update(_canonical(spec.columns, database_row).encode("utf-8") + b"\n")
                    result["database_rows"] += 1
                    for column, value in zip(spec.columns, database_row):
                        database_type_counts[column][_type_name(column, value)] += 1
                    if key_index is not None:
                        database_keys.append(_normalize(key_column, database_row[key_index]))
                if source_row is None or database_row is None:
                    if len(result["value_mismatch_samples"]) < 10:
                        result["value_mismatch_samples"].append({"row": row_number, "reason": "row_missing_on_one_side"})
                    continue
                for index, column in enumerate(spec.columns):
                    source_value = source_row[index]
                    database_value = database_row[index]
                    if _normalize(column, source_value) != _normalize(column, database_value):
                        if len(result["value_mismatch_samples"]) < 10:
                            result["value_mismatch_samples"].append({
                                "row": row_number,
                                "column": column,
                                "source": source_value,
                                "database": database_value,
                            })
                    if "code" in column.lower() and isinstance(source_value, str) and source_value.startswith("0"):
                        result["leading_zero_values"] += 1
                        if not isinstance(database_value, str) or database_value != source_value:
                            result["leading_zero_mismatches"] += 1

            result["source_sha256"] = source_digest.hexdigest()
            result["database_sha256"] = database_digest.hexdigest()
            result["row_count_match"] = result["source_rows"] == result["database_rows"]
            result["content_hash_match"] = result["source_sha256"] == result["database_sha256"]
            result["source_types"] = {column: dict(counts) for column, counts in source_type_counts.items()}
            result["database_types"] = {column: dict(counts) for column, counts in database_type_counts.items()}
            if key_column:
                result["stable_key_match"] = _hash_keys(source_keys) == _hash_keys(database_keys)
            table_results.append(result)

        foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        relation_checks = {
            "sqlite_foreign_key_violations": len(foreign_key_rows),
            "locality_region_country_mismatches": connection.execute(
                """SELECT COUNT(*) FROM geo_locality l JOIN geo_region r ON r.region_id=l.region_id
                   WHERE l.country_id<>r.country_id"""
            ).fetchone()[0] if {"geo_locality", "geo_region"}.issubset(database_tables) else None,
        }
    finally:
        connection.close()
        workbook.close()

    failed_tables = [
        item["sheet"] for item in table_results
        if not item["columns_match"]
        or not item["row_count_match"]
        or not item["content_hash_match"]
        or item["leading_zero_mismatches"]
        or item["stable_key_match"] is False
    ]
    passed = sheet_sequence_match and not failed_tables and relation_checks["sqlite_foreign_key_violations"] == 0
    return {
        "source": str(source),
        "database": str(database),
        "source_file_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "verdict": "PASS" if passed else "FAIL",
        "sheet_sequence_match": sheet_sequence_match,
        "failed_tables": failed_tables,
        "relations": relation_checks,
        "tables": table_results,
    }


def write_parity_report(report: dict, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Excel → SQLite parity report",
        "",
        f"**Verdict:** {report['verdict']}",
        "",
        f"**Workbook SHA-256:** `{report['source_file_sha256']}`",
        "",
        "| Sheet | Rows Excel | Rows SQLite | Columns | Hash | Leading zeros | Stable IDs |",
        "|---|---:|---:|---|---|---|---|",
    ]
    for item in report["tables"]:
        lines.append(
            f"| `{item['sheet']}` | {item['source_rows']} | {item['database_rows']} | "
            f"{'PASS' if item['columns_match'] else 'FAIL'} | "
            f"{'PASS' if item['content_hash_match'] else 'FAIL'} | "
            f"{'PASS' if item['leading_zero_mismatches'] == 0 else 'FAIL'} | "
            f"{'N/A' if item['stable_key_match'] is None else ('PASS' if item['stable_key_match'] else 'FAIL')} |"
        )
    lines.extend([
        "",
        "## Relationships",
        "",
        f"- SQLite foreign-key violations: {report['relations']['sqlite_foreign_key_violations']}",
        f"- Locality/region country mismatches: {report['relations']['locality_region_country_mismatches']}",
        "",
        "A PASS proves parity for the implemented structural and content checks. It does not prove upstream ETL reproducibility or production readiness.",
    ])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
