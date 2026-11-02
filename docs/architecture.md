# Architecture

## Decision

The project uses Python, SQLite and small CSV fixtures.

SQLite is the primary output because the workbook is about 56 MiB and the normalized tables fit comfortably in a local relational database. SQLite provides foreign keys, indexes, SQL checks and one portable artifact. Parquet would help analytical scans over much larger data, but would add PyArrow or DuckDB without improving this portfolio's core relational checks. Public CSV files are limited to small synthetic inputs; they are not the main storage model.

## Private/full flow

`Excel workbook → temporary SQLite database → structural verification → atomic replacement → independent parity → integrity and DQ reports`

The structural gate checks the exact sheet sequence and headers. Values are inserted without fuzzy matching. Dates become ISO text, booleans become `0/1`, identifiers remain unchanged, and classifier codes remain text. The target is not replaced until the temporary database passes SQLite integrity, foreign-key, manifest, column-order and status-rule checks. Independent parity then rereads both artifacts rather than trusting the import manifest.

## Public/demo flow

`Synthetic CSV fixtures → the same SQLite schema → normalization rules → quarantine → validation`

The demo does not contain rows copied from the private workbook. It intentionally covers exact and alternative names, external identifiers, equal names belonging to distinct GUIDs, unknown values, source conflict, invalid code and missing parent.

## Trust boundary

The full database, workbook and generated private reports are local artifacts excluded by `.gitignore`. Public code does not require access to corporate infrastructure.

