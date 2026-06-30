#!/usr/bin/env python3
"""
teardown.py — drop a namespace's output schemas for the Ab Initio -> Databricks
migration. The durable raw source (retail_analytics.raw) is never touched.

Usage:
    python seed/teardown.py --namespace dev
    python seed/teardown.py --namespace dev --catalog retail_analytics

Auth (env vars): DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN
"""
from __future__ import annotations

import argparse
import os

from databricks import sql

LAYERS = ["staging", "intermediate", "marts", "curated", "seeds"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--namespace", "-n", required=True)
    ap.add_argument("--catalog", default="retail_analytics")
    args = ap.parse_args()

    host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
    con = sql.connect(server_hostname=host,
                      http_path=os.environ["DATABRICKS_HTTP_PATH"],
                      access_token=os.environ["DATABRICKS_TOKEN"])
    cur = con.cursor()
    try:
        for layer in LAYERS:
            schema = f"{args.catalog}.{args.namespace}_{layer}"
            cur.execute(f"drop schema if exists {schema} cascade")
            print(f"dropped {schema}")
    finally:
        cur.close()
        con.close()
    print(f"namespace '{args.namespace}' torn down (raw untouched)")


if __name__ == "__main__":
    main()
