import io
import random
import utils
import matplotlib.pyplot as plt

from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont

# load font
protest_font_path = "resource/font/ProtestStrike-Regular.ttf"
protest_font = ImageFont.truetype(protest_font_path, size=110)
protest_font_small = ImageFont.truetype(protest_font_path, size=50)

ibm_font_path = 'resource/font/IBMPlexMono-Medium.ttf'
ibm_font = ImageFont.truetype(ibm_font_path, size=50)
ibm_font_small = ImageFont.truetype(ibm_font_path, size=30)

text_color_white = (255, 255, 255)
text_color_green = (46, 189, 133)
text_color_red = (246, 70, 93)


def red_or_green_color(way):
    if way == 'LONG':
        way_text_color = text_color_green
    else:
        way_text_color = text_color_red
    return way_text_color


def draw_symbol_to_entry_price(draw, symbol, amount, entry_price, realized=False):
    # symbol
    text_position = (110, 110)
    draw.text(text_position, symbol, font=ibm_font, fill=text_color_white)

    # position
    if realized:
        text_position = (110, 170)
        way = utils.long_or_short_closed_case(amount)
        draw.text(text_position, way, font=ibm_font, fill=red_or_green_color(way))
    else:
        text_position = (110, 170)
        way = utils.long_or_short(amount)
        draw.text(text_position, way, font=ibm_font, fill=red_or_green_color(way))

    # amount
    text_position = (110, 230)
    if utils.decimal_places(Decimal(amount)) > 8:
        amount = Decimal(amount).quantize(Decimal('.00000001'))
    amount_text = 'Size  ' + str(amount) + ' ' + symbol.replace('USDT', '')
    draw.text(text_position, amount_text, font=ibm_font_small, fill=text_color_white)

    # entry price
    text_position = (110, 270)
    if utils.decimal_places(Decimal(entry_price)) > 8:
        entry_price = Decimal(entry_price).quantize(Decimal('.00000001'))
    entry_text = 'Entry ' + str(entry_price)
    draw.text(text_position, entry_text, font=ibm_font_small, fill=text_color_white)

    return draw


def create_new_position_image(symbol: str, amount: str, entry_price: str) -> io.BytesIO:
    # get image file
    image = Image.open('resource/image/background_new_position.png')

    draw = ImageDraw.Draw(image)
    draw = draw_symbol_to_entry_price(draw, symbol, amount, entry_price)

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    return img_byte_arr


def create_position_image(symbol: str, amount: str, entry_price: str, mark_price: str, profit: str,
                          realized=False) -> io.BytesIO:
    # select image file
    if float(profit) > 0:
        image_path = f'resource/image/background_profit_{random.randint(1, 3)}.png'
    else:
        image_path = f'resource/image/background_loss_{random.randint(1, 3)}.png'

    image = Image.open(image_path)

    draw = ImageDraw.Draw(image)
    draw = draw_symbol_to_entry_price(draw, symbol, amount, entry_price, realized=realized)

    # mark price
    text_position = (110, 310)
    if utils.decimal_places(Decimal(mark_price)) > 8:
        mark_price = Decimal(mark_price).quantize(Decimal('.00000001'))
    mark_text = 'Mark  ' + str(mark_price)
    draw.text(text_position, mark_text, font=ibm_font_small, fill=text_color_white)

    # profit
    profit_text_color = text_color_green if float(profit) > 0 else text_color_red

    text_position = (85, 535)
    draw.text(text_position, '$', font=protest_font_small, fill=profit_text_color)

    text_position = (125, 498)
    if abs(float(profit)) < 1000:
        unrealized_profit = str(Decimal(profit).quantize(Decimal('.01')))
    elif 1000 < abs(float(profit)) < 10000:
        unrealized_profit = str(Decimal(profit).quantize(Decimal('.1')))
    else:
        unrealized_profit = str(Decimal(profit).quantize(Decimal('.0')))
    draw.text(text_position, unrealized_profit, font=protest_font, fill=profit_text_color)

    # realized
    if realized:
        text_position = (85, 463)
        realized_text = 'PROFIT'
        draw.text(text_position, realized_text, font=protest_font_small, fill=profit_text_color)
    else:
        text_position = (85, 463)
        realized_text = 'UNREALIZED'
        draw.text(text_position, realized_text, font=protest_font_small, fill=profit_text_color)

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    return img_byte_arr


def create_funding_chart(funding_data):
    times = [data['fundingTime'] for data in funding_data]
    rates = [float(data['fundingRate']) for data in funding_data]

    # 차트 생성
    plt.figure(figsize=(10, 5))
    plt.plot(times, rates, marker='o')
    plt.title('Funding Rate History')
    plt.xlabel('Time')
    plt.ylabel('Funding Rate')
    plt.grid(True)

    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png')
    img_stream.seek(0)
    return img_stream