# CLI installation

## MODIFIED Requirements

### Requirement: Install and invoke the backfill CLI

A fresh installation SHALL provide the distribution as `migreat` and the Python import package and CLI executable as `migreat`. The published distribution SHALL install on the documented Linux, macOS, and Windows targets.

#### Scenario: Invoke from a fresh installation

- **WHEN** a developer installs the published distribution on a supported target from a versioned GitHub Release wheel URL in a clean virtual environment or through the documented isolated installer
- **THEN** `migreat --help` succeeds and identifies itself as `migreat`
- **AND** the environment can import `migreat`

#### Scenario: Plan from the bundled test fixture

- **WHEN** a developer runs `migreat backfill plan tests/fixtures/orders-amount-cents.yaml` against the documented PostgreSQL fixture
- **THEN** the installed CLI prints the scoped historical fill and the number of pending rows
