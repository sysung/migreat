# dbt-column-addition Specification

## Purpose

Derive one in-place PostgreSQL column addition from two compiled dbt model versions without requiring a hand-written schema contract.

## Requirements

### Requirement: Identify one additive model change

Migreat SHALL accept an operator-identified deployed baseline and candidate compiled PostgreSQL dbt manifest, one model, a shared key, and inclusive historical bounds. It SHALL require the model to target the same table in both versions and the candidate to add exactly one named projection while keeping existing outputs and row-selection logic unchanged. The first version SHALL require an unfiltered direct table read.

#### Scenario: Compare compiled models

- **WHEN** the candidate adds one named projection to the same model and target while preserving the existing outputs and row selection
- **THEN** the plan identifies the added column and omits unchanged columns from the schema diff

#### Scenario: Reject an ambiguous comparison

- **WHEN** compiled SQL is unavailable, the selected model or relation differs, or Migreat cannot establish the supported additive change
- **THEN** the command reports a blocker and offers no write

#### Scenario: Reject a filtered model

- **WHEN** either model version filters the source rows
- **THEN** the plan reports that the model shape is unsupported and offers no write

### Requirement: Validate the proposed historical fill

Migreat SHALL derive the fill from the added SQL expression. It SHALL resolve the expression's input columns, output type, and scoped result values using PostgreSQL without writes. For a column-dependent fill, each scoped target key SHALL match exactly one row in the retained source. PostgreSQL expression semantics determine the result, including NULL propagation.

#### Scenario: Preview a calculated column

- **WHEN** the added projection uses supported row-local PostgreSQL calculations over one or more retained columns
- **THEN** the plan shows the added column, PostgreSQL output type, historical scope, and proposed SQL and bound values
- **AND** the calculation can combine arithmetic, comparisons, casts, and conditional expressions, such as subtracting a discount from an amount or using CASE and COALESCE

#### Scenario: Preview a row-independent value

- **WHEN** the added expression is a supported constant or transaction-time value
- **THEN** the plan describes how the value is assigned to historical rows
- **AND** a transaction-time expression resolves inside the confirmed write transaction

#### Scenario: PostgreSQL rejects the expression

- **WHEN** PostgreSQL reports an error while validating a supported expression against the live source
- **THEN** the report includes the database diagnostic and apply stops before confirmation

#### Scenario: Expression cannot be verified

- **WHEN** the candidate adds a projection whose dependencies, PostgreSQL type, or historical evaluation Migreat cannot safely establish
- **THEN** the plan shows the addition and explains the blocker without offering apply

#### Scenario: Live prerequisites fail

- **WHEN** the target column already exists or the scoped keys fail the historical matching checks
- **THEN** the report explains the blocker and leaves the tables unchanged
