document.addEventListener('DOMContentLoaded', () => {
    console.log("HanaView Dashboard Initialized");

    const dashboardElement = document.getElementById('dashboard');

    async function fetchData() {
        try {
            const response = await fetch('/api/data');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log("Data fetched successfully:", data);
            dashboardElement.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
        } catch (error) {
            console.error("Failed to fetch data:", error);
            dashboardElement.innerHTML = `<p>Error loading data: ${error.message}</p>`;
        }
    }

    fetchData();
});
