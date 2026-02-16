let scannerActive = true;
let myExchanges = ['binance', 'bybit', 'okx']; // Биржи по умолчанию

async function loadData() {
    try {
        const res = await fetch('./data/spreads.json');
        const data = await res.json();
        renderTable(data[currentTab]);
        
        // Проверка статуса (для кнопки)
        const statusRes = await fetch('./data/status.json');
        const status = await statusRes.json();
        updateStatusUI(status.active);
    } catch (e) { console.log("Ожидание данных..."); }
}

function updateStatusUI(isActive) {
    scannerActive = isActive;
    const btn = document.getElementById('btn-toggle');
    const statusText = document.getElementById('scanner-status');
    
    if (isActive) {
        btn.innerText = "Остановить сканер";
        btn.className = "btn-stop";
        statusText.innerText = "Статус: Работает";
    } else {
        btn.innerText = "Запустить сканер";
        btn.className = "btn-start";
        statusText.innerText = "Статус: Остановлен";
    }
}

// В реальном проекте для управления через кнопку нужен GitHub API Token.
// Пока сделаем локальную имитацию, чтобы бот видел флаг в файле.
async function toggleScanner() {
    alert("Для работы кнопки нужно настроить GitHub API. Бот пока работает по расписанию.");
}
