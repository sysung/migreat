# Proposal

## Why

A daily incremental job writes the new field for new records and skips old rows. Migreat should make a one-off historical fill reviewable and verifiable while the batch job is paused.

## What Changes

- Add `migreat backfill plan FILE` and `migreat backfill apply FILE` for a bounded PostgreSQL column fill. Apply previews the operation and requires explicit confirmation.
- Support one release order for the PoC. Pause and drain the old writer, add the destination column through the existing schema deployment process, fill and verify history, then deploy and resume the new writer.
- **BREAKING** Retire the standalone ODCS schema planner and applier, their bundled schema and dependencies, and the old documentation and tests. Replace the runtime with a small backfill module and CLI.
- Rehearse a single daily incremental dbt model against disposable PostgreSQL and run its existing enriched command after the fill.

## Capabilities

### New Capabilities

- `postgres-column-backfill` previews and applies a bounded in-place historical fill from retained PostgreSQL data.

### Modified Capabilities

- `cli-installation` uses the backfill demo as the installed CLI smoke test.
- `contract-migration-planning` retires the existing ODCS-based commands.

## Impact

The CLI, package data and dependencies, tests, and quickstart change. The release owner supplies additive DDL through their schema migration process. The sibling db-test setup is a verification fixture.
