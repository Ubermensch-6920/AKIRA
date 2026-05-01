"""Smoke tests: Pydantic models instantiate and serialize cleanly."""

from actuarial_model.assumptions.enums import ProductType
from actuarial_model.models.asset import AssetRecord
from actuarial_model.models.policy import MygaPolicyState
from actuarial_model.models.reinsurance import ReinsuranceTreaty


def test_assumption_set_instantiates(sample_assumption_set) -> None:
    assert sample_assumption_set.assumption_set_id == "as-test-0001"
    # Defaults populated for every framework block.
    assert sample_assumption_set.bel.expense_inflation_rate == 0.03


def test_myga_policy_discriminator(sample_policy: MygaPolicyState) -> None:
    assert sample_policy.product_type is ProductType.MYGA


def test_asset_record_round_trip(sample_asset: AssetRecord) -> None:
    payload = sample_asset.model_dump()
    restored = AssetRecord.model_validate(payload)
    assert restored == sample_asset


def test_reinsurance_treaty_quota_share(sample_treaty: ReinsuranceTreaty) -> None:
    assert sample_treaty.quota_share_pct == 0.50
    assert sample_treaty.qualifies_for_credit_stat is True
