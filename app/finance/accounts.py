from datetime import date
from app.finance.stocks import Stocks
from app.finance.utils import merge_lists


class AccountData:
    def __init__(self, account):
        self.name = account.name
        self._starting_balance = account.starting_balance
        self._category = account.category
        self._transactions = sorted(account.transactions, key=lambda x: x.date)
        self._ending_monthly_balances = self._generate_monthly_ending_balances()

    def __repr__(self):
        return '<AccountData {}>'.format(self.name)

    def _generate_monthly_ending_balances(self):
        ending_monthly_balances = {}
        current_balance = self._starting_balance

        for transaction in self._transactions:
            previous_balance = current_balance
            current_balance = round(current_balance + transaction.amount, 2)

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


class BrokerageAccount(AccountData):
    def __init__(self, account):
        AccountData.__init__(self, account)
        self.is_brokerage_account = True
        self._stocks = Stocks(self._transactions)  # N^2, bad

    def get_current_stock_holdings(self):
        return self._stocks.get_current_holdings()

    def get_stocks_monthly_market_values(self, year):
        return self._stocks.get_monthly_total_market_value_for_year(year)


class AccountsManager:
    def __init__(self, accounts=[]):
        self._accounts = []
        self._total_monthly_balances = {}
        self._monthly_balances_by_account = {}
        self._current_stock_holdings = {}
        self._stock_monthly_data = {}
        for account in accounts:
            self.add_account(account)

    def add_account(self, account):
        self._accounts.append(account)
        account_monthly_balances = account.get_monthly_ending_balances()
        self._monthly_balances_by_account[account.name] = account_monthly_balances

        self._total_monthly_balances = self.merge_yearly_data(
            self._total_monthly_balances, account_monthly_balances
        )

        if account.is_brokerage_account:
            account_current_holdings = account.get_current_stock_holdings()
            for symbol, yearly_data in account_current_holdings.items():
                if symbol not in self._current_stock_holdings:
                    new_yearly_data = yearly_data
                else:
                    new_yearly_data = self.merge_yearly_data(
                        self._current_stock_holdings[symbol], yearly_data
                    )

                self._current_stock_holdings[symbol] = new_yearly_data
            # need to update portfolio percentages

    @staticmethod
    def merge_yearly_data(x, y):
        years = set()
        years.update(x.keys())
        years.update(y.keys())

        total_yearly_data = {}
        for year in years:
            x_data = x.get(year)
            y_data = y.get(year)
            if x_data and y_data:
                data = merge_lists(x_data, y_data)
            elif x_data:
                data = x_data
            elif y_data:
                data = y_data
        if data:
            total_yearly_data[year] = data
        return total_yearly_data

    def get_accounts_monthly_ending_balances_for_year(self, year):
        ending_balances = {}
        for account_name, yearly_data in self._monthly_balances_by_account.items():
            if year in yearly_data:
                ending_balances[account_name] = yearly_data.get(year)
        return ending_balances

    def get_total_monthly_ending_balances_for_year(self, year):
        return self._total_monthly_balances.get(year)

    def get_current_stock_holdings(self):
        return self._current_stock_holdings

    def get_stocks_monthly_market_values(self, year):
        total_monthly_market_value = {}
        for account in self._brokerage_accounts:
            values = account.get_stocks_monthly_market_values()

