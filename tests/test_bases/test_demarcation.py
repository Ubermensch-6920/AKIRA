"""Pipeline-level tests: STAT / US GAAP / LDTI / EBS stay demarcated."""

import pytest

from actuarial_model.assumptions.enums import Basis, Framework
from actuarial_model.assumptions.lapse import LapseRateTable
from actuarial_model.pipeline import run_valuation
from tests.factories import VAL_DATE, assumption_set, flat_curve, policy

ALL_FRAMEWORKS = list(Framework)


def _run(aset=None, frameworks=ALL_FRAMEWORKS, **kwargs):
    return run_valuation(
        assumption_set=aset or assumption_set(),
        valuation_date=VAL_DATE,
        policies=kwargs.pop(
            "policies",
            [policy("A", surrender_charge_schedule_id="ATHENE_MYG_5"), policy("B", cohort_id="2025Q2")],
        ),
        curve_points=flat_curve(0.04),
        frameworks=frameworks,
        **kwargs,
    )


def _by_framework(output) -> dict[tuple[Framework, str], float]:
    return {
        (r.metadata.framework, r.components.get("component", "")): r.gross_reserve
        for r in output.reserve_results
    }


def test_every_basis_reports_its_own_frameworks():
    output = _run()
    assert set(output.bases) == set(Basis)
    for basis, result in output.bases.items():
        for measure in result.measures:
            assert measure.reserve_result.metadata.basis is basis
            assert measure.framework.basis is basis
        for capital in result.capital:
            assert capital.metadata.basis is basis
    assert [c.metadata.framework for c in output.bases[Basis.STAT].capital] == [Framework.NAIC_RBC]


def test_only_requested_bases_run():
    output = _run(frameworks=[Framework.BEL, Framework.EBS])
    assert set(output.bases) == {Basis.EBS}
    assert output.capital_results == []


def test_identical_blocks_share_one_projection():
    assert _run().projection_runs == 1


def test_each_basis_projects_on_its_own_assumption_block():
    base = _by_framework(_run())
    aset = assumption_set()
    aset.stat.vm22.lapse_config = LapseRateTable(table_id="stat-prudent", base_annual_rate=0.10)
    aset.stat.vm22.mortality.mortality_multiplier = 0.8
    output = _run(aset)
    loaded = _by_framework(output)

    assert output.projection_runs == 2  # STAT VM-22 block + the shared default block
    assert loaded[(Framework.STAT_VM22, "")] != pytest.approx(base[(Framework.STAT_VM22, "")])
    for key in [k for k in base if k[0] is not Framework.STAT_VM22]:
        assert loaded[key] == pytest.approx(base[key], rel=1e-12), key


def test_rbc_runs_off_stat_reserves_only():
    output = _run()
    rbc = output.bases[Basis.STAT].capital[0].components
    vm22 = next(r for r in output.reserve_results if r.metadata.framework is Framework.STAT_VM22)
    assert rbc["reserve_framework_used"] == "STAT_VM22"
    assert rbc["statutory_reserve_base"] == pytest.approx(vm22.net_reserve)


def test_aggregation_never_mixes_bases_or_frameworks():
    output = _run()
    primary = [m for m in output.measures if not m.supplementary]
    by_le = output.aggregation.by_legal_entity
    assert len(by_le) == len(primary)  # one legal entity → one row per primary measure
    assert {(r.metadata.basis, r.metadata.framework) for r in by_le} == {
        (m.reserve_result.metadata.basis, m.framework) for m in primary
    }
    for row in by_le:
        source = next(m for m in primary if m.framework is row.metadata.framework)
        assert row.gross_reserve == pytest.approx(source.reserve_result.gross_reserve, rel=1e-12)


def test_cohort_grain_splits_by_policy_labels():
    cohorts = [r for r in _run().aggregation.by_cohort if r.metadata.framework is Framework.BEL]
    assert sorted(r.cohort_id for r in cohorts) == ["2025Q1", "2025Q2"]
    assert all(r.components["source_policy_count"] == 1 for r in cohorts)


def test_supplementary_results_stay_out_of_aggregation():
    output = _run()
    components = {r.components.get("component") for r in output.aggregation.by_legal_entity}
    assert "DAC" not in components and "RISK_MARGIN" not in components
    assert {"DAC", "RISK_MARGIN"} <= {r.components.get("component") for r in output.reserve_results}


def test_policy_results_are_tagged_by_basis():
    frame = _run().policy_results()
    assert set(frame["basis"].unique()) == {b.value for b in Basis}
    assert frame.filter(frame["framework"] == "LDTI")["component"].unique().sort().to_list() == [
        "DAC",
        "LFPB",
    ]


def test_reinsurance_flows_to_every_basis(sample_treaty):
    output = _run(
        policies=[policy("A", reinsurance_treaty_id=sample_treaty.treaty_id)],
        treaties=[sample_treaty],
    )
    for r in output.reserve_results:
        if r.metadata.framework in (Framework.BEL, Framework.LDTI) and r.components.get("component") != "DAC":
            assert r.ceded_reserve == pytest.approx(0.5 * r.gross_reserve, rel=1e-12)
