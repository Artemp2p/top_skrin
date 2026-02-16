let currentTab = 'spot';

async function loadData() {
    try {
        const response = await fetch('data/spreads.json');
        const data = await response.json();
        renderTable(data[currentTab]);
        document.getElementById('last-update').innerText = new Date().toLocaleTimeString();
    } catch (e) {
        console.error("Данные еще не созданы ботом");
    }
}

function renderTable(items) {
    const tbody = document.getElementById('table-body');
    tbody.innerHTML = '';

    items.forEach(item => {
        // Пункт 11: Фильтрация спреда до 50%
        if (item.spread > 0 && item.spread <= 50) {
            const row = `
                <tr>
                    <td>${item.symbol}</td>
                    <td class="spread-high">${item.spread}%</td>
                    <td>${item.buyAt} / ${item.buyPrice}</td>
                    <td>${item.sellAt} / ${item.sellPrice}</td>
                    <td>${item.networks}</td>
                    <td class="dex-only">${item.liquidity || '-'}</td>
                </tr>`;
            tbody.innerHTML += row;
        }
    });
}

function openTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    loadData();
}

// Постоянное обновление (Пункт 10)
setInterval(loadData, 5000); 
loadData();
