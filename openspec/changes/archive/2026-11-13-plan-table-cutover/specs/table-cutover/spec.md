# Table cutover

## Purpose

Help operators review and assess PostgreSQL replacement tables before switching readers.

## ADDED Requirements

### Requirement: Preview a replacement table

The CLI SHALL render declared PostgreSQL schema SQL, value derivations, and cutover steps without writes.

#### Scenario: Review a full refresh

- **WHEN** a declaration specifies a replacement schema and retained history
- **THEN** the CLI displays the DDL, derivations, and operator steps for comparison, routing, and rollback

### Requirement: Assess full-refresh evidence

The CLI SHALL require fresh evidence bound to the plan and a shared input snapshot, zero unexplained keyed differences, and a viable rollback path before reporting readiness.

#### Scenario: Evidence meets the declared gates

- **WHEN** matching fresh evidence shows both builds and comparison used the declared snapshot, keyed parity passed, and rollback is viable
- **THEN** the CLI reports that supplied evidence supports the switch

#### Scenario: Prerequisite is missing

- **WHEN** evidence is missing, stale, or inconsistent, or an original timestamp has no retained source
- **THEN** the CLI reports a blocker and exits nonzero

#### Scenario: Evidence mode is unsupported

- **WHEN** the operator requests incremental, microbatch, or streaming
- **THEN** the CLI reports the mode is unsupported and exits nonzero
