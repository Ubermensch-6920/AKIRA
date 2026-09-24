# AKIRA Architecture - Visual Diagrams

## Basis demarcation

```mermaid
graph TB
    subgraph Inputs["📥 Inputs"]
        POL["MygaPolicyState[]"]
        AS["AssumptionSet<br/>stat · us_gaap · ldti · ebs · reinsurance"]
        CRV["CurvePoint[]"]
        TRT["ReinsuranceTreaty[]"]
    end

    subgraph Engine["⚙️ engine/ (gaspatchio)"]
        MP["model_points<br/>1 row / policy"]
        MYGA["projections/myga.py<br/>ActuarialFrame model"]
        PROJ["Projection<br/>list[f64] per cash-flow line"]
        RE["reinsurance.application<br/>gross → ceded / net"]
    end

    subgraph STAT["🇺🇸 STAT — bases/stat"]
        CARVM["CARVM<br/>greatest PV (guaranteed)"]
        VM22["VM-22<br/>DR + CTE SR"]
        RBC["NAIC RBC<br/>STAT reserves only"]
    end
    subgraph GAAP["📘 US GAAP — bases/us_gaap"]
        FV["ASC 820 fair value"]
    end
    subgraph LDTI["📗 LDTI — bases/ldti"]
        LFPB["LFPB (NPR)"]
        DAC["DAC (asset, supplementary)"]
    end
    subgraph EBS["🇧🇲 EBS — bases/ebs"]
        BEL["BEL @ risk-free"]
        TP["Technical provisions<br/>BEL @ rf+IP + risk margin"]
    end

    AGG["engine/aggregation<br/>(basis, framework) × cohort / segment / entity"]
    STORE["DuckDB<br/>runs · results · policy_results"]

    POL --> MP --> MYGA --> PROJ --> RE
    AS -- "per-basis block" --> MYGA
    TRT --> RE
    POL --> CARVM
    RE --> VM22 & FV & LFPB & BEL & TP
    CRV --> VM22 & FV & LFPB & BEL & TP
    CARVM & VM22 --> RBC
    CARVM & VM22 & FV & LFPB & BEL & TP --> AGG --> STORE
    DAC -. "reported, not aggregated" .-> STORE
    RBC --> STORE
```

## Projection per assumption block

Each framework config inherits `ProjectionBasisConfig`. The valuation context
hashes the projection fields (mortality, lapse, withdrawal, crediting) and runs
gaspatchio once per distinct block.

```mermaid
graph LR
    V["stat.vm22"] --> H{"hash of<br/>projection fields"}
    F["us_gaap.fas157"] --> H
    L["ldti"] --> H
    B["ebs.bel"] --> H
    T["ebs.technical_provisions"] --> H
    H -- "distinct block" --> G["gaspatchio run"]
    H -- "seen before" --> C["cached Projection"]
```

## MYGA gaspatchio model (per period t, all policies at once)

```mermaid
graph LR
    T["t, duration_months,<br/>policy_year, attained_age"] --> M["monthly_qx<br/>IAM × G2 × flat MI"]
    T --> L["monthly_lapse_rate<br/>base + shock years"]
    T --> W["withdrawal_rate<br/>free % × incidence"]
    W --> AV["av_bop → av_mid (+i)<br/>→ av_eop (−w)"]
    M --> IF["in_force_bop<br/>survival.cum_prod().previous_period()"]
    L --> IF
    IF --> CF["death · surrender · charge ·<br/>withdrawals · maturity · AV_eop"]
    AV --> CF
    T --> SC["surrender_charge_rate<br/>Table(schedule, policy_year)"] --> CF
```

## Result record

```mermaid
classDiagram
    class ResultMetadata {
        valuation_date
        framework: Framework
        basis: Basis  (derived)
        methodology_version
        run_id
        assumption_set_id
    }
    class ReserveResult {
        legal_entity / segment / cohort_id
        gross_reserve / ceded_reserve / net_reserve
        components
    }
    class MeasureResult {
        reserve_result: ReserveResult
        policy_detail: polars frame
        supplementary: bool
    }
    class BasisResult {
        basis: Basis
        measures: MeasureResult[]
        capital: CapitalResult[]
    }
    ReserveResult --> ResultMetadata
    MeasureResult --> ReserveResult
    BasisResult --> MeasureResult
```
