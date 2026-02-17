import ccxt
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 10000 
MIN_SPREAD = 0.5           
EXCHANGES = ['mexc', 'lbank'] # Исправлено: lbank вместо lbank2

def get_dex_data():
    dex_results = {}
    chains = ['bsc', 'ethereum', 'solana', 'base', 'arbitrum']
    
    # Заголовки, чтобы DEX не блокировал бота
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print(f"🔎 Глубокий скан сетей: {', '.join(chains)}")
    
    for chain in chains:
        try:
            url = f"https://api.dexscreener.com/latest/dex/chains/{chain}"
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                print(f"⚠️ {chain} вернул статус {response.status_code}")
                continue

            data = response.json()
            pairs = data.get('pairs', [])
            
            if not pairs:
                print(f"⚠️ В сети {chain} не найдено пар")
                continue

            for p in pairs:
                liq = p.get('liquidity', {}).get('usd', 0)
                if liq >= MIN_LIQUIDITY_USD:
                    symbol = p['baseToken']['symbol'].upper()
                    # Очистка обернутых токенов
                    clean_sym = symbol[1:] if symbol.startswith('W') and len(symbol) > 3 else symbol
                    price = float(p['priceUsd'])
                    
                    if clean_sym not in dex_results or liq > dex_results[clean_sym]['liq']:
                        dex_results[clean_sym] = {
                            'price': price,
                            'dex_name': f"{p['dexId']} ({chain})",
                            'liq': liq
                        }
            print(f"✅ {chain}: обработано")
        except Exception as e:
            print(f"❌ Ошибка на {chain}: {str(e)[:50]}")
            
    return dex_results

def fetch_cex_tickers(ex_id):
    try:
        # Прямое создание объекта биржи
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
    dex_coins = get_dex_data()
    print(f"📊 Всего монет собрано с DEX: {len(dex_coins)}")

    if not dex_coins:
        print("⛔️ Данные с DEX не получены. Проверьте соединение.")
        return

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
                t = tickers[coin]
                if not t['bid'] or not t['ask']: continue
                
                spread = ((t['bid'] - d_info['price']) / d_info['price']) * 100
                
                if MIN_SPREAD < spread < 50:
                    found_spreads.append({
                        'symbol': coin,
                        'spread': round(spread, 2),
                        'buyAt': d_info['dex_name'],
                        'sellAt': ex_id.upper(),
                        'dex_price': f"{d_info['price']:.6f}",
                        'cex_price': f"{t['bid']:.6f}",
                        'liquidity': f"${int(d_info['liq'])}"
                    })

    found_spreads.sort(key=lambda x: x['spread'], reverse=True)
    
    output = {'dex': found_spreads, 'spot': [], 'futures': []}
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"🎯 Итог: Найдено {len(found_spreads)} связок")

if __name__ == "__main__":
    main()
