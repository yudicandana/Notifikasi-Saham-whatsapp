#------------++++ Created by Yudi Prasetiyo ++++--------------#

import requests
import time
import json
from websocket import create_connection
import random
import re
import string
import config  # Import konfigurasi dari config.py
from datetime import datetime

def send_whatsapp_message(message):
    url = 'https://api.fonnte.com/send'
    payload = {
        'target': config.WHATSAPP_TARGET,  # Menggunakan target dari config.py
        'message': message,
        'schedule': '0',
        'typing': 'false',
        'delay': '2',
        'countryCode': '62'
    }
    headers = {
        'Authorization': config.FONNTE_AUTH_KEY  # Menggunakan kunci autentikasi dari config.py
    }

    response = requests.post(url, data=payload, headers=headers)
    if response.status_code == 200:
        print("Pesan berhasil dikirim!")
    else:
        print(f"Terjadi kesalahan: {response.text}")

# Generate a random session ID
def generate_session():
    string_length = 12
    letters = string.ascii_lowercase
    random_string = "".join(random.choice(letters) for _ in range(string_length))
    return "qs_" + random_string

# Prepend header to content
def prepend_header(content):
    return f"~m~{len(content)}~m~{content}"

# Construct a JSON message
def construct_message(func, param_list):
    return json.dumps({"m": func, "p": param_list}, separators=(",", ":"))

# Create a full message with header
def create_message(func, param_list):
    return prepend_header(construct_message(func, param_list))

# Send a message over the WebSocket connection
def send_message(ws, func, args):
    message = create_message(func, args)
    ws.send(message)

# Send a ping packet
def send_ping_packet(ws, result):
    ping_str = re.findall(".......(.*)", result)
    if ping_str:
        ping_str = ping_str[0]
        ws.send(f"~m~{len(ping_str)}~m~{ping_str}")

def socket_job(ws, symbols):
    received_symbols = set()
    stock_prices = {}

    while True:
        try:
            result = ws.recv()
            # Split the received message based on the TradingView delimiter
            messages = re.split(r'~m~\d+~m~', result)
            for message in messages:
                if not message.strip():
                    continue
                try:
                    json_res = json.loads(message)
                    if json_res.get("m") == "qsd":
                        try:
                            prefix = json_res["p"][1]
                            symbol = prefix["n"]
                            price = prefix["v"].get("lp", None)
                            volume = prefix["v"].get("volume", None)
                            change = prefix["v"].get("ch", None)
                            change_percentage = prefix["v"].get("chp", None)
                            stock_prices[symbol] = {
                                "price": price,
                                "volume": volume,
                                "change": change,
                                "change_percentage": change_percentage
                            }
                            received_symbols.add(symbol)
                            if received_symbols == set(symbols):
                                return stock_prices  # Exit the function to close the script and return the prices
                        except KeyError:
                            continue
                except json.JSONDecodeError:
                    continue

        except KeyboardInterrupt:
            print("\nGoodbye!")
            exit(0)
        except Exception as e:
            continue

# Main function to establish WebSocket connection and start job
def get_stock_prices(symbols):
    trading_view_socket = "wss://data.tradingview.com/socket.io/websocket"
    headers = json.dumps({"Origin": "https://data.tradingview.com"})
    ws = create_connection(trading_view_socket, headers=headers)
    session = generate_session()

    send_message(ws, "quote_create_session", [session])
    send_message(
        ws,
        "quote_set_fields",
        [
            session,
            "lp",
            "volume",
            "ch",
            "chp",
        ],
    )
    for symbol_id in symbols:
        send_message(ws, "quote_add_symbols", [session, symbol_id])

    return socket_job(ws, symbols)

def check_stock(symbol, alert_low, alert_high, last_alert_price, stock_prices):
    current_data = stock_prices.get(symbol)
    if current_data is not None:
        current_price = current_data["price"]
        formatted_price = f"IDR {current_price:,}".replace(",", ".")
        print(f"Checking {symbol} - Current Price: {formatted_price}")
        if symbol not in last_alert_price or current_price != last_alert_price[symbol]:
            if current_price <= alert_low:
                send_whatsapp_message(f"Halo, harga saham {symbol} sekarang adalah {formatted_price}, di bawah alert low {alert_low:,}".replace(",", ".") + " IDR")
                last_alert_price[symbol] = current_price
            elif current_price >= alert_high:
                send_whatsapp_message(f"Halo, harga saham {symbol} sekarang adalah {formatted_price}, di atas alert high {alert_high:,}".replace(",", ".") + " IDR")
                last_alert_price[symbol] = current_price
    else:
        print(f"Invalid stock symbol: {symbol}")

    return last_alert_price

if __name__ == "__main__":
    with open('datasaham.json', 'r') as file:
        stocks = json.load(file)
    
    last_alert_price = {}

    while True:
        print(f"\n=== Checking stock prices at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        symbols = [f"IDX:{stock['symbol']}" for stock in stocks]
        stock_prices = get_stock_prices(symbols)
        for stock in stocks:
            symbol = f"IDX:{stock['symbol']}"
            alert_low = stock['alert_low']
            alert_high = stock['alert_high']
            last_alert_price = check_stock(symbol, alert_low, alert_high, last_alert_price, stock_prices)
        print(f"=== End of check, sleeping for {config.CHECK_INTERVAL} seconds ===\n")
        time.sleep(config.CHECK_INTERVAL)
