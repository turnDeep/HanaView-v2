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

    function renderHeatmap(container, title, heatmapData) {
        // This function remains the same as before, but won't be called in this version
        // for clarity of the news feature output.
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

            if (data.news) {
                renderNews(dashboardElement, data.news);
            } else {
                dashboardElement.innerHTML = '<p>No news section in data.</p>';
            }

        } catch (error) {
            console.error("Failed to fetch data:", error);
            dashboardElement.innerHTML = `<p>Error loading data: ${error.message}</p>`;
        }
    }

    fetchData();
});
