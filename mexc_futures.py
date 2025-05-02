import ccxt
import pandas as pd
import requests
import time
from datetime import datetime
import threading

# ====== CONFIGURATION ======
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1367574351330803824/1epkOlLe3qba1bladexGraGlv_5T6lzlxhPxdgNQf0RX6eTGxb9bBI5kv8DlzpO8MOIx"
TIMEFRAME = '5m'
SCAN_INTERVAL = 300  # 5 minutes in seconds
MAX_PAIRS = 50
MIN_VOLUME = 100000  # Minimum 24h volume in USDT

# ====== INITIALIZE EXCHANGE ======
exchange = ccxt.mexc({
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': False  # Critical fix for time sync error
    },
    'enableRateLimit': True,
    'timeout': 30000,
})

# ====== DISCORD ALERTS ======
def send_alert(message, is_buy=True):
    color = 0x00FF00 if is_buy else 0xFF0000
    embed = {
        "title": "MEXC 5-MIN FUTURES ALERT",
        "description": message,
        "color": color,
        "timestamp": datetime.utcnow().isoformat()
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
    except Exception as e:
        print(f"⚠️ Alert failed: {e}")

# ====== HEARTBEAT MONITORING ======
def send_heartbeat():
    while True:
        try:
            requests.post(DISCORD_WEBHOOK_URL, 
                         json={"content": f"❤️ 5m Bot Alive @ {datetime.now().strftime('%H:%M:%S')}"})
            time.sleep(3600)  # Send every hour
        except:
            time.sleep(60)

threading.Thread(target=send_heartbeat, daemon=True).start()

# ====== FETCH FUTURES PAIRS ======
def get_futures_pairs():
    try:
        markets = exchange.load_markets()
        if not markets:
            raise Exception("No markets data received")
            
        pairs = [
            symbol for symbol in markets 
            if (markets[symbol].get('future') and 
                markets[symbol].get('active') and
                markets[symbol].get('quote') == 'USDT' and
                markets[symbol].get('info', {}).get('volume24h', 0) > MIN_VOLUME)
        ][:MAX_PAIRS]
        
        print(f"\n🔎 Scanning {len(pairs)} pairs:")
        for i, pair in enumerate(pairs[:5], 1):  # Print first 5 as sample
            print(f"{i}. {pair.replace(':USDT', '')}")
        if len(pairs) > 5:
            print(f"... and {len(pairs)-5} more")
            
        return pairs
        
    except Exception as e:
        print(f"⚠️ Pair fetch error: {type(e).__name__} - {str(e)}")
        return ['BTC/USDT:USDT', 'ETH/USDT:USDT']  # Fallback pairs

# ====== TRADING STRATEGY ======
def check_signals():
    while True:
        print(f"\n=== MEXC 5-MIN SCANNER === {datetime.now().strftime('%H:%M:%S')}")
        
        for pair in get_futures_pairs():
            try:
                ohlcv = exchange.fetch_ohlcv(pair, TIMEFRAME, limit=250)
                if len(ohlcv) < 50:
                    continue
                    
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # Calculate EMAs
                df['ema7'] = df['close'].ewm(span=7, adjust=False).mean()
                df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
                df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
                df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
                
                # Signal conditions
                current_close = df['close'].iloc[-1]
                ema7 = df['ema7'].iloc[-1]
                ema50 = df['ema50'].iloc[-1]
                
                buy = (ema7 > ema50) and (df['ema7'].iloc[-2] <= df['ema50'].iloc[-2])
                sell = (ema7 < ema50) and (df['ema7'].iloc[-2] >= df['ema50'].iloc[-2])
                
                if buy:
                    alert = f"✅ 🚀 LONG {pair.split(':')[0]}\nPrice: ${current_close:.2f}"
                    print(alert)
                    send_alert(alert, is_buy=True)
                    
                elif sell:
                    alert = f"✅ 🔻 SHORT {pair.split(':')[0]}\nPrice: ${current_close:.2f}"
                    print(alert)
                    send_alert(alert, is_buy=False)
                    
            except ccxt.NetworkError:
                time.sleep(10)
            except ccxt.ExchangeError:
                time.sleep(5)
            except Exception as e:
                print(f"⚠️ Pair error {pair}: {type(e).__name__} - {str(e)}")
                time.sleep(2)

# ====== MAIN EXECUTION ======
if __name__ == "__main__":
    send_alert("🟢 5-MIN BOT ACTIVATED")
    print("===== BOT STARTED =====")
    
    while True:
        try:
            check_signals()
            time.sleep(SCAN_INTERVAL)
        except Exception as e:
            print(f"🛑 CRITICAL ERROR: {type(e).__name__} - {str(e)}")
            send_alert(f"🛑 BOT CRASHED: {str(e)}")
            time.sleep(60)  # Wait before restart