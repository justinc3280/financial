from app.utils import current_date, get_decimal, get_month_name, get_num_days_in_month


class TimePeriodReturn:
    def __init__(
        self,
        starting_balance,
        ending_balance,
        holdings_manager,
        cash_flow_store,
        benchmark_holdings_manager,
        benchmark_return,
    ):
        self.starting_balance = starting_balance
        self.ending_balance = ending_balance
        self._holdings_manager = holdings_manager
        self._cash_flow_store = cash_flow_store

        self._benchmark_holdings_manager = benchmark_holdings_manager
        self._benchmark_return = benchmark_return

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
        if self._benchmark_return is not None:
            render['benchmark_return_pct'] = self._benchmark_return.return_pct
        if self.subperiod_returns:
            render['subperiod_returns'] = [
                period.render() for period in self.subperiod_returns
            ]
        return render


class MonthlyReturn(TimePeriodReturn):
    def __init__(
        self,
        year,
        month,
        holdings_manager,
        cash_flow_store=None,
        benchmark_holdings_manager=None,
    ):
        self.year = year
        self.month = month
        self.month_name = get_month_name(month)

        if cash_flow_store:
            self.total_cash_flow_amount, self.adjusted_cash_flow_amount = cash_flow_store.get_cash_flow_amount_for_month(
                year, month
            )
        else:
            self.total_cash_flow_amount = 0
            self.adjusted_cash_flow_amount = 0

        starting_balance = holdings_manager.get_total_holdings_starting_market_value_for_month(
            year, month
        )
        ending_balance = holdings_manager.get_total_holdings_market_value_for_month(
            year, month
        )

        if benchmark_holdings_manager:
            benchmark_return = self.__class__(
                year, month, holdings_manager=benchmark_holdings_manager
            )
        else:
            benchmark_return = None

        super().__init__(
            starting_balance,
            ending_balance,
            holdings_manager,
            cash_flow_store,
            benchmark_holdings_manager,
            benchmark_return,
        )

    def _generate_subperiod_returns(self):
        self.subperiod_returns = None

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
        holdings_manager,
        cash_flow_store=None,
        benchmark_holdings_manager=None,
    ):
        self.year = year
        starting_balance = holdings_manager.get_starting_total_market_value_for_year(
            year
        )
        ending_balance = holdings_manager.get_monthly_total_market_value_for_year(year)[
            -1
        ]

        if benchmark_holdings_manager:
            benchmark_return = self.__class__(
                year, holdings_manager=benchmark_holdings_manager
            )
        else:
            benchmark_return = None

        super().__init__(
            starting_balance,
            ending_balance,
            holdings_manager,
            cash_flow_store,
            benchmark_holdings_manager,
            benchmark_return,
        )

    def _generate_subperiod_returns(self):
        monthly_returns = []
        monthly_ending_balances = self._holdings_manager.get_monthly_total_market_value_for_year(
            self.year
        )
        for month, ending_balance in enumerate(monthly_ending_balances, start=1):
            monthly_return = MonthlyReturn(
                self.year,
                month,
                self._holdings_manager,
                self._cash_flow_store,
                self._benchmark_holdings_manager,
            )
            monthly_returns.append(monthly_return)
        self.subperiod_returns = monthly_returns

    def render(self):
        render = super().render()
        render['year'] = self.year
        return render


class MultiYearReturn(TimePeriodReturn):
    def __init__(
        self,
        start_year,
        end_year,
        holdings_manager,
        cash_flow_store=None,
        benchmark_holdings_manager=None,
    ):
        self.start_year = start_year
        self.end_year = end_year

        starting_balance = holdings_manager.get_starting_total_market_value_for_year(
            start_year
        )
        ending_balance = holdings_manager.get_monthly_total_market_value_for_year(
            end_year
        )[-1]

        if benchmark_holdings_manager:
            benchmark_return = self.__class__(
                start_year, end_year, holdings_manager=benchmark_holdings_manager
            )
        else:
            benchmark_return = None

        super().__init__(
            starting_balance,
            ending_balance,
            holdings_manager,
            cash_flow_store,
            benchmark_holdings_manager,
            benchmark_return,
        )

    def _generate_subperiod_returns(self):
        yearly_returns = []
        for year in range(self.start_year, self.end_year + 1):

            monthly_ending_balances = self._holdings_manager.get_monthly_total_market_value_for_year(
                year
            )
            yearly_return = YearlyReturn(
                year,
                self._holdings_manager,
                self._cash_flow_store,
                self._benchmark_holdings_manager,
            )
            yearly_returns.append(yearly_return)
        self.subperiod_returns = yearly_returns

    @property
    def annualized_return(self):
        num_months = 0
        for year in range(self.start_year, self.end_year + 1):
            if year == current_date.year:
                num_months += current_date.month - 1
                days_in_month = get_num_days_in_month(year, current_date.month)
                percent_of_month = round(current_date.day / days_in_month, 4)
                num_months += percent_of_month
            else:
                num_months += 12
        num_years = num_months / 12
        return (self.return_pct + 1) ** get_decimal((1 / num_years)) - 1

    def render(self):
        render = super().render()
        render['annualized_return'] = self.annualized_return
        if self._benchmark_return is not None:
            render[
                'benchmark_annualized_return'
            ] = self._benchmark_return.annualized_return
        return render

