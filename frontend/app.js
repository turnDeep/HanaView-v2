document.addEventListener('DOMContentLoaded', () => {
    console.log("HanaView Dashboard Initialized");

    // Register Service Worker
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js')
                .then(registration => {
                    console.log('Service Worker registered: ', registration);
                })
                .catch(registrationError => {
                    console.log('Service Worker registration failed: ', registrationError);
                });
        });
    }

    const dashboardElement = document.getElementById('dashboard');

    function renderNews(container, newsData) {
        if (!newsData || (!newsData.summary && !newsData.topics)) {
            container.innerHTML += '<h2>News</h2><p>No news data available.</p>';
            return;
        }

        const newsContainer = document.createElement('div');
        newsContainer.className = 'news-container';

        // --- 3-line summary ---
        if (newsData.summary) {
            const summaryDiv = document.createElement('div');
            summaryDiv.className = 'news-summary';
            const summaryTitle = document.createElement('h3');
            summaryTitle.textContent = '今朝の3行サマリー';
            summaryDiv.appendChild(summaryTitle);
            const summaryText = document.createElement('p');
            summaryText.textContent = newsData.summary;
            summaryDiv.appendChild(summaryText);
            newsContainer.appendChild(summaryDiv);
        }

        // --- Main Topics ---
        if (newsData.topics && newsData.topics.length > 0) {
            const topicsContainer = document.createElement('div');
            topicsContainer.className = 'main-topics-container';
            const topicsTitle = document.createElement('h3');
            topicsTitle.textContent = '主要トピック';
            topicsContainer.appendChild(topicsTitle);

            newsData.topics.forEach((topic, index) => {
                const topicBox = document.createElement('div');
                topicBox.className = 'topic-box';

                const topicTitle = document.createElement('p');
                topicTitle.className = 'topic-title';

                // Coloring titles based on index
                if (index === 0) {
                    topicTitle.classList.add('topic-title-red');
                } else {
                    topicTitle.classList.add('topic-title-blue');
                }
                topicTitle.textContent = `${index + 1}. ${topic.title}`;

                const topicBody = document.createElement('p');
                topicBody.textContent = topic.body;

                topicBox.appendChild(topicTitle);
                topicBox.appendChild(topicBody);
                topicsContainer.appendChild(topicBox);
            });
            newsContainer.appendChild(topicsContainer);
        }

        container.appendChild(newsContainer);
    }

    function getPerformanceColor(performance) {
        // Finviz風の色分け
        if (performance >= 3) return '#00c853';    // Strong Green
        if (performance > 1) return '#2e7d32';     // Medium Green
        if (performance > 0) return '#66bb6a';     // Light Green
        if (performance == 0) return '#888888';    // Neutral Gray
        if (performance > -1) return '#ef5350';    // Light Red
        if (performance > -3) return '#e53935';    // Medium Red
        return '#c62828';                          // Strong Red
    }

    function renderHeatmap(container, title, heatmapData) {
        if (!heatmapData || !heatmapData.stocks || heatmapData.stocks.length === 0) {
            container.innerHTML += `<div class="heatmap-error">No data for ${title}.</div>`;
            return;
        }

        const heatmapWrapper = document.createElement('div');
        heatmapWrapper.className = 'heatmap-wrapper';

        const headerTitle = document.createElement('h2');
        headerTitle.className = 'heatmap-main-title';
        headerTitle.textContent = title;
        heatmapWrapper.appendChild(headerTitle);

        // --- D3 Treemap Implementation ---
        const width = 1000;
        const height = 600;
        const svg = d3.create("svg")
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("width", "100%")
            .attr("height", "auto")
            .style("font-family", "sans-serif");

        // 1. Create hierarchy
        const groupedData = d3.group(heatmapData.stocks, d => d.sector, d => d.industry);
        const root = d3.hierarchy(groupedData)
            .sum(d => (d.market_cap && d.ticker) ? d.market_cap : 0) // Sum market_cap for leaf nodes
            .sort((a, b) => b.value - a.value);

        // 2. Create treemap layout
        const treemap = d3.treemap()
            .size([width, height])
            .paddingTop(28)
            .paddingInner(3)
            .round(true);

        treemap(root);

        // Tooltip
        const tooltip = d3.select("body").append("div")
            .attr("class", "heatmap-tooltip")
            .style("opacity", 0);

        // 3. Draw the cells
        const node = svg.selectAll("g")
            .data(root.descendants())
            .join("g")
            .attr("transform", d => `translate(${d.x0},${d.y0})`);

        // Sector and Industry Headers
        node.filter(d => d.depth === 1 || d.depth === 2)
            .append("text")
            .attr("class", d => d.depth === 1 ? "sector-label" : "industry-label")
            .attr("x", 4)
            .attr("y", 20)
            .text(d => d.data[0]);

        // Stock Tiles
        const leaf = node.filter(d => d.depth === 3);

        leaf.append("rect")
            .attr("class", "stock-rect")
            .attr("fill", d => getPerformanceColor(d.data.performance))
            .attr("width", d => d.x1 - d.x0)
            .attr("height", d => d.y1 - d.y0)
            .on("mouseover", (event, d) => {
                tooltip.transition().duration(200).style("opacity", .9);
                tooltip.html(`<strong>${d.data.ticker}</strong><br/>${d.data.industry}<br/>Perf: ${d.data.performance.toFixed(2)}%<br/>Mkt Cap: ${(d.data.market_cap / 1e9).toFixed(2)}B`)
                    .style("left", (event.pageX + 5) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", () => {
                tooltip.transition().duration(500).style("opacity", 0);
            });

        // Clip-path for text
        leaf.append("clipPath")
            .attr("id", d => `clip-${d.data.ticker}`)
            .append("rect")
            .attr("width", d => d.x1 - d.x0)
            .attr("height", d => d.y1 - d.y0);

        // Stock Labels (Ticker and Performance)
        leaf.append("text")
            .attr("class", "stock-label")
            .attr("clip-path", d => `url(#clip-${d.data.ticker})`)
            .selectAll("tspan")
            .data(d => [d.data.ticker, `${d.data.performance.toFixed(2)}%`])
            .join("tspan")
            .attr("x", 4)
            .attr("y", (d, i) => i === 0 ? "1.1em" : "2.2em")
            .text(d => d);

        heatmapWrapper.appendChild(svg.node());
        container.appendChild(heatmapWrapper);
    }


    function renderAllHeatmaps(container, sp500Data, nasdaqData) {
        if (sp500Data) {
            renderHeatmap(container, 'S&P 500 Heatmap', sp500Data);
        }
        if (nasdaqData) {
            renderHeatmap(container, 'NASDAQ 100 Heatmap', nasdaqData);
        }
    }

    async function fetchData() {
        try {
            const response = await fetch('/api/data');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log("Data fetched successfully:", data);

            dashboardElement.innerHTML = ''; // Clear loading message

            // News Section
            if (data.news) {
                renderNews(dashboardElement, data.news);
            }

            // Heatmaps Section
            const heatmapsContainer = document.createElement('div');
            heatmapsContainer.className = 'heatmaps-main-container';

            // Use the fetched data directly
            let sp500HeatmapData = data.sp500_heatmap;
            let nasdaqHeatmapData = data.nasdaq_heatmap;
            
            renderAllHeatmaps(heatmapsContainer, sp500HeatmapData, nasdaqHeatmapData);
            dashboardElement.appendChild(heatmapsContainer);

        } catch (error) {
            console.error("Failed to fetch data:", error);
            dashboardElement.innerHTML = `<p>Error loading data: ${error.message}</p>`;
        }
    }

    fetchData();
});