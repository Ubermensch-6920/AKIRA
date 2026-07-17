# Input Data Schemas

Phase 1 scaffold. Field lists below mirror the Pydantic models in
`src/actuarial_model/models/`. Lines marked **ASSUMPTION REQUIRED** are
placeholders pending the product spec.

## Seriatim — `PolicyStateBase` (common)

| Field            | Type                       | Notes                              |
|------------------|----------------------------|------------------------------------|
| `policy_id`      | `str`                      | Primary key                        |
| `product_type`   | `ProductType`              | MYGA / FIA / SPIA / PRT / VA / ULSG |
| `issue_date`     | `date`                     |                                    |
| `issue_age`      | `int`                      |                                    |
| `sex`            | `Literal["M","F","U"]`     |                                    |
| `issue_state`    | `str`                      | 2-letter US state code             |
| `legal_entity`   | `str`                      | Aggregation key                    |
| `segment`        | `str`                      | Aggregation key                    |
| `cohort_id`      | `str`                      | LDTI cohort grouping               |
| `valuation_date` | `date`                     |                                    |

## Seriatim — `MygaPolicyState` (Phase 1)

In addition to the base fields:

| Field                          | Type      | Notes                          |
|--------------------------------|-----------|--------------------------------|
| `single_premium`               | `float`   |                                |
| `account_value`                | `float`   |                                |
| `guaranteed_rate`              | `float`   | Annual, decimal                |
| `guarantee_period_years`       | `int`     |                                |
| `guarantee_end_date`           | `date`    |                                |
| `surrender_charge_schedule_id` | `str`     | FK to surrender-charge tables  |
| `has_mva`                      | `bool`    | Market value adjustment flag   |
| `death_benefit_basis`          | `str`     | `ROAV` / `ROP` / `OTHER` — Athene MYG & MaxRate pay full AV (`ROAV`) |
| `free_withdrawal_basis`        | `str`     | `PCT_AV` (MYG: 10% of AV, doc 76009) / `INTEREST_EARNED` (MaxRate: strategy rate × AV, doc 76047) |
| `free_withdrawal_pct`          | `float`   | Annual, decimal (default 10%); ignored under `INTEREST_EARNED` |
| `mgsv_premium_pct`             | `float`   | Nonforfeiture: MGSV premium percentage (default 87.5%) |
| `nonforfeiture_rate`           | `float`   | MGSV accumulation rate — set from the contract (SNFL corridor 1%–3%) |
| `reinsurance_treaty_id`        | `str?`    | FK to `ReinsuranceTreaty`      |

Field list aligned with the Athene product documents backing the embedded
surrender schedules (MYG — doc 76009; MaxRate — doc 76047).

## Asset — `AssetRecord`

| Field                | Type                                  | Notes                          |
|----------------------|---------------------------------------|--------------------------------|
| `asset_id`           | `str`                                 | Primary key                    |
| `cusip`              | `str?`                                |                                |
| `issuer`             | `str`                                 |                                |
| `sector`             | `str`                                 |                                |
| `asset_type`         | `str`                                 | BOND / MORTGAGE / STRUCTURED / EQUITY / CASH |
| `coupon_rate`        | `float?`                              |                                |
| `maturity_date`      | `date?`                               |                                |
| `par_amount`         | `float`                               |                                |
| `book_value`         | `float`                               |                                |
| `amortized_cost`     | `float`                               |                                |
| `market_value`       | `float`                               |                                |
| `fair_value_level`   | `Literal["LEVEL_1","LEVEL_2","LEVEL_3"]` | ASC 820                     |
| `unrealized_gl`      | `float`                               |                                |
| `oas_spread`         | `float?`                              | bps                            |
| `credit_rating`      | `str`                                 | S&P style                      |
| `naic_designation`   | `int`                                 | 1–6                            |
| `modified_duration`  | `float?`                              |                                |
| `convexity`          | `float?`                              |                                |
| `spread_duration`    | `float?`                              |                                |
| `gaap_classification`| `Literal["HTM","AFS","TRADING"]`      |                                |
| `admitted_flag`      | `bool`                                | STAT admittance                |
| `bma_asset_class`    | `str?`                                |                                |
| `market_value_ebs`   | `float?`                              | Post-BMA haircut               |

## Reinsurance — `ReinsuranceTreaty`

| Field                       | Type                       | Notes                              |
|-----------------------------|----------------------------|------------------------------------|
| `treaty_id`                 | `str`                      | Primary key                        |
| `treaty_name`               | `str`                      |                                    |
| `counterparty`              | `str`                      |                                    |
| `counterparty_rating`       | `str`                      |                                    |
| `auth_status`               | `ReinsurerAuthStatus`      |                                    |
| `treaty_type`               | `ReinsuranceTreatyType`    | Phase 1: `QUOTA_SHARE` only        |
| `effective_date`            | `date`                     |                                    |
| `termination_date`          | `date?`                    |                                    |
| `quota_share_pct`           | `float?`                   | Phase 1                            |
| `coinsurance_pct`           | `float?`                   | Phase 2                            |
| `modco_interest_rate`       | `float?`                   | Phase 2                            |
| `funds_withheld_rate`       | `float?`                   | Phase 2                            |
| `xl_attachment` / `xl_limit`| `float?`                   | Phase 2                            |
| `yrt_premium_scale`         | `str?`                     | Phase 2                            |
| `ceding_commission_pct`     | `float?`                   |                                    |
| `expense_allowance_pct`     | `float?`                   |                                    |
| `experience_refund_pct`     | `float?`                   |                                    |
| `collateral_type`           | `CollateralType`           |                                    |
| `collateral_amount`         | `float?`                   |                                    |
| `risk_transfer_method`      | `RiskTransferMethod`       |                                    |
| `qualifies_for_credit_stat` | `bool`                     |                                    |
| `qualifies_for_credit_gaap` | `bool`                     |                                    |
| `bma_haircut_pct`           | `float?`                   |                                    |
