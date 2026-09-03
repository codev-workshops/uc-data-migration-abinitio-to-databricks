#!/usr/bin/env python3
"""
Synthetic source generator + loader for the Ab Initio -> Databricks migration.

In the legacy Ab Initio estate the graphs read flat files described by DML record
formats (see ts-python-abinitio-etl/dml/). Here we materialize the equivalent
"raw" tables as Delta tables in Unity Catalog (catalog `retail_analytics`, schema
`raw`) so the dbt project has real data to run against end to end. The generated
content matches the local `uc-data-migration-abinitio-to-pyspark` seed so the two
targets reconcile against the same source.

Deterministic: a fixed RNG seed produces the same data every run, so dbt tests
and the reconciliation report are stable.

Usage:
    python seed/generate_and_load.py                       # default volumes
    python seed/generate_and_load.py --customers 100 --orders 160 --transactions 80

Auth (env vars, same ones dbt uses):
    DATABRICKS_HOST        e.g. https://dbc-xxxx.cloud.databricks.com
    DATABRICKS_HTTP_PATH   e.g. /sql/1.0/warehouses/xxxxxxxx
    DATABRICKS_TOKEN       dapi...
"""
from __future__ import annotations

import argparse
import os
import random

from databricks import sql

CATALOG = "retail_analytics"
RAW_SCHEMA = "raw"

FIRST_NAMES = ["John", "Jane", "Bob", "Alice", "Charlie", "Diana", "Edward",
               "Fiona", "George", "Helen", "Ivan", "Julia", "Kevin", "Laura",
               "Mike", "Nina", "Oscar", "Paula", "Quinn", "Rachel"]
LAST_NAMES = ["Smith", "Doe", "Johnson", "Williams", "Brown", "Martinez",
              "Garcia", "Lee", "Wilson", "Anderson", "Taylor", "Thomas", "Moore",
              "Jackson", "White", "Harris", "Clark", "Lewis", "Young", "King"]
CITIES = [("New York", "NY", "10001"), ("Chicago", "IL", "60601"),
          ("Houston", "TX", "77001"), ("Phoenix", "AZ", "85001"),
          ("Philadelphia", "PA", "19101"), ("San Antonio", "TX", "78201"),
          ("San Diego", "CA", "92101"), ("Dallas", "TX", "75201"),
          ("San Jose", "CA", "95101"), ("Austin", "TX", "73301")]
STREETS = ["Main St", "Oak Ave", "Pine Rd", "Elm St", "Maple Dr", "Cedar Ln",
           "Birch Way", "Spruce Ct", "Walnut Pl", "Ash Blvd"]
CUSTOMER_STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "INACTIVE", "PENDING"]
ORDER_STATUSES = ["SHIPPED", "DELIVERED", "PROCESSING", "CANCELLED"]
ORDER_DATES = [f"2024-01-{d:02d}" for d in range(15, 25)]
MERCHANTS = [("MERCHANT_A", "Retail"), ("MERCHANT_B", "Electronics"),
             ("MERCHANT_C", "Grocery"), ("MERCHANT_D", "Services")]
SKUS = ["SKU-100", "SKU-200", "SKU-300", "SKU-400", "SKU-500"]
# channel may be blank -> Ab Initio DML default is null("UNKNOWN").
TXN_CHANNELS = ["WEB", "STORE", "APP", "WEB", ""]


def gen_customers(n):
    rng = random.Random(101)
    rows = []
    for i in range(n):
        cid = 1001 + i
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[(i * 3) % len(LAST_NAMES)]
        city, state, zc = CITIES[i % len(CITIES)]
        street = f"{rng.randint(100, 999)} {STREETS[i % len(STREETS)]}"
        rows.append((cid, first, last, f"{first.lower()}.{last.lower()}{cid}@example.com",
                     street, city, state, zc,
                     CUSTOMER_STATUSES[rng.randrange(len(CUSTOMER_STATUSES))]))
    return rows


def gen_orders(n, customer_ids):
    rng = random.Random(202)
    rows = []
    for i in range(n):
        cid = rng.choice(customer_ids)
        item_count = rng.randint(1, 6)
        unit = rng.choice([19.99, 24.99, 29.99, 49.99, 79.98, 9.99])
        rows.append((f"ORD-2024-{i + 1:04d}", cid, rng.choice(ORDER_DATES),
                     ORDER_STATUSES[rng.randrange(len(ORDER_STATUSES))],
                     item_count, round(unit * item_count, 2), "USD"))
    return rows


def gen_transactions(n, customer_ids):
    rng = random.Random(303)
    rows = []
    for i in range(n):
        ts = (f"2024-01-{rng.randint(15, 24):02d} {rng.randint(8, 18):02d}:"
              f"{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}")
        merchant, category = rng.choice(MERCHANTS)
        qty = rng.randint(1, 3)
        line_total = round(rng.choice([10.0, 25.5, 49.99, 75.0, 199.99]), 2)
        rows.append((f"TXN{i + 1:03d}", ts, rng.choice(customer_ids),
                     rng.choice([1, 1, 1, 2]), merchant, category,
                     round(line_total * qty, 2), 1, rng.choice(SKUS), qty,
                     line_total, TXN_CHANNELS[rng.randrange(len(TXN_CHANNELS))]))
    return rows


def connect():
    host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
    return sql.connect(server_hostname=host,
                       http_path=os.environ["DATABRICKS_HTTP_PATH"],
                       access_token=os.environ["DATABRICKS_TOKEN"])


def _values(rows):
    out = []
    for r in rows:
        cells = []
        for v in r:
            if v is None:
                cells.append("null")
            elif isinstance(v, str):
                cells.append("'" + v.replace("'", "''") + "'")
            else:
                cells.append(str(v))
        out.append("(" + ", ".join(cells) + ")")
    return ",\n".join(out)


def load_table(cur, name, ddl_cols, rows):
    fq = f"{CATALOG}.{RAW_SCHEMA}.{name}"
    cur.execute(f"create or replace table {fq} ({ddl_cols})")
    if rows:
        cur.execute(f"insert into {fq} values\n{_values(rows)}")
    print(f"  loaded {len(rows):>4} rows -> {fq}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--customers", type=int, default=50)
    ap.add_argument("--orders", type=int, default=80)
    ap.add_argument("--transactions", type=int, default=40)
    args = ap.parse_args()

    customers = gen_customers(args.customers)
    ids = [1001 + i for i in range(args.customers)]
    orders = gen_orders(args.orders, ids)
    transactions = gen_transactions(args.transactions, ids)

    con = connect()
    cur = con.cursor()
    try:
        cur.execute(f"create catalog if not exists {CATALOG}")
        cur.execute(f"create schema if not exists {CATALOG}.{RAW_SCHEMA}")
        print(f"Loading Ab Initio raw extracts into {CATALOG}.{RAW_SCHEMA}")
        load_table(cur, "customers",
                   "customer_id bigint, first_name string, last_name string, "
                   "email string, street string, city string, state string, "
                   "zip string, status string", customers)
        load_table(cur, "orders",
                   "order_id string, customer_id bigint, order_date string, "
                   "order_status string, item_count int, amount decimal(12,2), "
                   "currency string", orders)
        load_table(cur, "transactions",
                   "txn_id string, txn_timestamp string, customer_id bigint, "
                   "txn_type int, merchant_name string, merchant_category string, "
                   "amount decimal(12,2), item_count int, sku string, quantity int, "
                   "line_total decimal(12,2), channel string", transactions)
        print("Done. These tables are the durable 'before' state for reconciliation.")
    finally:
        cur.close()
        con.close()


if __name__ == "__main__":
    main()
