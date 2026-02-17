import ccxt
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 3000   # Снижаем до 3к для новых листингов (Пункт 12)
MIN_SPREAD = 0.5           
EXCHANGES = ['mexc', 'lbank'] 

# Автоматическое использование прокси (Пункт 8)
raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    return PROXY_POOL[index] if index < len(PROXY_POOL) else None

def get_dex_data():
    """Сбор данных через эндпоинты последних листингов и топов"""
    dex_results = {}
    # Используем эндпоинты последних и самых активных пар
    endpoints = [
        "https://api.dexscreener.com/token-boosts/latest/v1",
        "https://api.dexscreener.com/token-boosts/top/v1",
        "https://api.dexscreener.com/latest/dex/search?q=USDT"
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    print(f"🔎 Сканирую топовые и новые листинги DEX...")
    
    for url in endpoints:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                # В новых эндпоинтах структура может отличаться, обрабатываем аккуратно
                data = response.json()
                # Если это поиск, берем 'pairs', если бусты - там список объектов напрямую
                pairs = data if isinstance(data, list) else data.get('pairs', [])
                
                for p in pairs:
                    # Извлекаем данные (учитываем разницу в форматах API)
                    base_token = p.get('baseToken', p.get('tokenAddress', {}))
                    if not base_token: continue
                    
                    symbol = p.get('baseToken', {}).get('symbol', '').upper()
                    if not symbol: continue
                    
                    # Ликвидность и цена (Пункт 12)
                    liq = p.get('liquidity', {}).get('usd', 0)
                    price = float(p.get('priceUsd', 0))
                    
                    if liq >= MIN_LIQUIDITY_USD and price > 0:
                        clean_sym = symbol[1:] if symbol.startswith('W') and len(symbol) > 3 else symbol
                        
                        if clean_sym not in dex_results or liq > dex_results[clean_sym]['liq']:
                            dex_results[clean_sym] = {
                                'price': price,
                                'dex_name': f"{p.get('dexId', 'DEX')} ({p.get('chainId', 'chain')})",
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
        return ex_id, {k.split('/')[0].upper(): v for k, v in tickers.items() if '/USDT' in k}
    except Exception as e:
        print(f"❌ {ex_id} error: {e}")
        return ex_id, {}

def main():
    # Функция очистки логов перед стартом (Пункт 10)
    print("🧹 Log cleaning: Подготовка свежего отчета...")
    report = {'dex': [], 'spot': [], 'futures': []}
    
    dex_coins = get_dex_data()
    print(f"📊 Собрано уникальных монет с DEX: {len(dex_coins)}")

    if dex_coins:
        all_cex_data = {}
        with ThreadPoolExecutor(max_workers=len(EXCHANGES)) as executor:
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
                    
                    # Ограничиваем спред реалистичными 50% (Пункт 7)
                    if MIN_SPREAD < spread < 50:
                        report['dex'].append({
                            'symbol': coin,
                            'spread': round(spread, 2),
                            'buyAt': d_info['dex_name'],
                            'sellAt': ex_id.upper(),
                            'dex_price': f"{d_info['price']:.8f}",
                            'cex_price': f"{t['bid']:.8f}",
                            'liquidity': f"${int(d_info['liq'])}"
                        })

    report['dex'].sort(key=lambda x: x['spread'], reverse=True)
    
    # Сохранение с автоматической перезаписью старых данных (Пункт 10)
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    print(f"🎯 Итог: Найдено {len(report['dex'])} связок")

if __name__ == "__main__":
    main()
