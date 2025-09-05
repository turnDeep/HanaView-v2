document.addEventListener('DOMContentLoaded', () => {
    console.log("HanaView Dashboard Initialized");

    const dashboardElement = document.getElementById('dashboard');

    function renderHeatmap(container, title, heatmapData) {
        if (!heatmapData || !heatmapData.sectors) {
            container.innerHTML += `<h2>${title}</h2><p>No heatmap data available.</p>`;
            return;
        }

        const heatmapContainer = document.createElement('div');
        heatmapContainer.className = 'heatmap-container';

        let totalMarketCap = 0;
        Object.values(heatmapData.sectors).forEach(stocks => {
            stocks.forEach(stock => {
                totalMarketCap += stock.market_cap || 0;
            });
        });

        for (const sectorName in heatmapData.sectors) {
            const sectorDiv = document.createElement('div');
            sectorDiv.className = 'sector';

            const sectorTitle = document.createElement('h3');
            sectorTitle.textContent = sectorName;
            sectorDiv.appendChild(sectorTitle);

            const stocksContainer = document.createElement('div');
            stocksContainer.className = 'stocks-container';

            const stocks = heatmapData.sectors[sectorName];
            stocks.forEach(stock => {
                const stockDiv = document.createElement('div');
                stockDiv.className = 'stock-tile';

                // Set color based on performance
                if (stock.performance > 0) {
                    stockDiv.style.backgroundColor = `rgba(0, 128, 0, ${Math.min(0.2 + stock.performance / 5, 1)})`; // Green
                } else {
                    stockDiv.style.backgroundColor = `rgba(255, 0, 0, ${Math.min(0.2 + Math.abs(stock.performance) / 5, 1)})`; // Red
                }

                // Set size based on market cap
                const sizePercentage = (stock.market_cap / totalMarketCap) * 5000; // Scaling factor
                stockDiv.style.width = `${Math.max(sizePercentage, 2)}%`;
                stockDiv.style.height = `${Math.max(sizePercentage, 2)}%`;

                stockDiv.innerHTML = `
                    <span class="ticker">${stock.ticker}</span>
                    <span class="performance">${stock.performance.toFixed(2)}%</span>
                `;
                stockDiv.title = `${stock.ticker}: ${stock.performance.toFixed(2)}%`;
                stocksContainer.appendChild(stockDiv);
            });

            sectorDiv.appendChild(stocksContainer);
            heatmapContainer.appendChild(sectorDiv);
        }

        const titleElement = document.createElement('h2');
        titleElement.textContent = title;
        container.appendChild(titleElement);
        container.appendChild(heatmapContainer);
    }

    async function fetchData() {
        try {
            const response = await fetch('/api/data');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log("Data fetched successfully:", data);

            // Clear loading message
            dashboardElement.innerHTML = '';

            // For now, render both heatmaps directly
            if (data.sp500_heatmap) {
                renderHeatmap(dashboardElement, 'S&P 500 Heatmap', data.sp500_heatmap);
            }
            if (data.nasdaq_heatmap) {
                renderHeatmap(dashboardElement, 'NASDAQ 100 Heatmap', data.nasdaq_heatmap);
            }

        } catch (error) {
            console.error("Failed to fetch data:", error);
            dashboardElement.innerHTML = `<p>Error loading data: ${error.message}</p>`;
        }
    }

    fetchData();
});
