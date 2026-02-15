document.addEventListener('DOMContentLoaded', function() {
    // --- Element Selectors ---
    const diaryBody = document.getElementById('diaryBody');
    const nutrientBody = document.getElementById('nutrientBody');
    const searchBtn = document.querySelector('.search-btn');
    const foodSearch = document.getElementById('foodSearch');
    const sortBy = document.getElementById('sortBy');
    const giFilter = document.getElementById('giFilter');
    const giSlider = document.getElementById('giSlider');
    const giSliderValue = document.getElementById('giSliderValue');
    const timeFilter = document.getElementById('timeFilter');
    const mealTypeFilter = document.getElementById('mealTypeFilter');

    // --- 1. Row Click Logic (Nutrient Breakdown via event delegation) ---
    diaryBody.addEventListener('click', function(e) {
        const row = e.target.closest('tr');
        if (!row) return;

        document.querySelectorAll('.diary-table tr').forEach(r => r.classList.remove('active-row'));
        row.classList.add('active-row');

        const entryId = row.dataset.id;
        fetchNutrients(entryId);
    });

    // --- 2. GI Slider/Dropdown Sync ---
    giSlider.addEventListener('input', function() {
        giSliderValue.textContent = this.value;
        if (giFilter.value !== 'custom') giFilter.value = 'custom';
    });

    giFilter.addEventListener('change', function() {
        if (this.value === 'low') giSlider.value = 55;
        else if (this.value === 'medium') giSlider.value = 69;
        else if (this.value === 'high') giSlider.value = 100;
        giSliderValue.textContent = giSlider.value;
    });

    // --- 3. Automatic "Sort By" Trigger ---
    sortBy.addEventListener('change', function() {
        executeSearch();
    });

    // --- 4. "Enter" Key Trigger for Food Search ---
    foodSearch.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            executeSearch();
        }
    });

    // --- 5. Advanced Search Button ---
    searchBtn.addEventListener('click', function() {
        executeSearch();
    });

    // --- 6. Helper Function to Gather Params & Redirect ---
    function executeSearch() {
        const params = new URLSearchParams();

        if (foodSearch.value) params.append('food', foodSearch.value);
        params.append('sort', sortBy.value);
        params.append('gi', giFilter.value);
        params.append('gi_max', giSlider.value);
        params.append('time', timeFilter.value);
        params.append('meal', mealTypeFilter.value);

        window.location.href = `/food-diary?${params.toString()}`;
    }
});

// Standalone function for nutrient fetching (used by row click handler)
async function fetchNutrients(id) {
    const nutrientBody = document.getElementById('nutrientBody');
    try {
        const response = await fetch(`/api/nutrients/${id}`);
        const data = await response.json();

        nutrientBody.innerHTML = '';

        data.nutrients.forEach(n => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${n.name}</td>
                <td>${n.value !== null ? n.value : '-'}</td>
                <td>${n.unit}</td>
            `;
            nutrientBody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error fetching nutrients:", err);
    }
}
