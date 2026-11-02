from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from .import_excel import initialize_database, project_root
from .normalization import resolve_locality
from .quarantine import add_quarantine


def _rows(path: Path):
    with path.open(encoding="utf-8", newline="") as stream:
        yield from csv.DictReader(stream)


def _none(value):
    return None if value in (None, "") else value


def create_demo(output: Path, replace: bool = False) -> dict:
    output = Path(output)
    if output.exists() and not replace:
        raise FileExistsError(f"Output already exists: {output}. Use --replace to overwrite it explicitly.")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    connection = sqlite3.connect(output)
    connection.execute("PRAGMA foreign_keys = ON")
    initialize_database(connection)
    example_dir = project_root() / "examples"

    for row in _rows(example_dir / "synthetic_countries.csv"):
        connection.execute(
            """INSERT INTO geo_country(country_id,country_code_alpha2,country_code_alpha3,country_code_numeric,country_name_ru,country_name_ru_alias,country_name_en,country_name_en_alias,is_active,updated_at)
               VALUES (?,?,?,?,?,?,?,?,1,'2026-01-01')""",
            (int(row["country_id"]), row["country_code_alpha2"], row["country_code_alpha3"], row["country_code_numeric"], row["country_name_ru"], _none(row["country_name_ru_alias"]), row["country_name_en"], _none(row["country_name_en_alias"])),
        )
    for row in _rows(example_dir / "synthetic_regions.csv"):
        connection.execute(
            """INSERT INTO geo_region(region_id,country_id,region_code_iso3166_2,region_name_ru,region_name_en,region_type,timezone_names,is_active)
               VALUES (?,?,?,?,?,?,?,1)""",
            (int(row["region_id"]), int(row["country_id"]), row["region_code_iso3166_2"], row["region_name_ru"], row["region_name_en"], row["region_type"], row["timezone_names"]),
        )
    for row in _rows(example_dir / "synthetic_localities.csv"):
        connection.execute(
            """INSERT INTO geo_locality(locality_id,country_id,region_id,locality_name_ru,locality_name_ru_alias,locality_name_en,locality_name_en_alias,locality_type_code,locality_type_name,timezone_name,is_active)
               VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
            (int(row["locality_id"]), int(row["country_id"]), int(row["region_id"]), row["locality_name_ru"], _none(row["locality_name_ru_alias"]), row["locality_name_en"], _none(row["locality_name_en_alias"]), row["locality_type_code"], row["locality_type_name"], row["timezone_name"]),
        )
    for row in _rows(example_dir / "synthetic_crosswalk.csv"):
        connection.execute(
            """INSERT INTO locality_external_ids(locality_id,fias_object_guid,okato_code,oktmo_current_code,canonical_load_status,canonical_region_id)
               VALUES (?,?,?,?, 'loaded', ?)""",
            (int(row["locality_id"]), row["fias_object_guid"], row["okato_code"], row["oktmo_current_code"], int(row["canonical_region_id"])),
        )
    for row in _rows(example_dir / "synthetic_history.csv"):
        connection.execute(
            """INSERT INTO history_locality(locality_history_id,locality_id,version_no,country_id,region_id,locality_name_ru,locality_name_en,locality_type_code,locality_type_name,timezone_name,is_active,valid_from,valid_to,is_current)
               VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?)""",
            (int(row["locality_history_id"]), int(row["locality_id"]), int(row["version_no"]), int(row["country_id"]), int(row["region_id"]), row["locality_name_ru"], row["locality_name_en"], row["locality_type_code"], row["locality_type_name"], row["timezone_name"], row["valid_from"], _none(row["valid_to"]), int(row["is_current"])),
        )
    for country in connection.execute("SELECT * FROM geo_country").fetchall():
        connection.execute(
            """INSERT INTO history_country(country_history_id,country_id,version_no,country_code_alpha2,country_code_alpha3,country_code_numeric,country_name_ru,country_name_en,is_active,valid_from,is_current)
               VALUES (?,?,?,?,?,?,?,?,1,'2026-01-01',1)""",
            (country[0], country[0], 1, country[1], country[3], country[5], country[7], country[9]),
        )
    for region in connection.execute("SELECT region_id,country_id,region_code_iso3166_2,region_name_ru,region_name_en,region_type,timezone_names FROM geo_region").fetchall():
        connection.execute(
            """INSERT INTO history_region(region_history_id,region_id,version_no,country_id,region_code_iso3166_2,region_name_ru,region_name_en,region_type,timezone_names,is_active,valid_from,is_current)
               VALUES (?,?,1,?,?,?,?,?,?,1,'2026-01-01',1)""",
            (region[0], *region),
        )

    results = []
    for mapping_id, case in enumerate(_rows(example_dir / "normalization_cases.csv"), start=1):
        result = resolve_locality(connection, case)
        connection.execute(
            """INSERT INTO source_normalization(mapping_id,source_system,entity_type,source_country_value,source_country_name,source_region_value,source_region_name,source_locality_value,normalized_country_id,normalized_region_id,normalized_locality_id,normalization_status,updated_at)
               VALUES (?,'synthetic_demo','locality',?,?,?,?,?,?,?,?,?,'2026-01-01')""",
            (mapping_id, _none(case["source_country_value"]), _none(case["source_country_name"]), _none(case["source_region_value"]), _none(case["source_region_name"]), _none(case["source_locality_value"]), result.country_id, result.region_id, result.locality_id, result.status),
        )
        if result.status != "matched":
            add_quarantine(connection, "synthetic_demo", "locality", case["case_id"], case, result.reason, result.status)
        results.append({"case_id": case["case_id"], "status": result.status, "expected": case["expected_status"], "reason": result.reason})
    connection.commit()
    connection.close()
    return {"database": str(output), "cases": results}

