/*
  stg_transactions.sql
  Migrated from: ts-python-abinitio-etl transaction detail graph
                 (dml/transaction_detail.dml, run via the daily batch estate).

  Ab Initio Original:
    Input-file component (pipe-delimited transaction extract) bound to
    transaction_detail.dml -> reformat -> typed transaction record. The DML
    record layout is:
      decimal(",") txn_id / customer_id / txn_type
      datetime("YYYY-MM-DD HH24:MI:SS") txn_timestamp
      merchant_info { string(null("")) merchant_name; string merchant_category;
                      decimal("10.2") amount }
      decimal(",") item_count
      line_items[item_count] { string sku; decimal quantity;
                               decimal("8.2") line_total }
      string("\n", null("UNKNOWN")) channel

  dbt Equivalent:
    Staging view reading raw.transactions. Faithful typed pass-through: every
    source row preserved, no business defaults applied here. txn_timestamp is
    parsed to a real TIMESTAMP (Ab Initio datetime("YYYY-MM-DD HH24:MI:SS")) and
    numeric fields are cast to match the DML precisions. The DML null(...)
    defaults (channel -> 'UNKNOWN', merchant_name -> '') are deliberately NOT
    applied here so the raw domain (including blank channels) stays visible to
    reconciliation; they are reproduced in curated_transactions.

    Note: the DML declares line_items as a variable-length array
    (record[item_count]). The raw extract materializes it flat — one line item
    per transaction row (item_count = 1) — so no explode is required to stay
    source-faithful to the extract.
*/

with source as (
    select * from {{ source('abinitio_raw', 'transactions') }}
)

select
    txn_id,
    to_timestamp(txn_timestamp, 'yyyy-MM-dd HH:mm:ss') as txn_timestamp,
    cast(customer_id as bigint) as customer_id,
    cast(txn_type as int) as txn_type,
    merchant_name,
    merchant_category,
    cast(amount as decimal(12, 2)) as amount,
    cast(item_count as int) as item_count,
    sku,
    cast(quantity as int) as quantity,
    cast(line_total as decimal(12, 2)) as line_total,
    channel
from source
