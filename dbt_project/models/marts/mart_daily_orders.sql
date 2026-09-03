/*
  mart_daily_orders.sql
  Migrated from: ts-python-abinitio-etl daily orders pipeline
                 (scripts/run_daily_orders.ksh, phase 4: production rollover).

  Ab Initio Original:
    Rollup component aggregating staged orders by order_date into the daily
    reporting table.

  dbt Equivalent:
    Mart table with a GROUP BY on order_date producing order_count,
    total_amount, and total_items.
*/

with orders as (
    select * from {{ ref('stg_orders') }}
)

select
    order_date,
    count(*) as order_count,
    sum(amount) as total_amount,
    sum(item_count) as total_items
from orders
group by order_date
order by order_date
