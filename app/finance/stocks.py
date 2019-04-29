import requests
from collections import defaultdict
from datetime import datetime, date
import calendar
import json
from redis import StrictRedis

redis = StrictRedis()

base_url = 'https://cloud.iexapis.com/v1'
token = 'pk_6f63e0a751884d75b526ca178528e749'

w_url = 'https://www.worldtradingdata.com/api/v1'
w_api_key = 'FDfrcOUb2rDUPTmA70vJuLXCi5PSLox3khlXfG8HQ6PaAMcqD3bWjp8gs7pW'


class Stocks:
    def __init__(self, transactions, show_market_values=True):
        self._show_market_values = show_market_values
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
                    if transaction.category.name
                    in ['Buy', 'Dividend Reinvest', 'Transfer Stock In']
                    else -1
                )
                quantity = (
                    quantity * properties.get('split_adjustment', 1) * buy_or_sell
                )
                if buy_or_sell > 0:
                    cost_basis = abs(transaction.amount) * buy_or_sell
                else:
                    cost_basis = abs(properties.get('cost_basis', 0)) * buy_or_sell
                if symbol not in self._current_data:
                    previous_quantity = previous_cost_basis = 0
                    new_quantity = quantity
                    new_cost_basis = cost_basis
                    self._current_data[symbol] = {
                        'quantity': new_quantity,
                        'cost_basis': new_cost_basis,
                    }
                else:
                    previous_quantity = self._current_data[symbol].get('quantity')
                    new_quantity = round(previous_quantity + quantity, 3)
                    previous_cost_basis = self._current_data[symbol].get('cost_basis')
                    new_cost_basis = round(previous_cost_basis + cost_basis, 4)
                    self._current_data[symbol]['quantity'] = new_quantity
                    self._current_data[symbol]['cost_basis'] = new_cost_basis

                transaction_year = transaction.date.year
                current_date = date.today()
                num_months = (
                    12 if transaction_year < current_date.year else current_date.month
                )

                # add year and use previous values for entire year
                if transaction_year not in data:
                    data[transaction_year] = [
                        {
                            'quantity': previous_quantity,
                            'cost_basis': previous_cost_basis,
                        }
                        for _ in range(0, num_months)
                    ]

                # overwrite the values for the remainder of the year after transaction
                for month_index in range(transaction.date.month - 1, num_months):
                    data[transaction_year][month_index]['quantity'] = new_quantity
                    data[transaction_year][month_index]['cost_basis'] = new_cost_basis

                # update all future years with new values up until end_date
                for i in range(transaction_year + 1, current_date.year + 1):
                    if new_quantity != 0:
                        num_months = 12 if i < current_date.year else current_date.month
                        data[i] = [
                            {'quantity': new_quantity, 'cost_basis': new_cost_basis}
                            for _ in range(0, num_months)
                        ]
                    else:
                        data.pop(i, None)

        if self._show_market_values:
            for symbol, yearly_data in stocks_data.items():
                start_date = str(date(min(yearly_data.keys()), 1, 1))
                end_date = str(date(max(yearly_data.keys()), 12, 31))
                monthly_price_data = self._get_stock_monthly_close_prices(
                    symbol, start_date, end_date
                )

                if monthly_price_data:
                    for year, monthly_data in yearly_data.items():
                        for month_num, month_data in enumerate(monthly_data, start=1):
                            date_str = '{}-{:02d}'.format(year, month_num)
                            close_price = monthly_price_data.get(date_str, 0)
                            month_data['price'] = float(close_price)

        self._stocks_data = stocks_data

    @staticmethod
    def _get_stock_monthly_close_prices(symbol, start_date, end_date=str(date.today())):
        redis_key = f'monthly_close_prices-{symbol}-{start_date}-{end_date}'
        result = redis.get(redis_key)

        if result:
            value_json = result.decode('utf-8')
            monthly_closing_prices = json.loads(value_json)
        else:
            url = f"""{w_url}/history?symbol={symbol}&sort=newest
                &date_from={start_date}&date_to={end_date}&api_token={w_api_key}"""
            data = requests.get(url).json()
            historical_prices = data.get('history')

            monthly_closing_prices = {}
            for date_str, prices in historical_prices.items():
                # Assume dict is sorted as newest first
                year_month_str = date_str[:7]
                if year_month_str not in monthly_closing_prices:
                    monthly_closing_prices[year_month_str] = prices.get('close')

            value_json = json.dumps(monthly_closing_prices)
            redis.set(redis_key, value_json, ex=86400)

        return monthly_closing_prices

    @staticmethod
    def _get_latest_stock_price(symbol):
        redis_key = f'current_price-{symbol}'
        result = redis.get(redis_key)

        if result:
            latest_price = float(result.decode('utf-8'))
        else:
            url = base_url + '/stock/{}/quote/?token={}'.format(symbol, token)
            quote = requests.get(url).json()
            latest_price = quote.get('latestPrice')

            redis.set(redis_key, latest_price, ex=3600)

        return latest_price

    def get_monthly_data_for_year(self, year):
        monthly_data = {}
        for symbol, data in self._stocks_data.items():
            if year in data:
                monthly_data[symbol] = data.get(year)
        return monthly_data

    def get_current_holdings(self):
        current_holdings = {}
        total_cost_basis = 0
        total_market_value = 0
        for symbol, data in self._current_data.items():
            if data.get('quantity', 0) > 0:
                current_data = dict(data)
                current_data['cost_per_share'] = round(
                    data.get('cost_basis') / data.get('quantity'), 4
                )
                current_data[
                    'latest_price'
                ] = latest_price = self._get_latest_stock_price(symbol)
                current_data['market_value'] = market_value = (
                    data.get('quantity') * latest_price
                )
                current_holdings[symbol] = current_data

                total_cost_basis += data.get('cost_basis', 0)
                total_market_value += market_value

        current_holdings['Total'] = {
            'cost_basis': total_cost_basis,
            'market_value': total_market_value,
        }

        for symbol in current_holdings:
            current_holdings[symbol]['portfolio_percentage'] = round(
                current_holdings[symbol].get('market_value') / total_market_value, 4
            )

        return current_holdings

