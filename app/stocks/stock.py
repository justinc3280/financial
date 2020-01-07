import concurrent.futures
from datetime import date
import logging

from app.caching import cached
from app.stocks.stock_data_api import get_historical_monthly_prices, get_latest_price
from app.stocks.returns import MultiYearReturn, YearlyReturn
from app.utils import (
    current_date,
    get_decimal,
    get_num_days_in_month,
    get_previous_month_and_year,
    round_decimal,
)

logger = logging.getLogger(__name__)


class StocksManager:
    # S&P 500 (TR)
    def __init__(self, accounts, starting_cash_balance=0, benchmark='VFINX'):
        self._accounts = accounts
        self._transactions = []
        self._starting_cash_balance = starting_cash_balance
        # starting holdings??

        for account in accounts:
            self._transactions.extend(account.transactions)
            self._starting_cash_balance += get_decimal(account.starting_balance)

        self._benchmark = benchmark
        self._benchmark_holdings = (
            HoldingsManager(transactions=[], starting_holdings={benchmark: (1, 0)})
            if benchmark
            else None
        )

        self._cash_flow_store = CashFlowStore(transactions=self._transactions)
        self._holdings = HoldingsManager(
            transactions=self._transactions,
            starting_cash_balance=self._starting_cash_balance,
        )

    def get_current_holdings(self):
        return self._holdings.render_current_holdings()

    def get_monthly_total_market_value_for_year(self, year):
        return self._holdings.get_monthly_total_market_value_for_year(year)

    def get_monthly_roi_data(self, year):
        yearly_return = YearlyReturn(
            year, self._holdings, self._cash_flow_store, self._benchmark_holdings
        )
        return yearly_return.render()

    def get_compounded_roi(self, start_year, end_year):
        multi_year_return = MultiYearReturn(
            start_year,
            end_year,
            self._holdings,
            self._cash_flow_store,
            self._benchmark_holdings,
        )
        return multi_year_return.render()


class CashFlowStore:
    # Can probably be combined with HoldingsManager...
    CASH_FLOW_CATEGORIES = [
        'Transfer Stock In',
        'Transfer Stock Out',
        'Transfer In',
        'Transfer Out',
        'Brokerage Fee',
        'Refund',
    ]

    def __init__(self, transactions):
        self._transactions = []  # list of tuples [(date, amount), ...]
        for transaction in sorted(transactions, key=lambda x: x.date):
            cash_flow_amount = self._get_transaction_cash_flow_amount(transaction)
            if cash_flow_amount:  # don't need to include 0 or None
                self._transactions.append((transaction.date, cash_flow_amount))

    def _get_transaction_cash_flow_amount(self, transaction):
        if transaction.category.name not in self.CASH_FLOW_CATEGORIES:
            cash_flow_amount = None
        elif transaction.category.name == 'Transfer Stock In':
            cash_flow_amount = transaction.get_property('market_value', 0)
        elif transaction.category.name == 'Transfer Stock Out':
            cash_flow_amount = -transaction.get_property('market_value', 0)
        else:
            cash_flow_amount = transaction.amount

        if cash_flow_amount is not None:
            cash_flow_amount = get_decimal(cash_flow_amount)
        return cash_flow_amount

    def get_cash_flow_amount_for_month(self, year, month):
        start_date = date(year, month, 1)
        days_in_month = get_num_days_in_month(year, month)
        end_date = date(year, month, days_in_month)

        total_amount = 0
        adjusted_amount = 0
        for transaction in self._transactions:
            transaction_date = transaction[0]
            if start_date <= transaction_date <= end_date:
                amount = transaction[1]
                total_amount += amount

                days_remaining_in_month = days_in_month - transaction_date.day
                adjustment_ratio = get_decimal(days_remaining_in_month / days_in_month)
                adjusted_amount += amount * adjustment_ratio

        return total_amount, adjusted_amount


class HistoricalDataPoint:
    # Stores the ending data for given month, cash too??
    def __init__(self, month, year, symbol, quantity, cost_basis):
        self.month = month
        self.year = year
        self.symbol = symbol
        self.quantity = quantity
        self.cost_basis = cost_basis
        self.price_per_share = None

    def update(self, new_quantity, new_cost_basis):
        self.quantity = new_quantity
        self.cost_basis = new_cost_basis

    def set_market_price(self, price_per_share):
        self.price_per_share = price_per_share

    @property
    def market_value(self):
        return (
            round_decimal(self.quantity * self.price_per_share)
            if self.price_per_share
            else None
        )

    def render(self):
        return {
            'symbol': self.symbol,
            'month': self.month,
            'year': self.year,
            'quantity': self.quantity,
            'cost_basis': self.cost_basis,
            'price_per_share': self.price_per_share,
            'market_value': self.market_value,
        }

    def __repr__(self):
        return '<HistoricalDataPoint {}, qty: {}>'.format(self.symbol, self.quantity)


class Holding:
    def __init__(self, symbol):
        self.symbol = symbol
        self.quantity = 0
        self.cost_basis = 0
        self.portfolio_percentage = None
        self._historical_data = {}  # (dict): year to list of HistoricalDataPoint

    # This function relies on it being called for transactions that have been sorted somewhere else
    # Make more robust.
    def update_holding(self, transaction_date, quantity, cost_basis):
        previous_quantity = self.quantity
        new_quantity = previous_quantity + quantity
        self.quantity = new_quantity

        previous_cost_basis = self.cost_basis
        new_cost_basis = previous_cost_basis + cost_basis
        self.cost_basis = new_cost_basis

        transaction_year = transaction_date.year

        # add year and use previous values for entire year
        if transaction_year not in self._historical_data:
            self._generate_historical_data_points_for_year(
                transaction_year, previous_quantity, previous_cost_basis
            )

        # overwrite the values for the remainder of the year after transaction
        for historical_data_point in self._historical_data[transaction_year][
            transaction_date.month - 1 :
        ]:
            historical_data_point.update(new_quantity, new_cost_basis)

        # update all future years with new values up until end_date
        for year in range(transaction_year + 1, current_date.year + 1):
            if new_quantity == 0:
                self._historical_data.pop(year, None)
            elif year not in self._historical_data:
                self._generate_historical_data_points_for_year(
                    year, new_quantity, new_cost_basis
                )
            else:
                for historical_data_point in self._historical_data[year]:
                    historical_data_point.update(new_quantity, new_cost_basis)

    def _generate_historical_data_points_for_year(self, year, quantity, cost_basis):
        num_months = 12 if year < current_date.year else current_date.month
        year_historical_data = []
        for month in range(1, num_months + 1):
            historical_data_point = HistoricalDataPoint(
                month, year, self.symbol, quantity, cost_basis
            )
            year_historical_data.append(historical_data_point)
        self._historical_data[year] = year_historical_data

    @staticmethod
    @cached
    def _get_stock_monthly_close_prices(symbol, start_date, end_date=str(current_date)):
        monthly_prices = get_historical_monthly_prices(symbol, start_date, end_date)
        if not monthly_prices:
            logger.warning('No monthly prices found for symbol %s', symbol)
        return monthly_prices

    def set_historical_market_values(self):
        start_date = str(date(min(self._historical_data.keys()), 1, 1))
        end_date = str(date(max(self._historical_data.keys()), 12, 31))
        monthly_price_data = self._get_stock_monthly_close_prices(
            self.symbol, start_date, end_date
        )

        for year, monthly_historical_data in self._historical_data.items():
            for historical_data_point in monthly_historical_data:
                date_str = '{}-{:02d}'.format(year, historical_data_point.month)
                close_price = monthly_price_data.get(date_str)

                # if current month hasen't had a trading day there will be no close price yet.
                if close_price is None:
                    continue

                close_price = get_decimal(close_price)
                historical_data_point.set_market_price(close_price)

    def get_monthly_historical_market_values(self, year):
        # For the cash holding, 'USD', value is stored on the cost basis instead of market value
        # Maybe set the market value as well??
        return [
            historical_data_point
            for historical_data_point in self._historical_data.get(year, [])
            if historical_data_point.market_value is not None or self.symbol == 'USD'
        ]

    def get_historical_data_for_month(self, year, month):
        yearly_data = self._historical_data.get(year, [])
        return (
            yearly_data[month - 1]
            if yearly_data and month <= len(yearly_data)
            else None
        )

    @staticmethod
    @cached
    def _get_latest_stock_price(symbol):
        return get_latest_price(symbol)

    @property
    def latest_price(self):
        return get_decimal(self._get_latest_stock_price(self.symbol))

    @property
    def market_value(self):
        return round_decimal(self.quantity * self.latest_price)

    @property
    def cost_per_share(self):
        if self.quantity > 0:
            return self.cost_basis / self.quantity
        else:
            return 0

    def set_percentage(self, total_portfolio_market_value):
        self.portfolio_percentage = self.market_value / total_portfolio_market_value

    def render(self):
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'cost_basis': self.cost_basis,
            'cost_per_share': self.cost_per_share,
            'latest_price': self.latest_price,
            'market_value': self.market_value,
            'portfolio_percentage': self.portfolio_percentage,
        }

    def __repr__(self):
        return '<Holding {}>'.format(self.symbol)


class HoldingsManager:
    STOCK_TRANSACTION_CATEGORIES = [
        'Buy',
        'Sell',
        'Dividend Reinvest',
        'Transfer Stock In',
        'Transfer Stock Out',
    ]

    def __init__(
        self,
        transactions,
        starting_cash_balance=0,
        starting_holdings={},
        start_date=date(2010, 1, 1),
    ):
        self._holdings = {}  # (dict): symbols to Holding object
        # self._total_cost_basis = 0

        cash_holding = Holding('USD')
        cash_holding.update_holding(
            start_date, starting_cash_balance, starting_cash_balance
        )
        self._cash_holding = cash_holding

        for symbol, holding_data in starting_holdings.items():
            holding = Holding(symbol)
            holding.update_holding(start_date, holding_data[0], holding_data[1])
            self._holdings[symbol] = holding

        for transaction in sorted(transactions, key=lambda x: x.date):
            cash_amount = get_decimal(transaction.amount)
            self._cash_holding.update_holding(
                transaction.date, cash_amount, cash_amount
            )
            if transaction.category.name in self.STOCK_TRANSACTION_CATEGORIES:
                symbol, quantity, cost_basis = self._get_transaction_data(transaction)
                if symbol and symbol not in self._holdings:
                    self._holdings[symbol] = Holding(symbol)
                self._holdings[symbol].update_holding(
                    transaction.date, quantity, cost_basis
                )

        self._set_market_prices()

    def _get_transaction_data(self, transaction):
        properties = transaction.get_properties()
        symbol = properties.get('symbol')
        quantity = get_decimal(properties.get('quantity'))
        if symbol and quantity:
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
            return symbol, quantity, cost_basis
        return None, None, None

    def _set_market_prices(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for holding in self._holdings.values():
                executor.submit(holding.set_historical_market_values)

    @property
    def total_cost_basis(self):
        # precalc not working because cost basis for qty 0 is off for some reason
        # return self._total_cost_basis
        total = 0
        for holding in self.get_current_holdings():
            total += holding.cost_basis
        return total

    @property
    def total_market_value(self):
        # market value fluctuates so it is calculated on the fly
        total = 0
        for holding in self._holdings.values():
            # Protect against iex 'Unknown Symbol' error (ex. ALOG)
            if holding.quantity > 0:
                total += holding.market_value
        return total

    def get_current_holdings(self):
        current_holdings = []
        for holding in self._holdings.values():
            if holding.quantity > 0:
                holding.set_percentage(self.total_market_value)
                current_holdings.append(holding)
        return current_holdings

    def get_total_holdings_market_value_for_month(self, year, month, include_cash=True):
        found_market_value = False
        total_value = 0
        for holding in self._holdings.values():
            month_data = holding.get_historical_data_for_month(year, month)
            if month_data and month_data.market_value is not None:
                found_market_value = True
                total_value += month_data.market_value

        if include_cash:
            cash_month_data = self._cash_holding.get_historical_data_for_month(
                year, month
            )
            if cash_month_data:
                total_value += cash_month_data.cost_basis

        # Need to return None for the following scenarios:
        # 1) prior to the first trading day of the current month,
        #    in this case cash will have a value but found_market_value will be False
        # 2) Future months past the current month

        # Need to return the cash amount for previous months before any holdings were present
        # In this case cash will have a value but found_market_value will be False

        # What if current month and no holdings????? Then market values wont matter, just use cash value

        return total_value if found_market_value or year < current_date.year else None

    def get_monthly_total_market_value_for_year(self, year, include_cash=True):
        num_months = 12 if year < current_date.year else current_date.month
        monthly_market_values = []
        for month in range(1, num_months + 1):
            total_month_market_value = self.get_total_holdings_market_value_for_month(
                year, month, include_cash
            )

            if total_month_market_value is not None:
                monthly_market_values.append(total_month_market_value)
            else:
                # Once you find month without market_values set, no futures months will have market values set
                # This shouldn't really be necessary because the only time this should hit is on the current_date.month
                # where there hasn't been a day where the stock market was open.
                break
        return monthly_market_values

    def get_starting_total_market_value_for_year(self, year, include_cash=True):
        return self.get_total_holdings_market_value_for_month(
            year - 1, 12, include_cash=include_cash
        )

    def get_starting_total_market_value_for_month(self, year, month, include_cash=True):
        prev_year, prev_month = get_previous_month_and_year(year, month)
        return self.get_total_holdings_market_value_for_month(
            prev_year, prev_month, include_cash
        )

    def render_current_holdings(self):
        current_holdings = {}
        current_holdings['holdings'] = [
            holding.render() for holding in self.get_current_holdings()
        ]
        current_holdings['total_cost_basis'] = self.total_cost_basis
        current_holdings['total_market_value'] = self.total_market_value
        return current_holdings
