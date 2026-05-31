-- DimDates
SELECT *
FROM (
	SELECT date_recorded  
	FROM currencies_daily_data
	UNION
	SELECT date_recorded
	FROM currencies_monthly_data
	UNION
	SELECT date_recorded
	FROM currencies_weekly_data
)
ORDER BY date_recorded;

-- DimBaseCurrencies
SELECT DISTINCT base_currency
FROM currencies_daily_data
ORDER BY base_currency;

-- DimQuoteCurrencies
SELECT DISTINCT 
	   quote_currency,
	   CASE 
	   	WHEN quote_currency = 'CNY'
	   	  THEN 'https://hatscripts.github.io/circle-flags/flags/cn.svg'
	   	WHEN quote_currency = 'EUR'
	   	  THEN 'https://hatscripts.github.io/circle-flags/flags/eu.svg'
	   	WHEN quote_currency = 'GBP'
	   	  THEN 'https://hatscripts.github.io/circle-flags/flags/gb.svg'
	   	WHEN quote_currency = 'JPY'
	   	  THEN 'https://hatscripts.github.io/circle-flags/flags/jp.svg'
	   	ELSE 'https://hatscripts.github.io/circle-flags/flags/us.svg'
	   END AS quote_flag_url
FROM currencies_daily_data
ORDER BY quote_currency;

-- Currencies Daily Data
SELECT *
FROM currencies_daily_data
ORDER BY date_recorded, base_currency, quote_currency;

-- Currencies Weekly Data
SELECT *
FROM currencies_weekly_data
ORDER BY date_recorded, base_currency, quote_currency;

-- Currencies Monthly Data
SELECT *
FROM currencies_monthly_data
ORDER BY date_recorded, base_currency, quote_currency;