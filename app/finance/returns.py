import calendar
import logging

from app.finance.utils import current_date, get_decimal

logger = logging.getLogger(__name__)


class TimePeriodReturn:
    def __init__(
        self, starting_balance, ending_balance, cash_flow_store, benchmark_return=None
    ):
        # Make better by passing in balance manager and benchmark balance manager
        # instead of hassle of dealing with ending balances dict
        self.starting_balance = starting_balance
        self.ending_balance = ending_balance
        self._cash_flow_store = cash_flow_store

        if benchmark_return:
            self.benchmark_return = benchmark_return

        self._generate_subperiod_returns()

    # Abstract method
    def _generate_subperiod_returns(self):
        raise NotImplementedError

    @property
    def return_pct(self):
        returns = [r.return_pct for r in self.subperiod_returns]
        return self.get_geometrically_linked_return(returns)

    @staticmethod
    def get_geometrically_linked_return(returns):
        if not returns:
            return None
        overall_return = returns[0] + 1
        if len(returns) > 1:
            for r in returns[1:]:
                overall_return *= r + 1
        return overall_return - 1

    def render(self):
        render = {
            'starting_balance': self.starting_balance,
            'ending_balance': self.ending_balance,
            'return_pct': self.return_pct,
        }
        if hasattr(self, 'benchmark_return'):
            render['benchmark_return_pct'] = self.benchmark_return.return_pct
        if self.subperiod_returns:
            render['subperiod_returns'] = [
                period.render() for period in self.subperiod_returns
            ]
        return render


class MonthlyReturn(TimePeriodReturn):
    def __init__(
        self,
        month,
        year,
        starting_balance,
        ending_balance,
        cash_flow_store=None,
        benchmark_start=None,
        benchmark_end=None,
    ):
        self.year = year
        self.month = month
        self.month_name = calendar.month_name[month]

        if cash_flow_store:
            self.total_cash_flow_amount, self.adjusted_cash_flow_amount = cash_flow_store.get_cash_flow_amount_for_month(
                year, month
            )
        else:
            self.total_cash_flow_amount = 0
            self.adjusted_cash_flow_amount = 0

        if benchmark_start and benchmark_end:
            benchmark_return = self.create_benchmark_return(
                month, year, benchmark_start, benchmark_end
            )
        else:
            benchmark_return = None

        super().__init__(
            starting_balance, ending_balance, cash_flow_store, benchmark_return
        )

    def _generate_subperiod_returns(self):
        self.subperiod_returns = None

    @classmethod
    def create_benchmark_return(cls, month, year, benchmark_start, benchmark_end):
        return cls(month, year, benchmark_start, benchmark_end)

    @property
    def gain(self):
        return self.ending_balance - self.total_cash_flow_amount - self.starting_balance

    @property
    def return_pct(self):
        # For MonthlyReturns, use modified dietz formula
        return self.gain / (self.starting_balance + self.adjusted_cash_flow_amount)

    def render(self):
        render = super().render()
        render['month_name'] = self.month_name
        render['gain'] = self.gain
        render['total_cash_flow_amount'] = self.total_cash_flow_amount
        render['adjusted_cash_flow_amount'] = self.adjusted_cash_flow_amount
        return render


class YearlyReturn(TimePeriodReturn):
    def __init__(
        self,
        year,
        starting_balance,
        ending_balances,
        cash_flow_store=None,
        benchmark_start=None,
        benchmark_ending_balances=None,
    ):
        self.year = year
        self.ending_balances = ending_balances
        ending_balance = ending_balances[year][-1]

        self.benchmark_start = benchmark_start
        self.benchmark_ending_balances = benchmark_ending_balances

        if benchmark_start and benchmark_ending_balances:
            benchmark_return = self.create_benchmark_return(
                year, benchmark_start, benchmark_ending_balances
            )
        else:
            benchmark_return = None

        super().__init__(
            starting_balance, ending_balance, cash_flow_store, benchmark_return
        )

    def _generate_subperiod_returns(self):
        monthly_returns = []
        starting_balance = self.starting_balance
        benchmark_start = self.benchmark_start
        for year, monthly_ending_balances in self.ending_balances.items():
            for month, ending_balance in enumerate(monthly_ending_balances, start=1):
                benchmark_end = (
                    self.benchmark_ending_balances[year][month - 1]
                    if hasattr(self, 'benchmark_return')
                    else None
                )

                monthly_return = MonthlyReturn(
                    month,
                    year,
                    starting_balance,
                    ending_balance,
                    self._cash_flow_store,
                    benchmark_start,
                    benchmark_end,
                )
                monthly_returns.append(monthly_return)
                starting_balance = ending_balance
                benchmark_start = benchmark_end
        self.subperiod_returns = monthly_returns

    @classmethod
    def create_benchmark_return(cls, year, benchmark_start, benchmark_ending_balances):
        return cls(year, benchmark_start, benchmark_ending_balances)

    def render(self):
        render = super().render()
        render['year'] = self.year
        return render


class MultiYearReturn(TimePeriodReturn):
    def __init__(
        self,
        start_year,
        end_year,
        starting_balance,
        ending_balances,
        cash_flow_store,
        benchmark_start=None,
        benchmark_ending_balances=None,
    ):
        self.start_year = start_year
        self.end_year = end_year
        self.ending_balances = ending_balances

        max_year = max(ending_balances.keys())
        ending_balance = ending_balances[max_year][-1]
        super().__init__(starting_balance, ending_balance, cash_flow_store)

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

    def render(self):
        render = super().render()
        render['annualized_return'] = self.annualized_return
        return render
