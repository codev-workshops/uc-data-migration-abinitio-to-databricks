/*
  stg_orders.sql
  Migrated from: ts-python-abinitio-etl daily orders pipeline
                 (scripts/run_daily_orders.ksh, phases 1-3: extract -> CDC ->
                 staging load).

  Ab Initio Original:
    Input-file component (pipe-delimited order extract) -> reformat -> typed
    STAGING.ORDERS load.

  dbt Equivalent:
    Staging view reading raw.orders. order_date is parsed to a real DATE
    (Ab Initio date("YYYY-MM-DD")). All source rows preserved.
*/

with source as (
    select * from {{ source('abinitio_raw', 'orders') }}
)

select
    order_id,
    cast(customer_id as bigint) as customer_id,
    to_date(order_date, 'yyyy-MM-dd') as order_date,
    upper(order_status) as order_status,
    cast(item_count as int) as item_count,
    cast(amount as decimal(12, 2)) as amount,
    currency
from source
