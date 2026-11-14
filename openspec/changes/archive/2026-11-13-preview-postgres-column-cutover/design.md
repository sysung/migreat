# Design

## Context

The existing backfill reads catalog metadata and bounded key/value snapshots. It previews in a read-only transaction, then rechecks under locks before filling a prepared column.

## Goals / Non-Goals

Add one nullable column and fill a bounded historical range through the existing commands. The daily writer is paused and drained by the operator. Model discovery, future-row defaults, and arbitrary SQL expressions are outside this slice.

## Decisions

- Add a distinct column-addition declaration. The declaration describes the desired schema and historical fill. Keep the existing seven-field declaration and its prepared-column behavior. The new shape names the destination, bigint key, and inclusive range. It selects either numeric scaling from a named retained bigint field matched by key or a transaction timestamp. The policy determines the output type (`numeric` or `timestamptz`). Numeric scaling takes an explicit finite decimal multiplier such as `0.01` for cents to dollars. The timestamp policy reads the target only.
- Build the ordered SQL once from validated identifiers and bound values. Use the same planner for both commands. Standalone `plan` displays a read-only preview and exits. Following Terraform's interactive flow, `apply` builds and displays a fresh plan in the same invocation, then requires the existing literal `yes` before running the reviewed statements. The first version uses this interactive mode. Show the policy in normal output. Show proposed numeric values from retained data and identify the timestamp as the apply transaction start. Read the catalog and scoped rows without simulating DDL. Keep the 1,000-key limit and existing relation checks.
- Start the write transaction after confirmation. Acquire locks in table order, with ACCESS EXCLUSIVE on the target and SHARE on the source if used. Recheck the reviewed state, add the nullable column without a default, and fill eligible rows inside the same transaction. Use one transaction timestamp for both the fill and verification. Before commit, verify the planned schema addition, unchanged scoped keys, and expected values. Any failure rolls back both statements. An empty scope still needs confirmation for the column addition.
- Require the new column to be absent. If it already exists, stop before confirmation. This keeps a rerun after a successful or uncertain commit from restamping history or adopting a column created elsewhere. The operator can inspect the database to determine the outcome.

## Risks / Trade-offs

The target lock blocks readers and writers during apply. Retain the existing lock and statement timeouts. An explicit update makes the bounded fill visible and leaves rows outside the range NULL. A column default at creation would broaden the fill to every existing row.
