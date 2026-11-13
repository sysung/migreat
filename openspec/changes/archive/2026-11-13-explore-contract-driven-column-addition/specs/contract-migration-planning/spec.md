# Contract migration planning

## Purpose

Review and apply one nullable addition to a populated PostgreSQL table from an ODCS contract.

## ADDED Requirements

### Requirement: Preview a nullable addition

The CLI SHALL validate an ODCS 3.2.0 contract and compare it to the live table before showing the SQL and its effect on existing rows.

#### Scenario: Preview an addition on a ten-row table

- **WHEN** the contract adds one nullable bigint to the live table
- **THEN** the preview shows one ADD COLUMN and explains that existing rows will read NULL
- **AND** the live schema and rows are unchanged

#### Scenario: Reject invalid input

- **WHEN** the contract is invalid or an existing column conflicts with it
- **THEN** the CLI exits with an error before applying any change

### Requirement: Apply the reviewed addition

The CLI SHALL require explicit confirmation and verify the starting and resulting schema under a table lock in the same transaction.

#### Scenario: Cancel the operation

- **WHEN** the user declines or closes the confirmation prompt
- **THEN** the table remains unchanged

#### Scenario: Apply to populated data

- **WHEN** the user confirms the preview and the starting schema still matches
- **THEN** the nullable bigint is added and all ten existing IDs survive with NULL in the new column

#### Scenario: Repeat after success

- **WHEN** the user runs apply again with the same contract
- **THEN** the CLI reports no changes

#### Scenario: Reject a stale preview

- **WHEN** the table schema changes after preview but before confirmation
- **THEN** the CLI rejects the stale plan and makes no additional change
