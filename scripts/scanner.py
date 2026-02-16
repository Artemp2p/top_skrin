import ccxt
import json
import os
import requests

# --- МАКСИМАЛЬНО МЯГКИЕ НАСТРОЙКИ ДЛЯ ТЕСТА ---
MIN_LIQUIDITY_USD = 100   # Почти любая ликвидность
MIN_SPREAD = -10.0        # Показывать всё, даже минус
MAX_SPREAD = 100.0

raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    return PROXY_POOL[index] if index < len(PROXY_POOL) else ''

def get_dex_data():
    dex_results = []
    # Полный список сетей
    chains = ['ethereum', 'bsc', 'arbitrum', 'polygon', 'base', 'solana', 'avalanche', 'optimism']
    
    for chain in chains:
        try:
            print(f"Запрос DEX данных для сети: {chain}...")
            url = f"https://api.dexscreener.com/latest/dex/chains/{chain}"
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                print(f"Ошибка API DexScreener для {chain}: {response.status_code}")
                continue
                
            data = response.json()
            pairs = data.get('pairs', [])
            found_on_chain = 0
            
            for p in pairs:
                liq = p.get('liquidity', {}).get('usd', 0)
                if liq >= MIN_LIQUIDITY_USD:
                    symbol = p['baseToken']['symbol'].upper()
                    dex_results.append({
                        'symbol': symbol,
                        'price': float(p['priceUsd']),
                        'dex': f"{p['dexId']} ({chain})",
                        'liq': liq
                    })
                    found_on_chain += 1
            print(f"Сеть {chain}: найдено {found_on_chain} подходящих пар")
        except Exception as e:
            print(f"Критическая ошибка на {chain}: {e}")
    return dex_results

def calculate_spreads():
    # Твои биржи
    active_exchanges = ['binance', 'bybit', 'okx', 'mexc', 'gateio']
    spot_data = {}
    
    print(f"Начинаю сбор данных с {len(active_exchanges)} бирж...")
    
    for i, name in enumerate(active_exchanges):
        try:
            params = {'enableRateLimit': True, 'timeout': 20000}
            proxy = get_proxy(i)
            if proxy:
                params['proxies'] = {'http': proxy, 'https': proxy}
            
            ex_class = getattr(ccxt, name)
            ex = ex_class(params)
            
            # Загружаем тикеры
            tickers = ex.fetch_tickers()
            count = 0
            for sym, t in tickers.items():
                if '/USDT' in sym and t['bid'] and t['ask']:
                    coin = sym.split('/')[0].upper()
                    spot_data[f"{name}_{coin}"] = {
                        'ex': name, 'coin': coin,
                        'bid': t['bid'], 'ask': t['ask'],
                        'inst': ex
                    }
                    count += 1
            print(f"Биржа {name}: загружено {count} рабочих пар")
        except Exception as e:
            print(f"Ошибка при работе с {name}: {e}")

    dex_data = get_dex_data()
    report = {'spot': [], 'futures': [], 'dex': []}

    print(f"Всего монет с CEX: {len(spot_data)}")
    print(f"Всего монет с DEX: {len(dex_data)}")

    # Сопоставление (Пункт 7)
    for d in dex_data:
        # Ищем совпадение символа в данных с бирж
        for key, s in spot_data.items():
            if d['symbol'] == s['coin']:
                # Считаем спред (Купить на DEX, продать на CEX)
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

    # Сортировка по спреду
    report['dex'] = sorted(report['dex'], key=lambda x: x['spread'], reverse=True)[:50]

    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    
    print(f"Скрипт завершен. Найдено связок: {len(report['dex'])}")

if __name__ == "__main__":
    calculate_spreads()
