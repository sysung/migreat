## ADDED Requirements

### Requirement: Install the CLI from GitHub

Migreat SHALL document isolated installation with uv from the public Git repository, including installation at a specific commit.

#### Scenario: Install outside a checkout

- **WHEN** a user with uv and Git installs from the documented GitHub URL
- **THEN** the installed `migreat --help` command succeeds outside a source checkout

#### Scenario: Pin the installed source

- **WHEN** a user replaces the branch in the install URL with a full commit SHA
- **THEN** the install uses the Migreat source at that commit
