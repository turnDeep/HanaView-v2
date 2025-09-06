document.addEventListener('DOMContentLoaded', () => {
    console.log("HanaView Dashboard Initialized");

    // --- Service Worker Registration ---
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js')
                .then(reg => console.log('Service Worker registered.', reg))
                .catch(err => console.log('Service Worker registration failed: ', err));
        });
    }

    // --- Tab-switching logic ---
    function initTabs() {
        const tabContainer = document.querySelector('.tab-container');
        tabContainer.addEventListener('click', (e) => {
            if (!e.target.matches('.tab-button')) return;

            const targetTab = e.target.dataset.tab;

            document.querySelectorAll('.tab-button').forEach(button => {
                button.classList.toggle('active', button.dataset.tab === targetTab);
            });
            document.querySelectorAll('.tab-pane').forEach(pane => {
                pane.classList.toggle('active', pane.id === `${targetTab}-content`);
            });
        });
    }

    // --- Rendering Functions ---

    function renderMarketOverview(container, marketData) {
        if (!container) return;
        container.innerHTML = ''; // Clear content

        const card = document.createElement('div');
        card.className = 'card';

        let content = '';

        // Fear & Greed Index
        const fgData = marketData.fear_and_greed;
        if (fgData && fgData.now !== null) {
            const rotation = (fgData.now / 100) * 180 - 90;
            content += `
                <div class="market-section">
                    <h3>Fear & Greed Index</h3>
                    <div class="fg-container">
                        <div class="fg-gauge">
                            <div class="fg-gauge-base"></div>
                            <div class="fg-gauge-needle" style="transform: rotate(${rotation}deg);"></div>
                            <div class="fg-gauge-center"></div>
                        </div>
                        <div class="fg-value-display">
                            <div class="fg-now-value">${fgData.now}</div>
                            <div class="fg-now-category">${fgData.category}</div>
                        </div>
                    </div>
                    <div class="fg-history">
                        <p><strong>Previous Close:</strong> ${fgData.previous_close || 'N/A'}</p>
                        <p><strong>1 Week Ago:</strong> ${fgData.prev_week || 'N/A'}</p>
                        <p><strong>1 Month Ago:</strong> ${fgData.prev_month || 'N/A'}</p>
                        <p><strong>1 Year Ago:</strong> ${fgData.prev_year || 'N/A'}</p>
                    </div>
                </div>
            `;
        }

        // AI Commentary
        if (marketData.ai_commentary) {
            content += `
                <div class="market-section">
                    <h3>AI市況解説</h3>
                    <p>${marketData.ai_commentary}</p>
                </div>
            `;
        }

        // TradingView Charts
        content += `
            <div class="market-grid">
                <div class="market-section">
                    <h3>VIX指数 (4時間足)</h3>
                    <div class="tradingview-widget-container" style="height:400px; width:100%;">
                        <div id="tradingview-vix"></div>
                    </div>
                </div>
                <div class="market-section">
                    <h3>米国10年債先物 (4時間足)</h3>
                    <div class="tradingview-widget-container" style="height:400px; width:100%;">
                        <div id="tradingview-t-note"></div>
                    </div>
                </div>
            </div>
        `;

        card.innerHTML = content;
        container.appendChild(card);

        // --- Embed TradingView Widgets ---
        // This requires the TradingView script to be loaded in index.html
        // The script is added to index.html in the next step.
        // For now, we define the creation logic.
        if (typeof TradingView !== 'undefined') {
            // VIX Chart
            new TradingView.widget({
                "autosize": true,
                "symbol": "TVC:VIX",
                "interval": "240",
                "timezone": "Asia/Tokyo",
                "theme": "light",
                "style": "1",
                "locale": "ja",
                "enable_publishing": false,
                "hide_side_toolbar": false,
                "allow_symbol_change": true,
                "container_id": "tradingview-vix"
            });

            // T-Note Chart
            new TradingView.widget({
                "autosize": true,
                "symbol": "ZN1!",
                "interval": "240",
                "timezone": "Asia/Tokyo",
                "theme": "light",
                "style": "1",
                "locale": "ja",
                "enable_publishing": false,
                "hide_side_toolbar": false,
                "allow_symbol_change": true,
                "container_id": "tradingview-t-note"
            });
        }
    }

    function renderNews(container, newsData) {
        if (!container) return;
        container.innerHTML = '';
        if (!newsData || (!newsData.summary && (!newsData.topics || newsData.topics.length === 0))) {
            container.innerHTML = '<div class="card"><p>ニュースデータがありません。</p></div>';
            return;
        }
        const card = document.createElement('div');
        card.className = 'card';
        if (newsData.summary) {
            card.innerHTML += `<div class="news-summary"><h3>今朝の3行サマリー</h3><p>${newsData.summary.replace(/\n/g, '<br>')}</p></div>`;
        }
        if (newsData.topics && newsData.topics.length > 0) {
            const topicsContainer = document.createElement('div');
            topicsContainer.className = 'main-topics-container';
            topicsContainer.innerHTML = '<h3>主要トピック</h3>';
            newsData.topics.forEach((topic, index) => {
                topicsContainer.innerHTML += `
                    <div class="topic-box">
                        <p class="topic-title ${index === 0 ? 'topic-title-red' : 'topic-title-blue'}">${index + 1}. ${topic.title}</p>
                        <p>${topic.body}</p>
                    </div>`;
            });
            card.appendChild(topicsContainer);
        }
        container.appendChild(card);
    }

    function getPerformanceColor(performance) {
        if (performance >= 3) return '#00c853';
        if (performance > 1) return '#2e7d32';
        if (performance > 0) return '#66bb6a';
        if (performance == 0) return '#888888';
        if (performance > -1) return '#ef5350';
        if (performance > -3) return '#e53935';
        return '#c62828';
    }

    function renderHeatmap(container, title, heatmapData) {
        if (!container) return;
        container.innerHTML = '';
        if (!heatmapData || !heatmapData.stocks || heatmapData.stocks.length === 0) {
            container.innerHTML = `<div class="card"><div class="heatmap-error">No data for ${title}.</div></div>`;
            return;
        }
        const card = document.createElement('div');
        card.className = 'card';
        const heatmapWrapper = document.createElement('div');
        heatmapWrapper.className = 'heatmap-wrapper';
        heatmapWrapper.innerHTML = `<h2 class="heatmap-main-title">${title}</h2>`;
        const width = 1000, height = 600;
        const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("width", "100%").attr("height", "auto").style("font-family", "sans-serif");
        const root = d3.hierarchy(d3.group(heatmapData.stocks, d => d.sector, d => d.industry)).sum(d => (d && d.market_cap) ? d.market_cap : 0).sort((a, b) => b.value - a.value);
        d3.treemap().size([width, height]).paddingTop(28).paddingInner(3).round(true)(root);
        const tooltip = d3.select("body").append("div").attr("class", "heatmap-tooltip").style("opacity", 0);
        const node = svg.selectAll("g").data(root.descendants()).join("g").attr("transform", d => `translate(${d.x0},${d.y0})`);
        node.filter(d => d.depth === 1 || d.depth === 2).append("text").attr("class", d => d.depth === 1 ? "sector-label" : "industry-label").attr("x", 4).attr("y", 20).text(d => d.data[0]);
        const leaf = node.filter(d => d.depth === 3);
        leaf.append("rect").attr("class", "stock-rect").attr("fill", d => getPerformanceColor(d.data.performance)).attr("width", d => d.x1 - d.x0).attr("height", d => d.y1 - d.y0)
            .on("mouseover", (event, d) => {
                tooltip.transition().duration(200).style("opacity", .9);
                tooltip.html(`<strong>${d.data.ticker}</strong><br/>${d.data.industry}<br/>Perf: ${d.data.performance.toFixed(2)}%<br/>Mkt Cap: ${(d.data.market_cap / 1e9).toFixed(2)}B`).style("left", (event.pageX + 5) + "px").style("top", (event.pageY - 28) + "px");
            }).on("mouseout", () => tooltip.transition().duration(500).style("opacity", 0));
        leaf.append("clipPath").attr("id", d => `clip-${d.data.ticker}`).append("rect").attr("width", d => d.x1 - d.x0).attr("height", d => d.y1 - d.y0);
        leaf.append("text").attr("class", "stock-label").attr("clip-path", d => `url(#clip-${d.data.ticker})`).selectAll("tspan").data(d => [d.data.ticker, `${d.data.performance.toFixed(2)}%`]).join("tspan").attr("x", 4).attr("y", (d, i) => i === 0 ? "1.1em" : "2.2em").text(d => d);
        heatmapWrapper.appendChild(svg.node());
        card.appendChild(heatmapWrapper);
        container.appendChild(card);
    }

    function renderIndicators(container, indicatorsData) {
        if (!container) return;
        container.innerHTML = '';
        if (!indicatorsData || !indicatorsData.economic || indicatorsData.economic.length === 0) {
            container.innerHTML = '<div class="card"><p>表示する経済指標はありません。</p></div>';
            return;
        }

        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = '<h3>経済指標カレンダー</h3>';

        const table = document.createElement('table');
        table.className = 'indicators-table';

        table.innerHTML = `
            <thead>
                <tr>
                    <th>時刻</th>
                    <th>国</th>
                    <th>指標名</th>
                    <th>重要度</th>
                    <th>予測</th>
                    <th>結果</th>
                </tr>
            </thead>
        `;

        const tbody = document.createElement('tbody');
        indicatorsData.economic.forEach(ind => {
            const row = document.createElement('tr');
            const importanceStars = '★'.repeat(ind.importance || 0).padEnd(3, '☆');
            row.innerHTML = `
                <td>${ind.time || '--'}</td>
                <td>${ind.country || '--'}</td>
                <td>${ind.name || '--'}</td>
                <td class="importance-${ind.importance || 0}">${importanceStars}</td>
                <td>${ind.forecast || '--'}</td>
                <td>${ind.result || '--'}</td>
            `;
            tbody.appendChild(row);
        });

        table.appendChild(tbody);
        card.appendChild(table);
        container.appendChild(card);
    }

    function renderColumn(container, columnData) {
        if (!container) return;
        container.innerHTML = '';
        const report = columnData ? columnData.weekly_report : null;

        if (!report || !report.content) {
            container.innerHTML = '<div class="card"><p>今週のAIコラムはまだありません。（毎週月曜日に生成されます）</p></div>';
            return;
        }

        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <div class="column-container">
                <h3>${report.title || '週次AIコラム'}</h3>
                <p class="column-date">Date: ${report.date || ''}</p>
                <div class="column-content">
                    ${report.content.replace(/\n/g, '<br>')}
                </div>
            </div>
        `;
        container.appendChild(card);
    }

    async function fetchDataAndRender() {
        try {
            const response = await fetch('/api/data');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            console.log("Data fetched successfully:", data);

            const lastUpdatedEl = document.getElementById('last-updated');
            if (data.last_updated) {
                lastUpdatedEl.textContent = `Last updated: ${new Date(data.last_updated).toLocaleString('ja-JP')}`;
            }

            renderMarketOverview(document.getElementById('market-content'), data.market);
            renderNews(document.getElementById('news-content'), data.news);
            renderHeatmap(document.getElementById('nasdaq-content'), 'NASDAQ 100 Heatmap', data.nasdaq_heatmap);
            renderHeatmap(document.getElementById('sp500-content'), 'S&P 500 Heatmap', data.sp500_heatmap);
            renderIndicators(document.getElementById('indicators-content'), data.indicators);
            renderColumn(document.getElementById('column-content'), data.column);

        } catch (error) {
            console.error("Failed to fetch data:", error);
            document.getElementById('dashboard-content').innerHTML = `<div class="card"><p>データの読み込みに失敗しました: ${error.message}</p></div>`;
        }
    }

    initTabs();
    fetchDataAndRender();
});