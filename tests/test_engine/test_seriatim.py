"""Tests for the seriatim dispatcher."""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import ProductType
from actuarial_model.assumptions.sets import ProjectionBasisConfig
from actuarial_model.engine import seriatim
from actuarial_model.engine.projections import fia, spia, ulsg, va
from actuarial_model.models.policy import FiaPolicyState
from tests.factories import VAL_DATE, assumption_set, policy


def test_routes_myga_policies():
    projection = seriatim.project([policy("A"), policy("B")], ProjectionBasisConfig(), VAL_DATE)
    assert projection.policy_ids == ["A", "B"]


def test_unsupported_product_raises():
    fia_policy = FiaPolicyState(
        policy_id="F1",
        issue_date=VAL_DATE,
        issue_age=60,
        sex="M",
        issue_state="NY",
        legal_entity="E",
        segment="S",
        cohort_id="C",
        valuation_date=VAL_DATE,
    )
    assert fia_policy.product_type is ProductType.FIA
    with pytest.raises(NotImplementedError, match="FIA"):
        seriatim.project([policy(), fia_policy], ProjectionBasisConfig(), VAL_DATE)


def test_empty_policy_list():
    assert seriatim.project([], ProjectionBasisConfig(), date(2025, 6, 30)).is_empty


@pytest.mark.parametrize(
    "module, input_cls",
    [(fia, fia.FiaProjectionInput), (spia, spia.SpiaProjectionInput),
     (va, va.VaProjectionInput), (ulsg, ulsg.UlsgProjectionInput)],
)
def test_phase2_3_projection_stubs(module, input_cls):
    with pytest.raises(NotImplementedError):
        module.calculate(input_cls(assumption_set=assumption_set(), policies=[]))
