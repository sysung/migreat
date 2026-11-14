# Proposal

## Why

Operators need to review the schema change and historical fill together before deploying an updated daily writer. The current preview assumes the destination column already exists.

## What Changes

- Show the proposed PostgreSQL column addition and scoped update before applying either.
- Let the operator explicitly select a numeric conversion of retained source values or the apply transaction timestamp for a single new nullable column.
- Use Terraform's interactive apply flow. Generate a fresh plan, show it, and require `yes` before running the reviewed SQL.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `postgres-column-backfill` adds a read-only preview and confirmed apply for a column addition.

## Impact

Backfill declaration, PostgreSQL backfill logic, CLI output, and README. The existing copy path remains available. dbt model discovery and streaming cutovers are outside this change.
