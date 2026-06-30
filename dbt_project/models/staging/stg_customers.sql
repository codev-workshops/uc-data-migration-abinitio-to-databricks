/*
  stg_customers.sql
  Migrated from: ts-python-abinitio-etl customer snapshot graph
                 (scripts/run_customer_cdc.ksh, step 1) reading customer.dml +
                 customer_address.dml.

  Ab Initio Original:
    Input-file component bound to customer.dml (comma-delimited) -> reformat ->
    typed staging record.

  dbt Equivalent:
    Staging view reading the raw.customers Delta table (Unity Catalog) that
    replaces the flat-file landing area. Faithful pass-through: no rows dropped,
    status domain preserved (ACTIVE/INACTIVE/PENDING).
*/

with source as (
    select * from {{ source('abinitio_raw', 'customers') }}
)

select
    cast(customer_id as bigint) as customer_id,
    first_name,
    last_name,
    email,
    concat_ws(', ', street, city, state, zip) as full_address,
    state,
    upper(status) as status
from source
