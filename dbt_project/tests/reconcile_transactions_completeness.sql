/*
  Reconciliation test: transaction completeness — no silent row loss / fan-out.

  The Ab Initio transaction detail graph (transaction_detail.dml) loaded one
  curated record per source transaction. The curated table must therefore carry
  exactly as many rows as the raw transaction extract: any dropped rows (a filter
  that lost transactions) or fanned-out rows (an over-eager explode of the
  line_items array) surfaces here.

  dbt singular test convention: the test FAILS if this query returns any rows.
*/
with source_count as (
    select count(*) as n
    from {{ source('abinitio_raw', 'transactions') }}
),

curated_count as (
    select count(*) as n
    from {{ ref('curated_transactions') }}
)

select
    s.n as source_count,
    c.n as curated_count,
    c.n - s.n as difference
from source_count s
cross join curated_count c
where s.n <> c.n
