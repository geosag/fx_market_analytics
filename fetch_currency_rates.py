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
# get request
#----------------------------------------
def get_data(base_url, from_date, to_date, base_currency, quote_currencies, group, headers, mapping, delay, items_list, max_retries=6, attempt=1):
    url = base_url + f'&from={from_date}' + f'&to={to_date}' + f'&base={base_currency}' + f'&quotes={quote_currencies}' + group
    response = requests.get(url, headers=headers, stream=True, timeout=(10, 60))
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
        response.close()
        return items_list
    retry_errors = (408, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524)
    if response.status_code in retry_errors:
        if attempt > max_retries:
            response.close()
            raise Exception(f"Request failed after {max_retries} retries. Status code: {response.status_code}")
        if response.status_code == 429:
            wait = response.headers.get("Retry-After")
            if wait:
                wait = int(wait)
            else:
                wait = delay
        else:
            wait = delay
        logging.warning(f"Temporary error {response.status_code} for {base_currency} between {from_date} and {to_date}. Retrying in {wait}s ({attempt}/{max_retries})...")
        response.close()
        time.sleep(wait)
        delay = min(delay * 2, 60)
        return get_data(base_url, from_date, to_date, base_currency, quote_currencies, group, headers, mapping, delay, items_list, max_retries, attempt + 1)
    response.close()
    raise Exception(f"Request failed with HTTP response status code: {response.status_code}")
#----------------------------------------
# main logic
#----------------------------------------
def main(connection):
    global data_type
    total_rows = 0
    logging.info(f'Process started for {data_type} data!')
    # define in which table the changes will be applied
    table = f'currencies_{data_type}_data'
    # delete everything from the table and fetch fresh
    query_db(text(f"DELETE FROM {table};"), {}, connection)
    # define dates and group based on data type
    if data_type == 'monthly':
        starting_date = date(1999, 1, 1)
        group = "&group=month"
    elif data_type == 'weekly':
        starting_date = date.today() - relativedelta(years = 5)
        group = "&group=week"
    else:
        starting_date = date.today() - relativedelta(years = 5)
        group = ""
    for i, currency in enumerate(valid_currencies):
        base_currency = currency
        # define quote currencies
        quote_currencies = ','.join(valid_currencies[:i] + valid_currencies[(i + 1):]) # to be used in the upcoming get request
        quote_currencies_list = [] # to be used in the clean_data function
        for currency in valid_currencies:
            if currency != base_currency:
                quote_currencies_list.append(currency)
        # define the dates to fetch
        from_date = starting_date
        to_date = date.today()
        items_list = []
        data = get_data(base_url, from_date, to_date, base_currency, quote_currencies, group, headers, mapping, delay, items_list)
        if len(data) > 0:
            # using pandas to clean and validate data before inserting data to table
            df_raw = pd.DataFrame(data)
            df_clean = clean_data(df_raw, base_currency, quote_currencies_list)
            if from_date == to_date:
                logging.info(f"Inserting data for {from_date}...")
            else:
                logging.info(f"Inserting data between {from_date} and {to_date}...")
            df_clean.to_sql(f"{table}", con=connection, if_exists="append", index=False, method="multi")
            # delete rows older than 5 years for daily and weekly data, if they exist
            if data_type != 'monthly':
                last_date = date.today() - relativedelta(years = 5)
                result = query_db(
                    text(f"""
                            SELECT MAX(date_recorded)
                            FROM {table}
                            WHERE base_currency = :base_currency
                            AND date_recorded < :last_date;
                    """),
                    {"base_currency": base_currency, "last_date": last_date},
                    connection
                )
                row = result.fetchone()
                if row[0]:
                    logging.info(f"Rows before {last_date} were found for {base_currency} as base currency. Deleting them...")
                    query_db(
                        text(f"""
                                DELETE FROM {table}
                                WHERE base_currency = :base_currency
                                AND date_recorded < :last_date;
                        """),
                        {"base_currency": base_currency, "last_date": last_date},
                        connection
                    )
                    logging.info(f"Rows before {last_date} have been deleted for {base_currency} as base currency.")
            logging.info(f'{len(df_clean)} rows were inserted for {base_currency} as base currency!')
            total_rows += len(df_clean)
        else:
            if from_date == to_date:
                logging.info(f"There is no data for {from_date}.")
            else:
                logging.info(f"There is no data for the dates between {from_date} and {to_date}.")
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