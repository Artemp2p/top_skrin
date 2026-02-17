import ccxt
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 5000   
MIN_SPREAD = 0.5           
EXCHANGES = ['mexc', 'lbank'] 

# Автоматическое использование прокси (Пункт 8)
raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    return PROXY_POOL[index] if index < len(PROXY_POOL) else None

def get_dex_data():
    """Сбор данных: GeckoTerminal (топы) + DexScreener (поиск)"""
    dex_results = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. Сбор через GeckoTerminal (дает больше реальных монет)
    chains = ['bsc', 'eth', 'solana', 'base']
    print(f"🔎 Сканирую GeckoTerminal (топ-пары)...")
    for chain in chains:
        try:
            url = f"https://api.geckoterminal.com/api/v2/networks/{chain}/new_pools"
            res = requests.get(url, headers=headers, timeout=15).json()
            for p in res.get('data', []):
                attr = p.get('attributes', {})
                liq = float(attr.get('reserve_in_usd', 0))
                if liq >= MIN_LIQUIDITY_USD:
                    symbol = attr.get('base_token_price_usd_token_symbol', '').upper()
                    price = float(attr.get('base_token_price_usd', 0))
                    if symbol and price > 0:
                        dex_results[symbol] = {'price': price, 'dex_name': f"Gecko ({chain})", 'liq': liq}
        except: continue

    # 2. Добор через DexScreener Search
    print(f"🔎 Добор через DexScreener...")
    try:
        ds_url = "https://api.dexscreener.com/latest/dex/search?q=USDT"
        ds_res = requests.get(ds_url, headers=headers, timeout=15).json()
        for p in ds_res.get('pairs', []):
            liq = p.get('liquidity', {}).get('usd', 0)
            if liq >= MIN_LIQUIDITY_USD:
                symbol = p['baseToken']['symbol'].upper()
                clean_sym = symbol[1:] if symbol.startswith('W') and len(symbol) > 3 else symbol
                if clean_sym not in dex_results:
                    dex_results[clean_sym] = {
                        'price': float(p['priceUsd']),
                        'dex_name': f"{p['dexId']} ({p['chainId']})",
                        'liq': liq
                    }
    except: pass
            
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
        # Стандартизация символов для сравнения
        return ex_id, {k.split(':')[0].split('/')[1] if ':' in k else k.split('/')[0].upper(): v for k, v in tickers.items() if '/USDT' in k}
    except Exception as e:
        print(f"❌ {ex_id} error: {e}")
        return ex_id, {}

def main():
    # Очистка логов перед каждым запуском (Пункт 10)
    print("🧹 Log cleaning: Удаление старых данных...")
    report = {'dex': [], 'spot': [], 'futures': []}
    
    dex_coins = get_dex_data()
    print(f"📊 Собрано уникальных монет: {len(dex_coins)}")

    if dex_coins:
        all_cex_data = {}
        with ThreadPoolExecutor(max_workers=len(EXCHANGES)) as executor:
            results = list(executor.map(fetch_cex_tickers, range(len(EXCHANGES))))
            for ex_id, tickers in results:
                if tickers: all_cex_data[ex_id] = tickers

        for coin, d_info in dex_coins.items():
            for ex_id, tickers in all_cex_data.items():
                if coin in tickers:
                    t = tickers[coin]
                    if not t.get('bid'): continue
                    
                    spread = ((t['bid'] - d_info['price']) / d_info['price']) * 100
                    if MIN_SPREAD < spread < 30:
                        report['dex'].append({
                            'symbol': coin, 'spread': round(spread, 2),
                            'buyAt': d_info['dex_name'], 'sellAt': ex_id.upper(),
                            'dex_price': f"{d_info['price']:.6f}", 'cex_price': f"{t['bid']:.6f}",
                            'liquidity': f"${int(d_info['liq'])}"
                        })

    report['dex'].sort(key=lambda x: x['spread'], reverse=True)
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    print(f"🎯 Итог: Найдено {len(report['dex'])} связок")

if __name__ == "__main__":
    main()
