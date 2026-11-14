# postgres-column-backfill Specification

## Purpose

Fill one historical PostgreSQL column in place during a coordinated daily batch deployment.

## Requirements

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

### Requirement: Preview a declared column addition and historical fill

For a column-addition declaration, the CLI SHALL show the proposed nullable column addition and scoped update with the declared historical policy and bounds. Planning SHALL leave the database unchanged.

#### Scenario: Preview a numeric conversion

- **WHEN** a new numeric column is declared with a retained bigint source field and a decimal multiplier
- **THEN** the plan identifies the source field, join key, multiplier, destination, and scoped counts and shows the proposed SQL and bound values

#### Scenario: Preview a transaction timestamp

- **WHEN** the transaction timestamp policy is selected for a new timestamp column
- **THEN** the plan shows that the update will use the apply transaction start time and identifies the historical range

#### Scenario: Reject an existing destination

- **WHEN** the new-column declaration names a column already present in the target
- **THEN** the CLI reports that the column already exists and performs no writes

### Requirement: Confirm and verify a column addition and fill

For a column-addition declaration, the CLI SHALL generate and display a fresh plan on each apply invocation and require the existing literal `yes` before any write. It SHALL recheck the reviewed state under locks and add, fill, and verify the column in one transaction.

#### Scenario: Apply the reviewed cutover

- **WHEN** the operator confirms a valid plan and the reviewed state still matches
- **THEN** the scoped rows receive the declared derived values or one shared apply transaction timestamp
- **AND** rows outside the historical range have NULL in the added column and their existing fields are preserved

#### Scenario: Add a column with an empty scope

- **WHEN** the operator confirms a valid plan whose scoped target selection is empty
- **THEN** the CLI adds the nullable column and reports zero rows filled

#### Scenario: Stop before a write or roll back the change

- **WHEN** confirmation is declined, the reviewed state changes, or apply or verification fails
- **THEN** the CLI leaves no committed column addition or historical fill from that attempt
