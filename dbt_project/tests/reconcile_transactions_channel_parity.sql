/*
  Reconciliation test: transaction channel default parity (per-value).

  dml/transaction_detail.dml declares:
      string("\n", null("UNKNOWN")) channel
  Ab Initio reads a blank delimited channel as an empty string and the null(...)
  clause substitutes the literal 'UNKNOWN' — so a blank source channel must land
  as 'UNKNOWN' in the curated table, never as NULL or blank, and a non-blank
  source channel must pass through unchanged.

  This is a per-value parity check, not an aggregate: it recomputes the DML
  default from the raw source for every transaction and compares it to the
  curated value. Row counts and control totals can still tie out while an
  individual channel class is wrong (the canonical defect in the playbook), so
  this control compares each transaction's channel to the source contract.

  dbt singular test convention: the test FAILS if this query returns any rows.
*/
with source as (
    select
        txn_id,
        coalesce(nullif(trim(channel), ''), 'UNKNOWN') as expected_channel
    from {{ source('abinitio_raw', 'transactions') }}
),

curated as (
    select
        txn_id,
        channel as actual_channel
    from {{ ref('curated_transactions') }}
)

select
    s.txn_id,
    s.expected_channel,
    c.actual_channel
from source s
inner join curated c
    on s.txn_id = c.txn_id
where c.actual_channel is null
    or c.actual_channel <> s.expected_channel
