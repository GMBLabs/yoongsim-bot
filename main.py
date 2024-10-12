import asyncio
import logging
import os
import image_utils

from dotenv import load_dotenv
from decimal import Decimal
from telegram import Update
from telegram.ext import CommandHandler, Application, CallbackContext
from binance import BinanceSocketManager, AsyncClient

# load env
load_dotenv()
TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
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


async def connect_websocket(async_client, application):
    while True:
        try:
            bsm = BinanceSocketManager(async_client)
            async with bsm.futures_user_socket() as stream:
                while True:
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


async def process_message(msg, application):
    global ps

    logger.info(f"Received message: {msg}")
    if msg['e'] == 'ACCOUNT_UPDATE':
        account = msg['a']

        # check new position & position change
        for position in account['P']:
            if ps[position['s']]['positionAmt'] == Decimal(0):
                # new position
                image_stream = image_utils.create_new_position_image(
                    position['s'],
                    position['pa'],
                    position['ep'],
                )

                await application.bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=image_stream,
                    caption=f"{TRADER_NAME}님이 트레이더가 신규 포지션을 생성했습니다 !"
                )
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
                    order['s'],
                    p['positionAmt'],
                    p['entryPrice'],
                    p['markPrice'],
                    p['realizedProfit'],
                    True
                )

                await application.bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=image,
                    caption=f"{TRADER_NAME}님이 트레이더가 포지션을 종료했습니다 !"
                )

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


async def periodic_update_positions(async_client):
    while True:
        await asyncio.sleep(10)
        await update_positions(async_client)


async def update_positions(async_client):
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


async def run_telegram_bot(application):
    await application.initialize()
    await application.start()
    await application.updater.start_polling()


async def send_ping(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('pong')


async def send_position(update: Update, context: CallbackContext) -> None:
    response_counter = 0
    for symbol, position in ps.items():
        if position['positionAmt'] == Decimal(0) and position['unRealizedProfit'] == Decimal(0):
            continue

        image_stream = image_utils.create_position_image(
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
        # todo: no positions
        await update.message.reply_text('포지션이 존재하지 않습니다.')


async def send_touch_grass(update: Update, context: CallbackContext) -> None:
    await update.message.reply_photo(photo='resource/image/touch_grass.png', caption='잔디를 만지는 중 입니다...')


async def main():
    # init binance
    async_client = await AsyncClient.create(BINANCE_API_KEY, BINANCE_API_SECRET)

    # init tg
    application = Application.builder().token(TELEGRAM_API_TOKEN).build()
    application.add_handler(CommandHandler('ping', send_ping))
    application.add_handler(CommandHandler('positions', send_position))
    application.add_handler(CommandHandler('grass', send_touch_grass))

    # init positions
    await update_positions(async_client)

    # run tg & watch positions
    await asyncio.gather(
        connect_websocket(async_client, application),
        periodic_update_positions(async_client),
        run_telegram_bot(application)
    )


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
