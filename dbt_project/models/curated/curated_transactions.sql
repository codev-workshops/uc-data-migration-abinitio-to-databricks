/*
  curated_transactions.sql
  Migrated from: ts-python-abinitio-etl transaction detail graph
                 (dml/transaction_detail.dml) — the curated transaction load.

  Ab Initio Original:
    Reformat that applied the DML record defaults before the transaction was
    loaded to the curated target. Two defaults are declared in
    transaction_detail.dml:
      * channel:       string("\n", null("UNKNOWN"))
      * merchant_name: string(",",  null(""))
    Ab Initio reads a blank delimited field as an empty string, and the null(...)
    clause substitutes the declared default. So a BLANK channel in the extract is
    read as the literal 'UNKNOWN' (never NULL), and a blank merchant_name is read
    as the empty string.

  dbt Equivalent:
    Curated table reading stg_transactions and reproducing the DML defaults
    value-for-value:
      channel       -> coalesce(nullif(trim(channel), ''), 'UNKNOWN')
      merchant_name -> coalesce(nullif(trim(merchant_name), ''), '')
    These reproduce legacy behaviour exactly; they are source-faithful, not an
    endorsement of the quirk (blank != NULL). The transactions_channel_parity
    control (dbt test + verify/reconcile.py) fails if the channel default is not
    applied. See the conversion playbook's worked example.

    One row per transaction (the extract is already flat, item_count = 1), so the
    completeness and control-total controls tie curated back to raw 1:1.
*/

with transactions as (
    select * from {{ ref('stg_transactions') }}
)

select
    txn_id,
    txn_timestamp,
    customer_id,
    txn_type,
    coalesce(nullif(trim(merchant_name), ''), '') as merchant_name,
    merchant_category,
    amount,
    item_count,
    sku,
    quantity,
    line_total,
    coalesce(nullif(trim(channel), ''), 'UNKNOWN') as channel
from transactions
