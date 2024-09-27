import asyncio
import logging
import os
import utils

from decimal import Decimal
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
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 포지션 정보 저장
ps = {}


async def process_message(msg, application):
    logger.info(f"Received message: {msg}")  # 수신된 메시지 출력
    if msg['e'] == 'ACCOUNT_UPDATE':
        account = msg['a']
        for position in account['P']:
            if float(position['pa']) != 0:
                # position 변화 감지 시 처리
                entry_price = Decimal(position['ep']).quantize(Decimal('0.00000001'))
                unrealized_profit = Decimal(position['up']).quantize(Decimal('1'))

                message = (
                    f"포지션 변화 감지\n"
                    f"포지션: {utils.long_or_short(position['pa'])}\n"
                    f"포지션 수량: {position['pa']}\n"
                    f"진입 가격: {entry_price}\n"
                    f"미실현 손익: {unrealized_profit}\n"
                )

                # 텔레그램 메시지 전송
                try:
                    await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                except Exception as e:
                    logger.error(f"Error sending message: {e}")

                # update position
                ps[position['s']] = {
                    'positionAmt': position['pa'],
                    'entryPrice': position['ep'],
                    'unRealizedProfit': position['up']
                }


async def user_socket_manager(client, application):
    while True:
        try:
            bsm = BinanceSocketManager(client)
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
            await asyncio.sleep(5)  # 재연결 시도


async def run_telegram_bot(application):
    await application.initialize()
    await application.start()
    await application.updater.start_polling()


async def send_ping(update, context):
    await update.message.reply_text('pong')


async def send_position(update: Update, context: CallbackContext) -> None:
    text = ''
    for symbol, position in ps.items():
        position_amount = Decimal(position['positionAmt'])
        entry_price = Decimal(position['entryPrice'])
        unrealized_profit = Decimal(position['unRealizedProfit']).quantize(Decimal('1'))

        text += (f"종목 : {symbol}\n"
                 f"포지션: {utils.long_or_short(position_amount)}\n"
                 f"포지션 수량: {position_amount:,}\n" 
                 f"진입 가격: {entry_price:,}\n" 
                 f"미실현 손익: {unrealized_profit:,.0f} {utils.loss_or_profit(unrealized_profit)}\n"  
                 f"--------------------------------\n")

    if text == '':
        text = "현재 보유 중 인 포지션이 없습니다."

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

    # init tg
    application = Application.builder().token(TELEGRAM_API_TOKEN).build()
    application.add_handler(CommandHandler('ping', send_ping))
    application.add_handler(CommandHandler('positions', send_position))

    # run tg & binance ws
    await asyncio.gather(
        run_telegram_bot(application),
        user_socket_manager(async_client, application)
    )

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
