# AKIRA Architecture - Visual Diagrams

## System Architecture Overview

```mermaid
graph TB
    subgraph Input["📥 INPUT LAYER"]
        AS["AssumptionSet<br/>(Master Config)"]
        SC["SeriatimPolicyInput<br/>(Policy Data)"]
    end
    
    subgraph Config["⚙️ CONFIGURATION COMPONENTS"]
        LAP["LapseConfig<br/>base_rate: 0.01<br/>shocks: {3:0.20...}"]
        WD["WithdrawalAssumptions<br/>free_pct: 0.10<br/>partial_rate: 0.05"]
        CR["CreditorConfig<br/>strategy: fixed<br/>rate: 0.03"]
    end
    
    subgraph Repos["📦 REPOSITORIES"]
        MRT["MortalityAssumption<br/>Repository<br/>SOA Tables"]
        LRT["LapseRateTable<br/>Repository"]
        WRT["SurrenderCharge<br/>Repository<br/>Athene Schedules"]
    end
    
    subgraph Calcs["🧮 CALCULATORS"]
        MRC["MortalityDecrement<br/>Calculator"]
        LRC["LapseDecrement<br/>Calculator"]
        WRC["WithdrawalCalculator"]
        CRC["CreditorCalculator"]
    end
    
    subgraph Output["📊 OUTPUT"]
        MRO["MortalityProjection<br/>Output"]
        DF["pandas DataFrame<br/>(Analysis Ready)"]
    end
    
    AS --> LAP & WD & CR
    SC --> MRC
    LAP --> LRC
    WD --> WRC
    CR --> CRC
    
    MRT --> MRC
    LRT --> LRC
    WRT --> WRC
    
    MRC --> MRO
    LRC --> MRO
    WRC --> MRO
    CRC --> MRO
    
    MRO --> DF
    
    style Input fill:#e1f5ff
    style Config fill:#f3e5f5
    style Repos fill:#fce4ec
    style Calcs fill:#fff3e0
    style Output fill:#e8f5e9
```

## Mortality Calculation Flow (Per Period)

```mermaid
graph LR
    subgraph Period["📍 Period N"]
        START["inforce_start<br/>= 1,000"]
    end
    
    subgraph Mort["💀 Mortality"]
        M["Get rates from<br/>MortalityRepository<br/>qx = 0.005"]
        M1["mortality_decrement<br/>= 1,000 × 0.005<br/>= 5"]
    end
    
    subgraph Lapse["📉 Lapse"]
        L["Get rate from<br/>LapseRateTable<br/>year 3 shock = 0.20"]
        L1["lapse_decrement<br/>= 1,000 × 0.20<br/>= 200"]
    end
    
    subgraph Withdraw["💳 Withdrawal"]
        W["Get rate from<br/>PartialWithdrawalTable<br/>base = 0.05"]
        W1["withdrawal_decrement<br/>= 1,000 × 0.05<br/>= 50"]
    end
    
    subgraph Credit["💰 Crediting"]
        C["Get rate from<br/>CreditorConfig<br/>fixed = 0.03"]
        C1["crediting_accrual<br/>= 1,000 × 0.03<br/>= +30"]
    end
    
    subgraph Calc["➗ Net Calculation"]
        E["inforce_end = max(<br/>1,000 - 5 - 200 - 50 + 30<br/>, 0)<br/>= 775"]
    end
    
    subgraph Output["📝 Row Output"]
        ROW["MortalityProjectionRow<br/>├─ mortality_decrement: 5<br/>├─ lapse_decrement: 200<br/>├─ withdrawal_decrement: 50<br/>├─ crediting_accrual: 30<br/>└─ inforce_end: 775"]
    end
    
    START --> M --> M1
    M1 --> L --> L1
    L1 --> W --> W1
    W1 --> C --> C1
    C1 --> E --> ROW
    
    style Period fill:#e3f2fd
    style Mort fill:#ffebee
    style Lapse fill:#fff3e0
    style Withdraw fill:#f3e5f5
    style Credit fill:#e8f5e9
    style Calc fill:#fce4ec
    style Output fill:#f1f8e9
```

## Class Relationships

```mermaid
classDiagram
    class AssumptionSet {
        +assumption_set_id: str
        +stat_carvm: StatCarvmConfig
        +stat_vm22: StatVm22Config
        +ldti: LdtiConfig
        +fas157: Fas157Config
        +ebs: EbsConfig
        +bel: BelConfig
    }
    
    class FrameworkConfig {
        +lapse_config: LapseConfig
        +withdrawal: WithdrawalAssumptions
        +creditor: CreditorConfig
    }
    
    class StatCarvmConfig {
        +carvm_basis: StatCarvmBasis
        +reinvestment_rate: StatReinvestmentRate
    }
    
    class LapseConfig {
        +base_annual_rate: float
        +shock_rates: dict[int, float]
        +is_active: bool
    }
    
    class WithdrawalAssumptions {
        +free_withdrawal: FreeWithdrawalConfig
        +partial_withdrawal: PartialWithdrawalTable
        +mva: MvaConfig
        +surrender_schedule_id: str
        +is_active: bool
    }
    
    class CreditorConfig {
        +strategy: str
        +fixed: FixedCreditingConfig
        +is_active: bool
    }
    
    class FixedCreditingConfig {
        +annual_rate: float
    }
    
    class MortalityProjectionRequest {
        +seriatim: SeriatimPolicyInput
        +assumptions: AssumptionSelection
        +projection_periods: int
        +frequency: ProjectionFrequency
    }
    
    class AssumptionSelection {
        +lapse_rate_table: LapseRateTable?
        +withdrawal_assumptions: WithdrawalAssumptions?
        +creditor_config: CreditorConfig?
    }
    
    class MortalityProjectionRow {
        +period: int
        +single_mortality_decrement: float
        +single_lapse_decrement: float
        +single_withdrawal_decrement: float
        +single_crediting_accrual: float
        +single_inforce_start: float
        +single_inforce_end: float
    }
    
    class MortalityProjectionOutput {
        +records: list[MortalityProjectionRow]
        +to_frame() DataFrame
    }
    
    AssumptionSet "1" *-- "6" FrameworkConfig
    FrameworkConfig <|-- StatCarvmConfig
    StatCarvmConfig "1" *-- "1" LapseConfig
    StatCarvmConfig "1" *-- "1" WithdrawalAssumptions
    StatCarvmConfig "1" *-- "1" CreditorConfig
    
    WithdrawalAssumptions "1" *-- "1" FreeWithdrawalConfig
    WithdrawalAssumptions "1" *-- "1" PartialWithdrawalTable
    WithdrawalAssumptions "1" *-- "1" MvaConfig
    
    CreditorConfig "1" *-- "1" FixedCreditingConfig
    
    MortalityProjectionRequest "1" *-- "1" SeriatimPolicyInput
    MortalityProjectionRequest "1" *-- "1" AssumptionSelection
    
    AssumptionSelection "1" *-- "0..1" LapseConfig
    AssumptionSelection "1" *-- "0..1" WithdrawalAssumptions
    AssumptionSelection "1" *-- "0..1" CreditorConfig
    
    MortalityProjectionOutput "1" *-- "*" MortalityProjectionRow
```

## Module Dependencies

```mermaid
graph TD
    A["assumptions/"] --> B["sets.py<br/>LapseConfig<br/>WithdrawalAssumptions<br/>CreditorConfig"]
    A --> C["enums.py<br/>LapseModel<br/>MortalityTable"]
    
    M["mortality/"] --> D["decrements.py<br/>MortalityDecrementCalculator<br/>MortalityProjectionRow"]
    
    L["lapse/"] --> E["rates.py<br/>LapseRateTable"]
    L --> F["calculator.py<br/>LapseDecrementCalculator"]
    
    W["withdrawal/"] --> G["rates.py<br/>SurrenderChargeSchedule<br/>FreeWithdrawalConfig<br/>MvaConfig<br/>PartialWithdrawalTable"]
    W --> H["calculator.py<br/>WithdrawalCalculator"]
    
    CR["crediting/"] --> I["calculator.py<br/>CreditorCalculator"]
    
    B --> D
    E --> F
    G --> H
    
    F --> D
    H --> D
    I --> D
    
    C --> D
    C --> E
    C --> G
    
    D --> O["Output:<br/>MortalityProjectionOutput"]
    O --> DF["DataFrame<br/>for Analysis"]
    
    style A fill:#f5f5f5
    style M fill:#fff3e0
    style L fill:#f3e5f5
    style W fill:#e3f2fd
    style CR fill:#e8f5e9
    style O fill:#f1f8e9
    style DF fill:#c8e6c9
```

## Data Types Flow

```mermaid
graph LR
    subgraph In["Inputs"]
        AS["AssumptionSet"]
        PI["SeriatimPolicyInput"]
    end
    
    subgraph Req["Request"]
        MPR["MortalityProjection<br/>Request"]
    end
    
    subgraph Proc["Processing"]
        MRL["Row List"]
    end
    
    subgraph Out["Output"]
        MPO["MortalityProjection<br/>Output"]
        DF["DataFrame"]
    end
    
    AS --> MPR
    PI --> MPR
    MPR -->|calculate| Proc
    Proc -->|append 120 rows| MPO
    MPO -->|to_frame| DF
    
    style In fill:#e1f5ff
    style Req fill:#fff3e0
    style Proc fill:#f3e5f5
    style Out fill:#c8e6c9
```

## State Machine: Single Life Projection

```mermaid
stateDiagram-v2
    [*] --> Period1: Start with 1000<br/>inforce
    
    Period1 --> Mortality1: Get mortality rate
    Mortality1 --> Lapse1: Subtract mortality
    Lapse1 --> Withdrawal1: Subtract lapse
    Withdrawal1 --> Crediting1: Subtract withdrawal
    Crediting1 --> EndPeriod1: Add crediting
    EndPeriod1 --> Period2: 775 inforce
    
    Period2 --> Mortality2: Get mortality rate
    Mortality2 --> Lapse2: Subtract mortality
    Lapse2 --> Withdrawal2: Subtract lapse
    Withdrawal2 --> Crediting2: Subtract withdrawal
    Crediting2 --> EndPeriod2: Add crediting
    EndPeriod2 --> Period3: ~580 inforce
    
    Period3 --> MorePeriods: Continue...
    MorePeriods --> Final: Period 120
    Final --> [*]: Output DataFrame<br/>with 120 rows

```

## Test Coverage Pyramid

```mermaid
graph TB
    subgraph E2E["🏆 Integration Tests<br/>test_mortality/test_decrements.py<br/>12 tests"]
        E1["Single & Joint Life"]
        E2["With All Decrements"]
        E3["With Crediting"]
        E4["Combined Scenario"]
    end
    
    subgraph Unit["🔧 Unit Tests<br/>68 tests"]
        U1["test_crediting/ (16)"]
        U2["test_lapse/ (14)"]
        U3["test_withdrawal/ (38)"]
    end
    
    subgraph Smoke["💨 Smoke Tests<br/>31 tests"]
        S1["Model instantiation"]
        S2["Framework stubs"]
        S3["Enum validation"]
    end
    
    E2E --> Unit
    Unit --> Smoke
    
    style E2E fill:#c8e6c9
    style Unit fill:#fff9c4
    style Smoke fill:#ffccbc
```
