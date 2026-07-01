# FX Market Analytics

A data pipeline and Power BI dashboard for monitoring and analyzing foreign exchange (FX) rates across 5 major currencies. Rate data is fetched from the European Central Bank (ECB), stored in Supabase, and visualized in a 2-page interactive dashboard.

📊 [**View the live dashboard**](https://app.powerbi.com/view?r=eyJrIjoiNWY4OTM4ODQtYzE4ZS00ZDQ1LWE5ZjgtMTIyNTQ0Y2M0Zjc4IiwidCI6IjIyMzk4NzFkLTBmNmItNDQ4NS04ZjIzLTM1NmE0MzJlYzNmYiJ9)

---

## Overview

The pipeline fetches exchange rates for EUR, USD, GBP, JPY, and CNY at three granularities (daily, weekly, and monthly) and loads them into a Supabase (PostgreSQL) database using Python (requests, pandas, sqlalchemy). A GitHub Actions workflow runs the script automatically once per day, keeping the Power BI dashboard current with both a short-term and long-term analytical view of rate behavior. Although the pipeline fetches data for the monthly granularity going back to 1999-01-01 for all currencies, the calculations and long-term analytical view in the dashboard go back to 2000-01-01, since there are no monthly rates between 1999-01-01 and 1999-12-31 for CNY (in contrast to the other currencies) for the selected provider.

---

## Dashboard

Both pages are filtered by a global base currency slicer.

**Page 1 - Overview**

* Table with latest rates, latest return, latest returns %, 5-year high/low, and current up/down streak for all quote currencies for the selected base
* Line chart showing percentage change from the start of the selected (calendar) period:

  * 7 days, 1 month, 3 months, 6 months, 1 year → daily data
  * 5 years → downsampled weekly data
  * MAX → downsampled monthly data (back to 2000)

**Page 2 - Insights**

*Recent behavior · 90-trading day correlation | 30-trading day volatility · daily data*

* Correlation matrix across all quote currencies
* Rolling volatility (%) column chart

*Long-term structure · since 2000 · downsampled monthly data*

* All-time high drawdown (%) chart per quote currency
* Percentiles table per quote currency, highlighting their rank since 2000

---

## Data pipeline

### Source

[Frankfurter API](https://frankfurter.dev/) - free public API that requires no authentication, with source data provided by the European Central Bank.

### Supabase tables

All three tables share the same schema with `(date_recorded, base_currency, quote_currency)` as primary key:

| Column | Type | Description |
|---|---|---|
| `date_recorded` | `DATE` | Date of the rate |
| `base_currency` | `CHAR(3)` | Base currency (e.g. EUR) |
| `quote_currency` | `CHAR(3)` | Quote currency (e.g. USD) |
| `rate` | `DECIMAL(19,6)` | Exchange rate |
| `created_at` | `TIMESTAMP` | Row insert timestamp |

|Table|Granularity|Coverage|
|-|-|-|
|`currencies_daily_data`|Trading days|Last 5 years|
|`currencies_weekly_data`|Weekly|Last 5 years|
|`currencies_monthly_data`|Monthly|January 1999 → present (dashboard calculations from 2000; CNY from 2000)|

### Automation

The pipeline runs on a daily schedule via GitHub Actions (`.github/workflows/scheduler.yml`). Supabase connection credentials are stored as repository secrets.

---

## Project structure

```
fx_market_analytics/
├── .github/
│   └── workflows/
│       └── scheduler.yml
├── supabase/
│   └── roles_permissions_policies.sql
│   └── select_queries.sql
│   └── tables_creation.sql
├── .gitignore
├── fetch_currency_rates.py
├── requirements.txt
└── README.md
```

---

## Tech stack

* Python - data fetching and pipeline
* Frankfurter API - exchange rate data
* Supabase (PostgreSQL) - data storage
* GitHub Actions - scheduled automation
* Power BI - dashboard and visualization

---
*Built by [Georgios Sagris](https://www.linkedin.com/in/georgesagris/)*

