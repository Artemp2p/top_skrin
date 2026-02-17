import ccxt
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 2000   # Снизили еще немного для теста
MIN_SPREAD = 0.1           # Поставим 0.1% чтобы увидеть, есть ли вообще коннект
EXCHANGES = ['mexc', 'lbank'] 

# Автоматические прокси (согласно вашим инструкциям)
raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    return PROXY_POOL[index] if index < len(PROXY_POOL) else None

def get_dex_data():
    dex_results = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    # Берем тренды + новые пулы для максимального охвата
    endpoints = [
        "https://api.geckoterminal.com/api/v2/networks/trending_pools",
        "https://api.geckoterminal.com/api/v2/networks/eth/new_pools",
        "https://api.geckoterminal.com/api/v2/networks/bsc/new_pools",
        "https://api.geckoterminal.com/api/v2/networks/base/new_pools",
        "https://api.geckoterminal.com/api/v2/networks/solana/new_pools"
    ]
    
    print(f"🔎 Сканирую DEX (Trends + New)...")
    for url in endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=15).json()
            for p in res.get('data', []):
                attr = p.get('attributes', {})
                name = attr.get('name', '')
                if '/' in name:
                    # Чистим символ: "WETH/USDC" -> "ETH"
                    raw_sym = name.split('/')[0].upper()
                    symbol = raw_sym[1:] if raw_sym.startswith('W') and len(raw_sym) > 3 else raw_sym
                    
                    price = float(attr.get('base_token_price_usd', 0))
                    liq = float(attr.get('reserve_in_usd', 0))

                    if liq >= MIN_LIQUIDITY_USD and price > 0:
                        if symbol not in dex_results or liq > dex_results[symbol]['liq']:
                            dex_results[symbol] = {
                                'price': price,
                                'dex_name': "DEX",
                                'liq': liq
                            }
        except: continue
    return dex_results

def fetch_cex_tickers(ex_id_index):
    ex_id = EXCHANGES[ex_id_index]
    try:
        config = {'enableRateLimit': True, 'timeout': 30000}
        proxy_url = get_proxy(ex_id_index)
        if proxy_url:
            config['proxies'] = {'http': proxy_url, 'https': proxy_url}
            
        ex = getattr(ccxt, ex_id)(config)
        tickers = ex.fetch_tickers()
        # Сохраняем только USDT пары, ключ в верхнем регистре
        return ex_id, {k.split('/')[0].upper(): v for k, v in tickers.items() if '/USDT' in k}
    except Exception as e:
        print(f"❌ {ex_id} error: {e}")
        return ex_id, {}

def main():
    # Log cleaning: подготовка
    print("🧹 Очистка старых логов и старт...")
    report = {'dex': [], 'spot': [], 'futures': []}
    
    dex_coins = get_dex_data()
    print(f"📊 Собрано монет с DEX: {len(dex_coins)}")

    all_cex_data = {}
    with ThreadPoolExecutor(max_workers=len(EXCHANGES)) as executor:
        results = list(executor.map(fetch_cex_tickers, range(len(EXCHANGES))))
        for ex_id, tickers in results:
            if tickers:
                all_cex_data[ex_id] = tickers
                print(f"✅ {ex_id.upper()} отдала {len(tickers)} пар")

    # Сопоставление
    for coin, d_info in dex_coins.items():
        for ex_id, tickers in all_cex_data.items():
            # Проверяем прямое совпадение
            if coin in tickers:
                t = tickers[coin]
                if not t['bid']: continue
                
                spread = ((t['bid'] - d_info['price']) / d_info['price']) * 100
                
                # Фильтр реалистичности
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
    
    # Пункт 10: Сохранение с очисткой старых данных
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    
    print(f"🎯 Найдено связок: {len(report['dex'])}")
    if len(report['dex']) > 0:
        print(f"🔥 Топ спред: {report['dex'][0]['symbol']} - {report['dex'][0]['spread']}%")

if __name__ == "__main__":
    main()
