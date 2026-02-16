import ccxt
import json
import os

# --- ПУНКТ 1 и 8: Настройка бирж и их IP (прокси) ---
# Замени данные на свои или используй секреты GitHub
EXCHANGES_CONFIG = {
    'binance': {
        'proxy': 'http://user:pass@ip1:port', # Твой IP для Бинанса
        'ccxt_class': ccxt.binance
    },
    'bybit': {
        'proxy': 'http://user:pass@ip2:port', # Твой IP для Байбита
        'ccxt_class': ccxt.bybit
    },
    'okx': {
        'proxy': 'http://user:pass@ip3:port', # Твой IP для OKX
        'ccxt_class': ccxt.okx
    }
}

def get_exchange_data(name, config, symbol):
    try:
        # Инициализация биржи с прокси
        ex = config['ccxt_class']({
            'proxies': {'http': config['proxy'], 'https': config['proxy']},
            'timeout': 10000,
            'enableRateLimit': True
        })
        
        ticker = ex.fetch_ticker(symbol)
        
        # ПУНКТ 6: Получение сетей (упрощенно)
        # Для реального проекта нужно вызывать ex.fetch_currencies()
        networks = "ERC20, TRC20" 
        
        return {
            'name': name,
            'bid': ticker['bid'], # Цена продажи
            'ask': ticker['ask'], # Цена покупки
            'networks': networks
        }
    except Exception as e:
        print(f"Ошибка {name}: {e}")
        return None

def main():
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'] # Список монет для скана
    results = {'spot': [], 'futures': [], 'dex': []}

    for symbol in symbols:
        prices = []
        for name, config in EXCHANGES_CONFIG.items():
            data = get_exchange_data(name, config, symbol)
            if data:
                prices.append(data)

        # ПУНКТ 5 и 11: Расчет спреда и фильтрация
        for i in range(len(prices)):
            for j in range(len(prices)):
                if i == j: continue
                
                # Покупаем на i (ask), продаем на j (bid)
                buy_ex = prices[i]
                sell_ex = prices[j]
                
                spread = ((sell_ex['bid'] - buy_ex['ask']) / buy_ex['ask']) * 100

                if 0.1 < spread < 50: # Фильтр: от 0.1% до 50%
                    results['spot'].append({
                        'symbol': symbol,
                        'spread': round(spread, 2),
                        'buyAt': buy_ex['name'],
                        'buyPrice': buy_ex['ask'],
                        'sellAt': sell_ex['name'],
                        'sellPrice': sell_ex['bid'],
                        'networks': buy_ex['networks']
                    })

    # Сохраняем результат
    os.makedirs('data', exist_ok=True)
    with open('data/spreads.json', 'w') as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    main()
