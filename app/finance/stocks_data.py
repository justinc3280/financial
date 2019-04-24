import requests
from cachetools import cached, TTLCache
from collections import defaultdict
from datetime import datetime, date

base_url = 'https://cloud.iexapis.com/v1'
token = 'pk_6f63e0a751884d75b526ca178528e749'

alpha_url = 'https://www.alphavantage.co'
alpha_key = 'S2IEL3KQTDWBOU86'


def get_url(symbol, key):
    return '{}/stock/{}/{}/?token={}'.format(base_url, symbol, key, token)


@cached(TTLCache(maxsize=100, ttl=3600))
def get_latest_stock_price(symbol):
    url = base_url + '/stock/{}/quote/?token={}'.format(symbol, token)
    quote = requests.get(url).json()
    return quote.get('latestPrice')


@cached(TTLCache(maxsize=100, ttl=3600))
def _get_monthly_time_series(symbol):
    url = alpha_url + '/query?function=TIME_SERIES_MONTHLY&symbol={}&apikey={}'.format(
        symbol, alpha_key
    )
    return requests.get(url).json()


def get_monthly_stock_ending_prices(symbol):
    data = _get_monthly_time_series(symbol)
    monthly_time_series = data.get('Monthly Time Series')
    if monthly_time_series:
        monthly_closing_prices = defaultdict(dict)
        for date_str, data in monthly_time_series.items():
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            monthly_closing_prices[date_obj.year][date_obj.month] = float(
                data.get('4. close')
            )
        return monthly_closing_prices
    return None


class Stocks:
    def __init__(self, transactions):
        self._transactions = transactions
        self._symbols = []
        self._current_data = {}
        self._generate_stock_data()

    def _generate_stock_data(self):
        stocks_data = defaultdict(lambda: defaultdict(list))
        for transaction in self._transactions:
            properties = transaction.get_properties()
            symbol = properties.get('symbol')
            quantity = properties.get('quantity')
            if symbol and quantity:
                if symbol not in self._symbols:
                    self._symbols.append(symbol)

                data = stocks_data[symbol]
                buy_or_sell = (
                    1
                    if transaction.category.name in ['Buy', 'Dividend Reinvest']
                    else -1
                )
                quantity = (
                    quantity * properties.get('split_adjustment', 1) * buy_or_sell
                )
                if symbol not in self._current_data:
                    previous_quantity = 0
                    new_quantity = quantity
                    self._current_data[symbol] = {'quantity': new_quantity}
                else:
                    previous_quantity = self._current_data[symbol].get('quantity')
                    new_quantity = round(previous_quantity + quantity, 3)

                transaction_year = transaction.date.year
                current_date = date.today()
                num_months = (
                    12 if transaction_year < current_date.year else current_date.month
                )
                if transaction_year not in data:
                    data[transaction_year] = [
                        {'quantity': previous_quantity} for _ in range(0, num_months)
                    ]

                for month_index in range(transaction.date.month - 1, num_months):
                    data[transaction_year][month_index]['quantity'] = new_quantity

                # update all future years up until end_date
                for i in range(transaction_year + 1, current_date.year + 1):
                    if new_quantity != 0:
                        num_months = 12 if i < current_date.year else current_date.month
                        data[i] = [
                            {'quantity': new_quantity} for _ in range(0, num_months)
                        ]
                    else:
                        data.pop(i, None)

        # insert price data
        for symbol, yearly_data in stocks_data.items():
            price_data = get_monthly_stock_ending_prices(symbol)
            if price_data:
                for year, monthly_data in yearly_data.items():
                    yearly_price_data = price_data.get(year)

                    for month_num, month_data in enumerate(monthly_data, start=1):
                        ending_price = yearly_price_data.get(month_num)
                        month_data['price'] = ending_price

        self._stocks_data = stocks_data

    def get_monthly_data_for_year(self, year):
        monthly_data = {}
        for symbol, data in self._stocks_data.items():
            if year in data:
                monthly_data[symbol] = data.get(year)
        return monthly_data

    def get_current_data_for_symbol(self, symbol):
        return self._current_data.get(symbol)

    def get_current_stocks(self):
        return self._current_data  # remove quantity 0
