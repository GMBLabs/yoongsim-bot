import asyncio
import aiohttp
import websockets
import json
import logging
import os
import utils

from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import CommandHandler, Application, CallbackContext

from binance import BinanceSocketManager, AsyncClient

# 환경 변수 로드
load_dotenv()
TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')

# 로깅 설정
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# 포지션 정보 저장
ps = {}


async def process_message(msg, application):
    if msg['e'] == 'ORDER_TRADE_UPDATE':
        order = msg['o']
        if order['x'] in ['TRADE', 'NEW', 'FILLED']:
            # update
            ps[order['s']] = {
                'positionAmt': order['z'],
                'entryPrice': order['Z'],
                'unRealizedProfit': order['up']
            }

            message = (
                f"Order Update:\n"
                f"Symbol: {order['s']}\n"
                f"Quantity: {order['q']}\n"
                f"Realized Profit: {order['rp']}"
            )
            logger.info(message)

            try:
                await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            except Exception as e:
                logger.error(f"Error sending message: {e}")


async def user_socket_manager(client, application):
    while True:
        try:
            bsm = BinanceSocketManager(client)
            user_socket = bsm.futures_user_socket()

            async with user_socket as stream:
                end_time = asyncio.get_event_loop().time() + 12 * 60 * 60  # 12 hours from now
                while asyncio.get_event_loop().time() < end_time:
                    try:
                        msg = await asyncio.wait_for(stream.recv(), timeout=60)
                        await process_message(msg, application)
                    except asyncio.TimeoutError:
                        logger.info("No message received in 60 seconds, continuing...")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

            logger.info("12 hours passed, restarting WebSocket connection")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            await asyncio.sleep(5)


async def run_telegram_bot(application):
    await application.initialize()
    await application.start()
    await application.updater.start_polling()


async def send_ping(update, context):
    await update.message.reply_text('pong')


async def send_position(update: Update, context: CallbackContext) -> None:
    text = ''
    for symbol, position in ps.items():
        text += (f"종목 : {symbol}\n"
                 f"포지션: {utils.long_or_short(position['positionAmt'])}\n"
                 f"포지션 수량: {position['positionAmt']}\n"
                 f"진입가격: {position['entryPrice']}\n"
                 f"미실현 손익: {position['unRealizedProfit']}\n"
                 f"--------------------------------\n")

    if text == '':
        text = "현재 보유중인 포지션이 없습니다."
    else:
        text = '현재 선물 포지션 정보\n--------------------------------\n' + text

    await update.message.reply_text(text)


async def main():
    # binance ws init
    async_client = await AsyncClient.create(BINANCE_API_KEY, BINANCE_API_SECRET)

    # init positions
    logger.info('------초기 포지션 설정------')
    for position in await async_client.futures_position_information():
        if float(position['positionAmt']) != 0:
            logger.info(f"Position: {position}")
            ps[position['symbol']] = {
                'positionAmt': position['positionAmt'],
                'entryPrice': position['entryPrice'],
                'unRealizedProfit': position['unRealizedProfit'],
            }

    application = Application.builder().token(TELEGRAM_API_TOKEN).build()
    application.add_handler(CommandHandler('ping', send_ping))
    application.add_handler(CommandHandler('positions', send_position))

    # Run both Telegram bot and Binance WebSocket
    await asyncio.gather(
        run_telegram_bot(application),
        user_socket_manager(async_client, application)
    )

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
