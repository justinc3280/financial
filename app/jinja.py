from decimal import Decimal, ROUND_HALF_UP


def percentage(fraction):
    return '{:.2%}'.format(fraction)


def money(amount, show_as_positive=False):
    if amount is None:
        return None

    if isinstance(amount, Decimal):
        amount = amount.quantize(Decimal('1.00'), rounding=ROUND_HALF_UP)
    else:
        amount = round(amount, 2)

    if show_as_positive:
        amount = abs(amount)

    if amount >= 0:
        return '${:,.2f}'.format(amount)
    else:
        return '(${:,.2f})'.format(abs(amount))


def date(date):
    return '{:%m/%d/%Y}'.format(date)


def int_or_float(number):
    if number.is_integer():
        return '{}'.format(int(number))
    else:
        return number


def sort_by_rank(keys):
    return sorted(keys, key=lambda element: element[0].rank)


def register_jinja_filters(environment):
    environment.filters.update(
        {
            'percentage': percentage,
            'money': money,
            'date': date,
            'int_or_float': int_or_float,
            'sort_by_rank': sort_by_rank,
        }
    )
