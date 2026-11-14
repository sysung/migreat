# PostgreSQL backfill delta

## MODIFIED Requirements

### Requirement: Confirm and verify a column addition and fill

For a column addition planned from YAML or dbt, `migreat apply` SHALL generate and display a fresh plan on each apply invocation and require the existing literal `yes` before any write. It SHALL recheck the reviewed state under locks and add, fill, and verify the column in one transaction.

#### Scenario: Apply the reviewed cutover

- **WHEN** the operator confirms a valid plan and the reviewed state still matches
- **THEN** the scoped rows receive the verified PostgreSQL values for the planned expression or the declared YAML policy
- **AND** rows outside the historical range have NULL in the added column and their existing fields are preserved

#### Scenario: Add a column with an empty scope

- **WHEN** the operator confirms a valid plan whose scoped target selection is empty
- **THEN** the CLI adds the nullable column and reports zero rows filled

#### Scenario: Stop before a write or roll back the change

- **WHEN** confirmation is declined, the reviewed state changes, or apply or verification fails
- **THEN** the CLI leaves no committed column addition or historical fill from that attempt
