import asyncio
import logging
import os
import image_utils
import time

from dotenv import load_dotenv
from decimal import Decimal
from telegram import Update
from telegram.ext import CommandHandler, Application, CallbackContext
from binance import BinanceSocketManager, AsyncClient
from pybit.unified_trading import HTTP, WebSocket

# load env
load_dotenv()
TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET')
TRADER_NAME = os.getenv('TRADER_NAME')

# logging setting
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# position
ps = {}
bybit_ps = {}


async def connect_websocket(async_client, application):
    while True:
        try:
            start_time = time.time()

            bsm = BinanceSocketManager(async_client)
            async with bsm.futures_user_socket() as stream:
                while True:
                    if time.time() - start_time > 86400:
                        logger.info("restart websocket connection...")
                        break

                    try:
                        msg = await stream.recv()
                        if msg:
                            await process_message(msg, application)
                    except asyncio.TimeoutError:
                        logger.info("WebSocket timeout error")
                    except Exception as e:
                        logger.error(f"WebSocket error: {e}")

        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            await asyncio.sleep(5)


async def connect_bybit_websocket(application):
    ws = WebSocket(
        testnet=False,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
        channel_type="private",
    )

    def callback_with_application(message):
        process_bybit_message(message, application)

    ws.subscribe('position', callback=callback_with_application)

    while True:
        try:
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await asyncio.sleep(5)


async def process_bybit_message(message, application):
    event = message['topic']
    data = message['data']

    if 'position' in event:
        if data['size'] == 0:
            image = image_utils.create_position_image(
                'bybit',
                data['symbol'],
                data['size'],
                data['entryPrice'],
                data['markPrice'],
                data['curRealisedPnl'],
                True
            )

            close_msg = await application.bot.send_photo(
                chat_id=TELEGRAM_CHAT_ID,
                photo=image,
                caption=f"{TRADER_NAME}님이 포지션을 종료했습니다 !"
            )

            # await application.bot.pin_chat_message(
            #     chat_id=TELEGRAM_CHAT_ID,
            #     message_id=close_msg.message_id,
            #     disable_notification=True
            # )
        else:
            # todo: new position
            print(f"New or updated position: {data}")


async def process_message(msg, application):
    global ps

    # logger.info(f"Received message: {msg}")
    if msg['e'] == 'ACCOUNT_UPDATE':
        account = msg['a']

        # check new position & position change
        for position in account['P']:
            if ps[position['s']]['positionAmt'] == Decimal(0):
                # new position
                image_stream = image_utils.create_new_position_image(
                    'binance',
                    position['s'],
                    position['pa'],
                    position['ep'],
                )

                new_msg = await application.bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=image_stream,
                    caption=f"{TRADER_NAME}님이 신규 포지션을 생성했습니다 !",
                    disable_notification=True
                )

                # await application.bot.pin_chat_message(chat_id=TELEGRAM_CHAT_ID, message_id=new_msg.message_id)
    if msg['e'] == 'ORDER_TRADE_UPDATE':
        order = msg['o']
        if order['X'] == 'FILLED':
            p = ps[order['s']]

            if order['S'] == 'SELL':
                p['positionAmt'] = p['positionAmt'] - Decimal(order['l'])
            else:
                p['positionAmt'] = p['positionAmt'] + Decimal(order['l'])
            p['realizedProfit'] = p['realizedProfit'] + Decimal(order['rp'])

            if p['positionAmt'] == Decimal(0):
                # if position close
                # exception : if position close and open at the same time ( reverse )
                # exception2 : if bot restart realized profit was reset
                image = image_utils.create_position_image(
                    'binance',
                    order['s'],
                    p['positionAmt'],
                    p['entryPrice'],
                    p['markPrice'],
                    p['realizedProfit'],
                    True
                )

                close_msg = await application.bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=image,
                    caption=f"{TRADER_NAME}님이 포지션을 종료했습니다 !"
                )

                # await application.bot.pin_chat_message(
                #     chat_id=TELEGRAM_CHAT_ID,
                #     message_id=close_msg.message_id,
                #     disable_notification=True
                # )

                # reset position
                p['entryPrice'] = Decimal(0)
                p['markPrice'] = Decimal(0)
                p['unRealizedProfit'] = Decimal(0)
                p['realizedProfit'] = Decimal(0)

            else:
                # position change
                pass

        if order['X'] == 'PARTIALLY_FILLED':
            p = ps[order['s']]

            if order['S'] == 'SELL':
                p['positionAmt'] = p['positionAmt'] - Decimal(order['l'])
            else:
                p['positionAmt'] = p['positionAmt'] + Decimal(order['l'])
            p['realizedProfit'] = p['realizedProfit'] + Decimal(order['rp'])


async def periodic_update_positions(async_client, bybit_client):
    while True:
        await asyncio.sleep(10)
        await update_binance_positions(async_client)
        await update_bybit_positions(bybit_client)


async def update_binance_positions(async_client):
    global ps

    for position in await async_client.futures_position_information():
        if position['symbol'] not in ps:
            # init position
            ps[position['symbol']] = {
                'positionAmt': Decimal(position['positionAmt']),
                'entryPrice': Decimal(position['entryPrice']),
                'markPrice': Decimal(position['markPrice']),
                'unRealizedProfit': Decimal(position['unRealizedProfit']),
                'realizedProfit': Decimal(0),
            }
        else:
            # update position
            ps[position['symbol']]['entryPrice'] = Decimal(position['entryPrice'])
            ps[position['symbol']]['markPrice'] = Decimal(position['markPrice'])
            ps[position['symbol']]['unRealizedProfit'] = Decimal(position['unRealizedProfit'])
            ps[position['symbol']]['realizedProfit'] = Decimal(0)


async def update_bybit_positions(bybit_client):
    response = bybit_client.get_positions(category="linear", settleCoin="USDT")
    positions = response['result']['list']

    for position in positions:
        if position['symbol'] not in bybit_ps:
            bybit_ps[position['symbol']] = {
                'positionAmt': Decimal(position['size']),
                'entryPrice': Decimal(position['avgPrice']),
                'markPrice': Decimal(position['markPrice']),
                'unRealizedProfit': Decimal(position['unrealisedPnl']),
                'realizedProfit': Decimal(position['cumRealisedPnl']),
            }
        else:
            bybit_ps[position['symbol']]['entryPrice'] = Decimal(position['avgPrice'])
            bybit_ps[position['symbol']]['markPrice'] = Decimal(position['markPrice'])
            bybit_ps[position['symbol']]['unRealizedProfit'] = Decimal(position['unrealisedPnl'])
            bybit_ps[position['symbol']]['realizedProfit'] = Decimal(position['cumRealisedPnl'])


async def run_telegram_bot(application):
    await application.initialize()
    await application.start()
    await application.updater.start_polling()


async def send_ping(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('pong')


async def send_position(update: Update, context: CallbackContext) -> None:
    response_counter = 0

    # binance
    for symbol, position in ps.items():
        if position['positionAmt'] == Decimal(0) and position['unRealizedProfit'] == Decimal(0):
            continue

        image_stream = image_utils.create_position_image(
            'binance',
            symbol,
            position['positionAmt'],
            position['entryPrice'],
            position['markPrice'],
            position['unRealizedProfit'],
            False
        )

        response_counter += 1
        await update.message.reply_photo(photo=image_stream)

    # bybit
    for symbol, position in bybit_ps.items():
        if position['positionAmt'] == Decimal(0) and position['unRealizedProfit'] == Decimal(0):
            continue

        image_stream = image_utils.create_position_image(
            'bybit',
            symbol,
            position['positionAmt'],
            position['entryPrice'],
            position['markPrice'],
            position['unRealizedProfit'],
            False
        )

        response_counter += 1
        await update.message.reply_photo(photo=image_stream)

    if response_counter == 0:
        await update.message.reply_photo(
            photo='resource/image/touch_grass.png',
            caption='잔디를 만지는 중 입니다...'
        )


# async def send_oi(update: Update, context: CallbackContext) -> None:
#     await update.message.reply_text('oi')
#
#
# async def send_long_short_ratio(update: Update, context: CallbackContext) -> None:
#     await update.message.reply_text('long_short_ratio')
#
#
# async def send_funding_rate(update: Update, context: CallbackContext) -> None:
#     ticker = context.args[0]
#     funding_data = await fetch_funding_data()
#
#     chart_image = create_funding_chart(funding_data)
#
#     await send_chart_to_telegram(chart_image)


async def main():
    # init binance
    binance_async_client = await AsyncClient.create(BINANCE_API_KEY, BINANCE_API_SECRET)

    # init bybit
    bybit_client = HTTP(
        testnet=False,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
    )

    # init tg
    application = Application.builder().token(TELEGRAM_API_TOKEN).build()
    application.add_handler(CommandHandler('ping', send_ping))
    application.add_handler(CommandHandler('positions', send_position))

    # init positions
    await update_binance_positions(binance_async_client)
    await update_bybit_positions(bybit_client)

    # run tg & watch positions
    await asyncio.gather(
        connect_websocket(binance_async_client, application),
        periodic_update_positions(binance_async_client, bybit_client),
        run_telegram_bot(application)
    )


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
