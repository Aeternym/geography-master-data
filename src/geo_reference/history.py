from __future__ import annotations

import sqlite3


def history_violations(connection: sqlite3.Connection) -> list[dict]:
    issues = []
    for entity in ("country", "region", "locality"):
        table = f"history_{entity}"
        id_col = f"{entity}_id"
        wrong_current = connection.execute(
            f"SELECT {id_col}, SUM(is_current) FROM {table} GROUP BY {id_col} HAVING SUM(is_current) <> 1"
        ).fetchall()
        if wrong_current:
            issues.append({"check": f"{entity}_current_version_count", "count": len(wrong_current), "sample": wrong_current[:5]})
        overlaps = connection.execute(
            f"""SELECT a.{id_col}, a.version_no, b.version_no
                FROM {table} a JOIN {table} b
                  ON a.{id_col}=b.{id_col} AND a.version_no < b.version_no
                WHERE COALESCE(a.valid_to, '9999-12-31') > b.valid_from
                  AND COALESCE(b.valid_to, '9999-12-31') > a.valid_from"""
        ).fetchall()
        if overlaps:
            issues.append({"check": f"{entity}_overlapping_periods", "count": len(overlaps), "sample": overlaps[:5]})
    return issues

