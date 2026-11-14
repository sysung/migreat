# CLI installation delta

## MODIFIED Requirements

### Requirement: Install and invoke the backfill CLI

A fresh installation SHALL provide the distribution, Python import package, and CLI executable under the name `migreat`.

#### Scenario: Invoke from a fresh installation

- **WHEN** a developer installs the project in a clean virtual environment and runs `migreat --help`
- **THEN** the command succeeds and identifies itself as `migreat`
- **AND** the environment can import `migreat`

#### Scenario: Plan from the bundled test fixture

- **WHEN** a developer runs `migreat plan tests/fixtures/orders-amount-cents.yaml` against the documented PostgreSQL fixture
- **THEN** the installed CLI prints the scoped historical fill and the number of pending rows

#### Scenario: Use top-level migration commands

- **WHEN** the operator invokes `migreat --help`
- **THEN** the migration commands are `plan` and `apply`
- **AND** the former `backfill` and `cutover` command groups are rejected as unknown commands
