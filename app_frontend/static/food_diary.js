document.addEventListener('DOMContentLoaded', function() {
    const diaryBody = document.getElementById('diaryBody');
    const nutrientBody = document.getElementById('nutrientBody');

    // 1. Handle Row Selection
    diaryBody.addEventListener('click', function(e) {
        // Find the closest row (tr) in case they clicked a td or span
        const row = e.target.closest('tr');
        if (!row) return;

        // Visual feedback: remove active class from others, add to this one
        document.querySelectorAll('.diary-table tr').forEach(r => r.classList.remove('active-row'));
        row.classList.add('active-row');

        const entryId = row.dataset.id;
        fetchNutrientDetails(entryId);
    });

    // 2. Fetch data from your Flask API
    async function fetchNutrientDetails(id) {
        nutrientBody.innerHTML = '<tr><td colspan="3">Loading...</td></tr>';
        
        try {
            const response = await fetch(`/api/nutrients/${id}`);
            const data = await response.json();

            // Clear and build the new table rows
            nutrientBody.innerHTML = '';
            data.nutrients.forEach(n => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${n.name}</td>
                    <td>${n.value}</td>
                    <td>${n.unit}</td>
                `;
                nutrientBody.appendChild(tr);
            });
        } catch (err) {
            console.error('Error fetching nutrients:', err);
            nutrientBody.innerHTML = '<tr><td colspan="3">Error loading data.</td></tr>';
        }
    }

    // 3. Handle Search/Filter Button
    const searchBtn = document.querySelector('.search-btn');
    searchBtn.addEventListener('click', function() {
        const gi = document.getElementById('giFilter').value;
        const meal = document.getElementById('mealTypeFilter').value;
        const sort = document.getElementById('sortBy').value;

        // Redirect with query params so Flask can filter the results
        window.location.href = `/food-diary?gi=${gi}&meal=${meal}&sort=${sort}`;
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const giFilter = document.getElementById('giFilter');
    const giSlider = document.getElementById('giSlider');
    const giValueText = document.getElementById('giSliderValue');

    // Sync Slider to Text
    giSlider.addEventListener('input', function() {
        giValueText.textContent = this.value;
        if (giFilter.value !== 'custom') giFilter.value = "custom";
    });

    // Sync Dropdown to Slider
    giFilter.addEventListener('change', function() {
        if (this.value === 'low') giSlider.value = 55;
        else if (this.value === 'medium') giSlider.value = 69;
        else if (this.value === 'high') giSlider.value = 100;
        giValueText.textContent = giSlider.value;
    });

    // Search Logic
    document.querySelector('.search-btn').addEventListener('click', function() {
        const queryParams = new URLSearchParams({
            gi_max: giSlider.value,
            time: document.getElementById('timeFilter').value,
            sort: document.getElementById('sortBy').value
        });
        window.location.href = `/food-diary?${queryParams.toString()}`;
    });
});


document.addEventListener('DOMContentLoaded', function() {
    // 1. Element Selectors
    const searchBtn = document.querySelector('.search-btn');
    const foodSearch = document.getElementById('foodSearch');
    const sortBy = document.getElementById('sortBy');
    const giFilter = document.getElementById('giFilter');
    const giSlider = document.getElementById('giSlider');
    const giSliderValue = document.getElementById('giSliderValue');
    const timeFilter = document.getElementById('timeFilter');
    const mealTypeFilter = document.getElementById('mealTypeFilter');

    // 2. GI Slider Logic (Sync Slider with Dropdown)
    giSlider.addEventListener('input', function() {
        giSliderValue.textContent = this.value;
        if (giFilter.value !== 'custom') {
            giFilter.value = 'custom';
        }
    });

    giFilter.addEventListener('change', function() {
        const val = this.value;
        if (val === 'low') giSlider.value = 55;
        else if (val === 'medium') giSlider.value = 69;
        else if (val === 'high') giSlider.value = 100;
        
        giSliderValue.textContent = giSlider.value;
    });

    // 3. The Search Execution
    searchBtn.addEventListener('click', function() {
        // Gather all values
        const params = new URLSearchParams();
        
        if (foodSearch.value) params.append('food', foodSearch.value);
        params.append('sort', sortBy.value);
        params.append('gi', giFilter.value);
        params.append('gi_max', giSlider.value);
        params.append('time', timeFilter.value);
        params.append('meal', mealTypeFilter.value);

        // Redirect with the new query string
        window.location.href = `/food-diary?${params.toString()}`;
    });

    // 4. Row Click Logic (Nutrient Breakdown)
    const tableRows = document.querySelectorAll('.diary-table tbody tr');
    tableRows.forEach(row => {
        row.addEventListener('click', function() {
            // Remove active class from all rows
            tableRows.forEach(r => r.classList.remove('active-row'));
            // Add to clicked row
            this.classList.add('active-row');

            const entryId = this.getAttribute('data-id');
            fetchNutrients(entryId);
        });
    });
});

async function fetchNutrients(id) {
    const nutrientBody = document.getElementById('nutrientBody');
    try {
        const response = await fetch(`/api/nutrients/${id}`);
        const data = await response.json();
        
        nutrientBody.innerHTML = ''; // Clear loading state
        
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

document.addEventListener('DOMContentLoaded', function() {
    // Selectors
    const searchBtn = document.querySelector('.search-btn');
    const foodSearch = document.getElementById('foodSearch');
    const sortBy = document.getElementById('sortBy');
    
    // Advanced Filter Selectors
    const giFilter = document.getElementById('giFilter');
    const giSlider = document.getElementById('giSlider');
    const giSliderValue = document.getElementById('giSliderValue');
    const timeFilter = document.getElementById('timeFilter');
    const mealTypeFilter = document.getElementById('mealTypeFilter');

    // --- 1. Automatic "Sort By" Trigger ---
    sortBy.addEventListener('change', function() {
        executeSearch(); // Refresh immediately when sort changes
    });

    // --- 2. "Enter" Key Trigger for Food Search ---
    foodSearch.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            executeSearch();
        }
    });

    // --- 3. Advanced Search Button ---
    searchBtn.addEventListener('click', function() {
        executeSearch();
    });

    // --- 4. Helper Function to Gather Params & Redirect ---
    function executeSearch() {
        const params = new URLSearchParams();
        
        // Always grab current values of everything
        if (foodSearch.value) params.append('food', foodSearch.value);
        params.append('sort', sortBy.value);
        params.append('gi', giFilter.value);
        params.append('gi_max', giSlider.value);
        params.append('time', timeFilter.value);
        params.append('meal', mealTypeFilter.value);

        // Redirect
        window.location.href = `/food-diary?${params.toString()}`;
    }

    // --- 5. GI Slider/Dropdown Sync (Internal Logic) ---
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
});