from datetime import datetime
import logging
import requests

logger = logging.getLogger(__name__)

base_url = 'https://cloud.iexapis.com/v1'
token = 'pk_6f63e0a751884d75b526ca178528e749'

w_url = 'https://www.worldtradingdata.com/api/v1'
w_api_key = 'FDfrcOUb2rDUPTmA70vJuLXCi5PSLox3khlXfG8HQ6PaAMcqD3bWjp8gs7pW'

alpha_url = 'https://www.alphavantage.co'
alpha_key = 'S2IEL3KQTDWBOU86'

# need exceptions if apis return errors
def _get_iex_latest_price(symbol):
    url = base_url + '/stock/{}/quote/?token={}'.format(symbol, token)
    quote = requests.get(url).json()
    return quote.get('latestPrice')


def _get_world_trade_data_historical_monthly_prices(symbol, start_date, end_date):
    url = f"""{w_url}/history?symbol={symbol}&sort=newest&date_from={start_date}&date_to={end_date}&api_token={w_api_key}"""
    data = requests.get(url).json()
    historical_prices = data.get('history')

    monthly_closing_prices = {}
    for date_str, prices in historical_prices.items():
        year_month_str = date_str[:7]
        if year_month_str not in monthly_closing_prices:
            monthly_closing_prices[year_month_str] = prices.get('close')
    return monthly_closing_prices


def _get_alpha_vantage_historical_monthly_prices(symbol, start_date, end_date):
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    url = f'{alpha_url}/query?function=TIME_SERIES_MONTHLY_ADJUSTED&symbol={symbol}&apikey={alpha_key}'
    data = requests.get(url).json()
    historical_prices = data.get('Monthly Adjusted Time Series')
    if historical_prices is None:
        error_message = data.get('Note')
        logger.error(
            'No data from Alpha Vantage for symbol: %s. Error Message: %s',
            symbol,
            error_message,
        )
        return None

    monthly_closing_prices = {}
    for date_str, prices in historical_prices.items():
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        if start_date <= date_obj <= end_date:
            year_month_str = date_str[:7]
            if year_month_str not in monthly_closing_prices:
                monthly_closing_prices[year_month_str] = float(prices.get('4. close'))
    return monthly_closing_prices


def get_historical_monthly_prices(symbol, start_date, end_date):
    if symbol in ['PSX', 'SBUX', 'VFINX']:
        # found issues with world trade data:
        # 1) SFTBY prices ended at 1/18/2019, now it works?
        # 2) SBUX and PSX missing data for 3/29/2019
        # 3) VFINX off by 1 cent on 2/28/2018 (251.28 should be 251.27)
        return _get_alpha_vantage_historical_monthly_prices(
            symbol, start_date, end_date
        )
    else:
        return _get_world_trade_data_historical_monthly_prices(
            symbol, start_date, end_date
        )


def get_latest_price(symbol):
    return _get_iex_latest_price(symbol)
