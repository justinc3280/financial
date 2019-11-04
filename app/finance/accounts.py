from datetime import date
from app.finance.stocks import Stocks
from app.finance.utils import get_decimal, merge_dict_of_lists


class AccountData:
    def __init__(self, account):
        self.name = account.name
        self._starting_balance = account.starting_balance
        self._category = account.category
        self._is_brokerage_account = (
            True if account.category.name == 'Brokerage Account' else False
        )
        self.transactions = sorted(account.transactions, key=lambda x: x.date)
        self._ending_monthly_balances = self._generate_monthly_ending_balances()

    def __repr__(self):
        return '<AccountData {}>'.format(self.name)

    def _generate_monthly_ending_balances(self):
        ending_monthly_balances = {}
        current_balance = get_decimal(self._starting_balance)

        for transaction in self.transactions:
            previous_balance = current_balance
            current_balance += get_decimal(transaction.amount)

            transaction_year = transaction.date.year
            current_date = date.today()
            num_months = (
                12 if transaction_year < current_date.year else current_date.month
            )

            # add year and use previous values for entire year
            if transaction_year not in ending_monthly_balances:
                ending_monthly_balances[transaction_year] = [
                    previous_balance for _ in range(0, num_months)
                ]

            # overwrite the values for the remainder of the year after transaction
            for month_index in range(transaction.date.month - 1, num_months):
                ending_monthly_balances[transaction_year][month_index] = current_balance

            # update all future years with new values up until end_date
            for i in range(transaction_year + 1, current_date.year + 1):
                num_months = 12 if i < current_date.year else current_date.month
                ending_monthly_balances[i] = [
                    current_balance for _ in range(0, num_months)
                ]

        return ending_monthly_balances

    def get_monthly_ending_balances(self):
        return self._ending_monthly_balances


class AccountManager:
    def __init__(self, accounts=[]):
        self._accounts = []
        self._total_monthly_balances = {}
        self._monthly_balances_by_account = {}
        self._stocks = None
        for account in accounts:
            self.add_account(account)

    def add_account(self, account):
        if not isinstance(account, AccountData):
            account = AccountData(account)

        self._accounts.append(account)
        account_monthly_balances = account.get_monthly_ending_balances()
        self._monthly_balances_by_account[account.name] = account_monthly_balances

        self._total_monthly_balances = merge_dict_of_lists(
            self._total_monthly_balances, account_monthly_balances
        )

        if account._is_brokerage_account:
            if not hasattr(self, '_stocks'):
                self._stocks = Stocks()

            self._stocks.add_account(account)

    def get_accounts_monthly_ending_balances_for_year(self, year):
        ending_balances = {}
        for account_name, yearly_data in self._monthly_balances_by_account.items():
            if year in yearly_data:
                ending_balances[account_name] = yearly_data.get(year)
        return ending_balances

    def get_total_monthly_ending_balances_for_year(self, year):
        return self._total_monthly_balances.get(year)

    def get_current_stock_holdings(self):
        if not self._stocks:
            return None
        return self._stocks.get_current_holdings()

    def get_stocks_monthly_market_values(self, year):
        if not self._stocks:
            return None
        return self._stocks.get_monthly_total_market_value_for_year(year)

    def get_stocks_monthly_data_for_year(self, year):
        if not self._stocks:
            return None
        return self._stocks.get_monthly_data_for_year(year)

    def get_brokerage_roi_data(self, year):
        if not self._stocks:
            return None
        return self._stocks.get_monthly_roi_data(year)

    def get_brokerage_compounded_roi(self, start_year, end_year):
        if not self._stocks:
            return None
        return self._stocks.get_compounded_roi(start_year, end_year)
