"""Tests for the cohort → segment → legal-entity aggregation rollup."""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import Framework
from actuarial_model.core.aggregation import AggregationInput, calculate
from actuarial_model.models.results import ReserveResult, ResultMetadata

VAL_DATE = date(2025, 1, 1)


def _result(
    *,
    framework: Framework = Framework.BEL,
    legal_entity: str = "ENT-A",
    segment: str = "MYGA-RETAIL",
    cohort_id: str = "2024Q1",
    gross: float = 100.0,
    ceded: float = 40.0,
) -> ReserveResult:
    return ReserveResult(
        metadata=ResultMetadata(
            valuation_date=VAL_DATE,
            framework=framework,
            methodology_version="test",
            run_id="RUN-1",
            assumption_set_id="as-test",
        ),
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        gross_reserve=gross,
        ceded_reserve=ceded,
        net_reserve=gross - ceded,
        components={},
    )


def test_single_result_passes_through_at_every_grain():
    output = calculate(AggregationInput(seriatim_results=[_result()]))
    assert len(output.by_cohort) == 1
    assert len(output.by_segment) == 1
    assert len(output.by_legal_entity) == 1
    assert output.by_cohort[0].gross_reserve == 100.0
    assert output.by_legal_entity[0].segment == "ALL"
    assert output.by_legal_entity[0].cohort_id == "ALL"
    assert output.by_segment[0].cohort_id == "ALL"


def test_cohorts_sum_into_segment():
    results = [
        _result(cohort_id="2024Q1", gross=100.0, ceded=40.0),
        _result(cohort_id="2024Q2", gross=50.0, ceded=10.0),
    ]
    output = calculate(AggregationInput(seriatim_results=results))

    assert len(output.by_cohort) == 2
    assert len(output.by_segment) == 1
    segment = output.by_segment[0]
    assert segment.gross_reserve == pytest.approx(150.0)
    assert segment.ceded_reserve == pytest.approx(50.0)
    assert segment.net_reserve == pytest.approx(100.0)
    assert segment.components["source_result_count"] == 2


def test_segments_sum_into_legal_entity():
    results = [
        _result(segment="MYGA-RETAIL", gross=100.0),
        _result(segment="MYGA-INSTITUTIONAL", gross=70.0),
        _result(legal_entity="ENT-B", segment="MYGA-RETAIL", gross=5.0),
    ]
    output = calculate(AggregationInput(seriatim_results=results))

    assert len(output.by_segment) == 3
    by_entity = {r.legal_entity: r for r in output.by_legal_entity}
    assert by_entity["ENT-A"].gross_reserve == pytest.approx(170.0)
    assert by_entity["ENT-B"].gross_reserve == pytest.approx(5.0)


def test_frameworks_never_mix():
    """A BEL and a CARVM result for the same cohort stay separate rows."""
    results = [
        _result(framework=Framework.BEL, gross=100.0),
        _result(framework=Framework.STAT_CARVM, gross=120.0),
    ]
    output = calculate(AggregationInput(seriatim_results=results))

    assert len(output.by_cohort) == 2
    assert len(output.by_legal_entity) == 2
    frameworks = {r.metadata.framework for r in output.by_legal_entity}
    assert frameworks == {Framework.BEL, Framework.STAT_CARVM}
    by_framework = {r.metadata.framework: r for r in output.by_legal_entity}
    assert by_framework[Framework.BEL].gross_reserve == 100.0
    assert by_framework[Framework.STAT_CARVM].gross_reserve == 120.0


def test_aggregation_level_tagged_in_components():
    output = calculate(AggregationInput(seriatim_results=[_result()]))
    assert output.by_cohort[0].components["aggregation_level"] == "cohort"
    assert output.by_segment[0].components["aggregation_level"] == "segment"
    assert output.by_legal_entity[0].components["aggregation_level"] == "legal_entity"
