PRAGMA foreign_keys = ON;

CREATE TABLE import_run (
    run_id INTEGER PRIMARY KEY,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_path TEXT NOT NULL,
    source_file_sha256 TEXT NOT NULL,
    source_size_bytes INTEGER NOT NULL
);

CREATE TABLE import_manifest (
    sheet_name TEXT PRIMARY KEY,
    table_name TEXT NOT NULL UNIQUE,
    source_rows INTEGER NOT NULL,
    source_sha256 TEXT NOT NULL
);

CREATE TABLE workbook_readme (
    topic TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE normalization_status_rule (
    status TEXT PRIMARY KEY
);

INSERT INTO normalization_status_rule(status) VALUES
    ('matched'),
    ('matched_existing'),
    ('matched_country_region_unresolved'),
    ('ambiguous'),
    ('unresolved'),
    ('unresolved_country'),
    ('source_conflict'),
    ('non_canonical_object');

CREATE TABLE geo_country (
    country_id INTEGER PRIMARY KEY,
    country_code_alpha2 TEXT NOT NULL UNIQUE,
    country_code_alpha2_alias TEXT,
    country_code_alpha3 TEXT NOT NULL UNIQUE,
    country_code_alpha3_alias TEXT,
    country_code_numeric TEXT NOT NULL UNIQUE,
    country_code_numeric_alias TEXT,
    country_name_ru TEXT NOT NULL,
    country_name_ru_alias TEXT,
    country_name_en TEXT NOT NULL,
    country_name_en_alias TEXT,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    updated_at TEXT
);

CREATE TABLE geo_region (
    region_id INTEGER PRIMARY KEY,
    country_id INTEGER NOT NULL REFERENCES geo_country(country_id),
    region_code_iso3166_2 TEXT,
    region_name_ru TEXT,
    region_name_en TEXT,
    region_type TEXT,
    federal_district_code TEXT,
    federal_district_name_ru TEXT,
    federal_district_name_en TEXT,
    timezone_names TEXT,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
);

CREATE TABLE geo_locality (
    locality_id INTEGER PRIMARY KEY,
    country_id INTEGER NOT NULL REFERENCES geo_country(country_id),
    region_id INTEGER REFERENCES geo_region(region_id),
    locality_name_ru TEXT,
    locality_name_ru_alias TEXT,
    locality_name_en TEXT,
    locality_name_en_alias TEXT,
    locality_type_code TEXT,
    locality_type_name TEXT,
    timezone_name TEXT,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
);

CREATE TABLE source_normalization (
    mapping_id INTEGER PRIMARY KEY,
    source_system TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    source_country_value TEXT,
    source_country_name TEXT,
    source_region_value TEXT,
    source_region_name TEXT,
    source_locality_value TEXT,
    normalized_country_id INTEGER REFERENCES geo_country(country_id),
    normalized_region_id INTEGER REFERENCES geo_region(region_id),
    normalized_locality_id INTEGER REFERENCES geo_locality(locality_id),
    normalization_status TEXT NOT NULL REFERENCES normalization_status_rule(status),
    updated_at TEXT
);

CREATE TABLE history_country (
    country_history_id INTEGER PRIMARY KEY,
    country_id INTEGER NOT NULL REFERENCES geo_country(country_id),
    version_no INTEGER NOT NULL,
    country_code_alpha2 TEXT NOT NULL,
    country_code_alpha2_alias TEXT,
    country_code_alpha3 TEXT NOT NULL,
    country_code_alpha3_alias TEXT,
    country_code_numeric TEXT NOT NULL,
    country_code_numeric_alias TEXT,
    country_name_ru TEXT NOT NULL,
    country_name_ru_alias TEXT,
    country_name_en TEXT NOT NULL,
    country_name_en_alias TEXT,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    is_current INTEGER NOT NULL CHECK (is_current IN (0, 1)),
    UNIQUE (country_id, version_no)
);

CREATE TABLE history_region (
    region_history_id INTEGER PRIMARY KEY,
    region_id INTEGER NOT NULL REFERENCES geo_region(region_id),
    version_no INTEGER NOT NULL,
    country_id INTEGER NOT NULL REFERENCES geo_country(country_id),
    region_code_iso3166_2 TEXT,
    region_name_ru TEXT,
    region_name_en TEXT,
    region_type TEXT,
    federal_district_code TEXT,
    federal_district_name_ru TEXT,
    federal_district_name_en TEXT,
    timezone_names TEXT,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    is_current INTEGER NOT NULL CHECK (is_current IN (0, 1)),
    UNIQUE (region_id, version_no)
);

CREATE TABLE history_locality (
    locality_history_id INTEGER PRIMARY KEY,
    locality_id INTEGER NOT NULL REFERENCES geo_locality(locality_id),
    version_no INTEGER NOT NULL,
    country_id INTEGER NOT NULL REFERENCES geo_country(country_id),
    region_id INTEGER REFERENCES geo_region(region_id),
    locality_name_ru TEXT,
    locality_name_ru_alias TEXT,
    locality_name_en TEXT,
    locality_name_en_alias TEXT,
    locality_type_code TEXT,
    locality_type_name TEXT,
    timezone_name TEXT,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    is_current INTEGER NOT NULL CHECK (is_current IN (0, 1)),
    UNIQUE (locality_id, version_no)
);

CREATE TABLE locality_external_ids (
    external_id_row_id INTEGER PRIMARY KEY,
    locality_id INTEGER REFERENCES geo_locality(locality_id),
    fias_object_id TEXT,
    fias_object_guid TEXT,
    fias_region_code TEXT,
    fias_name TEXT,
    gar_type_name TEXT,
    gar_parent_object_id TEXT,
    gar_hierarchy_path TEXT,
    gar_okato_raw TEXT,
    okato_code_11 TEXT,
    okato_mapping_status TEXT,
    gar_oktmo_raw TEXT,
    oktmo_locality_code TEXT,
    oktmo_mapping_status TEXT,
    gar_start_date TEXT,
    gar_end_date TEXT,
    gar_update_date TEXT,
    date_semantics TEXT,
    source_file TEXT,
    okato_code TEXT,
    okato_validation_status TEXT,
    oktmo_raw_code TEXT,
    oktmo_current_code TEXT,
    oktmo_resolution_status TEXT,
    canonical_load_status TEXT,
    gar_region_status TEXT,
    canonical_region_id INTEGER REFERENCES geo_region(region_id),
    locality_type_resolution_basis TEXT,
    timezone_resolution_status TEXT,
    okato_validation_basis TEXT,
    oktmo_resolution_basis TEXT,
    oktmo_recode_chain TEXT,
    logical_duplicate_group_id TEXT,
    gar_level TEXT,
    source_entity_role TEXT,
    source_role_comment TEXT,
    english_resolution_basis TEXT
);

CREATE TABLE source_registry (
    source_code TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    scope TEXT,
    role TEXT
);

CREATE TABLE dq_backlog (
    issue_id TEXT PRIMARY KEY,
    issue_type TEXT NOT NULL,
    affected_rows INTEGER,
    affected_groups INTEGER,
    severity TEXT NOT NULL,
    release_blocker INTEGER NOT NULL CHECK (release_blocker IN (0, 1)),
    current_behavior TEXT,
    proposed_future_action TEXT,
    owner TEXT,
    comment TEXT,
    count_basis TEXT
);

CREATE TABLE quarantine_summary (
    gar_region_code TEXT PRIMARY KEY,
    source_region_name TEXT,
    excluded_locality_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    canonical_action TEXT,
    detail_location TEXT,
    join_key TEXT
);

CREATE TABLE quarantine_record (
    quarantine_id INTEGER PRIMARY KEY,
    source_system TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    source_key TEXT,
    payload_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ambiguous', 'unresolved', 'source_conflict', 'invalid')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

