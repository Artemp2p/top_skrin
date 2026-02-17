import ccxt
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 10000  # Снизили до 10к для большего охвата
MIN_SPREAD = 0.5           
# Оставляем фокус на самых профитных для DEX биржах
EXCHANGES = ['mexc', 'lbank2'] 

def get_dex_data():
    """Глубокий поиск: сканируем топ-пары по разным сетям"""
    dex_results = {}
    # Список активных сетей для скана
    chains = ['bsc', 'ethereum', 'solana', 'base', 'arbitrum']
    
    print(f"🔎 Глубокий скан сетей: {', '.join(chains)}")
    
    for chain in chains:
        try:
            # Запрашиваем топ-300 пар для каждой сети
            url = f"https://api.dexscreener.com/latest/dex/chains/{chain}"
            res = requests.get(url, timeout=15).json()
            pairs = res.get('pairs', [])
            
            for p in pairs:
                liq = p.get('liquidity', {}).get('usd', 0)
                # Фильтр ликвидности (Пункт 12)
                if liq >= MIN_LIQUIDITY_USD:
                    base_token = p['baseToken']
                    symbol = base_token['symbol'].upper()
                    
                    # Очистка символа (WETH -> ETH)
                    clean_sym = symbol[1:] if symbol.startswith('W') and len(symbol) > 3 else symbol
                    price = float(p['priceUsd'])
                    
                    # Если монета уже есть, берем ту, где выше ликвидность
                    if clean_sym not in dex_results or liq > dex_results[clean_sym]['liq']:
                        dex_results[clean_sym] = {
                            'price': price,
                            'dex_name': f"{p['dexId']} ({chain})",
                            'liq': liq
                        }
        except Exception as e:
            print(f"⚠️ Ошибка сети {chain}: {e}")
            
    return dex_results

def fetch_cex_tickers(ex_id):
    try:
        # Добавляем таймаут и эмуляцию браузера для LBank/MEXC
        ex = getattr(ccxt, ex_id)({
            'enableRateLimit': True, 
            'timeout': 30000,
            'headers': {'User-Agent': 'Mozilla/5.0'}
        })
        tickers = ex.fetch_tickers()
        # Фильтруем только USDT пары
        return ex_id, {k.split('/')[0].upper(): v for k, v in tickers.items() if '/USDT' in k}
    except Exception as e:
        print(f"❌ Ошибка CEX {ex_id}: {e}")
        return ex_id, {}

def main():
    dex_coins = get_dex_data()
    print(f"✅ Найдено {len(dex_coins)} потенциальных монет на DEX")

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
                
                # Считаем спред: Купить на DEX, продать на CEX (Пункт 7)
                spread = ((t['bid'] - d_info['price']) / d_info['price']) * 100
                
                if MIN_SPREAD < spread < 50:
                    found_spreads.append({
                        'symbol': coin,
                        'spread': round(spread, 2),
                        'buyAt': d_info['dex_name'],
                        'sellAt': ex_id.replace('2', '').upper(),
                        'dex_price': f"${d_info['price']:.6f}",
                        'cex_price': f"${t['bid']:.6f}",
                        'liquidity': f"${int(d_info['liq'])}"
                    })

    found_spreads.sort(key=lambda x: x['spread'], reverse=True)
    
    # Сохраняем (Пункт 10)
    output = {'dex': found_spreads, 'spot': [], 'futures': []}
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"🎯 Итог: Найдено {len(found_spreads)} связок")

if __name__ == "__main__":
    main()
