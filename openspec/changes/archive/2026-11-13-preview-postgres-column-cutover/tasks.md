# Tasks

## 1. Preview the cutover

- [x] 1.1 Add the column-addition declaration and read-only preview with ordered SQL, bound values, and counts for numeric scaling and the apply transaction timestamp. Document one declaration for each policy in the README. On disposable PostgreSQL tables, run both plans and query the catalog to confirm the new column is still absent. Run an invalid policy and an already-present column case and confirm both exit nonzero before confirmation.

## 2. Apply and verify the cutover

- [x] 2.1 Have apply generate and show a fresh plan before the literal `yes` prompt, then run the reviewed SQL with stable lock order, a fresh comparison under lock, and schema and value verification before commit. In disposable PostgreSQL, invoke apply directly and verify that it displays SQL before asking for approval. Change a retained value after a standalone plan and check that apply previews the current value. Decline once and confirm the column stays absent. Confirm both policies on separate tables and query the column type, exact scaled values, one shared transaction timestamp, stable keys, unchanged unrelated values, and NULLs outside the range. Confirm an empty range adds the column and reports zero fills. Rerun a successful declaration and confirm the persisted values are unchanged.
- [x] 2.2 Exercise drift and rollback separately on disposable PostgreSQL. Change a retained value while confirmation is open and verify apply refuses the stale plan. Cause a write failure after DDL and verify the column and fill are both absent after rollback. Install the changed CLI and run the existing Docker-backed suite with `python -m unittest discover -s tests -v`.
