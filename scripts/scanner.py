import ccxt
import json
import os
import requests

# --- НАСТРОЙКИ (Пункты 1, 8, 11, 12) ---
MIN_LIQUIDITY_USD = 5000  # Мин. ликвидность на DEX (Пункт 12)
MAX_SPREAD = 50.0         # Максимальный спред (Пункт 11)
MIN_SPREAD = 0,0          # Минимальный спред для отображения

# --- ЛОГИКА АВТОМАТИЧЕСКИХ ПРОКСИ (Пункт 8) ---
# Получаем строку из Secrets и превращаем её в список
raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    """Возвращает прокси по индексу, если он существует"""
    return PROXY_POOL[index] if index < len(PROXY_POOL) else ''

# Конфигурация бирж с привязкой прокси (Пункт 8)
EXCHANGES_CONFIG = {
    'binance': {'class': ccxt.binance, 'proxy': get_proxy(0)},
    'bybit':   {'class': ccxt.bybit,   'proxy': get_proxy(1)},
    'okx':     {'class': ccxt.okx,     'proxy': get_proxy(2)},
    'gateio':  {'class': ccxt.gateio,  'proxy': get_proxy(3)},
    'mexc':    {'class': ccxt.mexc,    'proxy': get_proxy(4)}
}

# Далее идет остальной код (SYMBOLS, get_cex_data и т.д.)

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'TON/USDT', 'PEPE/USDT']

def get_cex_data():
    """Сбор цен со спота и фьючерсов (Пункты 2, 3, 6)"""
    spot_data = {}
    futures_data = {}

    for name, cfg in EXCHANGES_CONFIG.items():
        try:
            params = {'enableRateLimit': True}
            if cfg['proxy']:
                params['proxies'] = {'http': cfg['proxy'], 'https': cfg['proxy']}
            
            ex = cfg['class'](params)
            
            # Собираем данные по списку символов
            for symbol in SYMBOLS:
                # 1. Spot
                ticker = ex.fetch_ticker(symbol)
                # Пункт 6: Блокчейны (заглушка, для реальных данных нужно fetch_currencies)
                spot_data[f"{name}_{symbol}"] = {
                    'exchange': name, 'symbol': symbol,
                    'bid': ticker['bid'], 'ask': ticker['ask'],
                    'net': 'Multi-Chain'
                }

                # 2. Futures (Пункт 2)
                try:
                    f_symbol = symbol.replace('/USDT', '/USDT:USDT') # Формат CCXT для перпов
                    f_ticker = ex.fetch_ticker(f_symbol)
                    futures_data[f"{name}_{f_symbol}"] = {
                        'exchange': name, 'symbol': f_symbol,
                        'bid': f_ticker['bid'], 'ask': f_ticker['ask']
                    }
                except: continue
        except Exception as e:
            print(f"Ошибка {name}: {e}")
            
    return spot_data, futures_data

def get_dex_data():
    """Сканирование DEX через DexScreener (Пункты 4, 7, 12)"""
    dex_results = []
    try:
        # Ищем пары к USDT в популярных сетях
        response = requests.get("https://api.dexscreener.com/latest/dex/search?q=USDT").json()
        pairs = response.get('pairs', [])
        
        for p in pairs:
            liq = p.get('liquidity', {}).get('usd', 0)
            # Пункт 12: Проверка ликвидности
            if liq < MIN_LIQUIDITY_USD: continue
            
            dex_results.append({
                'symbol': p['baseToken']['symbol'],
                'price': float(p['priceUsd']),
                'dex': p['dexId'],
                'chain': p['chainId'],
                'liquidity': liq
            })
    except: pass
    return dex_results

def calculate_spreads():
    spot, futures = get_cex_data()
    dex = get_dex_data()
    
    report = {'spot': [], 'futures': [], 'dex': []}

    # Спред Spot-Spot (Пункт 3)
    keys = list(spot.keys())
    for i in range(len(keys)):
        for j in range(len(keys)):
            s1, s2 = spot[keys[i]], spot[keys[j]]
            if s1['symbol'] == s2['symbol'] and s1['exchange'] != s2['exchange']:
                spread = ((s2['bid'] - s1['ask']) / s1['ask']) * 100
                if MIN_SPREAD < spread < MAX_SPREAD:
                    report['spot'].append({
                        'symbol': s1['symbol'], 'spread': round(spread, 2),
                        'buyAt': f"{s1['exchange']} ({s1['ask']})",
                        'sellAt': f"{s2['exchange']} ({s2['bid']})",
                        'networks': s1['net']
                    })

    # Спред Futures-Futures (Пункт 2)
    f_keys = list(futures.keys())
    for i in range(len(f_keys)):
        for j in range(len(f_keys)):
            f1, f2 = futures[f_keys[i]], futures[f_keys[j]]
            if f1['symbol'] == f2['symbol'] and f1['exchange'] != f2['exchange']:
                spread = ((f2['bid'] - f1['ask']) / f1['ask']) * 100
                if MIN_SPREAD < spread < MAX_SPREAD:
                    report['futures'].append({
                        'symbol': f1['symbol'], 'spread': round(spread, 2),
                        'buyAt': f1['exchange'], 'sellAt': f2['exchange'],
                        'networks': 'Futures Contract'
                    })

    # Спред DEX-Spot (Пункты 4, 7)
    for d in dex:
        for s_key in spot:
            s = spot[s_key]
            if d['symbol'] == s['symbol'].split('/')[0]:
                spread = ((s['bid'] - d['price']) / d['price']) * 100
                if MIN_SPREAD < spread < MAX_SPREAD:
                    report['dex'].append({
                        'symbol': d['symbol'], 'spread': round(spread, 2),
                        'buyAt': f"{d['dex']} ({d['price']})",
                        'sellAt': f"{s['exchange']} ({s['bid']})",
                        'networks': d['chain'],
                        'liquidity': f"${int(d['liquidity'])}"
                    })

    # Сохраняем в JSON (Пункт 10)
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    print("Данные успешно обновлены.")

if __name__ == "__main__":
    calculate_spreads()
