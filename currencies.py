#----------------------------------------
import requests
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import pandas as pd
from sqlalchemy import create_engine, text, bindparam, Text
import time
import logging
import json
import os
import sys
from dotenv import find_dotenv, load_dotenv
#----------------------------------------
########## GLOBAL VARIABLES #############
#----------------------------------------
items_list = None
data_type = 'daily' # start with the data from the last 5 years
#---get_data variables---------------
headers = {"Accept": "application/x-ndjson"}
base_url = 'https://api.frankfurter.dev/v2/rates?providers=ECB'
valid_currencies = ['EUR','USD','GBP','CNY','JPY']
#---change key names-----------------
mapping = {
            'date': 'date_recorded',
            'base': 'base_currency',
            'quote': 'quote_currency',
            'rate': 'rate',
            'created_at': 'created_at'
          }
#---starting delay seconds in case of 429 HTTP response status code, in case a "Retry-After" header is not provided
delay = 2
#----------------------------------------
############## FUNCTIONS ################
#----------------------------------------
# test connection with database
#----------------------------------------
def check_connection():
    for i in range(1, 4):
        try:
            with engine.connect():
                return True
        except Exception:
            logging.exception(f"Database test connection attempt {i} failed!")
            time.sleep(5)
    return False
#----------------------------------------
# query database
#----------------------------------------
def query_db(query, parameters, connection):
    return connection.execute(query, parameters)
#----------------------------------------
# clean data with pandas
#----------------------------------------
def clean_data(df_raw, base_currency, quote_currencies_list):
    df_raw['date_recorded'] = pd.to_datetime(df_raw['date_recorded'], errors='coerce').dt.date # date cleanup
    df_raw['base_currency'] = df_raw['base_currency'].str.strip().str.upper().str[:3] # base currency cleanup
    df_raw['quote_currency'] = df_raw['quote_currency'].str.strip().str.upper().str[:3] # quote currency cleanup
    df_raw['rate'] = pd.to_numeric(df_raw['rate'], errors='coerce').round(6) # rate currency cleanup
    
    df_raw = df_raw.drop_duplicates(subset=['date_recorded', 'base_currency', 'quote_currency']) # remove duplicates
    
    # helper list for base currency to use .isin() method below - quote_currencies_list is already returned from return_fetching_dates function
    base_currency_list = []
    base_currency_list.append(base_currency)
    
    if (df_raw['date_recorded'].notna().all() and
        df_raw['base_currency'].isin(base_currency_list).all() and
        df_raw['quote_currency'].isin(quote_currencies_list).all() and
        (df_raw['rate'] > 0).all()):
        df_clean = df_raw
        return df_clean
    else:
        raise Exception(f"Invalid data: {df_raw}")
#----------------------------------------
# Define and return which dates are to be requested
#----------------------------------------
def return_fetching_dates(base_currency, starting_date, connection, table, time_interval):
    logging.info('Defining fetching dates...')
    quote_currencies_list = []
    for i in range(len(valid_currencies)):
        if not valid_currencies[i] == base_currency:
            quote_currencies_list.append(valid_currencies[i]) # quote currencies are all the other values left in the list besides currnt base currency
    result = query_db(text(f"""
                               SELECT MIN(date_recorded) AS date_min,
                                      MAX(date_recorded) AS date_max
                                 FROM (
                                       SELECT x.*, SUM(i) OVER(ORDER BY date_recorded) AS grp
                                         FROM (
                                               SELECT t.*,
                                                      CASE WHEN date_recorded > LAG(date_recorded) OVER(order BY date_recorded) + INTERVAL :time_interval
                                                           THEN 1 
                                                           ELSE 0 
                                                       END AS i
                                                 FROM (
                                                       SELECT DATE(dates_recorded) AS date_recorded
                                                         FROM generate_series(:starting_date, CURRENT_DATE, INTERVAL :time_interval) AS dates_recorded
                                                        WHERE dates_recorded NOT IN (
                                                                                     SELECT date_recorded
                                                                                       FROM {table}
                                                                                      WHERE base_currency = :base_currency
                                                                                        AND quote_currency IN :quote_currencies_list
                                                                                   GROUP BY date_recorded
                                                                                     HAVING COUNT(*) = 4)) AS t
                                                                                    ) AS x
                                                      ) AS y
                             GROUP BY grp
                             ORDER BY date_min;
                            """).bindparams(bindparam('quote_currencies_list', expanding = True)),
                      {"starting_date": starting_date, "time_interval": time_interval, "base_currency": base_currency, "quote_currencies_list": quote_currencies_list}, connection)
    rows = result.fetchall()
    fetching_dates = []
    if len(rows) > 0:
        for row in rows:
            if row[0] and row[1]:
                retrieved_date_min = row[0]
                retrieved_date_max = row[1]
                dates = {
                         'date_min': retrieved_date_min,
                         'date_max': retrieved_date_max
                        }
                fetching_dates.append(dates)
            else:
                raise Exception(f'Invalid dates retrieved: {row[0], row[1]}')
    else:
        date_min = date.today() - relativedelta(months = 6)
        dates = {
                 'date_min': date(date_min.year, date_min.month, 1),
                 'date_max': date.today()
                }
        fetching_dates.append(dates)
    logging.info('Fetching dates successfully defined and returned')
    return fetching_dates, quote_currencies_list
#----------------------------------------
# get request
#----------------------------------------
def get_data(base_url, from_date, to_date, base_currency, quote_currencies, group, headers, mapping, delay, items_list):
    response = requests.get(base_url + f'&from={from_date}' + f'&to={to_date}' + f'&base={base_currency}' + f'&quotes={quote_currencies}' + group, headers=headers, stream=True)
    if response.status_code == 200:
        if from_date == to_date:
            logging.info(f"Gathering data for {base_currency} as base currency for {from_date}...")
        else:
            logging.info(f"Gathering data for {base_currency} as base currency between {from_date} and {to_date}...")
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                renamed_data = {mapping[key]: value for key, value in data.items()}
                renamed_data['created_at'] = timestamp
                items_list.append(renamed_data)
        return items_list
    elif response.status_code == 429:
        wait = response.headers.get("Retry-After")
        if wait:
            time.sleep(int(wait))
        else:
            time.sleep(delay)
            delay = min((delay * 2), 60)
            return get_data(base_url, from_date, to_date, base_currency, quote_currencies, group, headers, mapping, delay, items_list)
    else:
         raise Exception(f"Request failed with HTTP response status code: {response.status_code}")
#----------------------------------------
# main logic
#----------------------------------------
def main(connection):
    global data_type
    total_rows = 0
    logging.info(f'Process started for {data_type} data!')
    # define in which table the changes will be applied based on if it's historical data or not 
    table = f'currencies_{data_type}_data'
    # condition to return the proper dates that are to be requested to fill the relevant data tables for the currencies
    if data_type == 'monthly':
        starting_date = date(1999, 1, 1)
        group = "&group=month"
        time_interval = '1 month'
    else:
        # delete everything from daily or weekly data and fetch fresh
        query_db(text(f"DELETE FROM {table};"), {}, connection)
        starting_date = date.today() - relativedelta(years = 5) # starting_date = current date - 5 years
        if data_type == 'weekly':
            group = "&group=week"
            time_interval = '1 week'
        else:
            group = ""
            time_interval = '1 day'
    for i, currency in enumerate(valid_currencies):
        rows_inserted = 0 # rows to be inserted in the current iteration
        base_currency = currency # define current base currency
        quote_currencies = ','.join(valid_currencies[:i] + valid_currencies[(i + 1):]) # modify valid_currencies to be used as a variable in the upcoming get request
        fetching_dates, quote_currencies_list = return_fetching_dates(base_currency, starting_date, connection, table, time_interval)
        for fetching_date in fetching_dates:
            from_date = fetching_date['date_min']
            if fetching_date['date_max'] > (from_date + relativedelta(years = 5)):
                to_date = from_date + relativedelta(years = 5)
            else:
                to_date = fetching_date['date_max']
            while True:
                items_list = []
                data = get_data(base_url, from_date, to_date, base_currency, quote_currencies, group, headers, mapping, delay, items_list)
                if len(data) > 0:
                    # delete possible gaps in the dates of the data or dates the have < 4 quote currencies inserted per base currency
                    query_db(text(f"DELETE FROM {table} WHERE base_currency = :base_currency AND date_recorded BETWEEN :retrieved_date_min AND :retrieved_date_max;"),
                             {"base_currency": base_currency, "retrieved_date_min": from_date, "retrieved_date_max": to_date}, connection)
                    # using pandas to clean and validate data before inserting the data to table
                    df_raw = pd.DataFrame(data)
                    df_clean = clean_data(df_raw, base_currency, quote_currencies_list)
                    if from_date == to_date:
                        logging.info(f"Inserting data for {from_date}...")
                    else:
                        logging.info(f"Inserting data between {from_date} and {to_date}...")
                    df_clean.to_sql(f"{table}", con=connection, if_exists="append", index=False, method = "multi")
                    # if data comes from the last 5 years range delete the dates on the table that are now > 5 years
                    if data_type != 'monthly':
                        year_interval = "'5 years'"
                        day_interval = "'1 day'"
                        result = query_db(text(f"SELECT MAX(date_recorded) FROM {table} WHERE date_recorded < (SELECT DATE(MAX(date_recorded) - INTERVAL :year_interval) FROM {table});"),
                                          {"year_interval": year_interval, "day_interval": day_interval}, connection)
                        row = result.fetchone()
                        if row[0]:
                            last_date = row[0]
                            logging.info(f"Rows with dates more than 5 years old (<= {last_date}) have been spotted for {base_currency} as base currency! Initiating deletion of these rows...")
                            query_db(text(f"DELETE FROM {table} WHERE base_currency = :base_currency AND date_recorded <= :last_date;"),
                                     {"base_currency": base_currency, "last_date": last_date}, connection)
                            logging.info(f"Rows with dates from {last_date} and before have been deleted successfully for {base_currency} as base currency")
                        # logging of the number of rows that were inserted for the current base currency
                    logging.info(f'{len(df_clean)} rows were inserted for {base_currency} as base currency!')
                    total_rows += len(df_clean)
                else:
                    if from_date == to_date:
                        logging.info(f"There is no data for {from_date}.")
                    else:
                        logging.info(f"There is no data for the dates between {from_date} and {to_date}.")
                if data_type == 'monthly': # from and to dates are updated for monthly data > 5 years 
                    if fetching_date['date_max'] > to_date:
                        from_date = to_date + relativedelta(months = 1)
                        if fetching_date['date_max'] > (from_date + relativedelta(years = 5)):
                            to_date += relativedelta(years = 5)
                        else:
                            to_date = fetching_date['date_max']
                    else:
                        break
                else:
                    break
    logging.info(f'Process ended for currency {data_type} data! Total rows inserted: {total_rows}.')
    if data_type != 'monthly':
        if data_type == 'daily':
            data_type = 'weekly'
        else:
            data_type = 'monthly'
        return main(connection)
    return    
#----------------------------------------
#########################################
#----------------------------------------
if __name__ == "__main__":
    # get the current timestamp--------------
    timestamp = datetime.now()
    # logging--------------------------------
    logging.basicConfig(
        level = logging.INFO,
        format = "%(asctime)s - %(levelname)s - %(message)s",
        handlers = [logging.StreamHandler(sys.stdout)] #logs streamed directly to GitHub Actions console
    )
    connection_string = os.getenv("CONNECTION_STRING")
    if connection_string:
        engine = create_engine(connection_string)
        db_test = check_connection()
        if db_test:
            logging.info('Connection with database was established!')
            # start transaction - both data from last 5 years and historical data under the same transaction
            try:
                with engine.begin() as connection:
                    main(connection)
            except Exception:
                logging.exception('Program ended abnormally!')
                sys.exit(1)
            logging.info('Program ended normally!')
            sys.exit(0)
        else:
            logging.error('Connection with database could not be established! Program ended.')
            sys.exit(1)
    else:
        logging.error('Connection string not found! Program ended.')
        sys.exit(1)
#----------------------------------------