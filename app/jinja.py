from app import app

@app.template_filter()
def percentage(fraction):
    return '{:.2%}'.format(fraction)

@app.template_filter()
def money(amount, show_as_positive=False):
    if show_as_positive:
        amount = -amount if amount < 0 else amount # maybe not right

    if amount >= 0:
        return '${:,.2f}'.format(amount)
    else:
        amount = -amount
        return '(${:,.2f})'.format(amount)


@app.template_filter()
def date(date):
    return '{:%m/%d/%Y}'.format(date)

@app.template_filter()
def int_or_float(number):
    if number.is_integer():
        return '{}'.format(int(number))
    else:
        return number

@app.template_filter()
def sort_by_rank(keys):
    return sorted(keys, key=lambda element: element[0].rank)
