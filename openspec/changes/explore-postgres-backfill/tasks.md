# Tasks

## 1. Build the bounded backfill

- [x] 1.1 Add `backfill.py` with strict YAML loading, capped bigint ranges, PostgreSQL table checks, and a consistent read-only preview. Verify malformed declarations, wrong database, missing destination column, empty scope, duplicate or missing matches, NULL sources, conflicts, and unsupported relations.
- [x] 1.2 Add confirmed apply with bounded locks, exact revalidation, a NULL-only update, and verification before commit. Verify lock timeout, same-count value drift, cancellation, forced failure before commit, unchanged out-of-scope data, and zero-write reruns in disposable PostgreSQL.
- [x] 1.3 Wire `backfill plan FILE` and `backfill apply FILE` into the CLI and document the paused batch workflow with the fixture. Verify help, no writes before literal confirmation, actionable errors, and useful status counts.

## 2. Retire the ODCS entry points

- [x] 2.1 Remove top-level `plan` and `apply`, the unused ODCS modules, bundled schema, dependency and package-data entry. Replace the legacy quickstart, fixtures, and test cases with backfill equivalents. Confirm no active references remain and a fresh wheel and Docker image contain only the supported CLI path.

## 3. Verify the release handoff

- [x] 3.1 Rehearse a fresh disposable db-test copy on a separate Compose project and volume. Build baseline IDs 1–10 and let that run exit. Apply reviewed fixture DDL while paused, preview, confirm the fill, and verify ten correct values before invoking the enriched model. Repeat the fill and verify zero updates.
- [x] 3.2 Run the existing enriched dbt command and verify 13 unique orders with matching values, the same table OID, preserved historical rows, and passing dbt tests. Add a new input ID and prove the unchanged enriched command can append it. Document observed results and clarify that the one-shot fixture simulates pause and drain.

## Workflow follow-up

- Port the verified walkthrough to the sibling db-test project, replacing its retired ODCS mount and README commands with fixture DDL and a read-only backfill declaration mount. Delete `contracts/orders.yaml` and the empty `contracts/` directory after switching both callers. Verify the documented Compose sequence on a fresh volume.
