const yearSelect = document.getElementById('yearSelect');
const minStartsSlider = document.getElementById('minStartsSlider');
const minStartsValue = document.getElementById('minStartsValue');
const leagueSelect = document.getElementById('leagueSelect');
const fetchBtn = document.getElementById('fetchBtn');
const loading = document.getElementById('loading');
const error = document.getElementById('error');
const statsContainer = document.getElementById('statsContainer');
const statsTable = document.getElementById('statsTable').getElementsByTagName('tbody')[0];

// Summary card elements
const totalQS = document.getElementById('totalQS');
const totalWasted = document.getElementById('totalWasted');
const wastedRate = document.getElementById('wastedRate');
const pitchersWithWasted = document.getElementById('pitchersWithWasted');

minStartsSlider.oninput = () => minStartsValue.textContent = minStartsSlider.value;

fetchBtn.onclick = async () => {
    const year = yearSelect.value;
    const league = leagueSelect.value;
    const minStarts = minStartsSlider.value;

    fetchBtn.disabled = true;
    loading.style.display = 'block';
    error.style.display = 'none';
    statsContainer.style.display = 'none';

    try {
        const response = await fetch(`/api/stats?year=${year}&league=${league}&min_starts=${minStarts}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to fetch data');
        }

        // Calculate summary stats
        const totalQualityStarts = data.reduce((sum, p) => sum + p.Quality_Starts, 0);
        const totalWastedStarts = data.reduce((sum, p) => sum + p.Wasted_Starts, 0);
        const wastedPercentage = totalQualityStarts > 0 ? (totalWastedStarts / totalQualityStarts * 100).toFixed(1) : 0;
        const pitchersAffected = data.filter(p => p.Wasted_Starts > 0).length;

        // Update summary cards
        totalQS.textContent = totalQualityStarts;
        totalWasted.textContent = totalWastedStarts;
        wastedRate.textContent = `${wastedPercentage}%`;
        pitchersWithWasted.textContent = pitchersAffected;

        // Clear and populate table
        statsTable.innerHTML = '';
        data.forEach((pitcher, index) => {
            const row = statsTable.insertRow();
            const wastedPct = pitcher.Quality_Starts > 0 ? (pitcher.Wasted_Starts / pitcher.Quality_Starts * 100).toFixed(1) : 0;
            
            row.innerHTML = `
                <td><strong>#${index + 1}</strong></td>
                <td><strong>${pitcher.Name}</strong></td>
                <td>${pitcher.Team}</td>
                <td class="quality-high">${pitcher.Quality_Starts}</td>
                <td class="wasted-high">${pitcher.Wasted_Starts}</td>
                <td class="wasted-high">${wastedPct}%</td>
                <td class="stat-number">${pitcher.W}</td>
                <td class="stat-number">${pitcher.L}</td>
                <td class="stat-number">${pitcher.ERA}</td>
            `;
        });

        statsContainer.style.display = 'block';
    } catch (err) {
        error.textContent = err.message;
        error.style.display = 'block';
    } finally {
        loading.style.display = 'none';
        fetchBtn.disabled = false;
    }
};

fetchBtn.click();
