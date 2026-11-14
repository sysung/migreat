# cli-installation Specification

## Purpose

Give developers one consistent name for installing, importing, and running migreat.

## Requirements

### Requirement: Install and invoke the backfill CLI

A fresh installation SHALL provide the distribution, Python import package, and CLI executable under the name `migreat`.

#### Scenario: Invoke from a fresh installation

- **WHEN** a developer installs the project in a clean virtual environment and runs `migreat --help`
- **THEN** the command succeeds and identifies itself as `migreat`
- **AND** the environment can import `migreat`

#### Scenario: Plan from the bundled test fixture

- **WHEN** a developer runs `migreat backfill plan tests/fixtures/orders-amount-cents.yaml` against the documented PostgreSQL fixture
- **THEN** the installed CLI prints the scoped historical fill and the number of pending rows

### Requirement: Install the CLI from GitHub

Migreat SHALL document isolated installation with uv from the public Git repository, including installation at a specific commit.

#### Scenario: Install outside a checkout

- **WHEN** a user with uv and Git installs from the documented GitHub URL
- **THEN** the installed `migreat --help` command succeeds outside a source checkout

#### Scenario: Pin the installed source

- **WHEN** a user replaces the branch in the install URL with a full commit SHA
- **THEN** the install uses the Migreat source at that commit
