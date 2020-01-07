import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

current_date = date.today()


def get_month_name(month_num):
    return calendar.month_name[month_num]


def get_num_days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def get_previous_month_and_year(year, month_num):
    if month_num == 1:
        prev_year = year - 1
        prev_month_num = 12
    else:
        prev_year = year
        prev_month_num = month_num - 1
    return prev_year, prev_month_num


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
