"""Smoke tests: reinsurance modules raise NotImplementedError in Phase 1."""

import pytest

from actuarial_model.assumptions.sets import AssumptionSet
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


def test_application_stub(
    sample_assumption_set: AssumptionSet, sample_treaty: ReinsuranceTreaty
) -> None:
    with pytest.raises(NotImplementedError):
        application.calculate(
            application.ReinsuranceApplicationInput(
                assumption_set=sample_assumption_set,
                treaties=[sample_treaty],
            )
        )


@pytest.mark.parametrize(
    "module, input_cls",
    [
        (quota_share, quota_share.QuotaShareInput),
        (coinsurance, coinsurance.CoinsuranceInput),
        (modco, modco.ModcoInput),
        (funds_withheld, funds_withheld.FundsWithheldInput),
        (yrt, yrt.YrtInput),
        (excess_of_loss, excess_of_loss.ExcessOfLossInput),
    ],
)
def test_treaty_stubs(module, input_cls, sample_treaty: ReinsuranceTreaty) -> None:
    with pytest.raises(NotImplementedError):
        module.calculate(input_cls(treaty=sample_treaty))


def test_risk_transfer_stub(
    sample_assumption_set: AssumptionSet, sample_treaty: ReinsuranceTreaty
) -> None:
    with pytest.raises(NotImplementedError):
        risk_transfer.calculate(
            risk_transfer.RiskTransferInput(
                assumption_set=sample_assumption_set,
                treaty=sample_treaty,
            )
        )
