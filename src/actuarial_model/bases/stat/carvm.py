"""
STAT — Pre-VM-22 CARVM reserve (gaspatchio).

Commissioner's Annuity Reserve Valuation Method per the configured
Actuarial Guideline (AG33 / AG35), on the ``stat.carvm`` assumption block.

Method (Phase 1):
  CARVM reserve = greatest present value of future *guaranteed* benefits.
  For a MYGA the candidate benefit at each future month m is the cash
  surrender value — guaranteed AV accumulated at ``guaranteed_rate`` less the
  surrender charge for that policy year — and, at the end of the guarantee
  period, the full account value (no charge). Each candidate is discounted
  at the statutory valuation rate; the reserve is the maximum. Evaluating
  m = 0 makes the current CSV a natural floor.

  Unlike every best-estimate basis, no lapse or mortality assumption enters:
  CARVM assumes the policyholder elects the benefit pattern most costly to
  the insurer. The candidate stream is a gaspatchio frame (one row per
  policy, one element per month to maturity) and the reserve is its
  row-wise ``max``.

Phase 1 simplifications (documented for review):
  - Elective benefits only (CSV / maturity). AG33 integrated streams with
    mortality-weighted death benefits are not yet overlaid; for ROAV death
    benefits this understates the reserve only marginally.
  - Free-partial-withdrawal corridors are not exercised as elective options.
  - No CFT (Reg 126) scenario overlay yet — single deterministic path.
  - Ceded reserve stays 0 — statutory reinsurance credit (authorization /
    collateral rules) is not yet applied.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl
from gaspatchio import ActuarialFrame, when

from ...assumptions.enums import Framework
from ...assumptions.sets import StatCarvmConfig
from ...assumptions.withdrawal import SurrenderChargeRepository
from ...engine.grid import grid_vector
from ...engine.model_points import myga_model_points
from ...engine.projection import LABEL_COLUMNS
from ...engine.tables import surrender_charge_table
from ...models.policy import MygaPolicyState
from ..common import DETAIL_COLUMNS, MeasureResult, RunStamp, reserve_result

METHODOLOGY_VERSION = "stat_carvm_v1.0.0"

_SURRENDER_REPO = SurrenderChargeRepository.with_athene_schedules()


def build_frame(
    model_points: pl.DataFrame,
    valuation_interest_rate: float,
    surrender_repository: SurrenderChargeRepository = _SURRENDER_REPO,
) -> ActuarialFrame:
    """Greatest-PV-of-guaranteed-benefits model over months 0..max maturity."""
    horizon = max(int(model_points["months_to_maturity"].max() or 0), 0)  # type: ignore[arg-type]
    af = ActuarialFrame(model_points)
    af.m = grid_vector(list(range(horizon + 1)), pl.Int64())
    af.policy_year = (af.duration_months_at_valuation + af.m) // 12 + 1
    af.surrender_charge_rate = surrender_charge_table(surrender_repository).lookup(
        surrender_charge_schedule_id=af.surrender_charge_schedule_id,
        policy_year=af.policy_year,
    )
    af.guaranteed_av = af.account_value * (1.0 + af.guaranteed_rate) ** (af.m / 12.0)
    # Full AV at maturity; CSV before it; nothing after it.
    af.benefit = (
        when(af.m == af.months_to_maturity)
        .then(af.guaranteed_av)
        .otherwise(
            when(af.m < af.months_to_maturity)
            .then(af.guaranteed_av * (1.0 - af.surrender_charge_rate))
            .otherwise(0.0)
        )
    )
    af.discount = (1.0 + valuation_interest_rate) ** (-af.m / 12.0)
    af.pv_benefit = af.benefit * af.discount
    af.csv_at_valuation = af.account_value * (1.0 - af.surrender_charge_rate.list.first())
    # A matured / maturing policy reserves its full account value.
    af.reserve = (
        when(af.months_to_maturity <= 0)
        .then(af.account_value)
        .otherwise(af.pv_benefit.list.max())
    )
    af.greatest_pv_month = (
        when(af.months_to_maturity <= 0).then(0).otherwise(af.pv_benefit.list.arg_max())
    )
    return af


def calculate(
    policies: Sequence[MygaPolicyState],
    config: StatCarvmConfig,
    stamp: RunStamp,
) -> MeasureResult:
    """CARVM reserve per policy and in total (no projection needed)."""
    i_val = config.valuation_interest_rate
    if policies:
        frame = (
            build_frame(myga_model_points(policies, stamp.valuation_date), i_val)
            .collect()
            .with_columns(
                pl.when(pl.col("months_to_maturity") <= 0)
                .then(pl.col("account_value"))
                .otherwise(pl.col("csv_at_valuation"))
                .alias("csv_at_valuation"),
                pl.col("months_to_maturity").clip(lower_bound=0),
            )
        )
    else:
        frame = pl.DataFrame(
            schema={
                **{name: pl.String() for name in LABEL_COLUMNS},
                "reserve": pl.Float64(),
                "csv_at_valuation": pl.Float64(),
                "greatest_pv_month": pl.Int64(),
                "months_to_maturity": pl.Int64(),
            }
        )

    detail = frame.select(
        *LABEL_COLUMNS,
        pl.col("reserve").alias("gross"),
        pl.lit(0.0).alias("ceded"),
        pl.col("reserve").alias("net"),
    ).select(DETAIL_COLUMNS)
    per_policy = frame.select(
        "policy_id", "reserve", "csv_at_valuation", "greatest_pv_month", "months_to_maturity"
    )
    result = reserve_result(
        stamp,
        Framework.STAT_CARVM,
        METHODOLOGY_VERSION,
        detail,
        {
            "carvm_basis": config.carvm_basis.value,
            "valuation_interest_rate": i_val,
        },
    )
    return MeasureResult(
        reserve_result=result, policy_detail=detail, extras={"policy_audit": per_policy}
    )
