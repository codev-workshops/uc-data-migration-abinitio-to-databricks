---
name: abinitio-to-databricks-conversion
description: Repo mechanics for converting an Ab Initio graph to a verified dbt/Databricks model in this repo — build/reconcile commands, namespaces, where the sources, macros, and reconciliation controls live. Supplements the general !convert-abinitio-to-databricks playbook.
---

## When to use this

Use this skill whenever you are converting an Ab Initio graph into a dbt model or
notebook job **in this repository**. It is the repo-specific companion to the
general procedure in the `!convert-abinitio-to-databricks` playbook
(`.workshop/playbooks/abinitio-to-databricks-conversion.devin.md`): the playbook
says *what* to do and *why* (source-parity principle, procedure, forbidden
actions); this skill says *how* to do it here (exact commands, paths, namespaces).

## Layout

- Ab Initio source estate (read-only): the `ts-python-abinitio-etl` repo (graphs,
  `dml/`, `psets/`, `scripts/*.ksh`).
- Raw extracts (the durable "before"): `retail_analytics.raw.*` Delta tables,
  loaded deterministically by `seed/generate_and_load.py` (`make seed`).
- Target dbt project: `dbt_project/` — `models/staging`, `models/intermediate`,
  `models/marts`; macros in `dbt_project/macros/` (e.g. DML `null(...)` defaults
  and code expansions); sources in `models/staging/_staging_sources.yml`.
- Reconciliation controls:
  - dbt singular tests (fail the build if they return rows):
    `dbt_project/tests/reconcile_*.sql`.
  - Cross-engine / report checks: `verify/reconcile.py`.
- Orchestration: `workflows/daily_orders_pipeline.yml` + the bundle `databricks.yml`.
- Connection is env-var based (`dbt_project/profiles.yml`): `DATABRICKS_HOST`,
  `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`. Catalog is `retail_analytics`.

## Namespaces (isolated, concurrent-safe)

Every run is namespaced by `NS` (→ `DBT_SCHEMA`). Outputs land in
`retail_analytics.<NS>_staging / _intermediate / _marts / _curated`, so multiple
runs (`NS=dev`, `NS=child1`, …) never collide and the durable "before" raw data in
`retail_analytics.raw` is never touched. Always build into the namespace you were
given; never write into another run's namespace or into `raw`.

## Build and verify

```bash
make demo-up   NS=<ns>   # seed (idempotent) + dbt build (models + schema tests + reconcile_*.sql)
make reconcile NS=<ns>   # human-facing source->target reconciliation report (verify/reconcile.py)
make demo-down NS=<ns>   # drop only that namespace's schemas (raw untouched)
```

- `make demo-up` runs `dbt build`, which executes the `reconcile_*.sql` singular
  tests; any returning rows fail the build.
- `make reconcile` runs `verify/reconcile.py`, which exits non-zero on any failed
  control and prints an attachable report.
- No-connection checks: `make lint` (sqlfluff) and `make parse` (dbt parse) run
  without a Databricks workspace and are what CI gates on.

## Adding reconciliation controls for a new graph

For each graph you convert, add controls under `dbt_project/tests/` named
`reconcile_<thing>.sql`, covering at minimum:

- **completeness** — model row count equals the documented in-scope source
  population (no silent row loss, no fan-out);
- **control total** — a SUM (e.g. total order/transaction amount) that ties out to
  the source extract;
- **parity** — every DML default / mapping / CDC delta class matches the source
  value-for-value.

For cross-engine (notebook/PySpark) outputs and domain controls like the
`transactions_channel_parity` check, add them to `verify/reconcile.py`. Each report
control should `SKIP` (not FAIL) until its target table exists, so the harness is
forward-looking and the SKIP→PASS transition is visible when the conversion lands.

## Close the loop

If a control fails, investigate against the Ab Initio source (the graph + DML) —
**do not** relax, delete, or hard-code the control to make it pass. Fix the model
and re-run `make demo-up NS=<ns>` and `make reconcile NS=<ns>` until both are
green, then open a PR that includes the reconciliation report output.

## Deploy / revert (optional, CD demo)

```bash
make deploy           # databricks bundle deploy -t dev (namespaced per user, schedule paused)
make run-job          # trigger the deployed daily_orders_pipeline job
make destroy          # databricks bundle destroy -t dev (revert)
```
