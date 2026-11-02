from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def export_table_csv(connection: sqlite3.Connection, table: str, output: Path) -> None:
    allowed = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if table not in allowed:
        raise ValueError(f"Unknown table: {table}")
    cursor = connection.execute(f'SELECT * FROM "{table}"')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow([item[0] for item in cursor.description])
        writer.writerows(cursor)

