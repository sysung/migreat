# Spec Delta

## ADDED Requirements

### Requirement: Install and invoke the backfill CLI

A fresh installation SHALL provide the distribution, Python import package, and CLI executable under the name `migreat`.

#### Scenario: Invoke from a fresh installation

- **WHEN** a developer installs the project in a clean virtual environment and runs `migreat --help`
- **THEN** the command succeeds and identifies itself as `migreat`
- **AND** the environment can import `migreat`

#### Scenario: Plan from the bundled test fixture

- **WHEN** a developer runs `migreat backfill plan tests/fixtures/orders-amount-cents.yaml` against the documented PostgreSQL fixture
- **THEN** the installed CLI prints the scoped historical fill and the number of pending rows

## REMOVED Requirements

### Requirement: Install and invoke migreat

**Reason**: The ODCS command used by the installation smoke test is retired.
**Migration**: Install the same distribution and run the backfill smoke test.
