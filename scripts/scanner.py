import ccxt
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 50000  # Ликвидность на DEX от 50,000$
MIN_SPREAD = 0.5           # Минимальный профит 0.5%
EXCHANGES = ['binance', 'bybit', 'okx', 'mexc', 'gateio', 'lbank2', 'htx', 'bingx', 'whitebit']

def get_dex_data():
    """Получаем жирные пары с DexScreener по всем сетям"""
    try:
        # Поиск по запросу USDT для фильтрации стейблкоинов и ликвидных пар
        url = "https://api.dexscreener.com/latest/dex/search?q=USDT"
        res = requests.get(url, timeout=15).json()
        pairs = res.get('pairs', [])
        
        valid_dex_coins = {}
        for p in pairs:
            liq = p.get('liquidity', {}).get('usd', 0)
            if liq >= MIN_LIQUIDITY_USD:
                symbol = p['baseToken']['symbol'].upper()
                # Убираем обернутые токены для сопоставления (WETH -> ETH)
                clean_sym = symbol[1:] if symbol.startswith('W') and len(symbol) > 3 else symbol
                dex_price = float(p['priceUsd'])
                
                if clean_sym not in valid_dex_coins or liq > valid_dex_coins[clean_sym]['liq']:
                    valid_dex_coins[clean_sym] = {
                        'price': dex_price,
                        'dex_name': f"{p['dexId']} ({p['chainId']})",
                        'liq': liq
                    }
        return valid_dex_coins
    except Exception as e:
        print(f"Ошибка DEX: {e}")
        return {}

def fetch_cex_tickers(ex_id):
    """Сбор цен с конкретной CEX"""
    try:
        ex = getattr(ccxt, ex_id)({'enableRateLimit': True, 'timeout': 20000})
        tickers = ex.fetch_tickers()
        return ex_id, {k.split('/')[0]: v for k, v in tickers.items() if '/USDT' in k}
    except:
        return ex_id, {}

def main():
    print("🚀 Запуск сканирования DEX-CEX...")
    dex_coins = get_dex_data()
    print(f"✅ Найдено {len(dex_coins)} ликвидных монет на DEX")

    all_cex_data = {}
    with ThreadPoolExecutor(max_workers=len(EXCHANGES)) as executor:
        results = list(executor.map(fetch_cex_tickers, EXCHANGES))
        for ex_id, tickers in results:
            if tickers:
                all_cex_data[ex_id] = tickers

    found_spreads = []
    for coin, d_info in dex_coins.items():
        for ex_id, tickers in all_cex_data.items():
            if coin in tickers:
                cex_price = tickers[coin]['bid']
                if not cex_price: continue
                
                # Считаем спред: Купили на DEX, продали на CEX
                spread = ((cex_price - d_info['price']) / d_info['price']) * 100
                
                if MIN_SPREAD < spread < 50: # 50% - фильтр ошибок API
                    found_spreads.append({
                        'symbol': coin,
                        'spread': round(spread, 2),
                        'buyAt': d_info['dex_name'],
                        'sellAt': ex_id.upper(),
                        'dex_price': d_info['price'],
                        'cex_price': cex_price,
                        'liquidity': f"${int(d_info['liq'])}"
                    })

    # Сортировка по профиту
    found_spreads.sort(key=lambda x: x['spread'], reverse=True)
    
    # Сохраняем результат для сайта
    output = {'dex': found_spreads, 'spot': [], 'futures': []}
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"🎯 Найдено связок: {len(found_spreads)}. Данные сохранены в spreads.json")

if __name__ == "__main__":
    main()
