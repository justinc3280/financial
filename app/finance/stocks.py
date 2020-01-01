import calendar
from collections import defaultdict
import concurrent.futures
from datetime import date
import json
import logging

from app.caching import cached
from app.finance.stock_data_api import get_historical_monthly_prices, get_latest_price
from app.finance.returns import MultiYearReturn, YearlyReturn
from app.finance.utils import (
    current_date,
    get_decimal,
    round_decimal,
    merge_dict_of_lists,
)

logger = logging.getLogger(__name__)


class Stocks:
    stock_transaction_categories = [
        'Buy',
        'Sell',
        'Dividend Reinvest',
        'Transfer Stock In',
        'Transfer Stock Out',
    ]
    # S&P 500 (TR)
    def __init__(self, accounts=[], benchmark='VFINX'):
        self._accounts = []
        self._transactions = []
        self._total_brokerage_cash_balances = {}
        for account in accounts:
            self.add_account(account)
        self._benchmark = benchmark
        self._initialized = False

    def __getattr__(self, name):
        if not self._initialized:
            self._initialize()
        return getattr(self, name)

    def add_account(self, account):
        self._accounts.append(account)
        self._transactions.extend(account.transactions)

        # maybe pass in a cash_balance store from account manager???
        # Or make cash a current holding object
        account_monthly_balances = account.get_monthly_ending_balances()
        self._total_brokerage_cash_balances = merge_dict_of_lists(
            self._total_brokerage_cash_balances, account_monthly_balances
        )

        self._initialized = False

    def _initialize(self):
        self._holdings = HoldingsManager(benchmark=self._benchmark)
        self._cash_flow_store = CashFlowStore()

        for transaction in sorted(self._transactions, key=lambda x: x.date):
            self._cash_flow_store.add_transaction(transaction)
            if transaction.category.name in self.stock_transaction_categories:
                self._holdings.add_transaction(transaction)

        self._holdings.set_market_prices()  # make lazy??
        self._initialized = True

    def get_current_holdings(self):
        return self._holdings.render_current_holdings()

    def get_monthly_total_market_value_for_year(self, year, benchmark=None):
        return self._holdings.get_monthly_total_market_value_for_year(year)

    def _get_total_ending_balances_for_years(
        self, start_year, end_year, benchmark=None
    ):
        ending_balances = {}
        for year in range(start_year - 1, end_year + 1):
            market_values = self.get_monthly_total_market_value_for_year(
                year, benchmark
            )
            if benchmark:
                cash_values = [0] * len(market_values)
            else:
                cash_values = self._total_brokerage_cash_balances.get(year)

            month_end_balances = []
            for i, amount in enumerate(market_values):
                cash = cash_values[i]
                month_end_balances.append(amount + cash)

            if year < start_year:
                starting_balance = month_end_balances[-1] if month_end_balances else 0
            elif month_end_balances:
                ending_balances[year] = month_end_balances
        return ending_balances, starting_balance

    def get_monthly_roi_data(self, year):
        ending_balances, starting_balance = self._get_total_ending_balances_for_years(
            year, year
        )

        benchmark_ending_balances, benchmark_start_balance = self._get_total_ending_balances_for_years(
            year, year, self._benchmark
        )

        yearly_return = YearlyReturn(
            year,
            starting_balance,
            ending_balances,
            self._cash_flow_store,
            benchmark_start_balance,
            benchmark_ending_balances,
        )
        return yearly_return.render()

    def get_compounded_roi(self, start_year, end_year):
        ending_balances, starting_balance = self._get_total_ending_balances_for_years(
            start_year, end_year
        )
        benchmark_ending_balances, benchmark_start_balance = self._get_total_ending_balances_for_years(
            start_year, end_year, self._benchmark
        )
        multi_year_return = MultiYearReturn(
            start_year,
            end_year,
            starting_balance,
            ending_balances,
            self._cash_flow_store,
            benchmark_start_balance,
            benchmark_ending_balances,
        )
        return multi_year_return.render()


class CashFlowStore:

    CASH_FLOW_CATEGORIES = [
        'Transfer Stock In',
        'Transfer Stock Out',
        'Transfer In',
        'Transfer Out',
        'Brokerage Fee',
        'Refund',
    ]

    def __init__(self):
        self._transactions = []  # list of tuples [(date, amount), ...]

    def add_transaction(self, transaction):
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
        days_in_month = calendar.monthrange(year, month)[1]
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
        return [
            historical_data_point
            for historical_data_point in self._historical_data.get(year, [])
            if historical_data_point.market_value is not None
        ]

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


class HoldingsManager:
    def __init__(self, benchmark=None):
        self._holdings = {}  # (dict): symbols to Holding object
        # self._total_cost_basis = 0

        self._benchmark_holdings = {}
        if benchmark:
            benchmark_holding = Holding(benchmark)
            # fix date, once pass in all transactions and set date to min date
            # minus one year so starting balance isn't 0
            benchmark_holding.update_holding(date(2010, 1, 1), 1, 0)
            self._benchmark_holdings[benchmark] = benchmark_holding

    def add_transaction(self, transaction):
        symbol, date, quantity, cost_basis = self._get_transaction_data(transaction)
        if symbol and symbol not in self._holdings:
            self._holdings[symbol] = Holding(symbol)
        self._holdings[symbol].update_holding(date, quantity, cost_basis)

        # cost basis is constant so it can be pre-calculated
        # self._total_cost_basis += cost_basis  # not working

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
            return symbol, transaction.date, quantity, cost_basis
        return None, None, None, None

    def set_market_prices(self):
        holdings = list(self._holdings.values()) + list(
            self._benchmark_holdings.values()
        )
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for holding in holdings:
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

    def get_monthly_total_market_value_for_year(self, year, benchmark=None):
        total_monthly_market_value = []
        if benchmark:
            holdings = [self._benchmark_holdings[benchmark]]
        else:
            holdings = self._holdings.values()
        for holding in holdings:
            for historical_data_point in holding.get_monthly_historical_market_values(
                year
            ):
                market_value = historical_data_point.market_value
                if historical_data_point.month - 1 >= len(total_monthly_market_value):
                    total_monthly_market_value.append(market_value)
                else:
                    total_monthly_market_value[
                        historical_data_point.month - 1
                    ] += market_value
        return total_monthly_market_value

    def render_current_holdings(self):
        current_holdings = {}
        current_holdings['holdings'] = [
            holding.render() for holding in self.get_current_holdings()
        ]
        current_holdings['total_cost_basis'] = self.total_cost_basis
        current_holdings['total_market_value'] = self.total_market_value
        return current_holdings
