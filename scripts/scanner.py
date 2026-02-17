import ccxt
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 10000 
MIN_SPREAD = 0.5           
EXCHANGES = ['mexc', 'lbank'] 

def get_dex_data():
    """Используем эндпоинт Latest Pairs для обхода 404 ошибок"""
    dex_results = {}
    # Список надежных эндпоинтов для глубокого скана
    urls = [
        "https://api.dexscreener.com/latest/dex/search?q=USDT",
        "https://api.dexscreener.com/latest/dex/search?q=USDC",
        "https://api.dexscreener.com/latest/dex/search?q=SOL"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print(f"🔎 Сканирую DEX через глобальный поиск...")
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code != 200:
                print(f"⚠️ Ошибка API: {response.status_code}")
                continue

            pairs = response.json().get('pairs', [])
            for p in pairs:
                liq = p.get('liquidity', {}).get('usd', 0)
                if liq >= MIN_LIQUIDITY_USD:
                    symbol = p['baseToken']['symbol'].upper()
                    # Убираем W (WETH -> ETH)
                    clean_sym = symbol[1:] if symbol.startswith('W') and len(symbol) > 3 else symbol
                    price = float(p['priceUsd'])
                    chain = p.get('chainId', 'unknown')
                    
                    if clean_sym not in dex_results or liq > dex_results[clean_sym]['liq']:
                        dex_results[clean_sym] = {
                            'price': price,
                            'dex_name': f"{p['dexId']} ({chain})",
                            'liq': liq
                        }
        except Exception as e:
            print(f"❌ Ошибка запроса: {e}")
            
    return dex_results

def fetch_cex_tickers(ex_id):
    """Сбор цен с CEX (MEXC/LBank)"""
    try:
        ex_class = getattr(ccxt, ex_id)
        ex = ex_class({
            'enableRateLimit': True, 
            'timeout': 30000,
            'headers': {'User-Agent': 'Mozilla/5.0'}
        })
        tickers = ex.fetch_tickers()
        return ex_id, {k.split('/')[0].upper(): v for k, v in tickers.items() if '/USDT' in k}
    except Exception as e:
        print(f"❌ Ошибка CEX {ex_id}: {e}")
        return ex_id, {}

def main():
    # Пункт 1: Очистка старых данных перед запуском
    print("🧹 Очистка старых логов...")
    report = {'dex': [], 'spot': [], 'futures': []}
    
    dex_coins = get_dex_data()
    print(f"📊 Собрано монет с DEX: {len(dex_coins)}")

    if not dex_coins:
        print("⛔️ Данные не найдены. Сохраняю пустой отчет.")
    else:
        all_cex_data = {}
        with ThreadPoolExecutor(max_workers=len(EXCHANGES)) as executor:
            results = list(executor.map(fetch_cex_tickers, EXCHANGES))
            for ex_id, tickers in results:
                if tickers:
                    all_cex_data[ex_id] = tickers

        for coin, d_info in dex_coins.items():
            for ex_id, tickers in all_cex_data.items():
                if coin in tickers:
                    t = tickers[coin]
                    if not t['bid']: continue
                    
                    spread = ((t['bid'] - d_info['price']) / d_info['price']) * 100
                    
                    if MIN_SPREAD < spread < 50:
                        report['dex'].append({
                            'symbol': coin,
                            'spread': round(spread, 2),
                            'buyAt': d_info['dex_name'],
                            'sellAt': ex_id.upper(),
                            'dex_price': f"{d_info['price']:.6f}",
                            'cex_price': f"{t['bid']:.6f}",
                            'liquidity': f"${int(d_info['liq'])}"
                        })

    report['dex'].sort(key=lambda x: x['spread'], reverse=True)
    
    # Сохранение итогов (Пункт 10)
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    print(f"🎯 Итог: Найдено {len(report['dex'])} связок")

if __name__ == "__main__":
    main()
