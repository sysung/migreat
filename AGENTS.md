## Tests and verifiers

| Rule | How to apply it |
| --- | --- |
| Add or extend tests and standalone verifiers only when the user explicitly authorizes them. | Before writing one, identify the incorrect outcome that can pass normal execution, such as a wrong backfill value after a successful command. |
| Use normal execution to check builds, installs, and commands. | Run the operation and use its exit status. Keep routine failures in the operation that already reports them. |

## Agent skills

### Issue tracker

Track work in GitHub Issues for `sysung/migreat`. Read [issue tracker conventions](docs/agents/issue-tracker.md) before working with tickets.

### Triage labels

Read [triage labels](docs/agents/triage-labels.md) before triaging issues.

### Domain docs

Read the [domain docs guide](docs/agents/domain.md) before exploring a domain change.
