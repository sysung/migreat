# Proposal

## Why

Operators should be able to plan a simple PostgreSQL column addition from the deployed and proposed dbt model versions without authoring a schema contract or migration declaration. A single plan and apply workflow gives the operator the same review before any write.

## What Changes

- **BREAKING** Replace the nested backfill commands with `migreat plan` and `migreat apply`. Remove the offline `cutover plan` command.
- Keep the existing YAML backfill and column-addition inputs. Derive one added column from the candidate model’s SQL expression using compiled baseline and candidate artifacts, a model, a key, and an inclusive historical range.
- Show the added column and any blockers. Check the proposed fill against live PostgreSQL in the same command. Apply regenerates the plan and requires explicit confirmation before a write.
- Give planning, transactions, and terminal interaction distinct owners.

## Capabilities

### New Capabilities

- `dbt-column-addition` covers discovery and validation of one additive dbt model change.

### Modified Capabilities

- `cli-installation` exposes the top-level plan and apply commands.
- `postgres-column-backfill` applies the same review and write guarantees to YAML and dbt inputs.
- `table-cutover` retires both requirements for the offline command.

## Impact

The CLI, backfill modules, package documentation, and existing CLI integration invocation are affected. PostgreSQL remains the database for both planning and applying. Existing YAML files can be used with the shorter commands. Replacement-table orchestration is outside this change.
