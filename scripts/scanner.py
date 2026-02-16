import ccxt
import json
import os
import requests

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 50000  # Ликвидность от 50,000$
MIN_SPREAD = 0.02
MAX_SPREAD = 50.0

# Прокси из секретов (Пункт 8)
raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    return PROXY_POOL[index] if index < len(PROXY_POOL) else ''

def get_dex_data():
    """Глубокий поиск по всем блокчейнам (Пункт 12)"""
    dex_results = []
    chains = ['ethereum', 'bsc', 'solana', 'base', 'arbitrum', 'polygon', 'avalanche', 'optimism']
    
    print(f"Начинаю глубокий скан DEX (Ликвидность > {MIN_LIQUIDITY_USD}$)...")
    
    for chain in chains:
        try:
            # Запрашиваем топ-пары для каждой сети отдельно для глубины
            url = f"https://api.dexscreener.com/latest/dex/chains/{chain}"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                pairs = response.json().get('pairs', [])
                count = 0
                for p in pairs:
                    liq = p.get('liquidity', {}).get('usd', 0)
                    if liq >= MIN_LIQUIDITY_USD:
                        # Очистка символа: WETH -> ETH, WBTC -> BTC
                        raw_sym = p['baseToken']['symbol'].upper()
                        symbol = raw_sym[1:] if raw_sym.startswith('W') and len(raw_sym) > 3 else raw_sym
                        
                        dex_results.append({
                            'symbol': symbol,
                            'price': float(p['priceUsd']),
                            'dex': f"{p['dexId']} ({chain})",
                            'liq': liq
                        })
                        count += 1
                print(f"Сеть {chain}: найдено {count} ликвидных пар")
        except Exception as e:
            print(f"Ошибка DEX {chain}: {e}")
    return dex_results

def calculate_spreads():
    # Твой расширенный список бирж
    active_exchanges = ['binance', 'bybit', 'okx', 'mexc', 'gateio', 'lbank', 'htx', 'bingx', 'whitebit']
    spot_data = {}
    
    print(f"Сбор данных с {len(active_exchanges)} бирж...")
    
    for i, name in enumerate(active_exchanges):
        try:
            params = {'enableRateLimit': True, 'timeout': 20000}
            proxy = get_proxy(i)
            if proxy:
                params['proxies'] = {'http': proxy, 'https': proxy}
            
            ex = getattr(ccxt, name)(params)
            tickers = ex.fetch_tickers()
            
            for sym, t in tickers.items():
                if '/USDT' in sym and t['bid'] and t['ask']:
                    coin = sym.split('/')[0].upper()
                    # Сохраняем данные
                    spot_data[f"{name}_{coin}"] = {
                        'ex': name, 'coin': coin,
                        'bid': t['bid'], 'ask': t['ask']
                    }
        except Exception as e:
            print(f"Биржа {name} пропущена. Причина: {e}")

    dex_data = get_dex_data()
    report = {'spot': [], 'futures': [], 'dex': []}

    # 1. Поиск связок Spot-Spot (Пункт 7)
    all_spot_keys = list(spot_data.keys())
    for i in range(len(all_spot_keys)):
        for j in range(len(all_spot_keys)):
            s1 = spot_data[all_spot_keys[i]]
            s2 = spot_data[all_spot_keys[j]]
            
            if s1['coin'] == s2['coin'] and s1['ex'] != s2['ex']:
                spread = ((s2['bid'] - s1['ask']) / s1['ask']) * 100
                if MIN_SPREAD < spread < MAX_SPREAD:
                    report['spot'].append({
                        'symbol': s1['coin'],
                        'spread': round(spread, 2),
                        'buyAt': f"{s1['ex']} ({s1['ask']})",
                        'sellAt': f"{s2['ex']} ({s2['bid']})",
                        'networks': "Multi-Chain"
                    })

    # 2. Поиск связок DEX-Spot
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
                        'networks': "Auto",
                        'liquidity': f"${int(d['liq'])}"
                    })

    # Сортировка по профиту
    report['spot'] = sorted(report['spot'], key=lambda x: x['spread'], reverse=True)
    report['dex'] = sorted(report['dex'], key=lambda x: x['spread'], reverse=True)

    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    
    print(f"Готово! Найдено связок Spot: {len(report['spot'])}, DEX: {len(report['dex'])}")

if __name__ == "__main__":
    calculate_spreads()
