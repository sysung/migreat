# Tasks

## 1. Review and execute through the new commands

- [x] 1.1 Move read-only planning and both SQL builders to `plan.py`. Carry the operation, snapshots, review details, blockers, and ordered bound SQL in one result. Verify YAML planning against the documented fixture and use PostgreSQL catalog and row reads to confirm the preview leaves both tables unchanged.
- [x] 1.2 Move write orchestration to `apply.py`. Share timeout, ordered locking, drift, and execution steps across the operation variants. Keep variant-specific locks and postconditions. Execute the reviewed statements and resolve timestamp expectations inside the write transaction. Verify that the existing integration scenarios still detect same-count drift, table replacement, lock timeout, and rollback on failed verification.
- [x] 1.3 Expose only top-level `plan` and `apply`, route YAML through the same report and confirmation flow, and remove `cutover.py` and its README instructions. Align existing test invocations and moved Python references without expanding scenarios or assertions. Install into a clean environment, run both help commands, confirm the old groups fail, and run the existing PostgreSQL suite.
- [x] 1.4 Use a disposable PostgreSQL instance to run the YAML timestamp and empty-scope column-addition commands. Read back the schema and rows to confirm an empty scope adds the column after confirmation and an in-scope timestamp fill uses one transaction timestamp. Confirm an already-correct existing-column fill exits before confirmation.

## 2. Translate one dbt column addition with the original scale implementation

- [x] 2.1 Add the paired manifest flags and document a compiled PostgreSQL example. Validate argument exclusivity, adapter, exact model identity, resolved relation, and compiled SQL. Confirm mixed input, missing compiled code, and changed target produce blockers through the CLI. Verify installation of the chosen PostgreSQL-aware parser on the supported installation targets.
- [x] 2.2 Compare the parsed direct-source queries. Require one new named projection, unchanged existing outputs, and no filter or other row-shaping clause. Admit the retained bigint field with explicit numeric cast and decimal multiplier. Run plan with changed existing output, a filter in both versions, and a valid unsupported expression such as integer division. Confirm that none can reach confirmation and that a recognized addition appears in the report.
- [x] 2.3 Resolve the source and run the generated read-only PostgreSQL expression probe in the planning transaction. Where safe, run the probe before custom field or type diagnostics that would mask PostgreSQL's error. Reuse existing scoped catalog and matching checks, then feed the validated operation into the same SQL builder and reviewed result. Verify a real native diagnostic using an admitted expression with a missing live field. Confirm that missing, duplicate, and NULL matches block apply.

## 3. Verify the complete dbt flow

- [x] 3.1 Drive a compiled baseline and candidate through `plan`, declined `apply`, and confirmed `apply` on a disposable PostgreSQL instance. Compare plan output and bound parameters with the fresh apply review. Query the database after each command to verify that plan and decline leave it unchanged and successful apply adds exactly one numeric column with expected keyed values, NULL outside the range, and unchanged existing fields.
- [x] 3.2 Change a scoped input value while a dbt apply waits for confirmation and verify a nonzero exit with no committed column. Run the existing suite and Docker help check through their normal entry points. Record commands, observed outcomes, and any checks the environment prevented.

## 4. Generalize the dbt column calculation

- [x] 4.1 Replace the dbt scale-only matcher with recursive scalar expression handling. Resolve retained fields, compose supported operators, casts, CASE, and COALESCE, preserve SQL literal typing and psycopg placeholder handling, and block unsupported nodes before execution. Verify with a multi-column expression combining these forms and an unsupported function.
- [x] 4.2 Resolve the added column's PostgreSQL type even for an empty scope. Evaluate admitted expressions over scoped historical keys in the read-only transaction and show native PostgreSQL errors. Verify a type modifier, missing-column and division-by-zero diagnostics and compare the reported type and values with a direct PostgreSQL SELECT.
- [x] 4.3 Carry reviewed input values, result values, and SQL into apply. Recheck referenced inputs and metadata under locks, execute the reviewed SQL, and verify exact keyed values including NULL and the resulting schema. Verify a compensating input change that leaves the result unchanged still blocks a stale apply.
- [x] 4.4 Support row-independent constants and transaction-time values. Add an inline TODO where they are classified to warn about potential differences from historical values. Verify a constant and a timestamp without source matches and a mixed column-and-time calculation with source matches. A pause at confirmation must change the transaction-time result without triggering a stale-plan failure.
- [x] 4.5 Update the README with the supported expression forms, multi-column example, and blocker behavior. Preserve existing YAML format and behavior. Verify the documented example and run the existing integration suite.

## 5. Verify the expanded workflow end to end

- [x] 5.1 Compile real dbt model pairs and compare plan, cancellation, and confirmed apply with PostgreSQL readbacks. Cover integer versus numeric division, a multi-column conditional, NULL propagation and COALESCE, an empty range, and unchanged out-of-range rows. Compare keyed values and column type with the candidate SELECT and verify preview and cancellation leave schema and rows unchanged.
- [x] 5.2 Exercise native errors, duplicate and missing key matches, unsupported expressions, and stale data. Verify failures produce no committed addition and use the existing rollback checks for a post-write verification failure. Rerun the existing YAML and Docker checks through their normal entry points and record outcomes and any environmental limits.

Verification uses existing tests and direct CLI and PostgreSQL runs with disposable inputs. Adding or extending behavioral tests or saving a standalone verifier requires explicit authorization.

## Arena synthesis

Candidate 2 supplied the base. Both candidates converged on a narrow PostgreSQL AST comparison, bound SQL carried in one reviewed result, and separate transaction ownership. The cross-judge also preferred candidate 2 for catching that an unchanged filter could still make the dbt model's scope differ from the backfill's key range. The first slice blocks filtered models. Candidate 1 contributed the ordering of the safe PostgreSQL probe before application diagnostics that might hide a native error. The plan excludes regex SQL comparison, execution of arbitrary compiled SQL, and a persisted-plan workflow.

## Arena synthesis for general calculations

Candidate 2 supplied the base for its expression ownership, mixed column-and-time semantics, and database readbacks. The cross-judge scored it 10/10 and candidate 1 9/10. Both candidates favored a bounded scalar AST, PostgreSQL-owned calculation semantics, and reuse of the reviewed write transaction. Candidate 1 contributed explicit temporary-schema ordering, literal and placeholder handling, and PostgreSQL-native comparisons where Python cannot reliably represent values. Raw compiled SQL, new policies for each example, and replaying preview values were rejected because they would weaken execution safety or change expression semantics. The added tasks were implemented and verified.

## Verification results

- Compiled real dbt manifests and ran `migreat plan` and `migreat apply` against isolated PostgreSQL. Direct SQL confirmed the documented net-dollars example, CASE and COALESCE, numeric precision, NULL propagation, integer and numeric division, remainder, and unchanged out-of-range rows. An empty range added the typed column and filled zero rows.
- CLI checks confirmed native missing-column and division-by-zero messages, unsupported function and key-match blockers, cancellation, and stale rejection after compensating input changes. A delayed confirmation produced a fresh transaction-time value for a mixed expression.
- `python -m unittest discover -s tests -v` passed all 11 existing tests. The Docker build and `migreat --help` in the built image passed.
