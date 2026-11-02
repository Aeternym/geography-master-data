-- Each statement returns violating rows or groups. A valid database returns no rows.

SELECT 'locality_region_country_mismatch' AS check_name, l.locality_id AS entity_id
FROM geo_locality l
JOIN geo_region r ON r.region_id = l.region_id
WHERE l.country_id <> r.country_id;

SELECT 'locality_without_region' AS check_name, locality_id AS entity_id
FROM geo_locality
WHERE region_id IS NULL;

SELECT 'invalid_normalization_status' AS check_name, mapping_id AS entity_id
FROM source_normalization n
LEFT JOIN normalization_status_rule r ON r.status = n.normalization_status
WHERE r.status IS NULL;

SELECT 'matched_without_target' AS check_name, mapping_id AS entity_id
FROM source_normalization
WHERE normalization_status IN ('matched', 'matched_existing')
  AND normalized_country_id IS NULL
  AND normalized_region_id IS NULL
  AND normalized_locality_id IS NULL;

SELECT 'nonmatched_with_locality_target' AS check_name, mapping_id AS entity_id
FROM source_normalization
WHERE normalization_status IN ('ambiguous', 'unresolved', 'unresolved_country', 'source_conflict', 'non_canonical_object')
  AND normalized_locality_id IS NOT NULL;

SELECT 'region_unresolved_status_inconsistent' AS check_name, mapping_id AS entity_id
FROM source_normalization
WHERE normalization_status = 'matched_country_region_unresolved'
  AND (normalized_country_id IS NULL OR normalized_region_id IS NOT NULL);

SELECT 'locality_without_timezone' AS check_name, locality_id AS entity_id
FROM geo_locality
WHERE timezone_name IS NULL OR trim(timezone_name) = '';

SELECT 'region_without_timezone' AS check_name, region_id AS entity_id
FROM geo_region
WHERE timezone_names IS NULL OR trim(timezone_names) = '';

SELECT 'invalid_okato_code' AS check_name, external_id_row_id AS entity_id
FROM locality_external_ids
WHERE okato_code IS NOT NULL
  AND (length(okato_code) <> 11 OR okato_code GLOB '*[^0-9]*');

SELECT 'invalid_oktmo_code' AS check_name, external_id_row_id AS entity_id
FROM locality_external_ids
WHERE oktmo_current_code IS NOT NULL
  AND (length(oktmo_current_code) NOT IN (8, 11) OR oktmo_current_code GLOB '*[^0-9]*');

SELECT 'external_id_region_mismatch' AS check_name, e.external_id_row_id AS entity_id
FROM locality_external_ids e
JOIN geo_locality l ON l.locality_id = e.locality_id
WHERE e.canonical_region_id IS NOT NULL
  AND l.region_id IS NOT NULL
  AND e.canonical_region_id <> l.region_id;

SELECT 'quarantine_missing_payload_or_reason' AS check_name, quarantine_id AS entity_id
FROM quarantine_record
WHERE trim(payload_json) = '' OR trim(reason) = '';

SELECT 'quarantine_summary_requires_review' AS check_name, gar_region_code AS entity_id, excluded_locality_count
FROM quarantine_summary
WHERE excluded_locality_count > 0;

SELECT 'quarantine_summary_invalid' AS check_name, gar_region_code AS entity_id
FROM quarantine_summary
WHERE excluded_locality_count < 0 OR trim(status) = '';

SELECT 'invalid_country_code' AS check_name, country_id AS entity_id
FROM geo_country
WHERE length(country_code_alpha2) <> 2
   OR country_code_alpha2 GLOB '*[^A-Z]*'
   OR length(country_code_alpha3) <> 3
   OR country_code_alpha3 GLOB '*[^A-Z]*'
   OR length(country_code_numeric) <> 3
   OR country_code_numeric GLOB '*[^0-9]*';

SELECT 'duplicate_fias_guid' AS check_name, fias_object_guid AS entity_id
FROM locality_external_ids
WHERE fias_object_guid IS NOT NULL
GROUP BY fias_object_guid
HAVING COUNT(DISTINCT locality_id) > 1;

SELECT 'country_history_current_count' AS check_name, country_id AS entity_id
FROM history_country GROUP BY country_id HAVING SUM(is_current) <> 1;

SELECT 'region_history_current_count' AS check_name, region_id AS entity_id
FROM history_region GROUP BY region_id HAVING SUM(is_current) <> 1;

SELECT 'locality_history_current_count' AS check_name, locality_id AS entity_id
FROM history_locality GROUP BY locality_id HAVING SUM(is_current) <> 1;

SELECT 'country_history_overlap' AS check_name, a.country_history_id AS entity_id
FROM history_country a
JOIN history_country b ON a.country_id = b.country_id AND a.version_no < b.version_no
WHERE COALESCE(a.valid_to, '9999-12-31') > b.valid_from
  AND COALESCE(b.valid_to, '9999-12-31') > a.valid_from;

SELECT 'region_history_overlap' AS check_name, a.region_history_id AS entity_id
FROM history_region a
JOIN history_region b ON a.region_id = b.region_id AND a.version_no < b.version_no
WHERE COALESCE(a.valid_to, '9999-12-31') > b.valid_from
  AND COALESCE(b.valid_to, '9999-12-31') > a.valid_from;

SELECT 'locality_history_overlap' AS check_name, a.locality_history_id AS entity_id
FROM history_locality a
JOIN history_locality b ON a.locality_id = b.locality_id AND a.version_no < b.version_no
WHERE COALESCE(a.valid_to, '9999-12-31') > b.valid_from
  AND COALESCE(b.valid_to, '9999-12-31') > a.valid_from;

