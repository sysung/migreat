# Tasks

## 1. GitHub Actions CI

- [ ] 1.1 Add the CI workflow for pull requests targeting `master` and pushes to `master`. Check that both events select the Python and Docker jobs.
- [ ] 1.2 Configure the Python 3.12 install and PostgreSQL integration check. Verify package installation and the existing suite in the Python job logs.
- [ ] 1.3 Configure the Docker build and help check. Verify that the image builds and the installed CLI prints help in the Docker job logs.

## 2. Verify on GitHub

- [ ] 2.1 On a PR targeting `master`, confirm both checks pass. On a disposable test branch, independently introduce a failing integration test and an invalid Dockerfile instruction. Confirm each produces a failed check, then revert both and confirm green checks.
- [ ] 2.2 After the workflow merges, confirm GitHub Actions runs both checks on the resulting push to `master`.
