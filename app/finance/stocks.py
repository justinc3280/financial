from collections import defaultdict
from datetime import date
import calendar
import json
from redis import StrictRedis
from app.finance.stock_data_api import get_historical_monthly_prices, get_latest_price
from app.finance.utils import get_decimal, round_decimal

redis = StrictRedis()


class Stocks:
    def __init__(self, accounts=[]):
        self._accounts = []
        self._transactions = []
        for account in accounts:
            self.add_account(account)
        self._initialized = False

    def add_account(self, account):
        self._accounts.append(account)
        self._transactions.extend(account.transactions)
        self._initialized = False

    def _initialize(self):
        transactions = sorted(self._transactions, key=lambda x: x.date)
        stock_transaction_categories = [
            'Buy',
            'Sell',
            'Dividend Reinvest',
            'Transfer Stock In',
            'Transfer Stock Out',
        ]

        current_data = {}
        stocks_data = defaultdict(lambda: defaultdict(list))
        for transaction in transactions:
            if transaction.category.name in stock_transaction_categories:
                properties = transaction.get_properties()
                symbol = properties.get('symbol')
                quantity = get_decimal(properties.get('quantity'))
                if symbol and quantity:
                    data = stocks_data[symbol]
                    buy_or_sell = (
                        1
                        if transaction.category.name
                        in ['Buy', 'Dividend Reinvest', 'Transfer Stock In']
                        else -1
                    )
                    quantity = (
                        quantity
                        * get_decimal(properties.get('split_adjustment', 1))
                        * buy_or_sell
                    )
                    if buy_or_sell > 0:
                        cost_basis = get_decimal(abs(transaction.amount) * buy_or_sell)
                    else:
                        cost_basis = get_decimal(
                            abs(properties.get('cost_basis', 0)) * buy_or_sell
                        )

                    if symbol not in current_data:
                        previous_quantity = 0
                        new_quantity = quantity
                        previous_cost_basis = 0
                        new_cost_basis = cost_basis
                        current_data[symbol] = {
                            'quantity': new_quantity,
                            'cost_basis': new_cost_basis,
                        }
                    else:
                        previous_quantity = current_data[symbol].get('quantity')
                        new_quantity = previous_quantity + quantity
                        previous_cost_basis = current_data[symbol].get('cost_basis')
                        new_cost_basis = previous_cost_basis + cost_basis
                        current_data[symbol]['quantity'] = new_quantity
                        current_data[symbol]['cost_basis'] = new_cost_basis

                    transaction_year = transaction.date.year
                    current_date = date.today()
                    num_months = (
                        12
                        if transaction_year < current_date.year
                        else current_date.month
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
                        data[transaction_year][month_index][
                            'cost_basis'
                        ] = new_cost_basis

                    # update all future years with new values up until end_date
                    for i in range(transaction_year + 1, current_date.year + 1):
                        if new_quantity != 0:
                            num_months = (
                                12 if i < current_date.year else current_date.month
                            )
                            data[i] = [
                                {'quantity': new_quantity, 'cost_basis': new_cost_basis}
                                for _ in range(0, num_months)
                            ]
                        else:
                            data.pop(i, None)

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
                        close_price = get_decimal(monthly_price_data.get(date_str, 0))
                        month_data['price'] = close_price
                        quantity = month_data.get('quantity')
                        month_data['market_value'] = (
                            round_decimal(quantity * close_price) if quantity > 0 else 0
                        )

        self._current_data = current_data
        self._stocks_data = stocks_data
        self._initialized = True

    @staticmethod
    def _get_stock_monthly_close_prices(symbol, start_date, end_date=str(date.today())):
        redis_key = f'monthly_close_prices-{symbol}-{start_date}-{end_date}'
        result = redis.get(redis_key)

        if result:
            value_json = result.decode('utf-8')
            monthly_closing_prices = json.loads(value_json)
        else:
            monthly_closing_prices = get_historical_monthly_prices(
                symbol, start_date, end_date
            )

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
            latest_price = get_latest_price(symbol)
            redis.set(redis_key, latest_price, ex=3600)

        return latest_price

    def get_monthly_data_for_year(self, year):
        if not self._initialized:
            self._initialize()

        monthly_data = {}
        for symbol, data in self._stocks_data.items():
            if year in data:
                monthly_data[symbol] = data.get(year)
        return monthly_data

    def get_monthly_total_market_value_for_year(self, year):
        if not self._initialized:
            self._initialize()

        total_monthly_market_value = []
        for symbol, data in self._stocks_data.items():
            for month_index, month_data in enumerate(data.get(year, [])):
                market_value = round_decimal(month_data.get('market_value', 0))
                if month_index >= len(total_monthly_market_value):
                    total_monthly_market_value.append(market_value)
                else:
                    total_monthly_market_value[month_index] += market_value
        return total_monthly_market_value

    def get_current_holdings(self, market_values=True):
        if not self._initialized:
            self._initialize()

        current_holdings = {}
        total_cost_basis = 0
        total_market_value = 0
        for symbol, data in self._current_data.items():
            if data.get('quantity', 0) > 0:
                current_data = dict(data)
                current_data['cost_per_share'] = data.get('cost_basis') / data.get(
                    'quantity'
                )
                current_data['latest_price'] = latest_price = get_decimal(
                    self._get_latest_stock_price(symbol)
                )
                current_data['market_value'] = market_value = round_decimal(
                    data.get('quantity') * latest_price
                )
                current_holdings[symbol] = current_data

                total_cost_basis += data.get('cost_basis', 0)
                total_market_value += market_value

        if total_market_value > 0:
            current_holdings['Total'] = {
                'cost_basis': total_cost_basis,
                'market_value': total_market_value,
            }

            for symbol in current_holdings:
                if symbol != 'Total':
                    current_holdings[symbol]['portfolio_percentage'] = (
                        current_holdings[symbol].get('market_value')
                        / total_market_value
                    )

        return current_holdings

