/*
  int_customer_orders.sql
  Migrated from: Ab Initio join + rollup graph (customer master joined to the
  order extract, aggregated per customer).

  Ab Initio Original:
    Join component (customer_id key) -> Rollup component producing per-customer
    order metrics.

  dbt Equivalent:
    Intermediate table joining stg_customers to stg_orders and aggregating.
    Inner join on customer_id reproduces the legacy join's "orders for known
    customers" contract.
*/

with customers as (
    select * from {{ ref('stg_customers') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

agg as (
    select
        customer_id,
        count(*) as order_count,
        sum(amount) as total_amount,
        sum(item_count) as total_items,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date
    from orders
    group by customer_id
)

select
    c.customer_id,
    c.first_name,
    c.last_name,
    c.state,
    c.status,
    coalesce(a.order_count, 0) as order_count,
    coalesce(a.total_amount, cast(0 as decimal(12, 2))) as total_amount,
    coalesce(a.total_items, 0) as total_items,
    a.first_order_date,
    a.last_order_date
from customers c
inner join agg a
    on c.customer_id = a.customer_id
