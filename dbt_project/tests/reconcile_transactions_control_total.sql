/*
  Reconciliation test: transaction control total ties out to the source extract.

  The transaction amount (Ab Initio merchant_info.amount, decimal("10.2")) must
  be conserved end to end: the sum across the curated transactions table must
  equal the sum across the raw transaction extract, to the cent. A unit/rounding
  error in the cast, a dropped row, or a fanned-out join surfaces here.

  dbt singular test convention: the test FAILS if this query returns any rows.
*/
with source_total as (
    select sum(cast(amount as decimal(12, 2))) as n
    from {{ source('abinitio_raw', 'transactions') }}
),

curated_total as (
    select sum(amount) as n
    from {{ ref('curated_transactions') }}
)

select
    s.n as source_total,
    c.n as curated_total,
    c.n - s.n as difference
from source_total s
cross join curated_total c
where s.n <> c.n
