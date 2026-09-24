"""
Assumption-set configuration objects.

`AssumptionSet` is the master configuration referenced by every valuation
run. It is demarcated into one block per accounting / regulatory basis:

    assumption_set.stat      STAT     — CARVM + VM-22 (+ NAIC RBC)
    assumption_set.us_gaap   US GAAP  — ASC 820 fair value (FAS 157)
    assumption_set.ldti      LDTI     — ASC 944 LFPB + DAC
    assumption_set.ebs       EBS      — Bermuda technical provisions + BEL

Every framework config inherits :class:`ProjectionBasisConfig`, i.e. carries
its own mortality / lapse / withdrawal / crediting assumptions, and the
gaspatchio engine projects each basis on its own block. Once
``is_locked=True``, edits are forbidden — new edits require creating a new
`AssumptionSet`.
"""

from datetime import date

from pydantic import BaseModel, Field

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
    Framework,
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
from .lapse import LapseRateTable
from .mortality import G2_MALE, IAM_2012_BASIC_FEMALE, IAM_2012_BASIC_MALE
from .withdrawal import FreeWithdrawalConfig, MvaConfig, PartialWithdrawalTable


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


class MortalityConfig(BaseModel):
    """Mortality basis: base table + G2 scale + flat improvement overlay.

    Table IDs refer to :class:`~actuarial_model.assumptions.mortality.MortalityAssumptionRepository`.
    """

    base_table_id_by_sex: dict[str, str] = Field(
        default_factory=lambda: {
            "M": IAM_2012_BASIC_MALE,
            "F": IAM_2012_BASIC_FEMALE,
            "U": IAM_2012_BASIC_MALE,
        }
    )
    improvement_table_id_by_sex: dict[str, str] = Field(
        default_factory=lambda: {"M": G2_MALE, "F": G2_MALE, "U": G2_MALE}
    )
    mortality_multiplier: float = Field(default=1.0, gt=0.0)
    g2_scale_multiplier: float = Field(default=1.0, ge=0.0)
    flat_improvement_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    # 2012 IAM Basic is a 2012 table; G2 improves it to each projection date.
    g2_base_date: date = date(2012, 1, 1)


class ProjectionBasisConfig(BaseModel):
    """Assumptions the gaspatchio projection engine runs on for one framework.

    Every framework config inherits this, so each basis can carry its own
    (e.g. margin-loaded STAT vs. best-estimate EBS) decrement assumptions.
    """

    mortality: MortalityConfig = Field(default_factory=MortalityConfig)
    lapse_config: LapseRateTable = Field(default_factory=_default_lapse_rate_table)
    withdrawal: WithdrawalAssumptions = Field(default_factory=WithdrawalAssumptions)
    creditor: CreditorConfig = Field(default_factory=CreditorConfig)


class StatCarvmConfig(ProjectionBasisConfig):
    """Pre-VM-22 CARVM configuration."""

    carvm_basis: StatCarvmBasis = StatCarvmBasis.AG35
    cft_scenario_set: StatCFTScenarios = StatCFTScenarios.REG_126
    reinvestment_rate: StatReinvestmentRate = StatReinvestmentRate.NEW_MONEY
    lapse_model: LapseModel = LapseModel.STATIC
    mortality_table: MortalityTable = MortalityTable.IAM_2012
    expense_fully_allocated: bool = True
    # ASSUMPTION REQUIRED: statutory valuation interest rate — should come from
    # the SVL dynamic valuation rate for the issue year and guarantee duration.
    valuation_interest_rate: float = 0.04


class StatVm22Config(ProjectionBasisConfig):
    """VM-22 (DR + SR) configuration."""

    reserve_component: Vm22Component = Vm22Component.DR_SR_MAX
    scenario_set: Vm22ScenarioSet = Vm22ScenarioSet.NAIC_10K
    cte_level: CTELevel = CTELevel.CTE70
    reinvestment_path: Vm22ReinvestmentPath = Vm22ReinvestmentPath.MEAN_REVERT
    lapse_model: LapseModel = LapseModel.DYNAMIC
    mortality_table: MortalityTable = MortalityTable.IAM_2012
    use_prescribed_margins: bool = True


class LdtiConfig(ProjectionBasisConfig):
    """ASC 944 LDTI configuration (LFPB + DAC)."""

    discount_source: LdtiDiscountSource = LdtiDiscountSource.BLOOMBERG_BVAL
    cohort_granularity: LdtiCohortGranularity = LdtiCohortGranularity.ANNUAL
    dac_basis: DacBasis = DacBasis.STRAIGHT_LINE
    assumption_update_freq: str = "ANNUAL"
    # ASSUMPTION REQUIRED: deferrable acquisition cost as a % of single
    # premium — placeholder until acquisition expenses are carried per policy.
    acquisition_cost_pct: float = 0.0
    use_contract_boundary: bool = True
    net_premium_ratio_cap: float = 1.0
    expense_fully_allocated: bool = True


class Fas157Config(ProjectionBasisConfig):
    """ASC 820 fair-value liability configuration."""

    fair_value_level: FairValueLevel = FairValueLevel.LEVEL_3
    risk_margin_method: RiskMarginMethod = RiskMarginMethod.COST_OF_CAPITAL
    cost_of_capital_rate: float = 0.06
    non_performance_risk: NonPerfRiskAdj = NonPerfRiskAdj.OWN_CREDIT
    discount_basis: Fas157DiscountBasis = Fas157DiscountBasis.OIS
    mortality_loaded: bool = False


class EbsConfig(ProjectionBasisConfig):
    """Bermuda Economic Balance Sheet configuration."""

    tp_approach: EbsTPApproach = EbsTPApproach.STANDARD
    illiquidity_premium: EbsIlliquidityPremium = EbsIlliquidityPremium.BMA_PUBLISHED
    risk_margin_method: RiskMarginMethod = RiskMarginMethod.COST_OF_CAPITAL
    cost_of_capital_rate: float = 0.06
    scr_approach: EbsSCRApproach = EbsSCRApproach.STANDARD_FORMULA
    lapse_stress: EbsLapseStress = EbsLapseStress.WORSE_OF
    mortality_improvement: MortalityImprovement = MortalityImprovement.MP2021
    apply_reinsurance_haircut: bool = True


class BelConfig(ProjectionBasisConfig):
    """Best-Estimate Liability (cross-cutting) configuration."""

    risk_free_curve: RiskFreeCurve = RiskFreeCurve.SOFR_OIS
    lapse_model: LapseModel = LapseModel.DYNAMIC
    mortality_table: MortalityTable = MortalityTable.IAM_2012
    mortality_improvement: MortalityImprovement = MortalityImprovement.MP2021
    expense_inflation_rate: float = 0.03
    projection_timestep: ProjectionTimestep = ProjectionTimestep.MONTHLY
    curve_interpolation: CurveInterpolation = CurveInterpolation.LINEAR


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


class StatBasisConfig(BaseModel):
    """STAT (US statutory) basis: CARVM and VM-22 reserves; NAIC RBC runs off these."""

    carvm: StatCarvmConfig = Field(default_factory=StatCarvmConfig)
    vm22: StatVm22Config = Field(default_factory=StatVm22Config)


class UsGaapBasisConfig(BaseModel):
    """US GAAP basis outside ASC 944 LDTI: ASC 820 fair-value liability."""

    fas157: Fas157Config = Field(default_factory=Fas157Config)


class EbsBasisConfig(BaseModel):
    """Bermuda EBS basis: technical provisions and the risk-free BEL."""

    technical_provisions: EbsConfig = Field(default_factory=EbsConfig)
    bel: BelConfig = Field(default_factory=BelConfig)


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

    stat: StatBasisConfig = Field(default_factory=StatBasisConfig)
    us_gaap: UsGaapBasisConfig = Field(default_factory=UsGaapBasisConfig)
    ldti: LdtiConfig = Field(default_factory=LdtiConfig)
    ebs: EbsBasisConfig = Field(default_factory=EbsBasisConfig)
    reinsurance: ReinsuranceConfig = Field(default_factory=ReinsuranceConfig)

    def framework_config(self, framework: Framework) -> ProjectionBasisConfig:
        """The config block (and therefore projection basis) a framework runs on."""
        configs: dict[Framework, ProjectionBasisConfig] = {
            Framework.STAT_CARVM: self.stat.carvm,
            Framework.STAT_VM22: self.stat.vm22,
            Framework.FAS157: self.us_gaap.fas157,
            Framework.LDTI: self.ldti,
            Framework.EBS: self.ebs.technical_provisions,
            Framework.BEL: self.ebs.bel,
        }
        try:
            return configs[framework]
        except KeyError as exc:
            raise ValueError(f"{framework.value} has no projection config block.") from exc
