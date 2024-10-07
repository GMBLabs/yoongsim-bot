import asyncio
import logging
import os
import utils
import time

from decimal import Decimal
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import CommandHandler, Application, CallbackContext

from binance import BinanceSocketManager, AsyncClient

# load env
load_dotenv()
TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')

# logging setting
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# position
ps = {}


async def update_positions(async_client, application, init=False):
    global ps

    new_ps = {}

    # get position
    for position in await async_client.futures_position_information():
        if float(position['positionAmt']) != 0:
            new_ps[position['symbol']] = {
                'positionAmt': position['positionAmt'],
                'entryPrice': position['entryPrice'],
                'markPrice': position['markPrice'],
                'unRealizedProfit': position['unRealizedProfit'],
            }

    # check position change
    if not init:
        # todo: position close image
        # todo: get data from position history
        # position close
        for symbol, old_position in ps.items():
            if symbol not in new_ps:
                position_amount = Decimal(old_position['positionAmt'])
                if position_amount == position_amount.to_integral():
                    position_amount = position_amount.quantize(Decimal('1'))
                else:
                    position_amount = position_amount.quantize(Decimal('0.00000001'))
                entry_price = Decimal(old_position['entryPrice'])
                if entry_price == entry_price.to_integral():
                    entry_price = entry_price.quantize(Decimal('1'))
                else:
                    entry_price = entry_price.quantize(Decimal('0.00000001'))
                mark_price = Decimal(old_position['markPrice'])
                if mark_price == mark_price.to_integral():
                    mark_price = mark_price.quantize(Decimal('1'))
                else:
                    mark_price = mark_price.quantize(Decimal('0.00000001'))
                realized_profit = Decimal(old_position['unRealizedProfit']).quantize(Decimal('1'))

                message = (
                    f"포지션이 종료되었습니다\n"
                    f"<b>종목</b>: <code>{symbol}</code>\n"
                    f"<b>수량</b> : {position_amount:,}\n"
                    f"<b>진입 가격</b>: {entry_price:,}\n"
                    f"<b>현재 가격</b>: {mark_price:,}\n"
                    f"<b>최종 실현 손익</b>: {realized_profit:,}\n"
                )
                try:
                    await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
                except Exception as e:
                    logger.error(f"Error sending message: {e}")

        # position change
        for symbol, new_position in new_ps.items():
            if symbol not in ps:
                # todo: new position image
                # new position
                position_amount = Decimal(new_position['positionAmt'])
                if position_amount == position_amount.to_integral():
                    position_amount = position_amount.quantize(Decimal('1'))
                else:
                    position_amount = position_amount.quantize(Decimal('0.00000001'))
                entry_price = Decimal(new_position['entryPrice'])
                if entry_price == entry_price.to_integral():
                    entry_price = entry_price.quantize(Decimal('1'))
                else:
                    entry_price = entry_price.quantize(Decimal('0.00000001'))

                message = (
                    f"새로운 포지션이 열렸습니다\n"
                    f"<b>종목</b>: <code>{symbol}</code>\n"
                    f"<b>수량</b> : {position_amount:,}\n"
                    f"<b>진입 가격</b>: {entry_price:,}\n"
                )
                try:
                    await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
            else:
                # todo: text refine
                # position change
                if ps[symbol]['positionAmt'] != new_position['positionAmt']:
                    # position change
                    old_amount = Decimal(ps[symbol]['positionAmt'])
                    if old_amount == old_amount.to_integral():
                        old_amount = old_amount.quantize(Decimal('1'))
                    else:
                        old_amount = old_amount.quantize(Decimal('0.00000001'))
                    new_amount = Decimal(new_position['positionAmt'])
                    if new_amount == new_amount.to_integral():
                        new_amount = new_amount.quantize(Decimal('1'))
                    else:
                        new_amount = new_amount.quantize(Decimal('0.00000001'))

                    if old_amount != new_amount:
                        # calc profit change
                        old_unrealized_profit = Decimal(ps[symbol]['unRealizedProfit'])
                        new_unrealized_profit = Decimal(new_position['unRealizedProfit'])
                        profit_change = new_unrealized_profit - old_unrealized_profit
                        profit_change = profit_change.quantize(Decimal('1'))

                        entry_price = Decimal(new_position['entryPrice'])
                        if entry_price == entry_price.to_integral():
                            entry_price = entry_price.quantize(Decimal('1'))
                        else:
                            entry_price = entry_price.quantize(Decimal('0.00000001'))

                        mark_price = Decimal(new_position['markPrice'])
                        if mark_price == mark_price.to_integral():
                            mark_price = mark_price.quantize(Decimal('1'))
                        else:
                            mark_price = mark_price.quantize(Decimal('0.00000001'))
                        realized_profit = Decimal(new_position['unRealizedProfit']).quantize(Decimal('1'))

                        if new_amount > old_amount:
                            # 추가 진입
                            message = (
                                f"포지션이 추가되었습니다.\n"
                                f"<b>종목</b>: <code>{symbol}</code>\n"
                                f"<b>이전 수량</b>: {old_amount:,}\n"
                                f"<b>변경된 수량</b>: {new_amount:,}\n"
                                f"<b>진입 가격</b>: {entry_price:,}\n"
                                f"<b>현재 가격</b>: {mark_price:,}\n"
                                f"<b>미실현 손익</b>: {realized_profit:,}\n"
                            )
                        else:
                            # 부분 청산
                            message = (
                                f"포지션이 부분 청산되었습니다.\n"
                                f"<b>종목</b>: <code>{symbol}</code>\n"
                                f"<b>이전 수량</b>: {old_amount:,}\n"
                                f"<b>변경된 수량</b>: {new_amount:,}\n"
                                f"<b>진입 가격</b>: {entry_price:,}\n"
                                f"<b>현재 가격</b>: {mark_price:,}\n"
                                f"<b>미실현 손익</b>: {realized_profit:,}\n"
                                f"<b>실현 손익</b>: {profit_change:,}\n"
                            )

                        try:
                            await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message,
                                                               parse_mode='HTML')
                        except Exception as e:
                            logger.error(f"Error sending message: {e}")

    # update global var
    ps = new_ps


async def periodic_update_positions(async_client, application):
    while True:
        await update_positions(async_client, application, False)
        await asyncio.sleep(10)


async def run_telegram_bot(application):
    await application.initialize()
    await application.start()
    await application.updater.start_polling()


async def send_ping(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('pong')


async def send_position(update: Update, context: CallbackContext) -> None:
    for symbol, position in ps.items():
        image_stream = utils.create_position_image(
            symbol,
            position['positionAmt'],
            position['entryPrice'],
            position['markPrice'],
            position['unRealizedProfit']
        )

        await update.message.reply_photo(photo=image_stream)


async def main():
    # init binance
    async_client = await AsyncClient.create(BINANCE_API_KEY, BINANCE_API_SECRET)

    # check account balance
    print(await async_client.futures_account_balance())

    # init tg
    application = Application.builder().token(TELEGRAM_API_TOKEN).build()
    application.add_handler(CommandHandler('ping', send_ping))
    application.add_handler(CommandHandler('positions', send_position))

    # init positions
    await update_positions(async_client, application, True)

    # run tg & watch positions
    await asyncio.gather(
        periodic_update_positions(async_client, application),
        run_telegram_bot(application)
    )


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
