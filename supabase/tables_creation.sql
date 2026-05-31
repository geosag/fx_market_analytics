CREATE TABLE IF NOT EXISTS currencies_daily_data (
    date_recorded   DATE              NOT NULL,
    base_currency   CHAR(3)           NOT NULL,
    quote_currency  CHAR(3)           NOT NULL,
    rate            DECIMAL(19, 6)    NOT NULL,
    created_at      TIMESTAMP         NOT NULL,
    
    PRIMARY KEY(date_recorded, base_currency, quote_currency)
);

CREATE TABLE IF NOT EXISTS currencies_weekly_data (
    date_recorded   DATE              NOT NULL,
    base_currency   CHAR(3)           NOT NULL,
    quote_currency  CHAR(3)           NOT NULL,
    rate            DECIMAL(19, 6)    NOT NULL,
    created_at      TIMESTAMP         NOT NULL,
    
    PRIMARY KEY(date_recorded, base_currency, quote_currency)
);

CREATE TABLE IF NOT EXISTS currencies_monthly_data (
    date_recorded   DATE              NOT NULL,
    base_currency   CHAR(3)           NOT NULL,
    quote_currency  CHAR(3)           NOT NULL,
    rate            DECIMAL(19, 6)    NOT NULL,
    created_at      TIMESTAMP         NOT NULL,
    
    PRIMARY KEY(date_recorded, base_currency, quote_currency)
);