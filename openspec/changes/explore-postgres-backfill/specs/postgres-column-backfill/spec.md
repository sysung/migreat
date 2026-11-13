# Spec Delta

## Purpose

Fill one historical PostgreSQL column in place during a coordinated daily batch deployment.

## ADDED Requirements

### Requirement: Preview a scoped historical fill

The CLI SHALL preview one declared source-to-target fill without writes. The declaration identifies the expected database, ordinary source and target tables, shared bigint key, destination value column, and inclusive historical range.

#### Scenario: Preview before deployment

- **WHEN** the old writer has been paused and drained and the operator plans a fill against a prepared table
- **THEN** the CLI shows the database, both tables, key range, and counts for pending, correct, and blocked rows
- **AND** the source and target remain unchanged

#### Scenario: Stop on blocked rows or missing prerequisites

- **WHEN** the database or table shape is wrong, the destination column is missing, the range exceeds the PoC limit, or a scoped row has a duplicate key, missing or NULL source value, or conflicting populated value
- **THEN** the command exits nonzero with a diagnostic and leaves the data unchanged

### Requirement: Confirm and verify a historical fill

The CLI SHALL preview and require an explicit `yes` before mutating data. After confirmation it SHALL recheck the reviewed state, update only pending destination values, and verify the results in one transaction.

#### Scenario: Decline or interrupt confirmation

- **WHEN** the operator declines, presses Ctrl-C, or closes input at the prompt
- **THEN** the CLI exits without writes

#### Scenario: Detect drift or a failed update

- **WHEN** the reviewed schema or scoped data changes before apply, locks cannot be acquired within the limit, or verification fails
- **THEN** apply reports failure and leaves no partial fill

#### Scenario: Preserve history and resume the daily writer

- **WHEN** a valid fill is confirmed and verified before the new writer runs
- **THEN** every scoped row matches the retained source value and existing row IDs, unrelated fields, table identity, and out-of-scope rows are preserved
- **AND** the existing enriched incremental command can append new orders and preserve the filled history

#### Scenario: Repeat a completed fill

- **WHEN** every scoped value already matches the source
- **THEN** the CLI reports zero pending rows and performs no writes
