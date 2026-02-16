import ccxt
import json
import os
import requests

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 5000 
MAX_SPREAD = 50.0        
MIN_SPREAD = 0.1         # Возвращаем рабочий спред
TOP_N_COINS = 200        # Сканировать топ-200 монет по объему

raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    return PROXY_POOL[index] if index < len(PROXY_POOL) else ''

EXCHANGES_CONFIG = {
    'binance': {'class': ccxt.binance, 'proxy': get_proxy(0)},
    'bybit':   {'class': ccxt.bybit,   'proxy': get_proxy(1)},
    'okx':     {'class': ccxt.okx,     'proxy': get_proxy(2)},
    'gateio':  {'class': ccxt.gateio,  'proxy': get_proxy(3)},
    'mexc':    {'class': ccxt.mexc,    'proxy': get_proxy(4)}
}

def get_top_symbols():
    """Автоматически получает топ монет по объему с Binance"""
    try:
        ex = ccxt.binance()
        tickers = ex.fetch_tickers()
        # Сортируем по объему в USDT и берем ТОП
        sorted_tickers = sorted(
            [t for t in tickers.values() if '/USDT' in t['symbol'] and t['quoteVolume']], 
            key=lambda x: x['quoteVolume'], reverse=True
        )
        return [t['symbol'] for t in sorted_tickers[:TOP_N_COINS]]
    except Exception as e:
        print(f"Ошибка получения ТОП монет: {e}")
        return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

def get_cex_data(symbols):
    spot_data = {}
    futures_data = {}

    for name, cfg in EXCHANGES_CONFIG.items():
        try:
            params = {'enableRateLimit': True}
            if cfg['proxy']:
                params['proxies'] = {'http': cfg['proxy'], 'https': cfg['proxy']}
            
            ex = cfg['class'](params)
            ex.load_markets() # Загружаем рынки один раз
            
            current_tickers = ex.fetch_tickers(symbols)
            
            for symbol in symbols:
                if symbol in current_tickers and current_tickers[symbol]['bid']:
                    t = current_tickers[symbol]
                    spot_data[f"{name}_{symbol}"] = {
                        'exchange': name, 'symbol': symbol,
                        'bid': t['bid'], 'ask': t['ask'], 'net': 'Multi-Chain'
                    }

                    # Фьючерсы (Пункт 2)
                    try:
                        f_sym = symbol.replace('/USDT', '/USDT:USDT')
                        if f_sym in ex.markets:
                            f_t = ex.fetch_ticker(f_sym)
                            futures_data[f"{name}_{f_sym}"] = {
                                'exchange': name, 'symbol': f_sym,
                                'bid': f_t['bid'], 'ask': f_t['ask']
                            }
                    except: continue
        except: continue
            
    return spot_data, futures_data

def get_dex_data():
    dex_results = []
    try:
        response = requests.get("https://api.dexscreener.com/latest/dex/search?q=USDT").json()
        for p in response.get('pairs', []):
            liq = p.get('liquidity', {}).get('usd', 0)
            if liq >= MIN_LIQUIDITY_USD:
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
    symbols = get_top_symbols()
    spot, futures = get_cex_data(symbols)
    dex = get_dex_data()
    
    report = {'spot': [], 'futures': [], 'dex': []}

    # Логика сравнения (Spot-Spot)
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

    # Логика сравнения (DEX-Spot)
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
    
    # Сохранение и "Очистка" (перезапись файла)
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    print(f"Сканирование завершено. Использовано монет: {len(symbols)}")

if __name__ == "__main__":
    calculate_spreads()
