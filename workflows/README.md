# Databricks Workflows — Replacing AutoSys/Control-M + KornShell Orchestration

## Overview

`daily_orders_pipeline.yml` is a Databricks Asset Bundle job resource that
replaces the Ab Initio batch orchestration previously defined in
`ts-python-abinitio-etl/scripts/run_daily_orders.ksh` and `run_customer_cdc.ksh`,
scheduled by AutoSys/Control-M. It is deployed via the bundle at the repo root
(`databricks.yml`): `make deploy` / `make run-job` / `make destroy`.

## Ab Initio/AutoSys → Databricks Workflow mapping

| Ab Initio / AutoSys construct | Databricks Workflow equivalent |
|---|---|
| AutoSys JIL job definition | Workflow resource in `daily_orders_pipeline.yml` (version-controlled) |
| KornShell wrapper (`run_daily_orders.ksh`) | the `daily_orders_pipeline` job |
| `air sandbox run <graph>` phase | a `dbt_task` |
| sequential `.ksh` phases | `tasks[].depends_on` DAG edges |
| `air sandbox run` exit-code checks + abort | task-level `max_retries` + failure notifications |
| mail on failure | `email_notifications.on_failure` (+ webhook) |
| AutoSys calendar / time conditions | `schedule.quartz_cron_expression` |
| `.ksh` per-phase log files | Databricks run history + Spark UI |
| manual restart from a failed phase | Workflow "Repair Run" (re-run from failed task) |

## Before (Ab Initio + AutoSys) vs After (Databricks Workflows)

### Before

```
AutoSys/Control-M             Co>Operating System
─────────────────            ─────────────────────
06:00 trigger  ───────────→  run_daily_orders.ksh
                               phase 1 air sandbox run extract_orders
                               phase 2 air sandbox run cdc_orders
                               phase 3 air sandbox run load_staging
                               phase 4 air sandbox run rollover_daily
                               mail on non-zero exit
```

- Job definition lives in the AutoSys GUI/JIL, not in version control.
- Restart-from-failed-phase is manual operator work.
- Logs scattered across the Co>Op sandbox file system.

### After

```
Databricks Workflow Engine
──────────────────────────
06:00 cron trigger
  ├── dbt_staging       (dbt run --select tag:staging)
  ├── dbt_intermediate  (depends on staging)
  ├── dbt_marts         (depends on intermediate)
  └── dbt_test          (depends on marts; reconcile_*.sql gate)

  On failure → email + webhook
  Repair Run → re-execute from the failed task only
```

- Job definition is version-controlled and code-reviewed.
- Automatic retries and partial re-runs (Repair Run).
- Reconciliation controls run as the final gate before the pipeline is "green".
