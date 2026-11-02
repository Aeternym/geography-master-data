CREATE INDEX idx_region_country ON geo_region(country_id);
CREATE INDEX idx_locality_parent ON geo_locality(country_id, region_id);
CREATE INDEX idx_locality_name_ru ON geo_locality(locality_name_ru);
CREATE INDEX idx_normalization_status ON source_normalization(normalization_status);
CREATE INDEX idx_history_country_period ON history_country(country_id, valid_from, valid_to);
CREATE INDEX idx_history_region_period ON history_region(region_id, valid_from, valid_to);
CREATE INDEX idx_history_locality_period ON history_locality(locality_id, valid_from, valid_to);
CREATE INDEX idx_external_fias_guid ON locality_external_ids(fias_object_guid);
CREATE INDEX idx_external_okato ON locality_external_ids(okato_code);
CREATE INDEX idx_external_oktmo ON locality_external_ids(oktmo_current_code);
CREATE INDEX idx_quarantine_status ON quarantine_record(status);

