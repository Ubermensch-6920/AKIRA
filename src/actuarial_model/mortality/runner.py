from __future__ import annotations

from datetime import date
from pathlib import Path

from actuarial_model.mortality.decrements import (
    AssumptionSelection,
    MortalityAssumptionRepository,
    MortalityDecrementCalculator,
    MortalityMethod,
    MortalityProjectionRequest,
    ProjectionFrequency,
    SeriatimLifeInput,
    SeriatimPolicyInput,
    Sex,
)


def build_assumption_selection() -> AssumptionSelection:
    """Controller-side assumption passthrough.

    Change assumptions here without editing the mortality calculator.
    """

    return AssumptionSelection(
        assumption_set_id="DEV_SOA_IAM_G2_PLUS_1PCT_MI",
        mortality_multiplier=1.0,
        g2_scale_multiplier=1.0,
        flat_improvement_rate=0.01,
        g2_base_date=date(2012, 1, 1),
        flat_improvement_base_date=None,  # None means use policy issue date.
        base_table_id_by_sex={
            Sex.MALE: "SOA_2012_IAM_BASIC_MALE_2581",
            Sex.FEMALE: "SOA_2012_IAM_BASIC_FEMALE_2582",
            Sex.UNISEX: "SOA_2012_IAM_BASIC_MALE_2581",
        },
        improvement_table_id_by_sex={
            # User requested table 2583 as the G2 scalar.
            Sex.MALE: "SOA_G2_MALE_2583",
            Sex.FEMALE: "SOA_G2_MALE_2583",
            Sex.UNISEX: "SOA_G2_MALE_2583",
        },
    )


def build_seriatim_policy() -> SeriatimPolicyInput:
    """Controller-side seriatim passthrough.

    Change policy/life inputs here without editing the mortality calculator.
    """

    return SeriatimPolicyInput(
        policy_id="DEV_JOINT_001",
        issue_date=date(2021, 1, 1),
        starting_policy_count=1_000.0,
        lives=[
            SeriatimLifeInput(life_id="LIFE_1", issue_age=60.0, sex=Sex.MALE),
            SeriatimLifeInput(life_id="LIFE_2", issue_age=62.0, sex=Sex.FEMALE),
        ],
    )


def build_projection_request() -> MortalityProjectionRequest:
    return MortalityProjectionRequest(
        run_id="DEV_RUN_20210101",
        seriatim=build_seriatim_policy(),
        assumptions=build_assumption_selection(),
        projection_periods=120,
        frequency=ProjectionFrequency.MONTHLY,
        method=MortalityMethod.CONSTANT_FORCE,
    )


def run_projection():
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    calculator = MortalityDecrementCalculator(repository)
    request = build_projection_request()
    output = calculator.calculate(request)
    return output.to_frame()


if __name__ == "__main__":
    df = run_projection()

    output_path = Path("mortality_projection_output.csv")
    df.to_csv(output_path, index=False)

    display_columns = [
        "period",
        "period_start_date",
        "attained_age_1",
        "base_annual_qx_1",
        "g2_rate_1",
        "adjusted_annual_qx_1",
        "period_qx_1",
        "attained_age_2",
        "base_annual_qx_2",
        "g2_rate_2",
        "adjusted_annual_qx_2",
        "period_qx_2",
        "both_alive_start",
        "joint_first_death_decrement",
        "joint_last_survivor_decrement",
        "joint_last_survivor_inforce_end",
    ]

    print(df[display_columns].head(12).to_string(index=False))
    print(f"\nWrote: {output_path.resolve()}")
