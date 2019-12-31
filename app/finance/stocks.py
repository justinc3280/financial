import calendar
from collections import defaultdict
import concurrent.futures
from datetime import date
import json
import logging

from app.caching import cached
from app.finance.stock_data_api import get_historical_monthly_prices, get_latest_price
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

    def __init__(self, accounts=[]):
        self._accounts = []
        self._transactions = []
        self._total_brokerage_cash_balances = {}
        for account in accounts:
            self.add_account(account)
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
        self._holdings = HoldingsManager()
        self._cash_flow_store = CashFlowStore()

        for transaction in sorted(self._transactions, key=lambda x: x.date):
            self._cash_flow_store.add_transaction(transaction)
            if transaction.category.name in self.stock_transaction_categories:
                self._holdings.add_transaction(transaction)

        self._holdings.set_market_values()  # make lazy??
        self._initialized = True

    def get_current_holdings(self):
        return self._holdings  # ???

    def _get_monthly_total_market_value_for_year(self, year):
        return self._holdings.get_monthly_total_market_value_for_year(year)

    def _get_total_ending_balances_for_years(self, start_year, end_year):
        ending_balances = {}
        for year in range(start_year - 1, end_year + 1):
            market_values = self._get_monthly_total_market_value_for_year(year)
            cash_values = self._total_brokerage_cash_balances.get(year)

            month_end_balances = []
            for i, amount in enumerate(market_values):
                cash = cash_values[i]
                month_end_balances.append(amount + cash)
            if year < start_year:
                starting_balance = month_end_balances[-1] if month_end_balances else 0
            else:
                ending_balances[year] = month_end_balances
        return ending_balances, starting_balance

    def get_monthly_roi_data(self, year):
        ending_balances, starting_balance = self._get_total_ending_balances_for_years(
            year, year
        )
        return YearlyReturn(
            year, starting_balance, ending_balances, self._cash_flow_store
        )

    def get_compounded_roi(self, start_year, end_year):
        ending_balances, starting_balance = self._get_total_ending_balances_for_years(
            start_year, end_year
        )
        return MultiYearReturn(
            start_year,
            end_year,
            starting_balance,
            ending_balances,
            self._cash_flow_store,
        )


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
        self.price_per_share = 0
        self.market_value = 0

    def update(self, new_quantity, new_cost_basis):
        self.quantity = new_quantity
        self.cost_basis = new_cost_basis

    def set_market_value(self, price_per_share):
        self.price_per_share = price_per_share
        self.market_value = round_decimal(self.quantity * price_per_share)


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
                # so use the previous month close price as a default
                if close_price is None:
                    prev_month_date_str = '{}-{:02d}'.format(
                        year, historical_data_point.month - 1
                    )
                    close_price = monthly_price_data.get(prev_month_date_str, 0)

                close_price = get_decimal(close_price)
                historical_data_point.set_market_value(close_price)

    def get_monthly_historical_market_values(self, year):
        return self._historical_data.get(year, [])

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


class HoldingsManager:
    def __init__(self):
        self._holdings = {}  # (dict): symbols to Holding object
        # self._total_cost_basis = 0

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

    def set_market_values(self):
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

    def get_monthly_total_market_value_for_year(self, year):
        total_monthly_market_value = []
        for holding in self._holdings.values():
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


class TimePeriodReturn:
    def __init__(self, starting_balance, cash_flow_store):
        self.starting_balance = starting_balance
        self._cash_flow_store = cash_flow_store

        self._generate_subperiod_returns()

    # Abstract method
    def _generate_subperiod_returns(self):
        raise NotImplementedError

    @property
    def gain(self):
        return self.ending_balance - self.total_cash_flow_amount - self.starting_balance

    @property
    def return_pct(self):
        if self.subperiod_returns:
            returns = [r.return_pct for r in self.subperiod_returns]
            return self.get_geometrically_linked_return(returns)
        else:
            # For MonthlyReturns, use modified dietz
            return self.gain / (self.starting_balance + self.adjusted_cash_flow_amount)

    @staticmethod
    def get_geometrically_linked_return(returns):
        if not returns:
            return None
        overall_return = returns[0] + 1
        if len(returns) > 1:
            for r in returns[1:]:
                overall_return *= r + 1
        return overall_return - 1


class MonthlyReturn(TimePeriodReturn):
    def __init__(self, month, year, starting_balance, ending_balance, cash_flow_store):
        self.year = year
        self.month = month
        self.month_name = calendar.month_name[month]
        self.ending_balance = ending_balance

        self.total_cash_flow_amount, self.adjusted_cash_flow_amount = cash_flow_store.get_cash_flow_amount_for_month(
            year, month
        )

        super().__init__(starting_balance, cash_flow_store)

    def _generate_subperiod_returns(self):
        self.subperiod_returns = None


class YearlyReturn(TimePeriodReturn):
    def __init__(self, year, starting_balance, ending_balances, cash_flow_store):
        self.year = year
        self.ending_balances = ending_balances
        super().__init__(starting_balance, cash_flow_store)

    def _generate_subperiod_returns(self):
        monthly_returns = []
        starting_balance = self.starting_balance

        for year, monthly_ending_balances in self.ending_balances.items():
            for month, ending_balance in enumerate(monthly_ending_balances, start=1):
                monthly_return = MonthlyReturn(
                    month, year, starting_balance, ending_balance, self._cash_flow_store
                )
                monthly_returns.append(monthly_return)
                starting_balance = ending_balance
        self.subperiod_returns = monthly_returns


class MultiYearReturn(TimePeriodReturn):
    def __init__(
        self, start_year, end_year, starting_balance, ending_balances, cash_flow_store
    ):
        self.start_year = start_year
        self.end_year = end_year
        self.ending_balances = ending_balances
        super().__init__(starting_balance, cash_flow_store)

    def _generate_subperiod_returns(self):
        yearly_returns = []
        starting_balance = self.starting_balance

        # make sure keys are sorted
        for year, monthly_ending_balances in self.ending_balances.items():
            monthly_ending_balances_dict = {year: monthly_ending_balances}
            yearly_return = YearlyReturn(
                year,
                starting_balance,
                monthly_ending_balances_dict,
                self._cash_flow_store,
            )
            yearly_returns.append(yearly_return)
            starting_balance = monthly_ending_balances[-1]
        self.subperiod_returns = yearly_returns

    @property
    def annualized_return(self):
        num_months = 0
        for year in range(self.start_year, self.end_year + 1):
            if year == current_date.year:
                num_months += current_date.month - 1
                days_in_month = calendar.monthrange(year, current_date.month)[1]
                percent_of_month = round(current_date.day / days_in_month, 4)
                num_months += percent_of_month
            else:
                num_months += 12
        num_years = num_months / 12
        return (self.return_pct + 1) ** get_decimal((1 / num_years)) - 1
