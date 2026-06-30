# Ab Initio → Databricks — Migration Target (dbt + Lakehouse)

Target-state dbt/Databricks project for migrating the legacy Ab Initio ETL estate
in
[`ts-python-abinitio-etl`](https://github.com/Cognition-Partner-Workshops/ts-python-abinitio-etl)
to the Databricks Lakehouse. Each Ab Initio graph maps to a dbt model (or a
notebook job when procedural), and every conversion is gated by a **source →
target reconciliation harness** that proves the output reproduces the legacy
extract.

This is the Databricks counterpart to
[`uc-data-migration-abinitio-to-pyspark`](https://github.com/Cognition-Partner-Workshops/uc-data-migration-abinitio-to-pyspark)
(the platform-agnostic, locally-runnable Spark target).

## Quick Start

```bash
pip install -r requirements.txt -r verify/requirements.txt

# No Databricks connection required (what CI gates on):
make lint          # sqlfluff lint on dbt_project/models/
make parse         # dbt parse (validates the project graph)

# With DATABRICKS_HOST / DATABRICKS_HTTP_PATH / DATABRICKS_TOKEN set:
make demo-up   NS=dev   # seed raw -> dbt build (models + schema + reconcile_*.sql tests)
make reconcile NS=dev   # source -> target reconciliation report
make demo-down NS=dev   # drop this namespace's schemas (raw untouched)
```

Outputs land in `retail_analytics.<NS>_staging / _intermediate / _marts`, so
multiple runs (`NS=dev`, `NS=alice`, …) never collide.

## Repository Structure

```
├── dbt_project/
│   ├── dbt_project.yml / profiles.yml   # env-var based Databricks connection
│   ├── models/
│   │   ├── staging/                     # stg_customers, stg_orders (+ sources, tests)
│   │   ├── intermediate/                # int_customer_orders
│   │   └── marts/                       # mart_daily_orders
│   ├── macros/                          # DML defaults + code expansions as Jinja macros
│   └── tests/reconcile_*.sql            # singular reconciliation tests (build gate)
├── verify/reconcile.py                  # source -> target reconciliation report (CI gate)
├── seed/                                # generate_and_load.py (raw -> Unity Catalog), teardown.py
├── workflows/                           # Databricks Workflow (Asset Bundle job) + mapping doc
├── databricks.yml                       # Asset Bundle (deploy / run-job / destroy)
├── docs/ABINITIO_TO_DBT_MIGRATION_MAP.md
├── .workshop/playbooks/                 # portable Devin Playbook source (copied into the org)
├── .agents/skills/                      # repo Skill: how to convert/verify here (auto-loaded)
└── Makefile
```

## The verification loop (why this repo exists)

The point of the migration is not to produce *some* output on Databricks — it is
to produce output we can **trust** reproduces what the legacy Ab Initio graphs
would have produced. Trust is established with deterministic reconciliation
controls between the raw source and the converted marts:

| Control | Where | Proves |
|---|---|---|
| `reconcile_orders_control_total` | dbt singular test | mart `SUM(total_amount)` ties out to source `SUM(amount)` |
| `customers_completeness` | `verify/reconcile.py` | staging customers = raw customers |
| `orders_completeness` | `verify/reconcile.py` | staging orders = raw orders |
| `orders_control_total` | `verify/reconcile.py` | mart total ties out to raw |
| `transactions_channel_parity` | `verify/reconcile.py` | curated channel applies the DML `null("UNKNOWN")` default (live-conversion target) |

dbt `build` fails if any `reconcile_*.sql` returns rows; `verify/reconcile.py`
exits non-zero on any FAIL, so both gate CI and pre-merge.

## Conversion Playbook & Skill

The reusable Ab Initio → Databricks **conversion procedure** is a
[Devin Playbook](https://docs.devin.ai/product-guides/creating-playbooks). Its
source lives at `.workshop/playbooks/abinitio-to-databricks-conversion.devin.md`.

**Facilitator / demo presenter:** before running, copy that file's contents into
your Devin organization (Settings → Playbooks → *Create a new Playbook*) so
sessions can invoke it as `!convert-abinitio-to-databricks`. The playbook is
portable; it is not auto-loaded from the repo — registering it in the org is what
makes it available across sessions.

The repo-specific mechanics (the `make demo-up` / `make reconcile` commands,
namespaces, and where the sources, macros, and reconciliation controls live) are
kept in a [Skill](https://docs.devin.ai/product-guides/skills) at
`.agents/skills/abinitio-to-databricks-conversion/SKILL.md`, which Devin
auto-discovers and loads when working in this repo.

### What is converted on `main` vs live

`main` carries the durable **before**-state — the customer and orders pipelines
already converted (staging → intermediate → marts), plus the reconciliation
harness, the seed loader, the playbook source, and the Skill. The work Devin does
**live** in the demo is the next wave — the transactions pipeline (flatten nested
line items + reproduce the DML `null("UNKNOWN")` channel default) and the
customer-CDC pipeline (compare-by-key + row hash → Delta `MERGE`). See
[`docs/ABINITIO_TO_DBT_MIGRATION_MAP.md`](docs/ABINITIO_TO_DBT_MIGRATION_MAP.md).

## Related Repositories

| Repo | Purpose |
|---|---|
| [`ts-python-abinitio-etl`](https://github.com/Cognition-Partner-Workshops/ts-python-abinitio-etl) | Source Ab Initio estate (graphs, DML, PSETs, CDC, KornShell orchestration) |
| [`uc-data-migration-abinitio-to-pyspark`](https://github.com/Cognition-Partner-Workshops/uc-data-migration-abinitio-to-pyspark) | Platform-agnostic PySpark target (local reconciliation) |
