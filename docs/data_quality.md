# Data quality

Implemented checks cover required tables and columns, foreign keys, canonical parent consistency, missing timezones and regions, external-code formats, shared normalization statuses, conflicting identifiers, false GUID merges, quarantine integrity, one current history version and non-overlapping periods. Excel→SQLite parity additionally checks column order, normalized types and values, content hashes, leading zeros and stable-key sets.

A synthetic `PASS` means only that these implemented checks found no violations. It does not establish full business compliance, upstream ETL reproducibility or production readiness.

The supplied full workbook is not ready for an unrestricted production claim. Its own verdict is partial compliance. Locally confirmed evidence includes:

- 550 canonical localities with no `region_id`;
- 14,102 populated logical duplicate group IDs;
- 4,977 excluded external rows represented by six source-conflict quarantine groups;
- 28 source DQ backlog entries, including 6 release blockers;
- 1,164 non-null timezone identifier changes plus one separate null-to-value correction;
- no overlapping history intervals found by the implemented scan;
- no duplicate FIAS GUID mapped to different canonical localities in the imported SQLite checks.

The 1,691 manual-review groups are recorded in `dq_backlog` and the workbook README, but the supporting technical classification table is absent from the supplied workbook. The value cannot be independently recalculated from the public sheets alone.

