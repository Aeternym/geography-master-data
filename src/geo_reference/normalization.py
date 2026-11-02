from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.casefold().replace("ё", "е").split())


@dataclass(frozen=True)
class MatchResult:
    status: str
    country_id: int | None = None
    region_id: int | None = None
    locality_id: int | None = None
    reason: str = ""


Candidate = tuple[int, int | None, int]


def _rows_to_candidates(rows) -> set[Candidate]:
    return {(int(row[0]), int(row[1]) if row[1] is not None else None, int(row[2])) for row in rows}


def _identifier_candidates(connection: sqlite3.Connection, column: str, value: str) -> set[Candidate]:
    rows = connection.execute(
        f"""SELECT l.country_id, l.region_id, e.locality_id
            FROM locality_external_ids e
            JOIN geo_locality l ON l.locality_id=e.locality_id
            WHERE {column}""",
        (value, value) if " OR " in column else (value,),
    ).fetchall()
    return _rows_to_candidates(rows)


def _country_candidates(connection: sqlite3.Connection, value: str) -> set[int]:
    normalized = normalize_text(value)
    rows = connection.execute(
        """SELECT country_id, country_code_alpha2, country_code_alpha3, country_code_numeric,
                  country_name_ru, country_name_ru_alias, country_name_en, country_name_en_alias
           FROM geo_country"""
    ).fetchall()
    candidates = set()
    for row in rows:
        codes = {str(item).upper() for item in row[1:4] if item is not None}
        names = {normalize_text(item) for item in row[4:] if item}
        if value.upper() in codes or normalized in names:
            candidates.add(int(row[0]))
    return candidates


def _region_candidates(connection: sqlite3.Connection, value: str) -> set[tuple[int, int]]:
    normalized = normalize_text(value)
    rows = connection.execute(
        "SELECT region_id, country_id, region_code_iso3166_2, region_name_ru, region_name_en FROM geo_region"
    ).fetchall()
    candidates = set()
    for region_id, country_id, code, name_ru, name_en in rows:
        if value.upper() == str(code or "").upper() or normalized in {
            normalize_text(name_ru),
            normalize_text(name_en),
        }:
            candidates.add((int(country_id), int(region_id)))
    return candidates


def _locality_name_candidates(connection: sqlite3.Connection, value: str) -> set[Candidate]:
    normalized = normalize_text(value)
    rows = connection.execute(
        """SELECT country_id, region_id, locality_id, locality_name_ru, locality_name_ru_alias,
                  locality_name_en, locality_name_en_alias
           FROM geo_locality"""
    ).fetchall()
    return {
        (int(row[0]), int(row[1]) if row[1] is not None else None, int(row[2]))
        for row in rows
        if normalized in {normalize_text(item) for item in row[3:] if item}
    }


def _combine_signals(signals: list[tuple[str, set]]) -> tuple[str, set, str]:
    """Combine provided signals without treating missing input as a contradiction."""
    if not signals:
        return "absent", set(), "No signal was provided"
    missing = [label for label, candidates in signals if not candidates]
    if missing:
        return "unresolved", set(), f"No canonical value found for: {', '.join(missing)}"
    intersection = set.intersection(*(candidates for _, candidates in signals))
    if not intersection:
        return "source_conflict", set(), "Provided signals resolve to different canonical objects"
    if len(intersection) > 1:
        return "ambiguous", intersection, "Provided signals do not identify one canonical object"
    return "matched", intersection, "All provided signals agree"


def _result_without_target(status: str, reason: str) -> MatchResult:
    return MatchResult(status=status, reason=reason)


def resolve_locality(connection: sqlite3.Connection, case: dict[str, str]) -> MatchResult:
    if str(case.get("conflicting_source", "")).lower() in {"1", "true", "yes"}:
        return _result_without_target("source_conflict", "Sources explicitly disagree; no canonical target assigned")

    external_code = (case.get("source_external_code") or "").strip()
    fias_guid = (case.get("source_fias_guid") or "").strip()
    if external_code and not re.fullmatch(r"\d{8}|\d{11}", external_code):
        return _result_without_target("unresolved", "External code has an invalid format")

    identifier_signals: list[tuple[str, set[Candidate]]] = []
    if fias_guid:
        identifier_signals.append((
            "FIAS GUID",
            _identifier_candidates(connection, "lower(e.fias_object_guid)=lower(?)", fias_guid),
        ))
    if external_code:
        identifier_signals.append((
            "external code",
            _identifier_candidates(
                connection,
                "e.okato_code=? OR e.oktmo_current_code=?",
                external_code,
            ),
        ))

    identifier_status, identifier_candidates, identifier_reason = _combine_signals(identifier_signals)
    if identifier_status in {"unresolved", "source_conflict", "ambiguous"}:
        return _result_without_target(identifier_status, identifier_reason)

    country_signals: list[tuple[str, set[int]]] = []
    country_value = (case.get("source_country_value") or "").strip()
    country_name = (case.get("source_country_name") or "").strip()
    if country_value:
        country_signals.append(("country code", _country_candidates(connection, country_value)))
    if country_name:
        country_signals.append(("country name", _country_candidates(connection, country_name)))
    country_status, country_candidates, country_reason = _combine_signals(country_signals)
    if country_status in {"unresolved", "source_conflict", "ambiguous"}:
        return _result_without_target(country_status, country_reason)

    region_signals: list[tuple[str, set[tuple[int, int]]]] = []
    region_value = (case.get("source_region_value") or "").strip()
    region_name = (case.get("source_region_name") or "").strip()
    if region_value:
        region_signals.append(("region code", _region_candidates(connection, region_value)))
    if region_name:
        region_signals.append(("region name", _region_candidates(connection, region_name)))
    region_status, region_candidates, region_reason = _combine_signals(region_signals)
    if region_status in {"unresolved", "source_conflict", "ambiguous"}:
        return _result_without_target(region_status, region_reason)

    locality_value = (case.get("source_locality_value") or "").strip()
    locality_name_candidates = _locality_name_candidates(connection, locality_value) if locality_value else set()
    if locality_value and not locality_name_candidates:
        return _result_without_target("unresolved", "No canonical locality found for the provided name")

    # A unique identifier match is authoritative only when every other supplied
    # identifier and geographic sign is compatible with the same canonical row.
    if identifier_status == "matched":
        candidate = next(iter(identifier_candidates))
        country_id, region_id, locality_id = candidate
        if country_signals and country_id not in country_candidates:
            return _result_without_target("source_conflict", "Identifier and country resolve to different objects")
        if region_signals and (country_id, region_id) not in region_candidates:
            return _result_without_target("source_conflict", "Identifier and region resolve to different objects")
        if locality_value and candidate not in locality_name_candidates:
            return _result_without_target("source_conflict", "Identifier and locality name resolve to different objects")
        return MatchResult("matched", country_id, region_id, locality_id, "All provided identifiers and geographic signs agree")

    if country_status == "absent":
        return _result_without_target("unresolved", "Country information is absent")
    country_id = next(iter(country_candidates))

    if region_status == "absent":
        return MatchResult("unresolved", country_id=country_id, reason="Region information is absent")
    compatible_regions = {item for item in region_candidates if item[0] == country_id}
    if not compatible_regions:
        return _result_without_target("source_conflict", "Country and region resolve to different objects")
    if len(compatible_regions) > 1:
        return MatchResult("ambiguous", country_id=country_id, reason="Region is not unique within the country")
    region_id = next(iter(compatible_regions))[1]

    if not locality_value:
        return MatchResult("unresolved", country_id, region_id, None, "Locality information is absent")
    compatible_localities = {
        item for item in locality_name_candidates if item[0] == country_id and item[1] == region_id
    }
    if len(compatible_localities) == 1:
        locality_id = next(iter(compatible_localities))[2]
        return MatchResult("matched", country_id, region_id, locality_id, "Unique canonical or alternative name within parent")
    if len(compatible_localities) > 1:
        return MatchResult("ambiguous", country_id, region_id, None, "Name maps to multiple distinct objects; no automatic merge")
    if locality_name_candidates:
        return _result_without_target("source_conflict", "Locality name resolves outside the supplied country or region")
    return MatchResult("unresolved", country_id, region_id, None, "No canonical locality found")
