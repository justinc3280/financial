import requests


base_test_url = 'https://sandbox.iexapis.com/'
version = 'beta'
test_token = 'Tpk_9b009416799c4054ad38760012f34bcb'

base_url = 'https://cloud.iexapis.com/'
token = 'pk_6f63e0a751884d75b526ca178528e749'


def get_latest_stock_price(symbol):
    url = base_url + version + '/stock/' + symbol + '/quote/?token=' + token
    quote = requests.get(url).json()
    return quote.get('latestPrice')


def get_stock_closing_price_on_date(symbol, date):
    return 0
