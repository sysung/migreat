# GitHub Actions CI

## Purpose

Give reviewers GitHub check results for the Python package, PostgreSQL integration suite, and Docker CLI.

## ADDED Requirements

### Requirement: Run CI on the default branch

GitHub Actions SHALL run CI for pull requests targeting `master` and pushes to `master`.

#### Scenario: Review a pull request

- **WHEN** a pull request targeting `master` is opened, reopened, or updated with commits
- **THEN** GitHub starts the CI checks for that pull request

#### Scenario: Push to the default branch

- **WHEN** a commit is pushed to `master`
- **THEN** GitHub starts the CI checks for that push

### Requirement: Verify the Python install and PostgreSQL integration suite

CI SHALL install migreat with Python 3.12 and execute the existing integration suite against its disposable PostgreSQL container.

#### Scenario: Run the integration suite

- **WHEN** the Python check runs
- **THEN** it installs the package and runs `python -m unittest discover -s tests -v`
- **AND** any installation or test failure fails the check

### Requirement: Verify the Docker CLI

CI SHALL build the repository Dockerfile and invoke `migreat --help` inside the resulting image.

#### Scenario: Check the Docker image

- **WHEN** the Docker check runs
- **THEN** it builds the image and runs the help command inside it
- **AND** any build or help failure fails the check
