document.addEventListener('DOMContentLoaded', () => {
    const fetchButton = document.getElementById('fetch-button');
    const leagueSelect = document.getElementById('league-select');
    const yearSelect = document.getElementById('year-select');
    const minStartsSlider = document.getElementById('min-starts-slider');
    const minStartsValue = document.getElementById('min-starts-value');
    const statsTableBody = document.getElementById('stats-table-body');
    const statusMessage = document.getElementById('status-message');
    
    // Update the slider value display
    minStartsSlider.addEventListener('input', () => {
        minStartsValue.textContent = minStartsSlider.value;
    });

    fetchButton.addEventListener('click', async () => {
        // Get user selections
        const league = leagueSelect.value;
        const year = yearSelect.value;
        const minStarts = minStartsSlider.value;

        // Clear previous results and show loading message
        statsTableBody.innerHTML = '';
        statusMessage.textContent = 'Fetching data... This may take a moment.';

        try {
            // Construct the API URL
            const apiUrl = `/api/stats?year=${year}&league=${league}&min_starts=${minStarts}`;
            
            // Fetch data from the Flask backend
            const response = await fetch(apiUrl);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Something went wrong.');
            }
            
            const data = await response.json();

            if (data.length === 0) {
                statusMessage.textContent = 'No pitchers found with the selected criteria.';
                return;
            }

            // Populate the table with the received data
            data.forEach(pitcher => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${pitcher.Name}</td>
                    <td>${pitcher.Team}</td>
                    <td>${pitcher.GS}</td>
                    <td>${pitcher.W}</td>
                    <td>${pitcher.L}</td>
                    <td>${pitcher.ERA}</td>
                    <td>${pitcher.IP}</td>
                    <td>${pitcher.SO}</td>
                    <td>${pitcher.BB}</td>
                    <td>${pitcher.WHIP}</td>
                    <td>${pitcher.Quality_Starts}</td>
                    <td>${pitcher.Wasted_Starts}</td>
                    <td>${pitcher.Wasted_Start_Example}</td>
                `;
                statsTableBody.appendChild(row);
            });
            
            statusMessage.textContent = `Found ${data.length} pitchers.`;

        } catch (error) {
            statusMessage.textContent = `Error: ${error.message}`;
            console.error('Fetch error:', error);
        }
    });
});
