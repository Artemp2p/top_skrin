import ccxt
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 5000   # Снижаем до 5к, чтобы зацепить новые листинги
MIN_SPREAD = 0.5           
EXCHANGES = ['mexc', 'lbank'] 

# Автоматическое использование прокси (согласно вашим инструкциям)
raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    return PROXY_POOL[index] if index < len(PROXY_POOL) else None

def get_dex_data():
    """Масштабируемый поиск через эндпоинт поиска по трендам"""
    dex_results = {}
    # Список запросов для максимального охвата
    queries = ['USDT', 'PEPE', 'SOL', 'MEME', 'AI', 'DOGE']
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    print(f"🔎 Масштабный поиск по трендам DEX...")
    
    for q in queries:
        try:
            url = f"https://api.dexscreener.com/latest/dex/search?q={q}"
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                pairs = response.json().get('pairs', [])
                for p in pairs:
                    liq = p.get('liquidity', {}).get('usd', 0)
                    vol = p.get('volume', {}).get('h24', 0)
                    
                    if liq >= MIN_LIQUIDITY_USD:
                        symbol = p['baseToken']['symbol'].upper()
                        # Очистка W-токенов (WETH -> ETH)
                        clean_sym = symbol[1:] if symbol.startswith('W') and len(symbol) > 3 else symbol
                        price = float(p['priceUsd'])
                        
                        if clean_sym not in dex_results or liq > dex_results[clean_sym]['liq']:
                            dex_results[clean_sym] = {
                                'price': price,
                                'dex_name': f"{p['dexId']} ({p.get('chainId', 'chain')})",
                                'liq': liq
                            }
        except: continue
            
    return dex_results

def fetch_cex_tickers(ex_id_index):
    ex_id = EXCHANGES[ex_id_index]
    try:
        proxy_url = get_proxy(ex_id_index)
        config = {'enableRateLimit': True, 'timeout': 30000}
        if proxy_url:
            config['proxies'] = {'http': proxy_url, 'https': proxy_url}
            
        ex = getattr(ccxt, ex_id)(config)
        tickers = ex.fetch_tickers()
        return ex_id, {k.split('/')[0].upper(): v for k, v in tickers.items() if '/USDT' in k}
    except Exception as e:
        print(f"❌ {ex_id} error: {e}")
        return ex_id, {}

def main():
    # Функция очистки логов (согласно вашим инструкциям)
    print("🧹 Log cleaning: Очистка старых данных...")
    report = {'dex': [], 'spot': [], 'futures': []}
    
    dex_coins = get_dex_data()
    print(f"📊 Собрано монет с DEX: {len(dex_coins)}")

    if dex_coins:
        all_cex_data = {}
        with ThreadPoolExecutor(max_workers=len(EXCHANGES)) as executor:
            # Передаем индексы для привязки прокси
            results = list(executor.map(fetch_cex_tickers, range(len(EXCHANGES))))
            for ex_id, tickers in results:
                if tickers:
                    all_cex_data[ex_id] = tickers

        for coin, d_info in dex_coins.items():
            for ex_id, tickers in all_cex_data.items():
                if coin in tickers:
                    t = tickers[coin]
                    if not t['bid']: continue
                    
                    spread = ((t['bid'] - d_info['price']) / d_info['price']) * 100
                    
                    if MIN_SPREAD < spread < 30:
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
    
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    print(f"🎯 Итог: Найдено {len(report['dex'])} связок")

if __name__ == "__main__":
    main()
