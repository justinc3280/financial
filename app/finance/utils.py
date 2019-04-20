import calendar
from datetime import date


def get_ending_month_date(year, month_num):
    ending_day = calendar.monthrange(year, month_num)[1]
    return date(year, month_num, ending_day)


def get_ending_month_dates_for_year(year):
    ending_dates = []
    for month_num in range(1, 13):
        ending_dates.append(get_ending_month_date(year, month_num))
    return ending_dates
