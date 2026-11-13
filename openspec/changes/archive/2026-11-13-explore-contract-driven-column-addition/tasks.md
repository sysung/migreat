# Tasks

## 1. Local PostgreSQL PoC

- [x] 1.1 Bundle the pinned ODCS schema and verify the installed CLI accepts the sample contract and rejects invalid ODCS.
- [x] 1.2 Preview and apply one nullable bigint addition. Verify cancellation, repeat behavior, and rejection of conflicting or stale schemas with the integration suite.
- [x] 1.3 Document installation, CLI usage, and the integration command in README.md.

## 2. End-to-end verification

- [x] 2.1 Run the documented integration suite against disposable PostgreSQL 17.12 and verify all ten original IDs survive with NULL in the new column.
