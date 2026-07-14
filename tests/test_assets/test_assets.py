"""Tests for the asset ledger and framework valuation views."""

import pytest

from actuarial_model.assets.ledger import AssetLedgerInput, load_assets
from actuarial_model.assets.ledger import calculate as run_ledger
from actuarial_model.assets.valuation import (
    AssetValuationInput,
)
from actuarial_model.assets.valuation import (
    calculate as run_valuation,
)
from actuarial_model.assumptions.enums import Framework
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.models.asset import AssetRecord


# ── Ledger ────────────────────────────────────────────────────────────────
def test_ledger_roundtrip(tmp_path, sample_asset: AssetRecord):
    db = str(tmp_path / "ledger.duckdb")
    output = run_ledger(AssetLedgerInput(assets=[sample_asset], db_path=db))
    assert output.asset_ids == [sample_asset.asset_id]

    loaded = load_assets(db)
    assert loaded == [sample_asset]


def test_ledger_upsert_replaces(tmp_path, sample_asset: AssetRecord):
    db = str(tmp_path / "ledger.duckdb")
    run_ledger(AssetLedgerInput(assets=[sample_asset], db_path=db))

    updated = sample_asset.model_copy(update={"book_value": 123_456.0})
    run_ledger(AssetLedgerInput(assets=[updated], db_path=db))

    loaded = load_assets(db)
    assert len(loaded) == 1
    assert loaded[0].book_value == 123_456.0


def test_ledger_empty_db_reads_empty(tmp_path):
    assert load_assets(str(tmp_path / "fresh.duckdb")) == []


def test_ledger_rejects_bad_table_name(tmp_path, sample_asset: AssetRecord):
    with pytest.raises(ValueError, match="identifier"):
        run_ledger(
            AssetLedgerInput(
                assets=[sample_asset],
                db_path=str(tmp_path / "x.duckdb"),
                table_name="ledger; DROP TABLE runs",
            )
        )


# ── Valuation views ───────────────────────────────────────────────────────
def _value(
    assumption_set: AssumptionSet, framework: Framework, asset: AssetRecord
) -> float:
    output = run_valuation(
        AssetValuationInput(
            assumption_set=assumption_set, framework=framework, assets=[asset]
        )
    )
    return output.carrying_values[asset.asset_id]


def test_stat_uses_book_value(
    sample_assumption_set: AssumptionSet, sample_asset: AssetRecord
):
    for framework in (Framework.STAT_CARVM, Framework.STAT_VM22, Framework.NAIC_RBC):
        assert _value(sample_assumption_set, framework, sample_asset) == 998_000.0


def test_stat_non_admitted_carries_zero(
    sample_assumption_set: AssumptionSet, sample_asset: AssetRecord
):
    non_admitted = sample_asset.model_copy(update={"admitted_flag": False})
    assert _value(sample_assumption_set, Framework.STAT_CARVM, non_admitted) == 0.0


def test_ldti_htm_uses_amortized_cost(
    sample_assumption_set: AssumptionSet, sample_asset: AssetRecord
):
    htm = sample_asset.model_copy(update={"gaap_classification": "HTM"})
    assert _value(sample_assumption_set, Framework.LDTI, htm) == 998_500.0
    # AFS falls back to market value.
    assert _value(sample_assumption_set, Framework.LDTI, sample_asset) == 1_010_000.0


def test_fair_value_frameworks_use_market(
    sample_assumption_set: AssumptionSet, sample_asset: AssetRecord
):
    assert _value(sample_assumption_set, Framework.FAS157, sample_asset) == 1_010_000.0
    assert _value(sample_assumption_set, Framework.BEL, sample_asset) == 1_010_000.0


def test_ebs_uses_post_haircut_value(
    sample_assumption_set: AssumptionSet, sample_asset: AssetRecord
):
    assert _value(sample_assumption_set, Framework.EBS, sample_asset) == 1_005_000.0
    no_ebs_value = sample_asset.model_copy(update={"market_value_ebs": None})
    assert _value(sample_assumption_set, Framework.EBS, no_ebs_value) == 1_010_000.0


def test_total_carrying_value(
    sample_assumption_set: AssumptionSet, sample_asset: AssetRecord
):
    second = sample_asset.model_copy(
        update={"asset_id": "AST-0002", "market_value": 500_000.0}
    )
    output = run_valuation(
        AssetValuationInput(
            assumption_set=sample_assumption_set,
            framework=Framework.FAS157,
            assets=[sample_asset, second],
        )
    )
    assert output.total_carrying_value == pytest.approx(1_510_000.0)
    assert output.valued_assets == [sample_asset, second]
