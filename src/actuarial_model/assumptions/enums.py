"""
Enumerations of all optionality / lever values used across the model.

Every assumption that materially affects a result is expressed as an Enum
here so that valuation runs, results, and audit trails reference an explicit
discrete choice rather than a free-form string.
"""

from enum import Enum


# ────────────────────────────────────────────────────────────────────────
# Products and frameworks
# ────────────────────────────────────────────────────────────────────────
class ProductType(str, Enum):
    """Insurance product family. Drives projection-engine dispatch."""

    MYGA = "MYGA"  # Phase 1
    FIA = "FIA"  # Phase 2
    SPIA = "SPIA"  # Phase 2
    PRT = "PRT"  # Phase 2
    VA = "VA"  # Phase 3
    ULSG = "ULSG"  # Phase 3


class Framework(str, Enum):
    """Reserving / valuation framework producing a result."""

    STAT_CARVM = "STAT_CARVM"
    STAT_VM22 = "STAT_VM22"
    LDTI = "LDTI"
    FAS157 = "FAS157"
    EBS = "EBS"
    BEL = "BEL"


# ────────────────────────────────────────────────────────────────────────
# STAT (Pre-VM-22 CARVM) levers
# ────────────────────────────────────────────────────────────────────────
class StatCarvmBasis(str, Enum):
    """CARVM basis selection (Actuarial Guideline)."""

    AG33 = "AG33"
    AG35 = "AG35"


class StatCFTScenarios(str, Enum):
    """Cash-flow-testing scenario set."""

    REG_126 = "REG_126"
    COMPANY = "COMPANY"


class StatReinvestmentRate(str, Enum):
    """Reinvestment-rate convention used in CARVM cash flow testing."""

    NEW_MONEY = "NEW_MONEY"
    PORTFOLIO = "PORTFOLIO"
    PRESCRIBED = "PRESCRIBED"


# ────────────────────────────────────────────────────────────────────────
# VM-22 levers
# ────────────────────────────────────────────────────────────────────────
class Vm22Component(str, Enum):
    """Which VM-22 reserve components are included."""

    DR_ONLY = "DR_ONLY"
    DR_SR_MAX = "DR_SR_MAX"


class CTELevel(str, Enum):
    """Conditional Tail Expectation level for stochastic reserve / capital."""

    CTE65 = "CTE65"
    CTE70 = "CTE70"
    CTE80 = "CTE80"


class Vm22ScenarioSet(str, Enum):
    """Stochastic scenario set for VM-22."""

    NAIC_10K = "NAIC_10K"
    PRESCRIBED_200 = "PRESCRIBED_200"
    COMPANY = "COMPANY"


class Vm22ReinvestmentPath(str, Enum):
    """Reinvestment-rate path style used inside VM-22 projections."""

    MEAN_REVERT = "MEAN_REVERT"
    FLAT_FORWARD = "FLAT_FORWARD"
    GRADE_ULTIMATE = "GRADE_ULTIMATE"


# ────────────────────────────────────────────────────────────────────────
# Mortality / lapse / improvement
# ────────────────────────────────────────────────────────────────────────
class LapseModel(str, Enum):
    """Lapse / surrender behavior model."""

    STATIC = "STATIC"
    DYNAMIC = "DYNAMIC"


class MortalityTable(str, Enum):
    """Base mortality table selection."""

    IAM_2012 = "IAM_2012"
    GAM_1983 = "GAM_1983"
    COMPANY = "COMPANY"


class MortalityImprovement(str, Enum):
    """Mortality improvement scale."""

    MP2021 = "MP2021"
    MP2020 = "MP2020"
    NONE = "NONE"


# ────────────────────────────────────────────────────────────────────────
# LDTI levers
# ────────────────────────────────────────────────────────────────────────
class LdtiDiscountSource(str, Enum):
    """Source of upper-medium-grade fixed-income yields used to discount LFPB."""

    BLOOMBERG_BVAL = "BLOOMBERG_BVAL"
    ICE = "ICE"
    INTERNAL = "INTERNAL"


class LdtiCohortGranularity(str, Enum):
    """Cohort aggregation granularity for LDTI net-premium-ratio buckets."""

    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"


class DacBasis(str, Enum):
    """Deferred acquisition cost amortization basis."""

    STRAIGHT_LINE = "STRAIGHT_LINE"  # post-LDTI
    EGP = "EGP"  # legacy


# ────────────────────────────────────────────────────────────────────────
# FAS 157 / ASC 820 levers
# ────────────────────────────────────────────────────────────────────────
class FairValueLevel(str, Enum):
    """ASC 820 fair value hierarchy classification."""

    LEVEL_2 = "LEVEL_2"
    LEVEL_3 = "LEVEL_3"


class RiskMarginMethod(str, Enum):
    """Method of computing the risk margin in fair-value liability."""

    COST_OF_CAPITAL = "COST_OF_CAPITAL"
    CALM = "CALM"
    EXPLICIT = "EXPLICIT"


class NonPerfRiskAdj(str, Enum):
    """Non-performance / own-credit risk adjustment treatment."""

    OWN_CREDIT = "OWN_CREDIT"
    PRESCRIBED = "PRESCRIBED"
    ZERO = "ZERO"


class Fas157DiscountBasis(str, Enum):
    """Discount basis for ASC 820 fair-value liabilities."""

    OIS = "OIS"
    SINGLE_A = "SINGLE_A"
    RF_ILLIQ = "RF_ILLIQ"


# ────────────────────────────────────────────────────────────────────────
# EBS (Bermuda Economic Balance Sheet) levers
# ────────────────────────────────────────────────────────────────────────
class EbsTPApproach(str, Enum):
    """Technical-provisions approach under BMA EBS."""

    STANDARD = "STANDARD"
    SBA = "SBA"  # Scenario-Based Approach


class EbsIlliquidityPremium(str, Enum):
    """Source of the illiquidity / matching adjustment premium."""

    BMA_PUBLISHED = "BMA_PUBLISHED"
    ZERO = "ZERO"
    INTERNAL = "INTERNAL"


class EbsLapseStress(str, Enum):
    """Lapse stress direction for EBS BSCR."""

    UP = "UP"
    DOWN = "DOWN"
    WORSE_OF = "WORSE_OF"


class EbsSCRApproach(str, Enum):
    """Solvency Capital Requirement methodology under EBS."""

    STANDARD_FORMULA = "STANDARD_FORMULA"
    PARTIAL_INTERNAL = "PARTIAL_INTERNAL"
    FULL_INTERNAL = "FULL_INTERNAL"


# ────────────────────────────────────────────────────────────────────────
# BEL / cross-cutting levers
# ────────────────────────────────────────────────────────────────────────
class RiskFreeCurve(str, Enum):
    """Risk-free curve choice for BEL discounting."""

    SOFR_OIS = "SOFR_OIS"
    USD_SWAP = "USD_SWAP"
    US_TREASURY = "US_TREASURY"


class ProjectionTimestep(str, Enum):
    """Cash flow projection grid frequency."""

    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"


class CurveInterpolation(str, Enum):
    """Yield curve interpolation method."""

    LINEAR = "LINEAR"
    CUBIC_SPLINE = "CUBIC_SPLINE"


# ────────────────────────────────────────────────────────────────────────
# Reinsurance enums
# ────────────────────────────────────────────────────────────────────────
class ReinsuranceTreatyType(str, Enum):
    """Reinsurance treaty structural type."""

    QUOTA_SHARE = "QUOTA_SHARE"  # Phase 1
    COINSURANCE = "COINSURANCE"  # Phase 2
    MODCO = "MODCO"  # Phase 2
    FUNDS_WITHHELD = "FUNDS_WITHHELD"  # Phase 2
    YRT = "YRT"  # Phase 2
    EXCESS_OF_LOSS = "EXCESS_OF_LOSS"  # Phase 2


class ReinsurerAuthStatus(str, Enum):
    """Reinsurer authorization status (drives STAT credit allowance)."""

    AUTHORIZED = "AUTHORIZED"
    CERTIFIED = "CERTIFIED"
    UNAUTHORIZED = "UNAUTHORIZED"
    RECIPROCAL = "RECIPROCAL"


class CollateralType(str, Enum):
    """Collateral posted to support reinsurance credit."""

    NONE = "NONE"
    LETTER_OF_CREDIT = "LETTER_OF_CREDIT"
    TRUST = "TRUST"
    FUNDS_WITHHELD = "FUNDS_WITHHELD"


class RiskTransferMethod(str, Enum):
    """Risk-transfer testing methodology (ASC 944 / SSAP 61R)."""

    REASONABLE_POSSIBILITY = "REASONABLE_POSSIBILITY"  # ASC 944
    ERD = "ERD"  # Expected Reinsurer Deficit
    DEPOSIT_ACCOUNTING = "DEPOSIT_ACCOUNTING"


class GrossToNetMethod(str, Enum):
    """How net cash flows are derived from gross cash flows under a treaty."""

    PROPORTIONAL = "PROPORTIONAL"  # QS
    LAYERED = "LAYERED"  # XL
    EXPERIENCE = "EXPERIENCE"  # YRT-style
