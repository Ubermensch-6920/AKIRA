from datetime import date

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
    assert df["joint_maturity_decrement"].sum() == 0
