const yearSlider = document.getElementById('yearSlider');
const yearValue = document.getElementById('yearValue');
const minStartsSlider = document.getElementById('minStartsSlider');
const minStartsValue = document.getElementById('minStartsValue');
const leagueSelect = document.getElementById('leagueSelect');
const fetchBtn = document.getElementById('fetchBtn');
const loading = document.getElementById('loading');
const error = document.getElementById('error');
const statsContainer = document.getElementById('statsContainer');
const statsTable = document.getElementById('statsTable').getElementsByTagName('tbody')[0];

yearSlider.oninput = () => yearValue.textContent = yearSlider.value;
minStartsSlider.oninput = () => minStartsValue.textContent = minStartsSlider.value;

fetchBtn.onclick = async () => {
    const year = yearSlider.value;
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

        statsTable.innerHTML = '';
        data.forEach(pitcher => {
            const row = statsTable.insertRow();
            row.innerHTML = `
                <td><strong>${pitcher.Name}</strong></td>
                <td>${pitcher.Team}</td>
                <td class="stat-number">${pitcher.GS}</td>
                <td class="stat-number">${pitcher.W}</td>
                <td class="stat-number">${pitcher.L}</td>
                <td class="stat-number">${pitcher.ERA}</td>
                <td class="stat-number">${pitcher.IP}</td>
                <td class="stat-number">${pitcher.SO}</td>
                <td class="stat-number">${pitcher.BB}</td>
                <td class="stat-number">${pitcher.WHIP}</td>
                <td class="stat-number quality-high">${pitcher.Quality_Starts}</td>
                <td class="stat-number wasted-high">${pitcher.Wasted_Starts}</td>
                <td style="font-size: 12px;">${pitcher.Wasted_Start_Example}</td>
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
