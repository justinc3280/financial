import requests
from cachetools import cached, TTLCache

cache = TTLCache(maxsize=100, ttl=3600)

base_url = 'https://cloud.iexapis.com/beta/'
token = 'pk_6f63e0a751884d75b526ca178528e749'


@cached(cache)
def get_latest_stock_price(symbol):
    url = base_url + '/stock/{}/quote/?token={}'.format(symbol, token)
    quote = requests.get(url).json()
    return quote.get('latestPrice')


def get_stock_closing_price_on_date(symbol, date):
    return 0
