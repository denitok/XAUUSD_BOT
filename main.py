
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from pytz import utc
import asyncio
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import datetime
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = '7980021462:AAFZJOVI2OTVc3sNeACqOtssjH3IzU2TouU'
TELEGRAM_CHAT_ID = '1385477109'
ALPHAVANTAGE_API_KEY = 'U0YZ7S02BNAJX1GF'
PAIR = 'XAUUSD'

bot = Bot(token=TELEGRAM_TOKEN)

async def send_message(text):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)

async def send_chart(df):
    plt.figure(figsize=(10,5))
    plt.plot(df['close'], label='Close Price')
    plt.title(f'{PAIR} Chart')
    plt.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    await bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=buf)

def get_data():
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={PAIR}&interval=15min&apikey={ALPHAVANTAGE_API_KEY}'
    r = requests.get(url)
    data = r.json()
    df = pd.DataFrame(data['Time Series (15min)']).T
    df.columns = ['open', 'high', 'low', 'close', 'volume']
    df = df.astype(float)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    return df

def calculate_indicators(df):
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    return df

def check_news():
    url = 'https://www.forexfactory.com/calendar'
    res = requests.get(url)
    soup = BeautifulSoup(res.text, 'lxml')
    events = soup.find_all('tr', {'class': 'calendar_row'})
    important = False
    for event in events:
        impact = event.find('td', {'class': 'impact'}).get('title', '')
        if 'High Impact Expected' in impact:
            important = True
    return important

def analyze_market():
    df = get_data()
    df = calculate_indicators(df)
    last = df.iloc[-1]
    signal = None
    if last['ema50'] > last['ema200'] and last['rsi'] > 50 and last['macd'] > 0:
        signal = 'BUY'
    elif last['ema50'] < last['ema200'] and last['rsi'] < 50 and last['macd'] < 0:
        signal = 'SELL'
    return signal, last['close'], df

async def auto_trade():
    while True:
        signal, price, df = analyze_market()
        if signal:
            news = check_news()
            if not news:
                sl = price - 6 if signal == 'BUY' else price + 6
                tp = price + 9 if signal == 'BUY' else price - 9
                await send_message(f'[AUTO SIGNAL]\n{signal}\nEntry: {price:.2f}\nSL: {sl:.2f}\nTP: {tp:.2f}')
                await send_chart(df)
        await asyncio.sleep(300)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot Aktif! Ketik /buy /sell /cekmarket untuk perintah manual.")

async def manual_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signal, price, df = analyze_market()
    sl = price - 6
    tp = price + 9
    await update.message.reply_text(f'[MANUAL BUY]\nEntry: {price:.2f}\nSL: {sl:.2f}\nTP: {tp:.2f}')
    await send_chart(df)

async def manual_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signal, price, df = analyze_market()
    sl = price + 6
    tp = price - 9
    await update.message.reply_text(f'[MANUAL SELL]\nEntry: {price:.2f}\nSL: {sl:.2f}\nTP: {tp:.2f}')
    await send_chart(df)

async def cek_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signal, price, df = analyze_market()
    await update.message.reply_text(f'[CEK MARKET]\nTrend: {signal}\nHarga: {price:.2f}')
    await send_chart(df)

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).timezone(utc).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('buy', manual_buy))
    app.add_handler(CommandHandler('sell', manual_sell))
    app.add_handler(CommandHandler('cekmarket', cek_market))

    asyncio.create_task(auto_trade())
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
