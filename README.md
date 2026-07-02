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
│   ├── roles_permissions_policies.sql
│   ├── select_queries.sql
│   └── tables_creation.sql
├── data_model/
│   └── PBI_model_view.png
├── .gitignore
├── fetch_currency_rates.py
├── requirements.txt
└── README.md
```

## Key DAX Measures

To power the financial insights on the dashboard, several complex DAX measures were created to handle rolling windows, statistical relationships, and historical performance tracking. Some of them include:

**1. 90-Day Rolling Correlation Coefficient**
Calculates the Pearson correlation coefficient dynamically between any two currency pairs over a 90-trading-day window, handling cross-filter context and row alignment within a matrix visual.

```dax
Correlation Coefficient = 
    VAR _BaseCurrency = SELECTEDVALUE('DimBaseCurrencies'[base_currency])
    VAR _CurrencyX = SELECTEDVALUE('QuoteCurrenciesMatrixX'[quote_currency])
    VAR _CurrencyY = SELECTEDVALUE('QuoteCurrenciesMatrixY'[quote_currency])
    VAR _ValidX = _CurrencyX <> _BaseCurrency
    VAR _ValidY = _CurrencyY <> _BaseCurrency 
    VAR _StartIndex = MAX('Currencies Daily Data'[Date Index]) - 90
    VAR _StartDate = 
        CALCULATE(
            MAX('Currencies Daily Data'[Date]),
            'Currencies Daily Data'[Date Index] = _StartIndex + 1
        )
    VAR _BaseTableX =
        CALCULATETABLE(
                SUMMARIZE(
                    'Currencies Daily Data',
                    'Currencies Daily Data'[Date],
                    "Rate", MAX('Currencies Daily Data'[Rate])
                ),
                TREATAS({_CurrencyX}, 'Currencies Daily Data'[Quote]),
                'Currencies Daily Data'[Quote] <> _BaseCurrency,
                'Currencies Daily Data'[Date] >= _StartDate
        )
    VAR _AlignedX =
        SELECTCOLUMNS(
            ADDCOLUMNS(
                _BaseTableX,
                "X",
                    VAR _CurrentRate = [Rate]
                    VAR _PreviousRate =
                        MAXX(
                            OFFSET(
                                   -1, 
                                   _BaseTableX, 
                                   ORDERBY('Currencies Daily Data'[Date])
                            ),
                            [Rate]
                        )
                RETURN 
                    DIVIDE(_CurrentRate - _PreviousRate, _PreviousRate)
            ),
            "date_recorded", 'Currencies Daily Data'[Date],
            "X", [X]
        )
    VAR _BaseTableY =
        CALCULATETABLE(
                SUMMARIZE(
                    'Currencies Daily Data',
                    'Currencies Daily Data'[Date],
                    "Rate", MAX('Currencies Daily Data'[Rate])
                ),
                TREATAS({_CurrencyY}, 'Currencies Daily Data'[Quote]),
                'Currencies Daily Data'[Quote] <> _BaseCurrency,
                'Currencies Daily Data'[Date] >= _StartDate
        )
    VAR _AlignedY =
        SELECTCOLUMNS(
            ADDCOLUMNS(
                _BaseTableY,
                "Y",
                    VAR _CurrentRate = [Rate]
                    VAR _PreviousRate =
                        MAXX(
                            OFFSET(
                                   -1, 
                                   _BaseTableY, 
                                   ORDERBY('Currencies Daily Data'[Date])
                            ),
                            [Rate]
                        )
                RETURN 
                    DIVIDE(_CurrentRate - _PreviousRate, _PreviousRate)
            ),
            "date_recorded", 'Currencies Daily Data'[Date],
            "Y", [Y]
        )
    VAR _Combined =
        NATURALINNERJOIN(
            _AlignedX,
            _AlignedY
        )
    
    VAR n = COUNTROWS(_Combined)
    VAR _SumX = SUMX(_Combined, [X])
    VAR _SumY = SUMX(_Combined, [Y])
    VAR _SumXY = SUMX(_Combined, [X] * [Y])
    VAR _SumX2 = SUMX(_Combined, [X] * [X])
    VAR _SumY2 = SUMX(_Combined, [Y] * [Y])

    VAR _CorrelationCoefficient =
        DIVIDE(
            n * _SumXY - _SumX * _SumY,
            SQRT(
                (n * _SumX2 - _SumX * _SumX) *
                (n * _SumY2 - _SumY * _SumY)
            )
        )
RETURN
    SWITCH(
        TRUE(),
        NOT _ValidX || NOT _ValidY, BLANK(),
        _CurrencyX = _CurrencyY, 1,
        ROUND(_CorrelationCoefficient, 2)
    )
```

**2. All-Time High for Drawdown Calculation**
Manipulates the filter context to isolate the historical maximum exchange rate up to the current date in the visual context (starting from 2000), serving as the baseline for calculating drawdowns (Used in the tooltip section of the visual).

```dax
Drawdown Chart Tooltip Max Rate = 
    VAR _CurrentDate = SELECTEDVALUE('Currencies Monthly Data'[Date])
    VAR _CurrentBase = SELECTEDVALUE('Currencies Monthly Data'[Base])
    VAR _CurrentQuote = SELECTEDVALUE('Currencies Monthly Data'[Quote])
    VAR _Result = 
        CALCULATE(
            MAX('QueryMonthly'[rate]),
            FILTER(
                ALL('QueryMonthly'),
                'QueryMonthly'[date_recorded] >= DATE(2000,1,1) &&
                'QueryMonthly'[date_recorded] <= _CurrentDate &&
                'QueryMonthly'[base_currency] = _CurrentBase &&
                'QueryMonthly'[quote_currency] = _CurrentQuote
            )
        )
RETURN
    _Result
```

**3. Current Up/Down Streak**
Bypasses DAX's lack of native recursion by evaluating consecutive days of positive, negative, or flat returns using dynamic date filtering and table row counting.

```dax
_LatestReturns = 
    VAR _PreviousDate =
        CALCULATE(
            MAX('Currencies Daily Data'[Date]),
            'Currencies Daily Data'[Date] < MAX('Currencies Daily Data'[Date])
        )
    VAR _PreviousRates =
        CALCULATE(
            MAX('Currencies Daily Data'[Rate]),
            'Currencies Daily Data'[Date] = _PreviousDate
        )
    VAR _LatestReturns = [_LatestRates] - _PreviousRates
RETURN
    _LatestReturns

Current Up/Down Streak = 
    VAR _MaxDateNoChanges = 
        CALCULATE(
            MAX('Currencies Daily Data'[Date]),
            'Currencies Daily Data'[Daily Return] <> 0
        )
    VAR _MaxDatenegativeOrZeroReturn = 
        CALCULATE(
            MAX('Currencies Daily Data'[Date]),
            'Currencies Daily Data'[Daily Return] <= 0
        )
    VAR _MaxDatePositiveOrZeroReturn = 
        CALCULATE(
            MAX('Currencies Daily Data'[Date]),
            'Currencies Daily Data'[Daily Return] >= 0
        )
    VAR _Result =
        SWITCH(
            TRUE(),
            [_LatestReturns] > 0, 
            COUNTROWS(
                FILTER(
                    'Currencies Daily Data',
                    'Currencies Daily Data'[Date] > _MaxDatenegativeOrZeroReturn
                )
            ),
            [_LatestReturns] < 0, 
            COUNTROWS(
                FILTER(
                    'Currencies Daily Data',
                    'Currencies Daily Data'[Date] > _MaxDatePositiveOrZeroReturn
                )
            ), 
            COUNTROWS(
                FILTER(
                    'Currencies Daily Data',
                    'Currencies Daily Data'[Date] > _MaxDateNoChanges
                )
            )
        )
RETURN
    SWITCH(
        TRUE(),
        [_LatestReturns] > 0, 
        IF(_Result = 1, _Result & " Day Up Streak", _Result & " Days Up Streak"),
        [_LatestReturns] < 0, 
        IF(_Result = 1, _Result & " Day Down Streak", _Result & " Days Down Streak"),
        IF(_Result = 1, _Result & " Day Of No Up/Down Changes", _Result & " Days Of No Up/Down Changes")
    )
```

**4. 30-Day Rolling Volatility (%)**
Leverages custom date index calculations to extract the standard deviation of daily returns strictly over the last 30 trading days.

```dax
30d_volatility = 
    VAR _StartIndex = MAX('Currencies Daily Data'[Date Index]) - 30
    VAR _StartDate = 
        CALCULATE(
            MAX('Currencies Daily Data'[Date]),
            'Currencies Daily Data'[Date Index] = _StartIndex + 1
        )
    VAR _30dVolatility = 
        CALCULATE(
            STDEV.S('Currencies Daily Data'[Daily Return Percentage]),
            DATESINPERIOD(
            'Currencies Daily Data'[Date],
            _StartDate, 
            6, 
            MONTH
        )
    )
    VAR _30dVolatilityPercentage = _30dVolatility

RETURN
    _30dVolatilityPercentage
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

