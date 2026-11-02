from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ALLOWED_NORMALIZATION_STATUSES, SPEC_BY_TABLE
from .sql_checks import run_sql_checks_connection


SQL_REQUIRED_TABLES = {
    "normalization_status_rule",
    "geo_country",
    "geo_region",
    "geo_locality",
    "source_normalization",
    "locality_external_ids",
    "history_country",
    "history_region",
    "history_locality",
    "quarantine_record",
    "quarantine_summary",
}


def _issue(check: str, severity: str, count: int, action: str, sample=None) -> dict:
    return {
        "check": check,
        "severity": severity,
        "count": count,
        "recommended_action": action,
        "sample": sample or [],
    }


def _severity(check: str) -> str:
    if check in {"invalid_normalization_status", "locality_region_country_mismatch", "foreign_keys"}:
        return "CRITICAL"
    if "timezone" in check:
        return "MEDIUM"
    if "quarantine" in check:
        return "HIGH"
    return "HIGH"


def validate_database(database: Path) -> dict:
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"Database not found: {database}")
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    issues = []
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = set(SPEC_BY_TABLE)
        missing_tables = sorted(required - tables)
        if missing_tables:
            issues.append(_issue("required_tables", "CRITICAL", len(missing_tables), "Create all required tables before loading data", missing_tables))
        if "normalization_status_rule" not in tables:
            issues.append(_issue("normalization_status_rule_table", "CRITICAL", 1, "Restore the shared normalization status rule table"))

        for table, spec in SPEC_BY_TABLE.items():
            if table not in tables:
                continue
            actual = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            missing_columns = [column for column in spec.columns if column not in actual]
            if missing_columns:
                issues.append(_issue(f"{table}_required_columns", "CRITICAL", len(missing_columns), "Restore the required columns", missing_columns))

        fk_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        if fk_rows:
            issues.append(_issue("foreign_keys", "CRITICAL", len(fk_rows), "Quarantine or repair orphan records", fk_rows[:10]))

        if "normalization_status_rule" in tables:
            database_statuses = {row[0] for row in connection.execute("SELECT status FROM normalization_status_rule")}
            if database_statuses != ALLOWED_NORMALIZATION_STATUSES:
                details = sorted(database_statuses ^ ALLOWED_NORMALIZATION_STATUSES)
                issues.append(_issue("normalization_status_rule_consistency", "CRITICAL", len(details), "Keep Python and database status rules identical", details))

        if SQL_REQUIRED_TABLES.issubset(tables):
            sql_result = run_sql_checks_connection(connection)
            for check in sql_result["checks"]:
                if check["count"]:
                    issues.append(_issue(
                        check["check"],
                        _severity(check["check"]),
                        check["count"],
                        "Review affected source records; do not coerce conflicts into successful matches",
                        check["sample"],
                    ))
        else:
            sql_result = {
                "verdict": "NOT_RUN",
                "violations": 0,
                "checks": [],
                "reason": "Required tables are missing",
            }

        status_counts = dict(connection.execute(
            "SELECT normalization_status, COUNT(*) FROM source_normalization GROUP BY normalization_status"
        )) if "source_normalization" in tables else {}
        quarantine = connection.execute(
            "SELECT status, COUNT(*) FROM quarantine_record GROUP BY status"
        ).fetchall() if "quarantine_record" in tables else []
        row_counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in sorted(required & tables)
        }
    finally:
        connection.close()

    return {
        "database": str(database),
        "verdict": "PASS" if not issues else "NOT_READY",
        "scope": "implemented_checks_only",
        "production_readiness": "not_assessed_by_a_PASS_result",
        "issues": issues,
        "issue_count": sum(item["count"] for item in issues),
        "row_counts": row_counts,
        "normalization_status_counts": status_counts,
        "quarantine_status_counts": dict(quarantine),
        "sql_integrity": sql_result,
    }


def write_report(report: dict, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Data Quality Report",
        "",
        f"**Verdict:** {report['verdict']}",
        "",
        "A PASS means only that the implemented checks found no violations. It does not prove full business compliance or production readiness.",
        "",
        "## Row counts",
        "",
        "| Table | Rows |",
        "|---|---:|",
    ]
    lines.extend(f"| `{table}` | {count} |" for table, count in report["row_counts"].items())
    lines.extend(["", "## Confirmed issues", ""])
    if report["issues"]:
        lines.extend(["| Check | Severity | Count | Recommended action |", "|---|---|---:|---|"])
        for item in report["issues"]:
            action = item["recommended_action"].replace("|", "/")
            lines.append(f"| `{item['check']}` | {item['severity']} | {item['count']} | {action} |")
    else:
        lines.append("No violations were found by the implemented checks. This does not prove source completeness or production readiness.")
    lines.extend(["", "## Normalization states", "", "| State | Rows |", "|---|---:|"])
    lines.extend(f"| `{status}` | {count} |" for status, count in report["normalization_status_counts"].items())
    lines.extend(["", "## Quarantine", "", "| State | Rows |", "|---|---:|"])
    lines.extend(f"| `{status}` | {count} |" for status, count in report["quarantine_status_counts"].items())
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
