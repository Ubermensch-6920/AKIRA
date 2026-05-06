# AKIRA Architecture & Data Flow

## 1. Module Structure

```
actuarial_model/
├── assumptions/                    # Assumption configuration framework
│   ├── enums.py                   # LapseModel, MortalityTable, Framework choices
│   ├── sets.py                    # AssumptionSet, CreditorConfig, LapseConfig, WithdrawalAssumptions
│   └── __init__.py                # Exports for public API
│
├── mortality/                      # Core mortality decrement engine
│   └── decrements.py              # MortalityDecrementCalculator, MortalityProjectionRow
│
├── lapse/                          # Lapse rate assumptions
│   ├── rates.py                   # LapseRateTable, LapseAssumptionRepository
│   ├── calculator.py              # LapseDecrementCalculator
│   └── __init__.py
│
├── withdrawal/                     # Withdrawal and surrender assumptions
│   ├── rates.py                   # SurrenderChargeSchedule, FreeWithdrawalConfig, MvaConfig, PartialWithdrawalTable
│   ├── calculator.py              # WithdrawalCalculator (free, surrender charge, MVA, partial)
│   └── __init__.py
│
├── crediting/                      # Interest crediting assumptions
│   ├── calculator.py              # CreditorCalculator (fixed rate, future: indexed/hybrid)
│   └── __init__.py
│
└── models/                         # Domain models (policies, assets, etc.)
```

## 2. Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  AssumptionSet (Master Config)           SeriatimPolicyInput       │
│  ├─ stat_carvm: StatCarvmConfig          ├─ policy_id              │
│  ├─ stat_vm22: StatVm22Config            ├─ issue_date             │
│  ├─ ldti: LdtiConfig                     ├─ lives[]                │
│  ├─ fas157: Fas157Config                 │   ├─ life_id            │
│  ├─ ebs: EbsConfig                       │   ├─ issue_age          │
│  └─ bel: BelConfig                       │   └─ sex                │
│      ├─ lapse_config: LapseConfig        └─ starting_policy_count  │
│      ├─ withdrawal: WithdrawalAssumptions                          │
│      └─ creditor: CreditorConfig                                   │
│                                                                      │
│  AssumptionSelection (Mortality-specific)                          │
│  ├─ lapse_rate_table: LapseRateTable?                             │
│  ├─ withdrawal_assumptions: WithdrawalAssumptions?                │
│  └─ creditor_config: CreditorConfig?                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│              MortalityProjectionRequest (Combined)                  │
│  ├─ seriatim: SeriatimPolicyInput                                  │
│  ├─ assumptions: AssumptionSelection                               │
│  ├─ projection_periods: int                                        │
│  └─ frequency: ProjectionFrequency (MONTHLY/QUARTERLY/ANNUAL)     │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    PROCESSING LAYER                                 │
│              MortalityDecrementCalculator.calculate()               │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
         ┌──────────────────────┴──────────────────────┐
         ↓                                              ↓
   ┌─────────────────┐                        ┌─────────────────┐
   │  Single Life    │                        │   Joint Life    │
   │  Calculation    │                        │   Calculation   │
   └─────────────────┘                        └─────────────────┘
         ↓                                              ↓
    For each period (1 to N):                  For each period (1 to N):
    ┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
    │ 1. Get mortality rates               │  │ 1. Get mortality rates (both lives)  │
    │    MortalityAssumptionRepository     │  │    MortalityAssumptionRepository     │
    │    → base_qx, g2_rate, adjusted_qx  │  │    → q1, q2, adjusted_qx1, adjusted  │
    │                                      │  │    → Calc joint states (both_alive,  │
    │ 2. Calculate decrements:             │  │       life1_only, life2_only, all_de │
    │    mortality_decrement = inforce *   │  │                                      │
    │      period_qx                       │  │ 2. Calculate decrements:             │
    │                                      │  │    mortality_decrement = q1 + q2     │
    │ 3. Calculate lapse decrement:        │  │    joint_first_death = 1 - (p1*p2)  │
    │    if lapse_rate_table:              │  │    joint_last_survivor = all_dead   │
    │      LapseRateTable.rate_at_duration │  │                                      │
    │      lapse_decrement = inforce *     │  │ 3. Calculate lapse decrement:        │
    │        annual_lapse_rate             │  │    if lapse_rate_table:              │
    │                                      │  │      LapseRateTable.rate_at_duration │
    │ 4. Calculate withdrawal decrement:   │  │      lapse_decrement = both_alive *  │
    │    if withdrawal_assumptions:        │  │        annual_lapse_rate             │
    │      WithdrawalCalculator.partial_   │  │                                      │
    │        withdrawal_decrement()        │  │ 4. Calculate withdrawal decrement:   │
    │                                      │  │    if withdrawal_assumptions:        │
    │ 5. Calculate crediting accrual:      │  │      WithdrawalCalculator.partial_   │
    │    if creditor_config:               │  │        withdrawal_decrement()        │
    │      CreditorCalculator.crediting_   │  │                                      │
    │        accrual()                     │  │ 5. Calculate crediting accrual:      │
    │                                      │  │    if creditor_config:               │
    │ 6. Calculate ending in-force:        │  │      CreditorCalculator.crediting_   │
    │    inforce_end = max(                │  │        accrual()                     │
    │      inforce_start                   │  │                                      │
    │      - mortality_decrement           │  │ 6. Update state vectors:             │
    │      - lapse_decrement               │  │    both_alive = survivors +          │
    │      - withdrawal_decrement          │  │      crediting_accrual               │
    │      + crediting_accrual,            │  │    life1_only = transitions          │
    │      0.0)                            │  │    life2_only = transitions          │
    │                                      │  │    all_dead = cumulative             │
    └──────────────────────────────────────┘  └──────────────────────────────────────┘
         ↓                                              ↓
    Append MortalityProjectionRow               Append MortalityProjectionRow
    ├─ period, dates, metadata                 ├─ period, dates, metadata
    ├─ mortality rates & decrements            ├─ mortality rates & decrements
    ├─ lapse decrement                         ├─ lapse decrement
    ├─ withdrawal decrement                    ├─ withdrawal decrement
    ├─ crediting accrual                       ├─ crediting accrual
    ├─ inforce_start & inforce_end             ├─ state_start & state_end
    └─ (repeat for next period)                └─ (repeat for next period)
         ↓                                              ↓
         └──────────────────────┬───────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     OUTPUT LAYER                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  MortalityProjectionOutput                                          │
│  ├─ records: list[MortalityProjectionRow]                          │
│  │   ├─ Period 1: mortality=X, lapse=Y, withdrawal=Z, crediting=C │
│  │   ├─ Period 2: mortality=X, lapse=Y, withdrawal=Z, crediting=C │
│  │   └─ Period N: mortality=X, lapse=Y, withdrawal=Z, crediting=C │
│  └─ to_frame() → pandas DataFrame                                  │
│      ├─ single_mortality_decrement (col)                           │
│      ├─ single_lapse_decrement (col)                               │
│      ├─ single_withdrawal_decrement (col)                          │
│      ├─ single_crediting_accrual (col)                             │
│      ├─ single_inforce_start & single_inforce_end (cols)           │
│      └─ ... (100+ columns for analysis)                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. Component Interaction Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                   ASSUMPTION CONFIGURATION                             │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  AssumptionSet (Master, per valuation run)                            │
│  ├─ Framework configs: [StatCarvm, StatVm22, Ldti, Fas157, Ebs, Bel]  │
│  │  └─ Each contains:                                                  │
│  │     ├─ lapse_config: LapseConfig                                    │
│  │     ├─ withdrawal: WithdrawalAssumptions                            │
│  │     └─ creditor: CreditorConfig                                     │
│  │                                                                      │
│  └─ Pass to MortalityProjectionRequest.assumptions (AssumptionSelection)
│     └─ Controller extracts relevant assumptions for mortality calc      │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
                                ↓
┌────────────────────────────────────────────────────────────────────────┐
│                 DECREMENT CALCULATOR (Orchestrator)                    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  MortalityDecrementCalculator                                         │
│  ├─ __init__(repository: MortalityAssumptionRepository)                │
│  │                                                                     │
│  ├─ calculate(request: MortalityProjectionRequest)                    │
│  │  └─ Determines: Single life or Joint life?                         │
│  │                                                                     │
│  ├─ _calculate_single_life()                                          │
│  │  ├─ For each period:                                               │
│  │  │  ├─ Query mortality rates                                       │
│  │  │  │  └─ Use MortalityAssumptionRepository.tables                 │
│  │  │  ├─ Query lapse rates                                           │
│  │  │  │  └─ Use LapseRateTable.rate_at_duration()                    │
│  │  │  ├─ Query withdrawal decrements                                 │
│  │  │  │  └─ Use WithdrawalCalculator.partial_withdrawal_decrement()  │
│  │  │  ├─ Query crediting accrual                                     │
│  │  │  │  └─ Use CreditorCalculator.crediting_accrual()               │
│  │  │  └─ Build MortalityProjectionRow                                │
│  │  └─ Return MortalityProjectionOutput                               │
│  │                                                                     │
│  └─ _calculate_joint_life()                                           │
│     └─ (Same pattern, managing state transitions for 4 states)        │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
        ↓              ↓              ↓              ↓
   [Mortality]   [Lapse]    [Withdrawal]      [Crediting]
     Rates        Rates          Rates          Strategy
      ↓             ↓              ↓              ↓
```

## 4. Decrements Calculation Order (Per Period)

```
Start of Period
│
├─ inforce_start = 1000
│
├─ Step 1: Mortality Decrement
│  └─ MortalityAssumptionRepository.get("SOA_2012_IAM_BASIC_MALE_2581")
│     └─ mortality_decrement = 1000 × 0.005 = 5
│
├─ Step 2: Lapse Decrement
│  └─ if lapse_rate_table:
│     └─ LapseRateTable.rate_at_duration(year=3)
│        └─ lapse_decrement = 1000 × 0.20 = 200  (shock rate at year 3)
│
├─ Step 3: Withdrawal Decrement
│  └─ if withdrawal_assumptions.is_active:
│     └─ WithdrawalCalculator.partial_withdrawal_decrement(
│          inforce_start=1000,
│          table=PartialWithdrawalTable(base_rate=0.05),
│          duration_years=3
│        )
│        └─ withdrawal_decrement = 1000 × 0.05 = 50
│
├─ Step 4: Crediting Accrual (POSITIVE)
│  └─ if creditor_config.is_active:
│     └─ CreditorCalculator.crediting_accrual(
│          inforce_start=1000,
│          config=CreditorConfig(annual_rate=0.03)
│        )
│        └─ crediting_accrual = 1000 × 0.03 = 30
│
├─ Step 5: Calculate Ending In-Force
│  └─ inforce_end = max(
│       1000 - 5 - 200 - 50 + 30,
│       0
│     )
│     = max(775, 0)
│     = 775
│
└─ End of Period
   └─ inforce_end becomes inforce_start for next period
```

## 5. Class Hierarchy & Relationships

```
┌──────────────────────────────────────────────────────────────┐
│                    Pydantic BaseModel                        │
├──────────────────────────────────────────────────────────────┤
│ (All config classes inherit from BaseModel for validation)   │
└──────────────────────────────────────────────────────────────┘
       ↑        ↑        ↑         ↑         ↑        ↑
       │        │        │         │         │        │
   ┌───┴────┬───┴──┬─────┴─────┬──┴───┬─────┴──┬────┴──┐
   │         │      │           │      │        │       │
LapseConfig WithdrawalAssumptions FixedCreditingConfig  │
                    │                │        │       │
         ┌─────────────┬─────────┤        │  CreditorConfig
         │             │         │        │       │
    FreeWithdrawalConfig PartialWithdrawalTable  MvaConfig
                                        │
   ┌─────────────────────────────────────┼──────────────────────┐
   │                                     │                      │
StatCarvmConfig, StatVm22Config, LdtiConfig, Fas157Config, EbsConfig, BelConfig
(Each contains lapse_config, withdrawal, creditor fields)
   │
   └─→ AssumptionSet (Master config with all 6 frameworks)
        │
        └─→ MortalityProjectionRequest
            └─→ AssumptionSelection (subset for mortality calc)
                ├─ lapse_rate_table: LapseRateTable
                ├─ withdrawal_assumptions: WithdrawalAssumptions
                └─ creditor_config: CreditorConfig
```

## 6. Repository Pattern (Assumption Stores)

```
┌─────────────────────────────────────────────────────┐
│      MortalityAssumptionRepository (Singleton)     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  _tables: dict[str, RateTable]                      │
│  ├─ "SOA_2012_IAM_BASIC_MALE_2581"                 │
│  ├─ "SOA_2012_IAM_BASIC_FEMALE_2582"               │
│  └─ "SOA_G2_MALE_2583"                             │
│                                                     │
│  @classmethod                                       │
│  with_embedded_soa_iam_g2()                        │
│  └─ Factory loading embedded SOA tables            │
│                                                     │
│  get(table_id: str) → RateTable                    │
│                                                     │
└─────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────┐
│    LapseAssumptionRepository (per controller)      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  _tables: dict[str, LapseRateTable]                 │
│  ├─ "standard_1pct_no_shock"                       │
│  └─ "standard_1pct_shocks" {3: 0.20, 5: 0.40}     │
│                                                     │
│  @staticmethod                                      │
│  default() → LapseAssumptionRepository              │
│  └─ Factory with standard tables                   │
│                                                     │
│  register(table: LapseRateTable)                   │
│  get(table_id: str) → LapseRateTable               │
│                                                     │
└─────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────┐
│  SurrenderChargeRepository (per controller)        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  _schedules: dict[str, SurrenderChargeSchedule]     │
│  ├─ "ATHENE_MYG_3" {1: 0.08, 2: 0.08, 3: 0.07}    │
│  ├─ "ATHENE_MYG_5" {1: 0.08, 2: 0.07, ..., 5:0.04}│
│  └─ "ATHENE_MAXRATE_7" {1-7: 0.10}                 │
│                                                     │
│  @classmethod                                       │
│  with_athene_schedules() → SurrenderChargeRepository│
│  └─ Factory with Athene product schedules          │
│                                                     │
│  register(schedule: SurrenderChargeSchedule)       │
│  get(schedule_id: str) → SurrenderChargeSchedule   │
│  list_schedules() → [schedule_ids]                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 7. Test Coverage Map

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Suite (111 tests)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ tests/test_crediting/test_crediting.py (16 tests)          │
│ ├─ FixedCreditingConfig (2 tests)                          │
│ ├─ CreditorConfig (3 tests)                                │
│ └─ CreditorCalculator (11 tests)                           │
│    ├─ get_annual_crediting_rate()                          │
│    ├─ crediting_accrual()                                  │
│    ├─ annual_to_periodic() [monthly/quarterly/annual]      │
│    └─ error handling                                        │
│                                                              │
│ tests/test_lapse/test_lapse_rates.py (14 tests)            │
│ ├─ LapseRateTable (5 tests)                                │
│ ├─ LapseAssumptionRepository (4 tests)                     │
│ └─ LapseDecrementCalculator (5 tests)                      │
│                                                              │
│ tests/test_withdrawal/test_withdrawal_rates.py (38 tests)  │
│ ├─ SurrenderChargeSchedule (5 tests)                       │
│ ├─ SurrenderChargeRepository (8 tests)                     │
│ ├─ FreeWithdrawalConfig (2 tests)                          │
│ ├─ MvaConfig (7 tests)                                     │
│ ├─ PartialWithdrawalTable (4 tests)                        │
│ ├─ WithdrawalCalculator (9 tests)                          │
│ └─ WithdrawalAssumptions integration (3 tests)             │
│                                                              │
│ tests/test_mortality/test_decrements.py (12 tests)         │
│ ├─ Single life baseline (1 test)                           │
│ ├─ Joint life baseline (1 test)                            │
│ ├─ Lapse integration (3 tests)                             │
│ ├─ Withdrawal integration (4 tests)                        │
│ ├─ Crediting integration (3 tests)                         │
│ │  ├─ Single life with crediting                          │
│ │  ├─ Joint life with crediting                           │
│ │  └─ Combined (lapse + withdrawal + crediting)           │
│ └─ Withdrawal inactive flag (1 test)                       │
│                                                              │
│ Other tests (31 tests)                                      │
│ ├─ Model smoke tests                                       │
│ ├─ Standards stubs                                         │
│ ├─ Core stubs                                              │
│ └─ Reinsurance stubs                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 8. Example Execution Flow

```python
# 1. Create assumption set
assumption_set = AssumptionSet(
    stat_vm22=StatVm22Config(
        lapse_config=LapseConfig(
            base_annual_rate=0.01,
            shock_rates={3: 0.20, 5: 0.40, 7: 0.50}
        ),
        withdrawal=WithdrawalAssumptions(
            partial_withdrawal=PartialWithdrawalTable(
                base_annual_rate=0.05
            ),
            is_active=True
        ),
        creditor=CreditorConfig(
            fixed=FixedCreditingConfig(annual_rate=0.03),
            is_active=True
        )
    )
)

# 2. Create seriatim policy input
policy_input = SeriatimPolicyInput(
    policy_id="P001",
    issue_date=date(2021, 1, 1),
    lives=[SeriatimLifeInput(life_id="L1", issue_age=60, sex=Sex.MALE)],
    starting_policy_count=1000
)

# 3. Create mortality projection request
request = MortalityProjectionRequest(
    seriatim=policy_input,
    assumptions=AssumptionSelection(
        lapse_rate_table=assumption_set.stat_vm22.lapse_config,
        withdrawal_assumptions=assumption_set.stat_vm22.withdrawal,
        creditor_config=assumption_set.stat_vm22.creditor
    ),
    projection_periods=120,
    frequency=ProjectionFrequency.MONTHLY
)

# 4. Calculate mortality decrements
calculator = MortalityDecrementCalculator(
    MortalityAssumptionRepository.with_embedded_soa_iam_g2()
)
output = calculator.calculate(request)

# 5. Convert to DataFrame for analysis
df = output.to_frame()
# Columns: single_mortality_decrement, single_lapse_decrement,
#          single_withdrawal_decrement, single_crediting_accrual,
#          single_inforce_start, single_inforce_end, ...
```

