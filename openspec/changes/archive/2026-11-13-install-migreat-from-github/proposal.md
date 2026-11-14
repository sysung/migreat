## Why

Users need a CLI install command that works from the public repository today.

## What Changes

- Document installation with uv from GitHub and pinning to a commit for backfills.
- Remove the separate package publication workflow. Keep CI on pushes and pull requests targeting master.
- This change supersedes the rollout planned in `publish-tagged-python-releases`.

## Capabilities

### Modified Capabilities

- `cli-installation` adds a direct GitHub install path.

## Impact

README and GitHub Actions. The existing package, version, and CLI entry point support source installation.
