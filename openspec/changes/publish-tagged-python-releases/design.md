# Design

## Context

Current CI runs the full PostgreSQL suite and Docker smoke test on Linux. The suite starts Docker and uses Unix pipe selection and signals. Migreat itself ships Python code, but psycopg and PyYAML have platform-dependent distributions. See [the proposal](proposal.md) for the change in distribution name.

## Goals / Non-Goals

**Goals**

- Deliver a versioned wheel and source distribution through GitHub Releases, with evidence that the installed CLI can run a backfill on the documented platforms.
- Keep the version tag, source revision, artifact metadata, and published files traceable to the same release.

**Non-Goals**

- Standalone binaries, Homebrew formulas, shell installers, and container registry publishing are outside the initial release scope.

## Decisions

### Use one distribution and one release version

Keep `migreat` as the distribution name, console entry point, and import. The only top-level subcommand is `backfill`, with `plan` and `apply`. Use `pyproject.toml` as the version source. For a release, require a stable `vMAJOR.MINOR.PATCH` tag with an exact version match and a commit reachable from `origin/master`. Use `v0.1.0` if that is still the reviewed package version and the tag is unused. Tag-derived versioning would add a build dependency for a check that static metadata already supports.

### Build once and verify what users will install

Add a dedicated release workflow. Tag pushes can publish. Manual dispatch rehearses build and verification without entering the publishing job. Build one wheel and one source distribution with the standard Python build frontend. Check metadata and archives, record SHA-256 hashes, and share the artifacts with verification and publishing jobs. Keep the existing PR and default-branch jobs.

Run fresh installs outside the source tree on Python 3.12 for Linux x64, macOS arm64 and Intel, and Windows x64. Exercise the installed entry point and runtime dependency imports. Verify the documentation's `uv tool install` path and the pip and pipx alternatives. Run the full Linux PostgreSQL suite against the wheel and smoke-test the Docker image. Also install from the source distribution in a separate Linux environment.

Run one portable PostgreSQL scenario per target against the installed wheel. Provision disposable local PostgreSQL on the runner, using the existing Linux container fixture, PostgreSQL 17 from Homebrew on macOS, and PostgreSQL server binaries on Windows. Use a fresh database and readiness timeout. Pass the fixture by absolute path and use bounded subprocess calls with explicit input and encoding. Check plan output and unchanged data, then send `yes`, check the update, and verify a repeated plan reports zero pending rows. Exercise redirected output on Windows because the current CLI prints a non-ASCII range separator. Keep the existing pipe, interrupt, lock, and rollback cases in the Linux suite.

### Scope publishing credentials to the upload job

Protect existing version tags and limit their creation to release maintainers. Only the gated release job receives `contents: write` using the workflow's GitHub token. Verify the build manifest, stage the verified wheel, source distribution, and manifest on a draft associated with the existing tag, then make the draft public after all assets are present. A maintainer-created tag records release intent. Manual dispatch never publishes.

## Risks / Trade-offs

- The unrelated PyPI distribution has the same name. Use the full versioned GitHub wheel URL in each install command.
- A pure Python wheel does not guarantee dependency availability on every platform. Report the architectures and Python versions actually verified. Use Python 3.12 for the initial matrix and test the latest stable Python on Linux as an additional compatibility check.
- Manual rehearsal verifies the pipeline through the publish gate. The first authorized release verifies the public download URLs.
- An upload can fail before the draft is complete. Check existing asset hashes before uploading missing assets from the same build. Preserve published tags and assets. Release a new version to correct a defective public artifact.

## Migration Plan

Update the install docs to lead with `uv tool install <wheel-url>`, then show pipx and pip in a virtual environment, including Windows commands and versioned GitHub wheel URLs. Provide a versioned example declaration for people without a checkout. If package metadata references the README, include it in the Docker build context before the package install.

Rehearse against the intended release commit. Configure tag protections, then create the first release tag when authorized. Verify the exact version is installable from the GitHub Release on the documented targets and compare downloaded file hashes with the tested artifacts before announcing the release.

## Arena synthesis

Both candidates chose one build, platform verification, and a dedicated publish job. The original Arena compared PyPI designs. The confirmed revision uses GitHub Releases. The cross-judge scored Candidate 1 at 9/10 and Candidate 2 at 8/10. Candidate 1 supplied the base because its release-tag protections, architecture choices, and Docker packaging changes were more concrete. Candidate 2 supplied negative gate checks, a missing-declaration CLI check, and public download hash verification. The final design adds an actual preview and confirmed apply on each platform. Existing CI remains separate to keep the release workflow small and independently reviewable.
