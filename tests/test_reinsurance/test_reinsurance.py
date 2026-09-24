"""Tests for quota share and treaty application on projection frames."""

import numpy as np
import pytest

from actuarial_model.assumptions.enums import ReinsuranceTreatyType
from actuarial_model.assumptions.sets import ProjectionBasisConfig
from actuarial_model.engine.projection import CASH_FLOW_COLUMNS, Projection
from actuarial_model.engine.projections import myga
from actuarial_model.models.reinsurance import ReinsuranceTreaty
from actuarial_model.reinsurance import (
    application,
    coinsurance,
    excess_of_loss,
    funds_withheld,
    modco,
    quota_share,
    risk_transfer,
    yrt,
)
from tests.factories import VAL_DATE, assumption_set, policy


@pytest.fixture
def gross() -> Projection:
    return myga.project(
        [policy("RE", reinsurance_treaty_id="TRT-0001"), policy("RET", account_value=50_000.0)],
        ProjectionBasisConfig(),
        VAL_DATE,
    )


def _rows(projection: Projection) -> dict[str, dict]:
    return {r["policy_id"]: r for r in projection.frame.to_dicts()}


def test_fifty_percent_split_and_conservation(gross, sample_treaty: ReinsuranceTreaty):
    split = application.apply(gross, [sample_treaty])
    g, c, n = _rows(gross), _rows(split.ceded), _rows(split.net)
    assert set(c) == {"RE"}  # only reinsured policies are ceded
    assert set(n) == {"RE", "RET"}
    for column in CASH_FLOW_COLUMNS:
        np.testing.assert_allclose(c["RE"][column], 0.5 * np.array(g["RE"][column]))
        np.testing.assert_allclose(
            np.array(c["RE"][column]) + np.array(n["RE"][column]), g["RE"][column]
        )
        np.testing.assert_allclose(n["RET"][column], g["RET"][column])  # retained at gross


def test_lives_in_force_not_ceded(gross, sample_treaty: ReinsuranceTreaty):
    split = application.apply(gross, [sample_treaty])
    assert _rows(split.ceded)["RE"]["lives_in_force"] == _rows(gross)["RE"]["lives_in_force"]
    assert _rows(split.net)["RE"]["lives_in_force"] == _rows(gross)["RE"]["lives_in_force"]


def test_explicit_pairing_overrides_frame(gross, sample_treaty: ReinsuranceTreaty):
    split = application.apply(gross, [sample_treaty], {"RET": "TRT-0001", "RE": None})
    assert split.ceded.policy_ids == ["RET"]


def test_no_pairing_means_all_retained(sample_treaty: ReinsuranceTreaty):
    external = Projection.from_cash_flows(VAL_DATE, {"X": {"death_benefits": [1.0, 2.0]}})
    split = application.apply(external, [sample_treaty])
    assert split.ceded.is_empty
    assert split.net.frame["death_benefits"].to_list() == [[1.0, 2.0]]


def test_unknown_treaty_id_raises(gross):
    with pytest.raises(ValueError, match="TRT-0001"):
        application.apply(gross, [])


def test_phase2_treaty_type_raises(gross, sample_treaty: ReinsuranceTreaty):
    coins = sample_treaty.model_copy(update={"treaty_type": ReinsuranceTreatyType.COINSURANCE})
    with pytest.raises(NotImplementedError, match="COINSURANCE"):
        application.apply(gross, [coins])


def test_quota_share_validation(sample_treaty: ReinsuranceTreaty):
    assert quota_share.validate_treaty(sample_treaty) == 0.5
    with pytest.raises(ValueError, match="quota_share_pct"):
        quota_share.validate_treaty(sample_treaty.model_copy(update={"quota_share_pct": None}))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        quota_share.validate_treaty(sample_treaty.model_copy(update={"quota_share_pct": 1.5}))
    with pytest.raises(ValueError, match="QUOTA_SHARE"):
        quota_share.validate_treaty(
            sample_treaty.model_copy(update={"treaty_type": ReinsuranceTreatyType.YRT})
        )


@pytest.mark.parametrize(
    "module, input_cls",
    [
        (coinsurance, coinsurance.CoinsuranceInput),
        (modco, modco.ModcoInput),
        (funds_withheld, funds_withheld.FundsWithheldInput),
        (yrt, yrt.YrtInput),
        (excess_of_loss, excess_of_loss.ExcessOfLossInput),
    ],
)
def test_phase2_treaty_stubs(module, input_cls, sample_treaty: ReinsuranceTreaty):
    with pytest.raises(NotImplementedError):
        module.calculate(input_cls(treaty=sample_treaty))


def test_risk_transfer_stub(sample_treaty: ReinsuranceTreaty):
    with pytest.raises(NotImplementedError):
        risk_transfer.calculate(
            risk_transfer.RiskTransferInput(assumption_set=assumption_set(), treaty=sample_treaty)
        )
