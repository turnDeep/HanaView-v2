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
        if (performance >= 5) return '#00c853';      // 明るい緑
        if (performance >= 3) return '#2e7d32';      // 緑
        if (performance >= 1) return '#66bb6a';      // 薄緑
        if (performance >= 0) return '#81c784';      // より薄い緑
        if (performance >= -1) return '#ffcdd2';     // 薄い赤
        if (performance >= -3) return '#ef5350';     // 赤
        if (performance >= -5) return '#e53935';     // 濃い赤
        return '#c62828';                            // 暗い赤
    }

    function calculateTileSize(marketCap, totalMarketCap, containerArea) {
        // 時価総額に基づくタイルサイズの計算
        const ratio = marketCap / totalMarketCap;
        const area = containerArea * ratio;
        const size = Math.sqrt(area);
        // 最小サイズと最大サイズの制限
        return Math.max(30, Math.min(150, size));
    }

    function renderHeatmap(container, title, heatmapData, periodLabel) {
        if (!heatmapData || !heatmapData.sectors) {
            container.innerHTML += `<div class="heatmap-error">No ${title} data available.</div>`;
            return;
        }

        const heatmapWrapper = document.createElement('div');
        heatmapWrapper.className = 'heatmap-wrapper';

        // タイトルとピリオドラベル
        const heatmapHeader = document.createElement('div');
        heatmapHeader.className = 'heatmap-header';
        const headerTitle = document.createElement('h3');
        headerTitle.textContent = `${title} - ${periodLabel}`;
        heatmapHeader.appendChild(headerTitle);
        heatmapWrapper.appendChild(heatmapHeader);

        const heatmapContainer = document.createElement('div');
        heatmapContainer.className = 'heatmap-container';

        // セクターごとに処理
        const sectors = heatmapData.sectors;
        const sectorOrder = [
            'Technology',
            'Healthcare',
            'Financial',
            'Consumer Cyclical',
            'Communication Services',
            'Industrials',
            'Consumer Defensive',
            'Energy',
            'Basic Materials',
            'Real Estate',
            'Utilities'
        ];

        // 全体の時価総額を計算
        let totalMarketCap = 0;
        Object.values(sectors).forEach(stocks => {
            stocks.forEach(stock => {
                totalMarketCap += stock.market_cap || 1000000000; // デフォルト10億ドル
            });
        });

        sectorOrder.forEach(sectorName => {
            if (!sectors[sectorName] || sectors[sectorName].length === 0) return;

            const sectorDiv = document.createElement('div');
            sectorDiv.className = 'sector';
            
            // セクター名
            const sectorTitle = document.createElement('div');
            sectorTitle.className = 'sector-title';
            sectorTitle.textContent = sectorName;
            sectorDiv.appendChild(sectorTitle);

            // 銘柄タイルコンテナ
            const stocksContainer = document.createElement('div');
            stocksContainer.className = 'stocks-container';

            // 銘柄をパフォーマンス順にソート（大きい順）
            const sortedStocks = [...sectors[sectorName]].sort((a, b) => {
                return Math.abs(b.performance) - Math.abs(a.performance);
            });

            sortedStocks.forEach(stock => {
                const stockTile = document.createElement('div');
                stockTile.className = 'stock-tile';
                
                // タイルサイズを時価総額に基づいて計算
                const containerArea = 10000; // 基準面積
                const tileSize = calculateTileSize(
                    stock.market_cap || 1000000000,
                    totalMarketCap,
                    containerArea
                );
                
                // スマホ用にサイズを調整（最大幅を制限）
                const mobileSize = Math.min(tileSize * 0.7, 60);
                stockTile.style.width = `${mobileSize}px`;
                stockTile.style.height = `${mobileSize}px`;
                
                // 色設定
                stockTile.style.backgroundColor = getPerformanceColor(stock.performance);
                
                // ティッカーシンボル
                const ticker = document.createElement('div');
                ticker.className = 'ticker';
                ticker.textContent = stock.ticker;
                
                // パフォーマンス
                const performance = document.createElement('div');
                performance.className = 'performance';
                const perfValue = stock.performance || 0;
                performance.textContent = `${perfValue > 0 ? '+' : ''}${perfValue.toFixed(2)}%`;
                
                stockTile.appendChild(ticker);
                stockTile.appendChild(performance);
                
                // ホバー/タップ時のツールチップ
                stockTile.title = `${stock.ticker}: ${perfValue > 0 ? '+' : ''}${perfValue.toFixed(2)}%`;
                
                stocksContainer.appendChild(stockTile);
            });

            sectorDiv.appendChild(stocksContainer);
            heatmapContainer.appendChild(sectorDiv);
        });

        heatmapWrapper.appendChild(heatmapContainer);
        container.appendChild(heatmapWrapper);
    }

    function renderAllHeatmaps(container, sp500Data, nasdaqData) {
        // S&P 500 Heatmaps
        if (sp500Data) {
            const sp500Section = document.createElement('div');
            sp500Section.className = 'heatmap-section';
            
            const sp500Title = document.createElement('h2');
            sp500Title.className = 'heatmap-main-title';
            sp500Title.textContent = 'S&P 500 Heatmap';
            sp500Section.appendChild(sp500Title);

            // 1-Day
            if (sp500Data.day) {
                renderHeatmap(sp500Section, 'S&P 500', sp500Data.day, '1-Day');
            }
            // 1-Week
            if (sp500Data.week) {
                renderHeatmap(sp500Section, 'S&P 500', sp500Data.week, '1-Week');
            }
            // 1-Month
            if (sp500Data.month) {
                renderHeatmap(sp500Section, 'S&P 500', sp500Data.month, '1-Month');
            }
            
            container.appendChild(sp500Section);
        }

        // NASDAQ 100 Heatmaps
        if (nasdaqData) {
            const nasdaqSection = document.createElement('div');
            nasdaqSection.className = 'heatmap-section';
            
            const nasdaqTitle = document.createElement('h2');
            nasdaqTitle.className = 'heatmap-main-title';
            nasdaqTitle.textContent = 'NASDAQ 100 Heatmap';
            nasdaqSection.appendChild(nasdaqTitle);

            // 1-Day
            if (nasdaqData.day) {
                renderHeatmap(nasdaqSection, 'NASDAQ 100', nasdaqData.day, '1-Day');
            }
            // 1-Week
            if (nasdaqData.week) {
                renderHeatmap(nasdaqSection, 'NASDAQ 100', nasdaqData.week, '1-Week');
            }
            // 1-Month
            if (nasdaqData.month) {
                renderHeatmap(nasdaqSection, 'NASDAQ 100', nasdaqData.month, '1-Month');
            }
            
            container.appendChild(nasdaqSection);
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
            
            // Mock data for testing (replace with actual data from backend)
            const mockSP500Data = {
                day: {
                    sectors: {
                        'Technology': [
                            { ticker: 'AAPL', performance: 2.5, market_cap: 3000000000000 },
                            { ticker: 'MSFT', performance: -1.2, market_cap: 2800000000000 },
                            { ticker: 'GOOGL', performance: 0.8, market_cap: 1800000000000 },
                            { ticker: 'NVDA', performance: 5.3, market_cap: 1200000000000 },
                            { ticker: 'META', performance: -2.1, market_cap: 900000000000 }
                        ],
                        'Healthcare': [
                            { ticker: 'JNJ', performance: 0.5, market_cap: 400000000000 },
                            { ticker: 'UNH', performance: 1.2, market_cap: 500000000000 },
                            { ticker: 'PFE', performance: -0.8, market_cap: 250000000000 }
                        ],
                        'Financial': [
                            { ticker: 'JPM', performance: 1.8, market_cap: 450000000000 },
                            { ticker: 'BAC', performance: 2.1, market_cap: 250000000000 },
                            { ticker: 'WFC', performance: -0.3, market_cap: 180000000000 }
                        ]
                    }
                },
                week: {
                    sectors: {
                        'Technology': [
                            { ticker: 'AAPL', performance: 4.2, market_cap: 3000000000000 },
                            { ticker: 'MSFT', performance: 2.8, market_cap: 2800000000000 },
                            { ticker: 'GOOGL', performance: -1.5, market_cap: 1800000000000 }
                        ]
                    }
                },
                month: {
                    sectors: {
                        'Technology': [
                            { ticker: 'AAPL', performance: -3.5, market_cap: 3000000000000 },
                            { ticker: 'MSFT', performance: 6.2, market_cap: 2800000000000 }
                        ]
                    }
                }
            };

            // Use actual data if available, otherwise use mock data
            const sp500HeatmapData = data.sp500_heatmap || mockSP500Data;
            const nasdaqHeatmapData = data.nasdaq_heatmap || mockSP500Data; // Use same mock for testing
            
            renderAllHeatmaps(heatmapsContainer, sp500HeatmapData, nasdaqHeatmapData);
            dashboardElement.appendChild(heatmapsContainer);

        } catch (error) {
            console.error("Failed to fetch data:", error);
            dashboardElement.innerHTML = `<p>Error loading data: ${error.message}</p>`;
        }
    }

    fetchData();
});