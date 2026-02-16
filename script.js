let currentTab = 'dex'; // По умолчанию открываем DEX, так как там сейчас больше всего данных

async function loadData() {
    try {
        // Добавляем timestamp, чтобы браузер не брал старый файл из кэша
        const response = await fetch('./data/spreads.json?t=' + Date.now());
        if (!response.ok) throw new Error("Файл не найден");
        
        const data = await response.json();
        console.log("Данные загружены:", data); // Для проверки в консоли браузера (F12)
        
        renderTable(data[currentTab]);
        document.getElementById('last-update').innerText = new Date().toLocaleTimeString();
    } catch (e) {
        console.error("Ошибка загрузки:", e);
        document.getElementById('table-body').innerHTML = 
            '<tr><td colspan="6" style="text-align:center; color:red;">Ошибка: Данные еще не собраны ботом. Запустите Action!</td></tr>';
    }
}

function renderTable(items) {
    const tbody = document.getElementById('table-body');
    tbody.innerHTML = '';

    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">В этой категории пока нет выгодных связок (>0.2%)</td></tr>';
        return;
    }

    items.forEach(item => {
        const row = `
            <tr>
                <td><b>${item.symbol}</b></td>
                <td style="color: #00c853; font-weight: bold;">${item.spread}%</td>
                <td>${item.buyAt}</td>
                <td>${item.sellAt}</td>
                <td><small>${item.networks || 'Auto'}</small></td>
                <td>${item.liquidity || '-'}</td>
            </tr>`;
        tbody.innerHTML += row;
    });
}

function openTab(tab) {
    currentTab = tab;
    // Смена активного класса у кнопок
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.currentTarget.classList.add('active');
    loadData();
}

// Запуск
loadData();
setInterval(loadData, 30000); // Обновлять раз в 30 сек
