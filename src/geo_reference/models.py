from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SheetSpec:
    sheet: str
    table: str
    columns: tuple[str, ...]


SPECS = (
    SheetSpec("README", "workbook_readme", ("topic", "value")),
    SheetSpec("core.geo_country", "geo_country", (
        "country_id", "country_code_alpha2", "country_code_alpha2_alias", "country_code_alpha3",
        "country_code_alpha3_alias", "country_code_numeric", "country_code_numeric_alias",
        "country_name_ru", "country_name_ru_alias", "country_name_en", "country_name_en_alias",
        "is_active", "updated_at",
    )),
    SheetSpec("core.geo_region", "geo_region", (
        "region_id", "country_id", "region_code_iso3166_2", "region_name_ru", "region_name_en",
        "region_type", "federal_district_code", "federal_district_name_ru",
        "federal_district_name_en", "timezone_names", "is_active",
    )),
    SheetSpec("core.geo_locality", "geo_locality", (
        "locality_id", "country_id", "region_id", "locality_name_ru", "locality_name_ru_alias",
        "locality_name_en", "locality_name_en_alias", "locality_type_code", "locality_type_name",
        "timezone_name", "is_active",
    )),
    SheetSpec("source_normalization", "source_normalization", (
        "mapping_id", "source_system", "entity_type", "source_country_value", "source_country_name",
        "source_region_value", "source_region_name", "source_locality_value", "normalized_country_id",
        "normalized_region_id", "normalized_locality_id", "normalization_status", "updated_at",
    )),
    SheetSpec("history.country", "history_country", (
        "country_history_id", "country_id", "version_no", "country_code_alpha2",
        "country_code_alpha2_alias", "country_code_alpha3", "country_code_alpha3_alias",
        "country_code_numeric", "country_code_numeric_alias", "country_name_ru", "country_name_ru_alias",
        "country_name_en", "country_name_en_alias", "is_active", "valid_from", "valid_to", "is_current",
    )),
    SheetSpec("history.region", "history_region", (
        "region_history_id", "region_id", "version_no", "country_id", "region_code_iso3166_2",
        "region_name_ru", "region_name_en", "region_type", "federal_district_code",
        "federal_district_name_ru", "federal_district_name_en", "timezone_names", "is_active",
        "valid_from", "valid_to", "is_current",
    )),
    SheetSpec("history.locality", "history_locality", (
        "locality_history_id", "locality_id", "version_no", "country_id", "region_id",
        "locality_name_ru", "locality_name_ru_alias", "locality_name_en", "locality_name_en_alias",
        "locality_type_code", "locality_type_name", "timezone_name", "is_active", "valid_from",
        "valid_to", "is_current",
    )),
    SheetSpec("locality_external_ids", "locality_external_ids", (
        "locality_id", "fias_object_id", "fias_object_guid", "fias_region_code", "fias_name",
        "gar_type_name", "gar_parent_object_id", "gar_hierarchy_path", "gar_okato_raw", "okato_code_11",
        "okato_mapping_status", "gar_oktmo_raw", "oktmo_locality_code", "oktmo_mapping_status",
        "gar_start_date", "gar_end_date", "gar_update_date", "date_semantics", "source_file", "okato_code",
        "okato_validation_status", "oktmo_raw_code", "oktmo_current_code", "oktmo_resolution_status",
        "canonical_load_status", "gar_region_status", "canonical_region_id", "locality_type_resolution_basis",
        "timezone_resolution_status", "okato_validation_basis", "oktmo_resolution_basis", "oktmo_recode_chain",
        "logical_duplicate_group_id", "gar_level", "source_entity_role", "source_role_comment",
        "english_resolution_basis",
    )),
    SheetSpec("source_registry", "source_registry", ("source_code", "source_name", "scope", "role")),
    SheetSpec("dq_backlog", "dq_backlog", (
        "issue_id", "issue_type", "affected_rows", "affected_groups", "severity", "release_blocker",
        "current_behavior", "proposed_future_action", "owner", "comment", "count_basis",
    )),
    SheetSpec("quarantine_summary", "quarantine_summary", (
        "gar_region_code", "source_region_name", "excluded_locality_count", "status", "canonical_action",
        "detail_location", "join_key",
    )),
)

SPEC_BY_SHEET = {spec.sheet: spec for spec in SPECS}
SPEC_BY_TABLE = {spec.table: spec for spec in SPECS}
ALLOWED_NORMALIZATION_STATUSES = {
    "matched", "matched_existing", "matched_country_region_unresolved", "ambiguous",
    "unresolved", "unresolved_country", "source_conflict", "non_canonical_object",
}

