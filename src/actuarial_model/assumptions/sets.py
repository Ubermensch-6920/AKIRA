"""
Assumption-set configuration objects.

`AssumptionSet` is the master configuration referenced by every valuation
run. Each framework has its own nested config block. Once `is_locked=True`,
edits are forbidden — new edits require creating a new `AssumptionSet`.
"""

from datetime import date

from pydantic import BaseModel, Field

from actuarial_model.lapse.rates import LapseRateTable
from actuarial_model.withdrawal.rates import FreeWithdrawalConfig, MvaConfig, PartialWithdrawalTable

from .enums import (
    CTELevel,
    CurveInterpolation,
    DacBasis,
    EbsIlliquidityPremium,
    EbsLapseStress,
    EbsSCRApproach,
    EbsTPApproach,
    FairValueLevel,
    Fas157DiscountBasis,
    GrossToNetMethod,
    LapseModel,
    LdtiCohortGranularity,
    LdtiDiscountSource,
    MortalityImprovement,
    MortalityTable,
    NonPerfRiskAdj,
    ProjectionTimestep,
    RiskFreeCurve,
    RiskMarginMethod,
    StatCarvmBasis,
    StatCFTScenarios,
    StatReinvestmentRate,
    Vm22Component,
    Vm22ReinvestmentPath,
    Vm22ScenarioSet,
)


def _default_lapse_rate_table() -> LapseRateTable:
    return LapseRateTable(table_id="default", base_annual_rate=0.01)


class WithdrawalAssumptions(BaseModel):
    """
    Withdrawal and surrender assumption bundle for a single framework.

    Covers the three withdrawal tiers on Athene MYGA products:
      - Free withdrawal: annual no-charge allowance (fixed % of AV)
      - Partial withdrawal: behavioural rate of excess withdrawals by duration
      - MVA: Market Value Adjustment on excess withdrawal / surrender amounts

    The surrender_schedule_id references a schedule in SurrenderChargeRepository
    and is resolved at projection time by the relevant engine. Setting it to None
    means no surrender charges apply (e.g., post-charge-period runoff).
    """

    free_withdrawal: FreeWithdrawalConfig = Field(default_factory=FreeWithdrawalConfig)
    partial_withdrawal: PartialWithdrawalTable = Field(
        default_factory=lambda: PartialWithdrawalTable(table_id="default")
    )
    mva: MvaConfig = Field(default_factory=MvaConfig)
    surrender_schedule_id: str | None = None
    is_active: bool = True


class FixedCreditingConfig(BaseModel):
    """Fixed interest crediting strategy configuration."""

    annual_rate: float = 0.03


class CreditorConfig(BaseModel):
    """Interest crediting assumption configuration."""

    strategy: str = "fixed"
    fixed: FixedCreditingConfig = Field(default_factory=FixedCreditingConfig)
    is_active: bool = True


class StatCarvmConfig(BaseModel):
    """Pre-VM-22 CARVM configuration."""

    carvm_basis: StatCarvmBasis = StatCarvmBasis.AG35
    cft_scenario_set: StatCFTScenarios = StatCFTScenarios.REG_126
    reinvestment_rate: StatReinvestmentRate = StatReinvestmentRate.NEW_MONEY
    lapse_model: LapseModel = LapseModel.STATIC
    mortality_table: MortalityTable = MortalityTable.IAM_2012
    expense_fully_allocated: bool = True
    lapse_config: LapseRateTable = Field(default_factory=_default_lapse_rate_table)
    withdrawal: WithdrawalAssumptions = Field(default_factory=WithdrawalAssumptions)
    creditor: CreditorConfig = Field(default_factory=CreditorConfig)


class StatVm22Config(BaseModel):
    """VM-22 (DR + SR) configuration."""

    reserve_component: Vm22Component = Vm22Component.DR_SR_MAX
    scenario_set: Vm22ScenarioSet = Vm22ScenarioSet.NAIC_10K
    cte_level: CTELevel = CTELevel.CTE70
    reinvestment_path: Vm22ReinvestmentPath = Vm22ReinvestmentPath.MEAN_REVERT
    lapse_model: LapseModel = LapseModel.DYNAMIC
    mortality_table: MortalityTable = MortalityTable.IAM_2012
    use_prescribed_margins: bool = True
    lapse_config: LapseRateTable = Field(default_factory=_default_lapse_rate_table)
    withdrawal: WithdrawalAssumptions = Field(default_factory=WithdrawalAssumptions)
    creditor: CreditorConfig = Field(default_factory=CreditorConfig)


class LdtiConfig(BaseModel):
    """ASC 944 LDTI configuration (LFPB + DAC)."""

    discount_source: LdtiDiscountSource = LdtiDiscountSource.BLOOMBERG_BVAL
    cohort_granularity: LdtiCohortGranularity = LdtiCohortGranularity.ANNUAL
    dac_basis: DacBasis = DacBasis.STRAIGHT_LINE
    assumption_update_freq: str = "ANNUAL"
    use_contract_boundary: bool = True
    net_premium_ratio_cap: float = 1.0
    expense_fully_allocated: bool = True
    lapse_config: LapseRateTable = Field(default_factory=_default_lapse_rate_table)
    withdrawal: WithdrawalAssumptions = Field(default_factory=WithdrawalAssumptions)
    creditor: CreditorConfig = Field(default_factory=CreditorConfig)


class Fas157Config(BaseModel):
    """ASC 820 fair-value liability configuration."""

    fair_value_level: FairValueLevel = FairValueLevel.LEVEL_3
    risk_margin_method: RiskMarginMethod = RiskMarginMethod.COST_OF_CAPITAL
    cost_of_capital_rate: float = 0.06
    non_performance_risk: NonPerfRiskAdj = NonPerfRiskAdj.OWN_CREDIT
    discount_basis: Fas157DiscountBasis = Fas157DiscountBasis.OIS
    mortality_loaded: bool = False
    lapse_config: LapseRateTable = Field(default_factory=_default_lapse_rate_table)
    withdrawal: WithdrawalAssumptions = Field(default_factory=WithdrawalAssumptions)
    creditor: CreditorConfig = Field(default_factory=CreditorConfig)


class EbsConfig(BaseModel):
    """Bermuda Economic Balance Sheet configuration."""

    tp_approach: EbsTPApproach = EbsTPApproach.STANDARD
    illiquidity_premium: EbsIlliquidityPremium = EbsIlliquidityPremium.BMA_PUBLISHED
    risk_margin_method: RiskMarginMethod = RiskMarginMethod.COST_OF_CAPITAL
    cost_of_capital_rate: float = 0.06
    scr_approach: EbsSCRApproach = EbsSCRApproach.STANDARD_FORMULA
    lapse_stress: EbsLapseStress = EbsLapseStress.WORSE_OF
    mortality_improvement: MortalityImprovement = MortalityImprovement.MP2021
    apply_reinsurance_haircut: bool = True
    lapse_config: LapseRateTable = Field(default_factory=_default_lapse_rate_table)
    withdrawal: WithdrawalAssumptions = Field(default_factory=WithdrawalAssumptions)
    creditor: CreditorConfig = Field(default_factory=CreditorConfig)


class BelConfig(BaseModel):
    """Best-Estimate Liability (cross-cutting) configuration."""

    risk_free_curve: RiskFreeCurve = RiskFreeCurve.SOFR_OIS
    lapse_model: LapseModel = LapseModel.DYNAMIC
    mortality_table: MortalityTable = MortalityTable.IAM_2012
    mortality_improvement: MortalityImprovement = MortalityImprovement.MP2021
    expense_inflation_rate: float = 0.03
    projection_timestep: ProjectionTimestep = ProjectionTimestep.MONTHLY
    curve_interpolation: CurveInterpolation = CurveInterpolation.LINEAR
    lapse_config: LapseRateTable = Field(default_factory=_default_lapse_rate_table)
    withdrawal: WithdrawalAssumptions = Field(default_factory=WithdrawalAssumptions)
    creditor: CreditorConfig = Field(default_factory=CreditorConfig)


class ReinsuranceConfig(BaseModel):
    """Cross-framework reinsurance treatment levers."""

    apply_stat_credit_check: bool = True
    apply_gaap_risk_transfer_test: bool = True
    bma_default_haircut_pct: float = 0.0
    gross_to_net_method: GrossToNetMethod = GrossToNetMethod.PROPORTIONAL
    # Phase 2 stubs — wired but inert
    apply_modco_asset_accounting: bool = False
    apply_funds_withheld_accounting: bool = False
    apply_xl_layering: bool = False


class AssumptionSet(BaseModel):
    """
    Master configuration object for a single valuation run.

    Every result record references this by ``assumption_set_id``. Once
    ``is_locked=True``, the set is immutable; new edits create a new set.
    """

    assumption_set_id: str
    version: str
    description: str
    created_by: str
    created_date: date
    is_locked: bool = False

    stat_carvm: StatCarvmConfig = Field(default_factory=StatCarvmConfig)
    stat_vm22: StatVm22Config = Field(default_factory=StatVm22Config)
    ldti: LdtiConfig = Field(default_factory=LdtiConfig)
    fas157: Fas157Config = Field(default_factory=Fas157Config)
    ebs: EbsConfig = Field(default_factory=EbsConfig)
    bel: BelConfig = Field(default_factory=BelConfig)
    reinsurance: ReinsuranceConfig = Field(default_factory=ReinsuranceConfig)
