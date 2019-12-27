import calendar
from collections import defaultdict
import concurrent.futures
from datetime import date
import json
import logging

from app.caching import cached
from app.finance.stock_data_api import get_historical_monthly_prices, get_latest_price
from app.finance.utils import get_decimal, round_decimal, merge_dict_of_lists

logger = logging.getLogger(__name__)


class Stocks:
    def __init__(self, accounts=[]):
        self._accounts = []
        self._transactions = []
        self._total_brokerage_cash_balances = {}
        for account in accounts:
            self.add_account(account)
        self._initialized = False
        self._current_holdings = CurrentHoldings()
        self._cash_flow_store = CashFlowStore()
        # self._ending_balances_store = EndingBalancesStore()
        self._stocks_data_store = StocksDataStore()

    def __getattr__(self, name):
        if not self._initialized:
            self._initialize()
        return getattr(self, name)

    def add_account(self, account):
        self._accounts.append(account)
        self._transactions.extend(account.transactions)

        account_monthly_balances = account.get_monthly_ending_balances()
        self._total_brokerage_cash_balances = merge_dict_of_lists(
            self._total_brokerage_cash_balances, account_monthly_balances
        )

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
        current_date = date.today()
        stocks_data = defaultdict(lambda: defaultdict(list))
        for transaction in transactions:
            self._cash_flow_store.add_transaction(transaction)
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

                    current_holding = self._current_holdings.get_holding(symbol)
                    if current_holding is None:
                        previous_quantity = 0
                        new_quantity = quantity
                        previous_cost_basis = 0
                        new_cost_basis = cost_basis
                    else:
                        previous_quantity = current_holding.quantity
                        new_quantity = previous_quantity + quantity
                        previous_cost_basis = current_holding.cost_basis
                        new_cost_basis = previous_cost_basis + cost_basis
                    self._current_holdings.add_transaction(
                        symbol, date, quantity, cost_basis
                    )

                    transaction_year = transaction.date.year
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

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_symbol = {}
            for symbol, yearly_data in stocks_data.items():
                start_date = str(date(min(yearly_data.keys()), 1, 1))
                end_date = str(date(max(yearly_data.keys()), 12, 31))
                future_obj = executor.submit(
                    self._get_stock_monthly_close_prices, symbol, start_date, end_date
                )
                future_to_symbol.update({future_obj: symbol})

            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    monthly_price_data = future.result()
                except Exception as e:
                    logger.exception(e)
                    continue

                if monthly_price_data:
                    yearly_data = stocks_data[symbol]
                    for year, monthly_data in yearly_data.items():
                        for month_num, month_data in enumerate(monthly_data, start=1):
                            date_str = '{}-{:02d}'.format(year, month_num)
                            prev_month_date_str = '{}-{:02d}'.format(
                                year, month_num - 1
                            )
                            # if current month hasen't had a trading day there will be no close price yet.
                            # so use the previous month close price as a default
                            close_price = get_decimal(
                                monthly_price_data.get(
                                    date_str,
                                    monthly_price_data.get(prev_month_date_str, 0),
                                )
                            )
                            month_data['price'] = close_price
                            quantity = month_data.get('quantity')
                            month_data['market_value'] = (
                                round_decimal(quantity * close_price)
                                if quantity > 0
                                else 0
                            )

        self._stocks_data = stocks_data
        self._initialized = True

    @staticmethod
    @cached
    def _get_stock_monthly_close_prices(symbol, start_date, end_date=str(date.today())):
        monthly_prices = get_historical_monthly_prices(symbol, start_date, end_date)
        if not monthly_prices:
            logger.warning('No monthly prices found for symbol %s', symbol)
        return monthly_prices

    @staticmethod
    @cached
    def _get_latest_stock_price(symbol):
        return get_latest_price(symbol)

    def get_monthly_total_market_value_for_year(self, year):
        total_monthly_market_value = []
        for symbol, data in self._stocks_data.items():
            for month_index, month_data in enumerate(data.get(year, [])):
                market_value = round_decimal(month_data.get('market_value', 0))
                if month_index >= len(total_monthly_market_value):
                    total_monthly_market_value.append(market_value)
                else:
                    total_monthly_market_value[month_index] += market_value
        return total_monthly_market_value

    def get_current_holdings(self):
        self._initialize()  # why needed?
        current_holdings = self._current_holdings
        return current_holdings

    def _get_total_ending_balances_for_year(self, year):
        market_values = self.get_monthly_total_market_value_for_year(year)
        cash_values = self._total_brokerage_cash_balances.get(year)

        data = []
        for i, amount in enumerate(market_values):
            cash = cash_values[i]
            data.append(amount + cash)
        return data

    def get_monthly_roi_data(self, year):
        monthly_ending_values = self._get_total_ending_balances_for_year(year)

        previous_year_data = self._get_total_ending_balances_for_year(year - 1)
        starting_value = previous_year_data[-1] if previous_year_data else 0

        return YearlyReturn(
            year, starting_value, monthly_ending_values, self._cash_flow_store
        )

    def get_compounded_roi(self, start_year, end_year):
        data = {}
        num_months = 0
        current_date = date.today()
        annual_returns = []

        ending_balances = {}
        for year in range(start_year, end_year + 1):
            ending_balances[year] = self._get_total_ending_balances_for_year(year)

        previous_year_data = self._get_total_ending_balances_for_year(start_year - 1)
        starting_balance = (
            previous_year_data[-1] if previous_year_data else get_decimal(0)
        )

        return MultiYearReturn(
            start_year,
            end_year,
            starting_balance,
            ending_balances,
            self._cash_flow_store,
        )


class StocksDataStore:
    def __init__(self):
        self._stock_transaction_categories = [
            'Buy',
            'Sell',
            'Dividend Reinvest',
            'Transfer Stock In',
            'Transfer Stock Out',
        ]


class EndingBalancesStore:
    pass


class CashFlowStore:
    def __init__(self):
        self._transactions = []  # list of tuples, [(date, amount)]
        self._cash_flow_categories = [
            'Transfer Stock In',
            'Transfer Stock Out',
            'Transfer In',
            'Transfer Out',
            'Brokerage Fee',
            'Refund',
        ]

    def _get_cash_flow_amount(self, transaction):
        if transaction.category.name not in self._cash_flow_categories:
            cash_flow_amount = None
        elif transaction.category.name == 'Transfer Stock In':
            cash_flow_amount = transaction.get_property('market_value', 0)
        elif transaction.category.name == 'Transfer Stock Out':
            cash_flow_amount = -transaction.get_property('market_value', 0)
        else:
            cash_flow_amount = transaction.amount

        if cash_flow_amount is not None:
            cash_flow_amount = get_decimal(cash_flow_amount)  # why?
        return cash_flow_amount

    def add_transaction(self, transaction):
        cash_flow_amount = self._get_cash_flow_amount(transaction)

        if cash_flow_amount:  # don't need to include 0 or None
            self._transactions.append((transaction.date, cash_flow_amount))

    def get_transactions_in_range(self, start_date, end_date):
        return [
            transaction
            for transaction in self._transactions
            if start_date <= transaction[0] <= end_date  # ????
        ]

    def get_transactions_for_year(self, year):
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        return self.get_transactions_in_range(start_date, end_date)

    def get_total_cash_flow_amount_for_month(self, year, month):
        start_date = date(year, month, 1)
        days_in_month = calendar.monthrange(year, month)[1]
        end_date = date(year, month, days_in_month)
        cash_flow_transactions = self.get_transactions_in_range(
            start_date, end_date
        )  # first loop

        total_value = 0
        for _, amount in cash_flow_transactions:  # second loop
            total_value += amount
        return total_value

    def get_adjusted_cash_flow_amount_for_month(self, year, month):
        start_date = date(year, month, 1)
        days_in_month = calendar.monthrange(year, month)[1]
        end_date = date(year, month, days_in_month)
        cash_flow_transactions = self.get_transactions_in_range(
            start_date, end_date
        )  # first loop

        adjusted_value = 0
        for transaction_date, amount in cash_flow_transactions:  # second loop
            num_days_remaining_in_month = days_in_month - transaction_date.day
            adjusted_value += amount * get_decimal(
                num_days_remaining_in_month / days_in_month
            )
        return adjusted_value


class CurrentHolding:
    def __init__(self, symbol, quantity, cost_basis):
        self.symbol = symbol
        # quantity and cost_basis are decimals?
        self.quantity = quantity
        self.cost_basis = cost_basis
        self.portfolio_percentage = None
        # expand to historical qty, cost basis, market value
        self._historical_data = {}

    def update_holding(self, quantity, cost_basis):
        self.quantity += quantity
        self.cost_basis += cost_basis

    @staticmethod  # will caching work properly if multiple CurrentHolding
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
        if (
            self.quantity > 0
        ):  # can assume > 0? will cost_basis always be 0 if quantity is 0?
            return self.cost_basis / self.quantity
        else:
            return 0

    def set_percentage(self, total_portfolio_market_value):
        self.portfolio_percentage = self.market_value / total_portfolio_market_value


class CurrentHoldings:
    def __init__(self):
        # Current data to be a dict symbols of CurrentHolding obj ...
        self._current_data = {}
        # self._total_cost_basis = 0

    def add_transaction(self, symbol, date, quantity, cost_basis):
        if symbol not in self._current_data:
            self._current_data[symbol] = CurrentHolding(symbol, quantity, cost_basis)
        else:
            self._current_data[symbol].update_holding(quantity, cost_basis)

        # cost basis is constant so it can be pre-calculated
        # self._total_cost_basis += cost_basis  # not working

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
        for holding in self._current_data.values():
            # Protect against iex 'Unknown Symbol' error (ex. ALOG)
            if holding.quantity > 0:
                total += holding.market_value
        return total

    def get_current_holdings(self):
        current_holdings = []
        for holding in self._current_data.values():
            if holding.quantity > 0:
                holding.set_percentage(self.total_market_value)
                current_holdings.append(holding)
        return current_holdings

    def get_holding(self, symbol):
        return self._current_data.get(symbol)


def get_geometrically_linked_return(returns):
    if not returns:
        return None
    overall_return = returns[0] + 1
    if len(returns) > 1:
        for r in returns[1:]:
            overall_return *= r + 1
    return overall_return - 1


class TimePeriodReturn:
    @property
    def gain(self):
        return self.ending_balance - self.total_cash_flow_amount - self.starting_balance

    @property
    def return_pct(self):
        return self.gain / (self.starting_balance + self.adjusted_cash_flow_amount)


# How do I handle current month in calculations, since not a full month.
class MonthlyReturn(TimePeriodReturn):
    def __init__(
        self, month_index, year, starting_balance, ending_balance, cash_flow_store
    ):
        # Month is an integer (ex. 1=January, 2=February...12=December)
        self.month_index = month_index
        self.year = year
        self.month = calendar.month_name[month_index]

        # Balances a Decimal
        self.starting_balance = starting_balance
        self.ending_balance = ending_balance
        self._cash_flow_store = cash_flow_store

    @property
    def total_cash_flow_amount(self):
        return self._cash_flow_store.get_total_cash_flow_amount_for_month(
            self.year, self.month_index
        )

    @property
    def adjusted_cash_flow_amount(self):
        return self._cash_flow_store.get_adjusted_cash_flow_amount_for_month(
            self.year, self.month_index
        )


# Eventually this doesn't need to be a yearly return, but some arbitrary time period
# Can probably consolidate MonthlyReturn and YearlyReturn into generic time period returns
class YearlyReturn:
    def __init__(
        self, year, starting_balance, monthly_ending_balances, cash_flow_store
    ):
        # year is an integer
        # starging_balance is a Decimal
        # monthly_ending_balances is a list of Decimals for each month.
        #   Previous year will have 12, current year will have up to and including current month.
        self.year = year
        self.starting_balance = starting_balance
        self._cash_flow_store = cash_flow_store
        self.monthly_returns = self._get_monthly_returns(monthly_ending_balances)
        self.return_pct = self._get_yearly_return()

    # What to do with remaining months in year???? Just blank
    def _get_monthly_returns(self, ending_balances):
        monthly_data = []
        for i, ending_balance in enumerate(ending_balances):
            month_index = i + 1
            starting_balance = (
                self.starting_balance if i == 0 else ending_balances[i - 1]
            )
            monthly_return = MonthlyReturn(
                month_index,
                self.year,
                starting_balance,
                ending_balance,
                self._cash_flow_store,
            )
            monthly_data.append(monthly_return)
        return monthly_data

    def _get_yearly_return(self):
        returns = [r.return_pct for r in self.monthly_returns]
        return get_geometrically_linked_return(returns)


class MultiYearReturn:
    def __init__(
        self, start_year, end_year, starting_balance, ending_balances, cash_flow_store
    ):
        self.start_year = start_year
        self.end_year = end_year
        self.starting_balance = starting_balance
        # ending_balances is a dict of year keys with lists for months
        self._cash_flow_store = cash_flow_store
        self.ending_balances = ending_balances

    @property
    def yearly_returns(self):
        # Should this be dict, is ending balances dict in correct order
        yearly_data = []
        for year, monthly_ending_balances in self.ending_balances.items():
            starting_balance = (
                self.starting_balance
                if year == self.start_year
                else self.ending_balances[year - 1][-1]
            )
            yearly_return = YearlyReturn(
                year, starting_balance, monthly_ending_balances, self._cash_flow_store
            )
            yearly_data.append(yearly_return)
        return yearly_data

    @property
    def return_pct(self):
        returns = [r.return_pct for r in self.yearly_returns]
        return get_geometrically_linked_return(returns)

    @property
    def annualized_return(self):
        current_date = date.today()
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
