def long_or_short(amount):
    if float(amount) > 0:
        return 'LONG'
    else:
        return 'SHORT'


def loss_or_profit(amount):
    if float(amount) > 0:
        return '수익 중 💰'
    else:
        return '손실 중 💸'


def decimal_places(decimal_value):
    return -decimal_value.as_tuple().exponent if decimal_value.as_tuple().exponent < 0 else 0
