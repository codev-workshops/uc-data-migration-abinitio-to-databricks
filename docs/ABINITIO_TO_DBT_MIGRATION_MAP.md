# Ab Initio → dbt/Databricks Migration Map

Construct-level mapping from the legacy Ab Initio estate
([`ts-python-abinitio-etl`](https://github.com/Cognition-Partner-Workshops/ts-python-abinitio-etl))
to this dbt/Databricks Lakehouse target. Use it as the reference when converting
a graph.

## Runtime & orchestration

| Ab Initio | Databricks target |
|---|---|
| Co>Operating System (`air sandbox run`) | Databricks SQL warehouse / dbt |
| Graph (`.mp`) | dbt model (set-based) or notebook job (procedural) |
| `m_partition` / partition parallelism | Spark partitions / cluster autoscaling |
| KornShell wrapper (`scripts/*.ksh`) | Databricks Workflow (`workflows/daily_orders_pipeline.yml`) |
| AutoSys / Control-M schedule | Workflow `schedule.quartz_cron_expression` |
| PSET (`define KEY value`) | dbt `vars` / job parameters / `DBT_SCHEMA` namespace |
| LIBNAME-style file landing | Unity Catalog external/Delta tables (`retail_analytics.raw`) |

## DML record layouts → Delta / dbt types

DML lives in the source repo's `dml/`; the equivalents land in the
`retail_analytics.raw` Delta tables (see `seed/generate_and_load.py`) and the
staging models.

| DML construct | Example | Databricks type |
|---|---|---|
| `decimal(",")` (id / count) | `customer_id`, `item_count` | `bigint` / `int` |
| `decimal("8.2", "\|")` (money) | `amount`, `line_total` | `decimal(12,2)` |
| `string(",")` | `first_name`, `channel` | `string` |
| `date("YYYY-MM-DD")` | `order_date` | `to_date(...)` → `date` |
| `datetime("YYYY-MM-DD HH24:MI:SS")` | `txn_timestamp` | `to_timestamp(...)` → `timestamp` |
| `string(..., null("UNKNOWN"))` | `channel` default | `coalesce(nullif(trim(col),''),'UNKNOWN')` |
| `[item_count]` variable array | `line_items[]` | `array<struct<...>>` / `explode` |
| delimiter (`","`, `"\|"`) | per record | reader option / seed loader |

> **Blank ≠ NULL.** Ab Initio reads a blank delimited field as an empty string;
> the `null(...)` clause substitutes the default. Reproduce DML defaults
> deliberately — see the channel worked example in the conversion playbook.

## Transform components → dbt / SQL

| Ab Initio component | dbt / Databricks |
|---|---|
| Reformat | `select` / computed columns |
| Filter by Expression | `where` |
| Join | `join ... on` (broadcast for small lookups) |
| Rollup | `group by ... agg` |
| Dedup Sorted | `qualify row_number() over (...)` |
| Scan (running total) | window function |
| **Compare Records by Key (CDC)** | Delta `MERGE INTO` keyed on by-keys + row hash |

## Program-level migration map

| Ab Initio pipeline | dbt model(s) | Status | Pattern |
|---|---|---|---|
| Customer snapshot (`run_customer_cdc.ksh` step 1) | `stg_customers` | on `main` | source → staging view |
| Daily orders extract→staging (`run_daily_orders.ksh` ph.1-3) | `stg_orders` | on `main` | typed read + date parse |
| Customer/order join + rollup | `int_customer_orders` | on `main` | join + `group by` |
| Orders production rollover (`run_daily_orders.ksh` ph.4) | `mart_daily_orders` | on `main` | rollup → mart |
| Transactions detail (`transaction_detail.dml`) | `stg_transactions` → `curated_transactions` | **live conversion** | flatten + DML `null("UNKNOWN")` default |
| Customer CDC (`cdc_processor.py`, `customer_cdc.pset`) | `snapshots/` + `MERGE` | **live conversion** | compare-by-key + row hash |

"Live conversion" rows are the work Devin does during the demo via
`!convert-abinitio-to-databricks`; `main` carries the durable before-state plus
the reconciliation harness.

## Reconciliation contract

Every conversion is gated by:

- **dbt singular tests** (`dbt_project/tests/reconcile_*.sql`) — fail the build if
  they return rows (e.g. `reconcile_orders_control_total.sql`);
- **the report harness** (`verify/reconcile.py`) — completeness, control totals,
  and per-class parity (e.g. the transactions channel-default parity), exiting
  non-zero on any FAIL so it gates CI and pre-merge.

A report control `SKIP`s until its target table exists, then must `PASS`.
