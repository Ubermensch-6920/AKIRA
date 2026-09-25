"""
The projection carrier passed from the engine to every basis.

A :class:`Projection` is a polars frame with one row per policy: label
columns plus one ``list[f64]`` column per cash-flow line, each list holding
one element per period of the shared :class:`ProjectionGrid`. This replaces
the per-period Pydantic records of the pre-gaspatchio engine — reinsurance
splits and every basis's present values are whole-column list arithmetic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import polars as pl

from .grid import ProjectionGrid

LABEL_COLUMNS = ("policy_id", "legal_entity", "segment", "cohort_id")

# Monetary cash-flow lines (each a list over the grid).
CASH_FLOW_COLUMNS = (
    "account_value_bop",
    "interest_credited",
    "partial_withdrawals",
    "surrender_charge",
    "mva_adjustment",
    "surrender_benefits",
    "death_benefits",
    "maturity_benefits",
    "account_value_eop",
)
# Policy counts — carried, never split by reinsurance.
COUNT_COLUMNS = ("lives_in_force",)
# Liability outflows paid at period end: what every basis discounts.
OUTFLOW_COLUMNS = (
    "death_benefits",
    "surrender_benefits",
    "partial_withdrawals",
    "maturity_benefits",
)


def list_sum(columns: Sequence[str]) -> pl.Expr:
    """Element-wise sum of list columns."""
    expr = pl.col(columns[0])
    for name in columns[1:]:
        expr = expr + pl.col(name)
    return expr


@dataclass(frozen=True)
class Projection:
    """Per-policy projected cash flows on a shared monthly grid."""

    grid: ProjectionGrid
    frame: pl.DataFrame
    methodology_version: str = ""

    @property
    def valuation_date(self) -> date:
        return self.grid.valuation_date

    @property
    def policy_ids(self) -> list[str]:
        return self.frame["policy_id"].to_list()

    @property
    def is_empty(self) -> bool:
        return self.frame.height == 0

    def labels(self) -> pl.DataFrame:
        """The label columns — the grain every basis reports at."""
        return self.frame.select(LABEL_COLUMNS)

    def with_frame(self, frame: pl.DataFrame) -> Projection:
        return Projection(grid=self.grid, frame=frame, methodology_version=self.methodology_version)

    def total(self, column: str) -> list[float]:
        """Portfolio total of one cash-flow line, per period."""
        if self.is_empty:
            return [0.0] * self.grid.n_periods
        stacked = self.frame.select(pl.col(column).list.to_array(self.grid.n_periods)).to_series()
        return stacked.to_numpy().sum(axis=0).tolist()

    @classmethod
    def empty(cls, grid: ProjectionGrid, methodology_version: str = "") -> Projection:
        schema: dict[str, pl.DataType] = {name: pl.String() for name in LABEL_COLUMNS}
        schema.update({name: pl.List(pl.Float64()) for name in CASH_FLOW_COLUMNS + COUNT_COLUMNS})
        return cls(grid=grid, frame=pl.DataFrame(schema=schema), methodology_version=methodology_version)

    @classmethod
    def from_cash_flows(
        cls,
        valuation_date: date,
        cash_flows: Mapping[str, Mapping[str, Sequence[float]]],
        *,
        labels: Mapping[str, Mapping[str, str]] | None = None,
        methodology_version: str = "external",
    ) -> Projection:
        """Build a projection from explicit per-policy cash-flow vectors.

        For externally produced cash flows and hand-calculated tests.
        ``cash_flows[policy_id][column]`` is the per-period vector; every
        vector must have the same length (the grid length) and any column
        omitted is zero.
        """
        lengths = {len(v) for cfs in cash_flows.values() for v in cfs.values()}
        if len(lengths) > 1:
            raise ValueError(f"Cash-flow vectors must share one length; got {sorted(lengths)}.")
        if not cash_flows or not lengths:
            raise ValueError("from_cash_flows needs at least one non-empty cash-flow vector.")
        n_periods = lengths.pop()
        grid = ProjectionGrid(valuation_date=valuation_date, n_periods=n_periods)

        rows: dict[str, list] = {name: [] for name in LABEL_COLUMNS + CASH_FLOW_COLUMNS + COUNT_COLUMNS}
        for policy_id, cfs in cash_flows.items():
            unknown = set(cfs) - set(CASH_FLOW_COLUMNS + COUNT_COLUMNS)
            if unknown:
                raise ValueError(f"Unknown cash-flow columns for {policy_id}: {sorted(unknown)}")
            policy_labels = (labels or {}).get(policy_id, {})
            rows["policy_id"].append(policy_id)
            for name in LABEL_COLUMNS[1:]:
                rows[name].append(policy_labels.get(name, "ALL"))
            for name in CASH_FLOW_COLUMNS + COUNT_COLUMNS:
                rows[name].append([float(x) for x in cfs.get(name, [0.0] * n_periods)])
        schema: dict[str, pl.DataType] = {name: pl.String() for name in LABEL_COLUMNS}
        schema.update({name: pl.List(pl.Float64()) for name in CASH_FLOW_COLUMNS + COUNT_COLUMNS})
        return cls(
            grid=grid,
            frame=pl.DataFrame(rows, schema=schema),
            methodology_version=methodology_version,
        )
