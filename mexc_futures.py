import ccxt
import pandas as pd
import requests
import time
from datetime import datetime

# ====== CONFIGURATION ======
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1367574351330803824/1epkOlLe3qba1bladexGraGlv_5T6lzlxhPxdgNQf0RX6eTGxb9bBI5kv8DlzpO8MOIx"
TIMEFRAME = '5m'
SCAN_INTERVAL = 300  # 5 minutes in seconds
MAX_PAIRS = 50
EMA_CANDLES = 300  # More candles for stable EMAs

# ====== INITIALIZE EXCHANGE ======
exchange = ccxt.mexc({
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True
    },
    'enableRateLimit': True  # Crucial for API stability
})

# ====== ENHANCED DISCORD ALERTS ======
def send_alert(message):
    try:
        payload = {
            "content": message,
            "username": "MEXC Scanner Bot",
            "avatar_url": "https://i.imgur.com/7GF7Q3X.png"
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"⚠️ Alert failed: {str(e)[:100]}")

# ====== IMPROVED PAIR FETCHING ======
def get_futures_pairs():
    try:
        markets = exchange.load_markets()
        return [
            symbol for symbol in markets 
            if markets[symbol]['future'] and 
            markets[symbol]['active'] and
            not markets[symbol]['inverse']  # Skip inverse contracts
        ][:MAX_PAIRS]
    except Exception as e:
        print(f"⚠️ Market fetch error: {str(e)[:100]}")
        return []

# ====== ROBUST SIGNAL DETECTION ======
def check_signals():
    print(f"\n=== MEXC 5-MIN FUTURES SCANNER ===")
    print(f"🔍 Scanning at {datetime.now().strftime('%H:%M:%S')}")
    
    pairs = get_futures_pairs()
    if not pairs:
        print("⚠️ No pairs available for scanning")
        return

    for pair in pairs:
        try:
            # Get candle data with retry logic
            ohlcv = None
            for _ in range(3):  # Retry up to 3 times
                try:
                    ohlcv = exchange.fetch_ohlcv(pair, TIMEFRAME, limit=EMA_CANDLES)
                    break
                except ccxt.NetworkError:
                    time.sleep(2)
            
            if not ohlcv or len(ohlcv) < 50:  # Minimum data check
                continue
                
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Calculate EMAs with error handling
            df['ema7'] = df['close'].ewm(span=7, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
            df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
            
            # Current and previous values
            current = df.iloc[-1]
            previous = df.iloc[-2]
            
            # Enhanced Signal Logic
            buy_signal = (
                (current['ema7'] > current['ema50']) and 
                (previous['ema7'] <= previous['ema50']) and
                (current['ema7'] < current['ema200']) and
                (current['ema21'] < current['ema200']) and
                (current['ema50'] < current['ema200']) and
                (current['volume'] > df['volume'].rolling(20).mean().iloc[-1] * 1.2)  # Volume filter
            )
            
            sell_signal = (
                (current['ema7'] < current['ema50']) and 
                (previous['ema7'] >= previous['ema50'])
            )
            
            # Generate alerts with more context
            if buy_signal:
                alert_msg = (
                    f"🚀 **LONG SIGNAL** {pair.split(':')[0]}\n"
                    f"💰 Price: ${current['close']:.4f}\n"
                    f"📊 Volume: {current['volume']:.2f}\n"
                    f"⏰ Time: {datetime.fromtimestamp(current['timestamp']/1000).strftime('%H:%M')}"
                )
                print(f"✅ {alert_msg}")
                send_alert(alert_msg)
                
            elif sell_signal:
                alert_msg = (
                    f"🔻 **SHORT SIGNAL** {pair.split(':')[0]}\n"
                    f"💰 Price: ${current['close']:.4f}\n"
                    f"⏰ Time: {datetime.fromtimestamp(current['timestamp']/1000).strftime('%H:%M')}"
                )
                print(f"✅ {alert_msg}")
                send_alert(alert_msg)
                
        except Exception as e:
            print(f"⚠️ Error processing {pair}: {str(e)[:100]}")
            time.sleep(1)  # Prevent rate limits

# ====== MAIN LOOP WITH ERROR HANDLING ======
if __name__ == "__main__":
    send_alert("🟢 **MEXC 5-MIN FUTURES SCANNER ACTIVATED**")
    
    while True:
        try:
            start_time = time.time()
            check_signals()
            elapsed = time.time() - start_time
            sleep_time = max(5, SCAN_INTERVAL - elapsed)  # Minimum 5s sleep
            time.sleep(sleep_time)
        except KeyboardInterrupt:
            send_alert("🔴 **Scanner manually stopped**")
            break
        except Exception as e:
            print(f"⚠️ Critical error: {str(e)}")
            time.sleep(30)  # Wait before retry