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


def merge_lists(x, y, round_to=2):
    new_list = []
    long_list = x if len(x) >= len(y) else y
    short_list = y if len(x) >= len(y) else x
    for index, data in enumerate(long_list):
        if index < len(short_list):
            new_data = round(data + short_list[index], round_to)
        else:
            new_data = data
        new_list.append(new_data)
    return new_list
