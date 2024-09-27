

def long_or_short(amount):
    if float(amount) > 0:
        return '📈 Long'
    else:
        return '📉 SHORT'


def loss_or_profit(amount):
    if float(amount) > 0:
        return '수익 중 💰'
    else:
        return '손실 중 💸'
