# Data model

## Stable entities

`country_id`, `region_id` and `locality_id` are stable internal identifiers. Import preserves them and never renumbers them. Parent relationships are explicit. A nullable locality `region_id` is allowed only because the audited source contains unresolved parentage; validation reports it as a DQ issue.

## Crosswalk

`locality_external_ids` links a canonical locality to FIAS/GAR, OKATO and OKTMO evidence. Codes use `TEXT` so leading zeros survive. A null `locality_id` represents an excluded or unresolved source row rather than an invented match.

## History

History tables keep an entity ID, version number, validity interval and current flag. Validation checks one current version and non-overlapping periods. The source documentation warns that some dates are technical correction times rather than proven legal effective dates.

## Normalization states

The model preserves every source status. The core public workflow focuses on:

- `matched`: one supported canonical target;
- `ambiguous`: more than one supported target;
- `unresolved`: no supported target;
- `source_conflict`: sources disagree and automatic assignment is blocked.

The private workbook also contains `matched_existing`, `matched_country_region_unresolved`, `unresolved_country` and `non_canonical_object`; the importer retains them rather than collapsing their meaning.

