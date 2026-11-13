# Proposal

## Why

Reviewers need GitHub check results showing that migreat installs, passes its PostgreSQL integration suite, and runs from its Docker image. Today the README describes running these checks locally. See [issue #2](https://github.com/sysung/migreat/issues/2).

## What Changes

- Run CI for pull requests targeting `master` and pushes to `master`.
- Install migreat with Python 3.12 and run the existing PostgreSQL integration suite.
- Build the Docker image and run the CLI help command inside it.
- Surface failed commands as failed GitHub checks.

## Capabilities

### New Capabilities

- `github-actions-ci` — Verify the Python installation, PostgreSQL integration suite, and Docker CLI through GitHub checks.

### Modified Capabilities

## Impact

Adds a GitHub Actions workflow that exercises the existing package, test fixture, and Dockerfile. Image publishing, deployment, and branch protection are outside this change.
