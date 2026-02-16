import ccxt
import json
import os
import requests

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 1000 
MIN_SPREAD = 0.2
MAX_SPREAD = 50.0

raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    return PROXY_POOL[index] if index < len(PROXY_POOL) else ''

def get_dex_data():
    """Исправленный запрос к DexScreener (Пункт 12)"""
    dex_results = []
    # Используем проверенный эндпоинт поиска последних пар
    url = "https://api.dexscreener.com/latest/dex/search?q=USDT"
    
    try:
        print("Запрос данных с DEX...")
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            pairs = response.json().get('pairs', [])
            for p in pairs:
                liq = p.get('liquidity', {}).get('usd', 0)
                if liq >= MIN_LIQUIDITY_USD:
                    symbol = p['baseToken']['symbol'].upper()
                    dex_results.append({
                        'symbol': symbol,
                        'price': float(p['priceUsd']),
                        'dex': f"{p['dexId']} ({p.get('chainId', 'chain')})",
                        'liq': liq
                    })
            print(f"DEX: Найдено {len(dex_results)} пар")
        else:
            print(f"Ошибка DexScreener: {response.status_code}")
    except Exception as e:
        print(f"Ошибка DEX: {e}")
    return dex_results

def calculate_spreads():
    # Твои биржи
    active_exchanges = ['binance', 'bybit', 'okx', 'mexc', 'gateio']
    spot_data = {}
    
    for i, name in enumerate(active_exchanges):
        try:
            # Использование прокси (Пункт 8)
            params = {'enableRateLimit': True, 'timeout': 20000}
            proxy = get_proxy(i)
            if proxy:
                params['proxies'] = {'http': proxy, 'https': proxy}
                print(f"Биржа {name}: использую прокси")
            
            ex = getattr(ccxt, name)(params)
            tickers = ex.fetch_tickers()
            
            for sym, t in tickers.items():
                if '/USDT' in sym and t['bid'] and t['ask']:
                    coin = sym.split('/')[0].upper()
                    spot_data[f"{name}_{coin}"] = {
                        'ex': name, 'coin': coin,
                        'bid': t['bid'], 'ask': t['ask']
                    }
        except Exception as e:
            print(f"Биржа {name} пропущена (вероятно блок IP или нет прокси)")

    dex_data = get_dex_data()
    report = {'spot': [], 'futures': [], 'dex': []}

    # Поиск связок (Пункт 7)
    for d in dex_data:
        for key, s in spot_data.items():
            if d['symbol'] == s['coin']:
                spread = ((s['bid'] - d['price']) / d['price']) * 100
                if MIN_SPREAD < spread < MAX_SPREAD:
                    report['dex'].append({
                        'symbol': d['symbol'],
                        'spread': round(spread, 2),
                        'buyAt': d['dex'],
                        'sellAt': s['ex'],
                        'networks': "Auto-detect",
                        'liquidity': f"${int(d['liq'])}"
                    })

    # Сортировка
    report['dex'] = sorted(report['dex'], key=lambda x: x['spread'], reverse=True)

    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    
    print(f"Итог: Найдено {len(report['dex'])} связок DEX-CEX")

if __name__ == "__main__":
    calculate_spreads()
