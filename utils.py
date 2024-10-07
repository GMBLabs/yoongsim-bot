import io
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont


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


def load_image(image_path: str) -> io.BytesIO:
    img_byte_arr = io.BytesIO()
    with open(image_path, 'rb') as image_file:
        img_byte_arr.write(image_file.read())
    img_byte_arr.seek(0)
    return img_byte_arr


def create_position_image(symbol: str, amount: str, entry_price: str, mark_price: str,profit: str) -> io.BytesIO:
    # select image file
    if float(profit) > 0:
        image_path = 'resource/image/background_profit.png'
    else:
        image_path = 'resource/image/background_loss.png'

    # load image
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    # load font
    unbounded_font_path = "resource/font/Unbounded-SemiBold.ttf"
    unbounded_font = ImageFont.truetype(unbounded_font_path, size=110)
    unbounded_font_small = ImageFont.truetype(unbounded_font_path, size=50)

    ibm_font_path = 'resource/font/IBMPlexMono-Medium.ttf'
    ibm_font = ImageFont.truetype(ibm_font_path, size=50)
    ibm_font_small = ImageFont.truetype(ibm_font_path, size=30)

    # symbol
    text_position = (170, 130)
    text_color_white = (255, 255, 255)
    draw.text(text_position, symbol, font=ibm_font, fill=text_color_white)

    # position
    text_position = (170, 190)
    way = long_or_short(amount)
    if way == 'LONG':
        way_text_color = (46, 189, 133)
    else:
        way_text_color = (246, 70, 93)
    draw.text(text_position, way, font=ibm_font, fill=way_text_color)

    # entry price
    text_position = (170, 250)
    entry_price = 'Entry ' + entry_price
    draw.text(text_position, entry_price, font=ibm_font_small, fill=text_color_white)

    # mark price
    text_position = (170, 290)
    mark_price = 'Mark  ' + mark_price
    draw.text(text_position, mark_price, font=ibm_font_small, fill=text_color_white)

    # profit
    text_position = (85, 500)
    profit_text_color = (46, 189, 133) if float(profit) > 0 else (246, 70, 93)
    draw.text(text_position, '$', font=unbounded_font_small, fill=profit_text_color)

    text_position = (125, 450)
    profit_text_color = (46, 189, 133) if float(profit) > 0 else (246, 70, 93)
    if abs(float(profit)) < 1000:
        unrealized_profit = str(Decimal(profit).quantize(Decimal('.01')))
    elif 1000 < abs(float(profit)) < 10000:
        unrealized_profit = str(Decimal(profit).quantize(Decimal('.1')))
    else:
        unrealized_profit = str(Decimal(profit).quantize(Decimal('.0')))
    draw.text(text_position, unrealized_profit, font=unbounded_font, fill=profit_text_color)

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    return img_byte_arr
