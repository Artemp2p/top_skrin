import ccxt
import json
import os
import requests

# --- КОНФИГУРАЦИЯ ---
MIN_LIQUIDITY_USD = 2000
MIN_SPREAD = 0.2

def get_networks(ex, coin):
    """Пункт 6: Получение реальных сетей для монеты"""
    try:
        if not ex.currencies: ex.load_markets()
        if coin in ex.currencies:
            nets = ex.currencies[coin].get('networks', {})
            return "/".join(nets.keys())
    except: pass
    return "BEP20/ERC20/TRC20"

def get_dex_data():
    """Пункт 12: Скан всех популярных блокчейнов"""
    dex_results = []
    chains = ['ethereum', 'bsc', 'arbitrum', 'polygon', 'base', 'solana', 'avalanche']
    
    for chain in chains:
        try:
            url = f"https://api.dexscreener.com/latest/dex/chains/{chain}"
            data = requests.get(url, timeout=10).json()
            for p in data.get('pairs', []):
                liq = p.get('liquidity', {}).get('usd', 0)
                if liq >= MIN_LIQUIDITY_USD:
                    dex_results.append({
                        'symbol': p['baseToken']['symbol'],
                        'price': float(p['priceUsd']),
                        'dex': f"{p['dexId']} ({chain})",
                        'liq': liq
                    })
        except: continue
    return dex_results

def main():
    # Проверка статуса (кнопка старт/стоп)
    try:
        with open('data/status.json', 'r') as f:
            if not json.load(f).get('active', True): 
                print("Сканер остановлен пользователем."); return
    except: pass

    # Твои биржи (Пункт 1: можно расширять список)
    active_exchanges = ['binance', 'bybit', 'okx', 'mexc', 'gateio']
    spot_data = {}
    
    # Сбор данных с CEX
    for name in active_exchanges:
        try:
            ex = getattr(ccxt, name)({'enableRateLimit': True})
            tickers = ex.fetch_tickers()
            for sym, t in tickers.items():
                if '/USDT' in sym and t['bid']:
                    coin = sym.split('/')[0]
                    spot_data[f"{name}_{sym}"] = {
                        'ex': name, 'sym': sym, 'coin': coin,
                        'bid': t['bid'], 'ask': t['ask'],
                        'net': get_networks(ex, coin) # Сети (Пункт 6)
                    }
        except: continue

    dex_data = get_dex_data()
    report = {'spot': [], 'futures': [], 'dex': []}

    # Поиск DEX-Spot связок (Пункт 4, 7)
    for d in dex_data:
        for key, s in spot_data.items():
            if d['symbol'] == s['coin']:
                spread = ((s['bid'] - d['price']) / d['price']) * 100
                if MIN_SPREAD < spread < 50:
                    report['dex'].append({
                        'symbol': d['symbol'],
                        'spread': round(spread, 2),
                        'buyAt': d['dex'],
                        'sellAt': s['ex'],
                        'networks': s['net'],
                        'liquidity': f"${int(d['liq'])}"
                    })

    # Сохранение (Пункт 10)
    with open('data/spreads.json', 'w') as f:
        json.dump(report, f, indent=4)

if __name__ == "__main__":
    main()
