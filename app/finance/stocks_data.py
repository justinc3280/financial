import requests
from cachetools import cached, TTLCache
from collections import defaultdict
from datetime import datetime

ttl_cache = TTLCache(maxsize=100, ttl=3600)

base_url = 'https://cloud.iexapis.com/v1'
token = 'pk_6f63e0a751884d75b526ca178528e749'

alpha_url = 'https://www.alphavantage.co'
alpha_key = 'S2IEL3KQTDWBOU86'


def get_url(symbol, key):
    return '{}/stock/{}/{}/?token={}'.format(base_url, symbol, key, token)


@cached(ttl_cache)
def get_latest_stock_price(symbol):
    url = base_url + '/stock/{}/quote/?token={}'.format(symbol, token)
    quote = requests.get(url).json()
    return quote.get('latestPrice')


@cached(ttl_cache)
def _get_monthly_time_series(symbol):
    url = alpha_url + '/query?function=TIME_SERIES_MONTHLY&symbol={}&apikey={}'.format(
        symbol, alpha_key
    )
    return requests.get(url).json()


def get_monthly_stock_ending_prices(symbol):
    data = _get_monthly_time_series(symbol)
    monthly_time_series = data.get('Monthly Time Series')
    monthly_closing_prices = defaultdict(dict)
    for date_str, data in monthly_time_series.items():
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        monthly_closing_prices[date_obj.year][date_obj.month] = float(
            data.get('4. close')
        )
    return monthly_closing_prices
