# CLI installation

## Purpose

Give developers one consistent name for installing, importing, and running migreat.

## ADDED Requirements

### Requirement: Install and invoke migreat

A fresh installation SHALL provide the distribution, Python import package, and CLI executable under the name `migreat`.

#### Scenario: Invoke from a fresh installation

- **WHEN** a developer installs the project in a clean virtual environment and runs `migreat --help`
- **THEN** the command succeeds and identifies itself as `migreat`
- **AND** the environment can import `migreat`

#### Scenario: Plan from the bundled contract

- **WHEN** a developer runs `migreat plan tests/fixtures/orders.yaml` against the PostgreSQL fixture
- **THEN** the installed CLI validates the contract using its packaged ODCS schema and previews the nullable column addition
