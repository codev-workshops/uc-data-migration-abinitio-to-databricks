/*
  Reconciliation test: order control total ties out to the source extract.

  The Ab Initio daily orders pipeline (run_daily_orders.ksh) rolled the staged
  orders up into the daily reporting table. The control total — total order
  amount — must be conserved end to end: the sum across the daily mart must equal
  the sum across the raw order extract, to the cent. Any silent row loss, a
  fanned-out join, or a unit/rounding error in the conversion surfaces here.

  dbt singular test convention: the test FAILS if this query returns any rows.
*/
with source_total as (
    select sum(cast(amount as decimal(12, 2))) as n
    from {{ source('abinitio_raw', 'orders') }}
),

mart_total as (
    select sum(total_amount) as n
    from {{ ref('mart_daily_orders') }}
)

select
    s.n as source_total,
    m.n as mart_total,
    m.n - s.n as difference
from source_total s
cross join mart_total m
where s.n <> m.n
