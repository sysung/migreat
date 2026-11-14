# Tasks

## 1. Package and document the CLI

- [x] 1.1 Verify and complete distribution metadata for `migreat`, preserving the `migreat` import and entry point. Include project description, README, source link, and license. Copy the README into the Docker build before installation. Build from a clean tree, run `twine check --strict`, and inspect wheel and sdist metadata, contents, and version.
- [ ] 1.2 Document uv, pipx, and pip in a virtual environment, with Windows and POSIX instructions, Python prerequisites, exact-version examples, and a versioned example declaration usable outside the checkout. Verify the commands against the built artifacts before release and the public package after upload.

## 2. Verify the release artifacts

- [ ] 2.1 Add the tag and verification-only workflow triggers. Validate stable tag syntax, version equality, and reachability from `master`. Build once and upload the wheel, sdist, and hash manifest for downstream jobs. Exercise malformed, mismatched, and off-branch refs, and confirm manual dispatch on a tag skips publishing.
- [ ] 2.2 Install the exact wheel outside the checkout on Linux x64, macOS arm64 and Intel, and Windows x64. Verify import path, distribution version, `pip check`, help, and missing-declaration failure. Exercise uv, pipx, and pip in isolated environments on each target. Verify a clean Linux sdist install and smoke-test the wheel on Linux with the latest stable Python.
- [ ] 2.3 Run the existing full PostgreSQL suite against the installed wheel on Linux and smoke-test the Docker image. On each supported target run a portable test against disposable local PostgreSQL that checks preview without writes, confirmed apply, verified values, and zero pending on repeat. Record OS, architecture, Python, and PostgreSQL versions with the workflow evidence.

## 3. Publish and verify the public install

- [x] 3.1 Add the dedicated GitHub Release job gated on release validation and all verification jobs. Verify its event, environment, permissions, and artifact inputs, including that a failed prerequisite prevents upload. Document tag protection, release tagging, and hash-based recovery for incomplete drafts.
- [ ] 3.2 Run the verification-only workflow on the intended release commit. Review all platform results, the downloadable build artifacts, and the skipped publish job.
- [ ] 3.3 Configure tag protections. After release authorization, push the reviewed version tag and verify the public GitHub Release contains the tested wheel and sdist. Compare both public file hashes with the workflow manifest.
- [ ] 3.4 Install the exact released version from the public GitHub Release wheel URL in fresh environments on the documented targets with no local artifact fallback. Exercise the documented installers, check the `migreat` entry point and metadata, and run the portable PostgreSQL scenario from an URL-installed copy on each target. Record the GitHub Release URL, tag and commit, workflow URL, artifact hashes, and platform results. Mark the release complete only when public installs pass.
