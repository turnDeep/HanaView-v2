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

    function renderLightweightChart(containerId, data, title) {
        const container = document.getElementById(containerId);
        if (!container || !data || data.length === 0) {
            container.innerHTML = `<p>Chart data for ${title} is not available.</p>`;
            return;
        }
        container.innerHTML = ''; // Clear previous content

        const chart = LightweightCharts.createChart(container, {
            width: container.clientWidth,
            height: 300, // Fixed height for chart
            layout: {
                backgroundColor: '#ffffff',
                textColor: '#333333',
            },
            grid: {
                vertLines: { color: '#e1e1e1' },
                horzLines: { color: '#e1e1e1' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            timeScale: {
                borderColor: '#cccccc',
                timeVisible: true,
                secondsVisible: false,
            },
        });

        const candlestickSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderDownColor: '#ef5350',
            borderUpColor: '#26a69a',
            wickDownColor: '#ef5350',
            wickUpColor: '#26a69a',
        });

        // Convert backend time string to UTC timestamp for the chart
        const chartData = data.map(item => ({
            time: (new Date(item.time).getTime() / 1000), // Convert to UNIX timestamp (seconds)
            open: item.open,
            high: item.high,
            low: item.low,
            close: item.close,
        }));

        candlestickSeries.setData(chartData);
        chart.timeScale().fitContent();

        // Handle resizing
        new ResizeObserver(entries => {
            if (entries.length > 0 && entries[0].contentRect.width > 0) {
                chart.applyOptions({ width: entries[0].contentRect.width });
            }
        }).observe(container);
    }

    function renderMarketOverview(container, marketData) {
        if (!container) return;
        container.innerHTML = ''; // Clear content

        const card = document.createElement('div');
        card.className = 'card';

        let content = '';

        // Fear & Greed Index
        const fgData = marketData.fear_and_greed;
        if (fgData) {
            // Add a cache-busting query parameter
            const timestamp = new Date().getTime();
            content += `
                <div class="market-section">
                    <h3>Fear & Greed Index</h3>
                    <div class="fg-container" style="display: flex; justify-content: center; align-items: center; min-height: 400px;">
                        <img src="/fear_and_greed_gauge.png?v=${timestamp}" alt="Fear and Greed Index Gauge" style="max-width: 100%; height: auto;">
                    </div>
                </div>
            `;
        }

        // Lightweight Charts
        content += `
            <div class="market-grid">
                <div class="market-section">
                    <h3>VIX (4h足)</h3>
                    <div class="chart-container" id="vix-chart-container"></div>
                </div>
                <div class="market-section">
                    <h3>米国10年債金利 (4h足)</h3>
                    <div class="chart-container" id="t-note-chart-container"></div>
                </div>
            </div>
        `;

        // AI Commentary
        if (marketData.ai_commentary) {
            content += `
                <div class="market-section">
                    <h3>AI市況解説</h3>
                    <p>${marketData.ai_commentary}</p>
                </div>
            `;
        }

        card.innerHTML = content;
        container.appendChild(card);

        // Render lightweight charts
        if (marketData.vix && marketData.vix.history) {
            renderLightweightChart('vix-chart-container', marketData.vix.history, 'VIX');
        }
        if (marketData.t_note_future && marketData.t_note_future.history) {
            renderLightweightChart('t-note-chart-container', marketData.t_note_future.history, '10y T-Note');
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
        
        // Add sector and industry labels with size-based visibility
        node.filter(d => d.depth === 1 || d.depth === 2).each(function(d) {
            const groupWidth = d.x1 - d.x0;
            const groupHeight = d.y1 - d.y0;
            const groupArea = groupWidth * groupHeight;
            
            // Minimum area thresholds
            const minAreaForSector = 2000;  // Minimum area to show sector label
            const minAreaForIndustry = 1500; // Minimum area to show industry label
            
            if (d.depth === 1 && groupArea > minAreaForSector) {
                // Sector label
                const fontSize = Math.min(16, Math.max(12, groupWidth / 15));
                d3.select(this).append("text")
                    .attr("class", "sector-label")
                    .attr("x", 4)
                    .attr("y", 20)
                    .style("font-size", `${fontSize}px`)
                    .text(d.data[0]);
            } else if (d.depth === 2 && groupArea > minAreaForIndustry) {
                // Industry label - with truncation if needed
                const fontSize = Math.min(13, Math.max(10, groupWidth / 20));
                const maxChars = Math.floor(groupWidth / 7); // Approximate character limit based on width
                let labelText = d.data[0];
                
                // Truncate text if it's too long for the available space
                if (labelText.length > maxChars && maxChars > 3) {
                    labelText = labelText.substring(0, maxChars - 1) + "…";
                }
                
                // Only show if there's enough space
                if (maxChars > 5) {
                    d3.select(this).append("text")
                        .attr("class", "industry-label")
                        .attr("x", 4)
                        .attr("y", 20)
                        .style("font-size", `${fontSize}px`)
                        .text(labelText);
                }
            }
        });
        
        const leaf = node.filter(d => d.depth === 3);
        leaf.append("rect").attr("class", "stock-rect").attr("fill", d => getPerformanceColor(d.data.performance)).attr("width", d => d.x1 - d.x0).attr("height", d => d.y1 - d.y0)
            .on("mouseover", (event, d) => {
                tooltip.transition().duration(200).style("opacity", .9);
                tooltip.html(`<strong>${d.data.ticker}</strong><br/>${d.data.industry}<br/>Perf: ${d.data.performance.toFixed(2)}%<br/>Mkt Cap: ${(d.data.market_cap / 1e9).toFixed(2)}B`).style("left", (event.pageX + 5) + "px").style("top", (event.pageY - 28) + "px");
            }).on("mouseout", () => tooltip.transition().duration(500).style("opacity", 0));
        
        // Calculate tile dimensions and apply dynamic text sizing
        leaf.each(function(d) {
            const tileWidth = d.x1 - d.x0;
            const tileHeight = d.y1 - d.y0;
            const tileArea = tileWidth * tileHeight;
            const minAreaForText = 800; // Minimum area to show text
            const minAreaForPerf = 1500; // Minimum area to show performance percentage
            
            if (tileArea > minAreaForText) {
                const selection = d3.select(this);
                
                // Calculate font size based on tile dimensions
                // Use the smaller dimension to ensure text fits
                const minDimension = Math.min(tileWidth, tileHeight);
                let fontSize = Math.max(8, Math.min(16, minDimension / 4));
                
                // Add clipPath for text overflow
                selection.append("clipPath")
                    .attr("id", `clip-${d.data.ticker}`)
                    .append("rect")
                    .attr("width", tileWidth)
                    .attr("height", tileHeight);
                
                const textGroup = selection.append("text")
                    .attr("class", "stock-label")
                    .attr("clip-path", `url(#clip-${d.data.ticker})`)
                    .style("font-size", `${fontSize}px`);
                
                // Add ticker symbol
                textGroup.append("tspan")
                    .attr("x", 4)
                    .attr("y", fontSize + 2)
                    .text(d.data.ticker);
                
                // Add performance percentage only if tile is large enough
                if (tileArea > minAreaForPerf) {
                    const perfFontSize = fontSize * 0.85;
                    textGroup.append("tspan")
                        .attr("x", 4)
                        .attr("y", fontSize + perfFontSize + 4)
                        .style("font-size", `${perfFontSize}px`)
                        .text(`${d.data.performance.toFixed(1)}%`);
                }
            }
        });
        
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
            renderHeatmap(document.getElementById('nasdaq-heatmap-1d'), 'NASDAQ 100 (1-Day)', data.nasdaq_heatmap_1d);
            renderHeatmap(document.getElementById('nasdaq-heatmap-1w'), 'NASDAQ 100 (1-Week)', data.nasdaq_heatmap_1w);
            renderHeatmap(document.getElementById('nasdaq-heatmap-1m'), 'NASDAQ 100 (1-Month)', data.nasdaq_heatmap_1m);
            renderHeatmap(document.getElementById('sp500-heatmap-1d'), 'S&P 500 (1-Day)', data.sp500_heatmap_1d);
            renderHeatmap(document.getElementById('sp500-heatmap-1w'), 'S&P 500 (1-Week)', data.sp500_heatmap_1w);
            renderHeatmap(document.getElementById('sp500-heatmap-1m'), 'S&P 500 (1-Month)', data.sp500_heatmap_1m);
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
