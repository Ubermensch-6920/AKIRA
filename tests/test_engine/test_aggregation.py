"""Tests for per-policy aggregation."""

import polars as pl
import pytest

from actuarial_model.assumptions.enums import Framework
from actuarial_model.bases.common import MeasureResult, reserve_result
from actuarial_model.engine import aggregation
from tests.factories import stamp


def _measure(framework: Framework, rows: list[tuple[str, str, str, str, float]], supplementary=False):
    detail = pl.DataFrame(
        rows, schema=["policy_id", "legal_entity", "segment", "cohort_id", "gross"], orient="row"
    ).with_columns(pl.lit(0.0).alias("ceded"), pl.col("gross").alias("net"))
    return MeasureResult(
        reserve_result=reserve_result(stamp(), framework, "test", detail, {}),
        policy_detail=detail,
        supplementary=supplementary,
    )


def test_grains_sum_policies():
    m = _measure(
        Framework.BEL,
        [("1", "E1", "S1", "C1", 10.0), ("2", "E1", "S1", "C2", 20.0), ("3", "E1", "S2", "C1", 5.0),
         ("4", "E2", "S1", "C1", 1.0)],
    )
    out = aggregation.calculate([m])
    assert len(out.by_cohort) == 4
    seg = {(r.legal_entity, r.segment): r.gross_reserve for r in out.by_segment}
    assert seg == {("E1", "S1"): 30.0, ("E1", "S2"): 5.0, ("E2", "S1"): 1.0}
    le = {r.legal_entity: r for r in out.by_legal_entity}
    assert le["E1"].gross_reserve == pytest.approx(35.0)
    assert le["E1"].segment == "ALL" and le["E1"].cohort_id == "ALL"
    assert le["E1"].components == {"aggregation_level": "legal_entity", "source_policy_count": 3}


def test_frameworks_never_mix():
    out = aggregation.calculate(
        [_measure(Framework.BEL, [("1", "E", "S", "C", 1.0)]),
         _measure(Framework.STAT_CARVM, [("1", "E", "S", "C", 2.0)])]
    )
    assert sorted(r.gross_reserve for r in out.by_legal_entity) == [1.0, 2.0]


def test_supplementary_excluded_and_empty_run():
    out = aggregation.calculate([_measure(Framework.LDTI, [("1", "E", "S", "C", 9.0)], True)])
    assert out.by_cohort == out.by_segment == out.by_legal_entity == []
    assert aggregation.calculate([]).by_legal_entity == []
