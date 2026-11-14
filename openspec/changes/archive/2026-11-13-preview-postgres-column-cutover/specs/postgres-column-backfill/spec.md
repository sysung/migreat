# Spec Delta

## ADDED Requirements

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
