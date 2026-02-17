import ccxt
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
MIN_LIQUIDITY_USD = 5000   # Оптимально для MEXC/LBank
MIN_SPREAD = 0.2           # Минимальный порог для теста
EXCHANGES = ['mexc', 'lbank'] 

# Автоматические прокси из секретов (согласно вашим инструкциям)
raw_proxies = os.getenv('PROXY_LIST', '')
PROXY_POOL = [p.strip() for p in raw_proxies.split('\n') if p.strip()]

def get_proxy(index):
    return PROXY_POOL[index] if index < len(PROXY_POOL) else None

def get_dex_data():
    """Глубокий сбор через несколько эндпоинтов GeckoTerminal"""
    dex_results = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Список сетей и типов пулов для максимального охвата (Пункт 12)
    networks = ['eth', 'bsc', 'solana', 'base', 'arbitrum', 'polygon', 'avalanche']
    types = ['trending_pools', 'new_pools']
    
    print(f"🔎 Начинаю глубокий сбор с {len(networks)} сетей...")
    
    for net in networks:
        for t in types:
            try:
                url = f"https://api.geckoterminal.com/api/v2/networks/{net}/{t}"
                res = requests.get(url, headers=headers, timeout=10).json()
                
                for p in res.get('data', []):
                    attr = p.get('attributes', {})
                    name = attr.get('name', '')
                    
                    if '/' in name:
                        # Чистим тикер: "PEPE/WETH" -> "PEPE"
                        symbol = name.split('/')[0].upper().strip()
                        # Убираем обертки (WETH -> ETH, WBTC -> BTC)
                        if symbol.startswith('W') and len(symbol) > 3:
                            symbol = symbol[1:]
                            
                        price = float(attr.get('base_token_price_usd') or 0)
                        liq = float(attr.get('reserve_in_usd') or 0)

                        if liq >= MIN_LIQUIDITY_USD and price > 0:
                            if symbol not in dex_results or liq > dex_results[symbol]['liq']:
                                dex_results[symbol] = {
                                    'price': price,
                                    'dex_name': f"{net.upper()}",
                                    'liq': liq
                                }
            except:
                continue
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
        # Собираем только USDT пары, приводим ключи к чистому виду
        return ex_id, {k.split('/')[0].upper().strip(): v for k, v in tickers.items() if '/USDT' in k}
    except Exception as e:
        print(f"❌ {ex_id} error: {e}")
        return ex_id, {}

def main():
    # Log cleaning: очистка перед записью (согласно вашим инструкциям)
    print("🧹 Очистка старых данных и запуск сканера...")
    report = {'dex': [], 'spot': [], 'futures': []}
    
    dex_coins = get_dex_data()
    print(f"📊 Всего уникальных монет собрано с DEX: {len(dex_coins)}")

    all_cex_data = {}
    with ThreadPoolExecutor(max_workers=len(EXCHANGES)) as executor:
        results = list(executor.map(fetch_cex_tickers, range(len(EXCHANGES))))
        for ex_id, tickers in results:
            if tickers:
                all_cex_data[ex_id] = tickers
                print(f"✅ {ex_id.upper()} готова: {len(tickers)} пар")

    # Поиск связок
    for coin, d_info in dex_coins.items():
        for ex_id, tickers in all_cex_data.items():
            if coin in tickers:
                t = tickers[coin]
                if not t['bid']: continue
                
                # Спред: (Цена_CEX - Цена_DEX) / Цена_DEX
                spread = ((t['bid'] - d_info['price']) / d_info['price']) * 100
                
                if MIN_SPREAD < spread < 40:
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
    
    # Сохранение (Пункт 10)
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)
    
    print(f"🎯 Найдено связок: {len(report['dex'])}")

if __name__ == "__main__":
    main()
