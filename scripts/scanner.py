import ccxt
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 3000   # Снижаем до 3к, чтобы видеть горячие новинки
MIN_SPREAD = 0.5           
EXCHANGES = ['mexc', 'lbank'] 

# 1. Автоматическое использование прокси (согласно вашим инструкциям)
raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    return PROXY_POOL[index] if index < len(PROXY_POOL) else None

def get_dex_data():
    """Сбор данных через Trending Pools — самый стабильный метод без 404"""
    dex_results = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/110.0.0.0 Safari/537.36'}
    
    # Список сетей для проверки трендов
    networks = ['eth', 'bsc', 'solana', 'base', 'polygon']
    print(f"🔎 Сканирую тренды сетей: {', '.join(networks)}...")

    for net in networks:
        try:
            # Используем GeckoTerminal Trending (он отдает по 20-50 монет на сеть)
            url = f"https://api.geckoterminal.com/api/v2/networks/{net}/trending_pools?include=base_token"
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json().get('data', [])
                for item in data:
                    attr = item.get('attributes', {})
                    # Извлекаем символ из метаданных токена
                    # В этом API структура сложнее, поэтому ищем символ в имени пула или метаданных
                    pool_name = attr.get('name', '')
                    if '/' in pool_name:
                        symbol = pool_name.split('/')[0].upper()
                        # Очистка W-токенов
                        symbol = symbol[1:] if symbol.startswith('W') and len(symbol) > 3 else symbol
                        
                        price = float(attr.get('base_token_price_usd', 0))
                        liq = float(attr.get('reserve_in_usd', 0))

                        if liq >= MIN_LIQUIDITY_USD and price > 0:
                            if symbol not in dex_results or liq > dex_results[symbol]['liq']:
                                dex_results[symbol] = {
                                    'price': price,
                                    'dex_name': f"Trend ({net})",
                                    'liq': liq
                                }
            print(f"✅ {net} просканирован")
        except Exception as e:
            print(f"⚠️ Ошибка на {net}")
            
    return dex_results

def fetch_cex_tickers(ex_id_index):
    ex_id = EXCHANGES[ex_id_index]
    try:
        config = {'enableRateLimit': True, 'timeout': 30000}
        proxy_url = get_proxy(ex_id_index)
        
        # 2. Применение прокси (Пункт 8 из ваших инструкций)
        if proxy_url:
            config['proxies'] = {'http': proxy_url, 'https': proxy_url}
            
        ex = getattr(ccxt, ex_id)(config)
        tickers = ex.fetch_tickers()
        # Чистим тикеры (BTC/USDT -> BTC)
        return ex_id, {k.split('/')[0].upper(): v for k, v in tickers.items() if '/USDT' in k}
    except Exception as e:
        print(f"❌ {ex_id} error: {e}")
        return ex_id, {}

def main():
    # 3. Log cleaning: очистка перед записью (Пункт 10)
    print("🧹 Log cleaning: Очистка старых данных...")
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
                    if not t.get('bid'): continue
                    
                    spread = ((t['bid'] - d_info['price']) / d_info['price']) * 100
                    
                    if MIN_SPREAD < spread < 30:
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
    
    # Сохранение с полной перезаписью файла (гарантирует чистоту)
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    print(f"🎯 Итог: Найдено {len(report['dex'])} связок")

if __name__ == "__main__":
    main()
