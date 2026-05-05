from datetime import date

from actuarial_model.lapse import LapseRateTable
from actuarial_model.withdrawal import (
    FreeWithdrawalConfig,
    PartialWithdrawalTable,
)
from actuarial_model.assumptions import WithdrawalAssumptions
from actuarial_model.mortality.decrements import (
    AssumptionSelection,
    MortalityAssumptionRepository,
    MortalityDecrementCalculator,
    MortalityProjectionRequest,
    ProjectionFrequency,
    SeriatimLifeInput,
    SeriatimPolicyInput,
    Sex,
)


def test_single_life_projection_runs():
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    request = MortalityProjectionRequest(
        run_id="TEST",
        seriatim=SeriatimPolicyInput(
            policy_id="P1",
            issue_date=date(2021, 1, 1),
            lives=[SeriatimLifeInput(life_id="L1", issue_age=60, sex=Sex.MALE)],
            starting_policy_count=1000,
        ),
        assumptions=AssumptionSelection(),
        projection_periods=12,
        frequency=ProjectionFrequency.MONTHLY,
    )
    output = MortalityDecrementCalculator(repository).calculate(request)
    df = output.to_frame()

    assert len(df) == 12
    assert df["single_mortality_decrement"].sum() > 0
    assert df["single_lapse_decrement"].sum() == 0
    assert df["single_withdrawal_decrement"].sum() == 0
    assert df["single_maturity_decrement"].sum() == 0
    assert df["single_inforce_end"].iloc[-1] < 1000


def test_joint_life_projection_state_conservation():
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    request = MortalityProjectionRequest(
        run_id="TEST",
        seriatim=SeriatimPolicyInput(
            policy_id="P2",
            issue_date=date(2021, 1, 1),
            lives=[
                SeriatimLifeInput(life_id="L1", issue_age=60, sex=Sex.MALE),
                SeriatimLifeInput(life_id="L2", issue_age=62, sex=Sex.FEMALE),
            ],
            starting_policy_count=1000,
        ),
        assumptions=AssumptionSelection(),
        projection_periods=24,
        frequency=ProjectionFrequency.MONTHLY,
    )
    output = MortalityDecrementCalculator(repository).calculate(request)
    df = output.to_frame()

    final = df.iloc[-1]
    state_total = (
        final["both_alive_end"]
        + final["life1_only_alive_end"]
        + final["life2_only_alive_end"]
        + final["all_dead_end"]
    )

    assert len(df) == 24
    assert abs(state_total - 1000) < 1e-8
    assert final["joint_first_death_inforce_end"] <= 1000
    assert final["joint_last_survivor_inforce_end"] <= 1000
    assert df["joint_lapse_decrement"].sum() == 0
    assert df["joint_withdrawal_decrement"].sum() == 0
    assert df["joint_maturity_decrement"].sum() == 0


def test_single_life_with_uniform_lapse():
    """Test single life projection with uniform lapse rate."""
    lapse_table = LapseRateTable(
        table_id="test_uniform",
        base_annual_rate=0.01,
    )
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    assumptions = AssumptionSelection(lapse_rate_table=lapse_table)

    request = MortalityProjectionRequest(
        run_id="TEST_LAPSE",
        seriatim=SeriatimPolicyInput(
            policy_id="P3",
            issue_date=date(2021, 1, 1),
            lives=[SeriatimLifeInput(life_id="L1", issue_age=60, sex=Sex.MALE)],
            starting_policy_count=1000,
        ),
        assumptions=assumptions,
        projection_periods=12,
        frequency=ProjectionFrequency.MONTHLY,
    )
    output = MortalityDecrementCalculator(repository).calculate(request)
    df = output.to_frame()

    assert len(df) == 12
    assert df["single_lapse_decrement"].sum() > 0
    assert all(lapse > 0 for lapse in df["single_lapse_decrement"])
    assert df["single_inforce_end"].iloc[-1] < df["single_inforce_start"].iloc[0]


def test_single_life_with_shock_lapse():
    """Test single life projection with lapse shock rates."""
    lapse_table = LapseRateTable(
        table_id="test_shocks",
        base_annual_rate=0.01,
        shock_rates={3: 0.20, 5: 0.40, 7: 0.50},
    )
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    assumptions = AssumptionSelection(lapse_rate_table=lapse_table)

    request = MortalityProjectionRequest(
        run_id="TEST_LAPSE_SHOCK",
        seriatim=SeriatimPolicyInput(
            policy_id="P4",
            issue_date=date(2021, 1, 1),
            lives=[SeriatimLifeInput(life_id="L1", issue_age=60, sex=Sex.MALE)],
            starting_policy_count=1000,
        ),
        assumptions=assumptions,
        projection_periods=84,
        frequency=ProjectionFrequency.MONTHLY,
    )
    output = MortalityDecrementCalculator(repository).calculate(request)
    df = output.to_frame()

    assert len(df) == 84
    assert df["single_lapse_decrement"].sum() > 0
    assert all(lapse >= 0 for lapse in df["single_lapse_decrement"])


def test_joint_life_with_uniform_lapse():
    """Test joint life projection with uniform lapse rate."""
    lapse_table = LapseRateTable(
        table_id="test_uniform",
        base_annual_rate=0.01,
    )
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    assumptions = AssumptionSelection(lapse_rate_table=lapse_table)

    request = MortalityProjectionRequest(
        run_id="TEST_JOINT_LAPSE",
        seriatim=SeriatimPolicyInput(
            policy_id="P5",
            issue_date=date(2021, 1, 1),
            lives=[
                SeriatimLifeInput(life_id="L1", issue_age=60, sex=Sex.MALE),
                SeriatimLifeInput(life_id="L2", issue_age=62, sex=Sex.FEMALE),
            ],
            starting_policy_count=1000,
        ),
        assumptions=assumptions,
        projection_periods=24,
        frequency=ProjectionFrequency.MONTHLY,
    )
    output = MortalityDecrementCalculator(repository).calculate(request)
    df = output.to_frame()

    assert len(df) == 24
    assert df["joint_lapse_decrement"].sum() > 0
    assert all(lapse > 0 for lapse in df["joint_lapse_decrement"])


def test_single_life_with_uniform_withdrawal():
    """Test single life projection with uniform withdrawal rate."""
    withdrawal_config = WithdrawalAssumptions(
        free_withdrawal=FreeWithdrawalConfig(annual_free_pct=0.10),
        partial_withdrawal=PartialWithdrawalTable(
            table_id="test_uniform",
            base_annual_rate=0.05,
        ),
        is_active=True,
    )
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    assumptions = AssumptionSelection(withdrawal_assumptions=withdrawal_config)

    request = MortalityProjectionRequest(
        run_id="TEST_WITHDRAWAL",
        seriatim=SeriatimPolicyInput(
            policy_id="P6",
            issue_date=date(2021, 1, 1),
            lives=[SeriatimLifeInput(life_id="L1", issue_age=60, sex=Sex.MALE)],
            starting_policy_count=1000,
        ),
        assumptions=assumptions,
        projection_periods=12,
        frequency=ProjectionFrequency.MONTHLY,
    )
    output = MortalityDecrementCalculator(repository).calculate(request)
    df = output.to_frame()

    assert len(df) == 12
    assert df["single_withdrawal_decrement"].sum() > 0
    assert all(w > 0 for w in df["single_withdrawal_decrement"])
    assert df["single_inforce_end"].iloc[-1] < df["single_inforce_start"].iloc[0]


def test_single_life_with_duration_dependent_withdrawal():
    """Test single life with withdrawal rates that vary by policy duration."""
    withdrawal_config = WithdrawalAssumptions(
        free_withdrawal=FreeWithdrawalConfig(annual_free_pct=0.10),
        partial_withdrawal=PartialWithdrawalTable(
            table_id="test_duration",
            base_annual_rate=0.02,
            rates_by_duration={1: 0.01, 3: 0.08, 5: 0.12},
        ),
        is_active=True,
    )
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    assumptions = AssumptionSelection(withdrawal_assumptions=withdrawal_config)

    request = MortalityProjectionRequest(
        run_id="TEST_WITHDRAWAL_DURATION",
        seriatim=SeriatimPolicyInput(
            policy_id="P7",
            issue_date=date(2021, 1, 1),
            lives=[SeriatimLifeInput(life_id="L1", issue_age=60, sex=Sex.MALE)],
            starting_policy_count=1000,
        ),
        assumptions=assumptions,
        projection_periods=60,
        frequency=ProjectionFrequency.MONTHLY,
    )
    output = MortalityDecrementCalculator(repository).calculate(request)
    df = output.to_frame()

    assert len(df) == 60
    assert df["single_withdrawal_decrement"].sum() > 0


def test_joint_life_with_withdrawal():
    """Test joint life projection with withdrawal rates."""
    withdrawal_config = WithdrawalAssumptions(
        free_withdrawal=FreeWithdrawalConfig(annual_free_pct=0.10),
        partial_withdrawal=PartialWithdrawalTable(
            table_id="test",
            base_annual_rate=0.05,
        ),
        is_active=True,
    )
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    assumptions = AssumptionSelection(withdrawal_assumptions=withdrawal_config)

    request = MortalityProjectionRequest(
        run_id="TEST_JOINT_WITHDRAWAL",
        seriatim=SeriatimPolicyInput(
            policy_id="P8",
            issue_date=date(2021, 1, 1),
            lives=[
                SeriatimLifeInput(life_id="L1", issue_age=60, sex=Sex.MALE),
                SeriatimLifeInput(life_id="L2", issue_age=62, sex=Sex.FEMALE),
            ],
            starting_policy_count=1000,
        ),
        assumptions=assumptions,
        projection_periods=24,
        frequency=ProjectionFrequency.MONTHLY,
    )
    output = MortalityDecrementCalculator(repository).calculate(request)
    df = output.to_frame()

    assert len(df) == 24
    assert df["joint_withdrawal_decrement"].sum() > 0
    assert all(w > 0 for w in df["joint_withdrawal_decrement"])


def test_withdrawal_inactive():
    """Test that inactive withdrawal config produces zero decrements."""
    withdrawal_config = WithdrawalAssumptions(
        free_withdrawal=FreeWithdrawalConfig(annual_free_pct=0.10),
        partial_withdrawal=PartialWithdrawalTable(table_id="test", base_annual_rate=0.05),
        is_active=False,
    )
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    assumptions = AssumptionSelection(withdrawal_assumptions=withdrawal_config)

    request = MortalityProjectionRequest(
        run_id="TEST",
        seriatim=SeriatimPolicyInput(
            policy_id="P9",
            issue_date=date(2021, 1, 1),
            lives=[SeriatimLifeInput(life_id="L1", issue_age=60, sex=Sex.MALE)],
            starting_policy_count=1000,
        ),
        assumptions=assumptions,
        projection_periods=12,
        frequency=ProjectionFrequency.MONTHLY,
    )
    output = MortalityDecrementCalculator(repository).calculate(request)
    df = output.to_frame()

    assert df["single_withdrawal_decrement"].sum() == 0
