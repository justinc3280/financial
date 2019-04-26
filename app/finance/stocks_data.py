import requests
from cachetools import cached, TTLCache
from collections import defaultdict
from datetime import datetime, date
import calendar

base_url = 'https://cloud.iexapis.com/v1'
token = 'pk_6f63e0a751884d75b526ca178528e749'

w_url = 'https://www.worldtradingdata.com/api/v1'
w_api_key = 'FDfrcOUb2rDUPTmA70vJuLXCi5PSLox3khlXfG8HQ6PaAMcqD3bWjp8gs7pW'


@cached(TTLCache(maxsize=100, ttl=3600))
def get_latest_stock_price(symbol):
    url = base_url + '/stock/{}/quote/?token={}'.format(symbol, token)
    quote = requests.get(url).json()
    return quote.get('latestPrice')


class Stocks:
    def __init__(self, transactions):
        self._transactions = transactions
        self._current_data = {}
        self._generate_stock_data()

    def _generate_stock_data(self):
        stocks_data = defaultdict(lambda: defaultdict(list))
        for transaction in self._transactions:
            properties = transaction.get_properties()
            symbol = properties.get('symbol')
            quantity = properties.get('quantity')
            if symbol and quantity:
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

        for symbol, yearly_data in stocks_data.items():
            price_data = self._get_daily_stock_prices(symbol)
            if price_data:
                for year, monthly_data in yearly_data.items():
                    for month_num, month_data in enumerate(monthly_data, start=1):
                        date_str = self._get_last_day_of_month_str(year, month_num)
                        day_prices = price_data.get(date_str)
                        if not day_prices:
                            i = 1
                            while not day_prices and i < 4:
                                date_str = self._get_last_day_of_month_str(
                                    year, month_num, offset=i
                                )
                                i = i + 1
                                day_prices = price_data.get(date_str)
                        if day_prices:
                            month_data['price'] = float(day_prices.get('close'))

        self._stocks_data = stocks_data

    @staticmethod
    def _get_daily_stock_prices(symbol):
        start_date = '2011-01-01'
        end_date = str(date.today())
        url = w_url + '/history?symbol={}&date_from={}&date_to={}&api_token={}'.format(
            symbol, start_date, end_date, w_api_key
        )
        data = requests.get(url).json()
        return data.get('history')

    @staticmethod
    def _get_last_day_of_month_str(year, month, offset=0):
        ending_day = calendar.monthrange(year, month)[1] - offset
        return str(date(year, month, ending_day))

    def get_monthly_data_for_year(self, year):
        monthly_data = {}
        for symbol, data in self._stocks_data.items():
            if year in data:
                monthly_data[symbol] = data.get(year)
        return monthly_data

