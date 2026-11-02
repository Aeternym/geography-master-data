from __future__ import annotations

import json
import sqlite3


def add_quarantine(connection: sqlite3.Connection, source_system: str, entity_type: str, source_key: str, payload: dict, reason: str, status: str) -> None:
    safe_payload = {str(key): value for key, value in payload.items() if key is not None}
    connection.execute(
        """INSERT INTO quarantine_record(source_system, entity_type, source_key, payload_json, reason, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (source_system, entity_type, source_key, json.dumps(safe_payload, ensure_ascii=False, sort_keys=True), reason, status),
    )

