# Design

## Context

The repository has no GitHub Actions workflow. The README documents a Python 3.12 package install, a unittest suite, and Docker build and help commands. The suite starts, seeds, and removes its own PostgreSQL 17.12 container through the Docker CLI.

## Goals / Non-Goals

Use the repository's existing verification commands on GitHub-hosted runners. Image publishing, deployment, and branch protection remain separate decisions.

## Decisions

- Add one workflow at `.github/workflows/ci.yml` with `pull_request` and `push` branch filters for `master`, the current default branch. [GitHub Actions branch filters](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpull_requestpull_request_targetbranchesbranches-ignore)
- Run two independent jobs on GitHub-hosted Ubuntu runners. The Python job selects Python 3.12, runs `python -m pip install .`, then runs `python -m unittest discover -s tests -v`. The Docker job runs `docker build -t migreat .` and `docker run --rm migreat --help`. Independent jobs show both outcomes even if one fails.
- Let the suite manage PostgreSQL and use normal step failure handling. Give the workflow read-only contents access for checkout.

## Risks / Trade-offs

The temporary stack base is PR #1's feature branch. The `master` pull request filter will not trigger there. Verify the implemented workflow on a PR targeting `master` after PR #1 lands, then verify the push trigger after the workflow merges.
