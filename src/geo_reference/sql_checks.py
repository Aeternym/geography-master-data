from __future__ import annotations

import re
import sqlite3
from pathlib import Path

def integrity_statements() -> list[tuple[str, str]]:
    project_root = Path(__file__).resolve().parents[2]
    text = (project_root / "sql" / "integrity_checks.sql").read_text(encoding="utf-8")
    statements = []
    for raw in text.split(";"):
        statement = raw.strip()
        if not statement:
            continue
        match = re.search(r"SELECT\s+'([^']+)'\s+AS\s+check_name", statement, flags=re.IGNORECASE)
        if not match:
            raise ValueError("Every integrity statement must return a literal check_name")
        statements.append((match.group(1), statement))
    return statements


def run_sql_checks_connection(connection: sqlite3.Connection) -> dict:
    checks = []
    for expected_name, statement in integrity_statements():
        rows = connection.execute(statement).fetchall()
        if rows and any(row[0] != expected_name for row in rows):
            raise ValueError(f"Integrity statement {expected_name} returned an inconsistent check name")
        checks.append({
            "check": expected_name,
            "count": len(rows),
            "sample": [list(row[1:]) for row in rows[:10]],
        })
    violations = sum(item["count"] for item in checks)
    return {"verdict": "PASS" if violations == 0 else "NOT_READY", "violations": violations, "checks": checks}


def run_sql_checks(database: Path) -> dict:
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"Database not found: {database}")
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        result = run_sql_checks_connection(connection)
        result["database"] = str(database)
        return result
    finally:
        connection.close()
