#!/usr/bin/env python3
"""
reconcile.py — source -> target reconciliation report for the Ab Initio ->
Databricks migration.

Why this exists
---------------
The point of the migration is not just to produce *some* output on Databricks —
it is to produce output we can *trust* matches what the legacy Ab Initio graphs
would have produced. Because there is no live Co>Operating System runtime here,
"trust" is established with deterministic reconciliation controls (row counts,
control totals, domain coverage) between the raw source and the converted marts.

dbt schema/singular tests already gate these invariants on every build (see
dbt_project/tests/reconcile_*.sql). This script is the human-facing companion:
it runs the same family of controls and prints a single reconciliation report you
can show live and attach to a PR. It exits non-zero if any control fails, so it
also works as a CI / pre-merge gate.

This is the harness *framework* with the order-domain controls. When a new graph
is converted, its conversion adds the matching controls here (e.g. the
transactions channel-default parity) — see
.workshop/playbooks/abinitio-to-databricks-conversion.devin.md and
.agents/skills/abinitio-to-databricks-conversion/SKILL.md.

Usage
-----
    python verify/reconcile.py --namespace dev
    python verify/reconcile.py --namespace run1 --catalog retail_analytics
    python verify/reconcile.py --namespace dev --report reconciliation_report.md

Credentials are read from the environment (same vars dbt uses):
    DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field

from databricks import sql


@dataclass
class CheckResult:
    name: str
    status: str  # PASS | FAIL | SKIP
    detail: str = ""
    metrics: dict = field(default_factory=dict)


class Reconciler:
    def __init__(self, catalog: str, namespace: str):
        host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
        self.con = sql.connect(
            server_hostname=host,
            http_path=os.environ["DATABRICKS_HTTP_PATH"],
            access_token=os.environ["DATABRICKS_TOKEN"],
        )
        self.catalog = catalog
        self.ns = namespace
        self.raw = f"{catalog}.raw"
        self.staging = f"{catalog}.{namespace}_staging"
        self.intermediate = f"{catalog}.{namespace}_intermediate"
        self.marts = f"{catalog}.{namespace}_marts"
        self.curated = f"{catalog}.{namespace}_curated"
        self.results: list[CheckResult] = []

    def _scalar(self, query: str):
        cur = self.con.cursor()
        try:
            cur.execute(query)
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            cur.close()

    def _table_exists(self, fqtn: str) -> bool:
        cur = self.con.cursor()
        try:
            cur.execute(f"show tables in {fqtn.rsplit('.', 1)[0]}")
            target = fqtn.rsplit(".", 1)[1]
            return any(r[1] == target for r in cur.fetchall())
        except Exception:
            return False
        finally:
            cur.close()

    # ------------------------------------------------------------------ checks
    def check_customers_completeness(self):
        """Staging customers must equal the source customer population (no loss)."""
        expected = self._scalar(f"select count(*) from {self.raw}.customers")
        actual = self._scalar(f"select count(*) from {self.staging}.stg_customers")
        ok = expected == actual
        self.results.append(CheckResult(
            "customers_completeness", "PASS" if ok else "FAIL",
            f"raw customers = {expected}, staging customers = {actual}",
            {"expected": expected, "actual": actual},
        ))

    def check_orders_completeness(self):
        """Staging orders must equal the source order population (no loss/fan-out)."""
        expected = self._scalar(f"select count(*) from {self.raw}.orders")
        actual = self._scalar(f"select count(*) from {self.staging}.stg_orders")
        ok = expected == actual
        self.results.append(CheckResult(
            "orders_completeness", "PASS" if ok else "FAIL",
            f"raw orders = {expected}, staging orders = {actual}",
            {"expected": expected, "actual": actual},
        ))

    def check_orders_control_total(self):
        """Total order amount in the daily mart must tie out to the raw extract."""
        src = self._scalar(f"select sum(cast(amount as decimal(12,2))) from {self.raw}.orders")
        mart = self._scalar(f"select sum(total_amount) from {self.marts}.mart_daily_orders")
        ok = src == mart
        self.results.append(CheckResult(
            "orders_control_total", "PASS" if ok else "FAIL",
            f"raw SUM(amount) = {src}, mart SUM(total_amount) = {mart}",
            {"expected": str(src), "actual": str(mart)},
        ))

    def check_transactions_completeness(self):
        """Live-converted control: curated transactions must equal the source
        transaction population (no silent row loss, no fan-out from the DML
        line_items array). SKIPs until the transactions pipeline is converted."""
        if not self._table_exists(f"{self.curated}.curated_transactions"):
            self.results.append(CheckResult(
                "transactions_completeness", "SKIP",
                "curated_transactions not produced yet (live conversion target)"))
            return
        expected = self._scalar(f"select count(*) from {self.raw}.transactions")
        actual = self._scalar(
            f"select count(*) from {self.curated}.curated_transactions")
        ok = expected == actual
        self.results.append(CheckResult(
            "transactions_completeness", "PASS" if ok else "FAIL",
            f"raw transactions = {expected}, curated transactions = {actual}",
            {"expected": expected, "actual": actual},
        ))

    def check_transactions_control_total(self):
        """Live-converted control: total transaction amount in the curated table
        must tie out to the raw extract, to the cent. SKIPs until the
        transactions pipeline is converted."""
        if not self._table_exists(f"{self.curated}.curated_transactions"):
            self.results.append(CheckResult(
                "transactions_control_total", "SKIP",
                "curated_transactions not produced yet (live conversion target)"))
            return
        src = self._scalar(
            f"select sum(cast(amount as decimal(12,2))) from {self.raw}.transactions")
        curated = self._scalar(
            f"select sum(amount) from {self.curated}.curated_transactions")
        ok = src == curated
        self.results.append(CheckResult(
            "transactions_control_total", "PASS" if ok else "FAIL",
            f"raw SUM(amount) = {src}, curated SUM(amount) = {curated}",
            {"expected": str(src), "actual": str(curated)},
        ))

    def check_transactions_channel_parity(self):
        """Live-converted control: the curated transactions table must apply the
        DML default channel = null("UNKNOWN") — a blank source channel becomes the
        literal 'UNKNOWN', never NULL. SKIPs until the transactions pipeline is
        converted (see the playbook's worked example)."""
        if not self._table_exists(f"{self.curated}.curated_transactions"):
            self.results.append(CheckResult(
                "transactions_channel_parity", "SKIP",
                "curated_transactions not produced yet (live conversion target)"))
            return
        nulls = self._scalar(
            f"select count(*) from {self.curated}.curated_transactions "
            f"where channel is null or trim(channel) = ''"
        )
        ok = nulls == 0
        self.results.append(CheckResult(
            "transactions_channel_parity", "PASS" if ok else "FAIL",
            f"{nulls} transaction(s) with NULL/blank channel "
            f"(expected the DML default 'UNKNOWN')",
            {"null_channels": nulls},
        ))

    # ------------------------------------------------------------------- driver
    def run(self) -> bool:
        self.check_customers_completeness()
        self.check_orders_completeness()
        self.check_orders_control_total()
        self.check_transactions_completeness()
        self.check_transactions_control_total()
        self.check_transactions_channel_parity()
        self.con.close()
        return all(r.status != "FAIL" for r in self.results)

    def render(self) -> str:
        icon = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}
        lines = [
            f"# Reconciliation Report — {self.catalog} / namespace `{self.ns}`",
            "",
            "Source -> target controls proving the converted marts match the legacy",
            "Ab Initio extract's intent. FAIL blocks the migration; SKIP means a",
            "prerequisite (e.g. the live-converted transactions pipeline) has not",
            "been produced yet.",
            "",
            "| Control | Result | Detail |",
            "|---|---|---|",
        ]
        for r in self.results:
            lines.append(f"| `{r.name}` | {icon[r.status]} | {r.detail} |")
        n_fail = sum(1 for r in self.results if r.status == "FAIL")
        n_skip = sum(1 for r in self.results if r.status == "SKIP")
        n_pass = sum(1 for r in self.results if r.status == "PASS")
        lines += ["", f"**{n_pass} passed, {n_fail} failed, {n_skip} skipped.**", ""]
        return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--namespace", "-n", default="dev")
    ap.add_argument("--catalog", default="retail_analytics")
    ap.add_argument("--report", help="optional path to write the markdown report")
    args = ap.parse_args()

    rec = Reconciler(args.catalog, args.namespace)
    ok = rec.run()
    report = rec.render()
    print(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"(report written to {args.report})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
