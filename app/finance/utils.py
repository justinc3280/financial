import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def get_ending_month_date(year, month_num):
    ending_day = calendar.monthrange(year, month_num)[1]
    return date(year, month_num, ending_day)


def get_ending_month_dates_for_year(year):
    ending_dates = []
    for month_num in range(1, 13):
        ending_dates.append(get_ending_month_date(year, month_num))
    return ending_dates


def merge_lists(x, y):
    new_list = []
    long_list = x if len(x) >= len(y) else y
    short_list = y if len(x) >= len(y) else x
    for index, data in enumerate(long_list):
        if index < len(short_list):
            new_data = data + short_list[index]
        else:
            new_data = data
        new_list.append(new_data)
    return new_list


def merge_dict_of_lists(x, y):
    keys = set()
    keys.update(x.keys())
    keys.update(y.keys())

    total_data = {}
    for key in keys:
        x_data = x.get(key)
        y_data = y.get(key)
        if x_data and y_data:
            data = merge_lists(x_data, y_data)
        elif x_data:
            data = x_data
        elif y_data:
            data = y_data
        if data:
            total_data[key] = data

    return total_data


def get_decimal(flt):
    return Decimal(str(flt))


def round_decimal(decimal):
    decimal = get_decimal(decimal)
    return decimal.quantize(Decimal('1.00'), rounding=ROUND_HALF_UP)
