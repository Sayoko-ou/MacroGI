document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    const fileInput = document.getElementById('file-upload');
    const cameraInput = document.getElementById('camera-upload');
    const previewContainer = document.getElementById('image-preview-container');
    const imagePreview = document.getElementById('image-preview');
    const clearBtn = document.getElementById('clear-image-btn');
    const initialActions = document.getElementById('initial-actions');
    const scanNowBtn = document.getElementById('scan-now-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const foodNameInput = document.getElementById('food-name');
    const mealTypeSelect = document.getElementById('meal-type');
    const nutrientTableBody = document.getElementById('nutrient-table-body');
    const predictGiBtn = document.getElementById('predict-gi-btn');
    const giResultArea = document.getElementById('gi-result-area');
    const giValueDisplay = document.getElementById('gi-value-display');
    const glValueDisplay = document.getElementById('gl-value-display'); // New GL Element
    const saveEntryBtn = document.getElementById('save-entry-btn');
    const addRowBtn = document.getElementById('add-row-btn');
    const retakePrompt = document.getElementById('retake-prompt');

    // Configuration: Sugar is excluded as requested
    const VALID_NUTRIENTS = ["Energy", "Protein", "Total Fat", "Carbohydrate", "Fiber", "Sodium"];
    let selectedFile = null;
    let giPredicted = false;

    // --- Validation Helpers ---

    /**
     * Checks if the table contains any actual nutrient data (> 0).
     * Prevents running AI on empty rows.
     */
    function hasNutrientData() {
        const values = document.querySelectorAll('.nutrient-val');
        if (values.length === 0) return false;
        return Array.from(values).some(input => parseFloat(input.value) > 0);
    }

    /**
     * Re-scans the table to find which nutrients are NOT currently displayed.
     * Allows deleted nutrients to be added back to the dropdown.
     */
    function getAvailableNutrients() {
        const currentLabels = [];
        document.querySelectorAll('#nutrient-table-body tr').forEach(row => {
            const staticLabel = row.querySelector('td strong');
            const select = row.querySelector('.nutrient-name-select');
            if (staticLabel) currentLabels.push(staticLabel.innerText.trim());
            if (select) currentLabels.push(select.value.trim());
        });
        return VALID_NUTRIENTS.filter(n => !currentLabels.includes(n));
    }

    // --- Image Handling ---

    function handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            selectedFile = file;
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                previewContainer.classList.remove('hidden');
                initialActions.classList.add('hidden');
                scanNowBtn.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        }
    }

    if(fileInput) fileInput.addEventListener('change', handleFileSelect);
    if(cameraInput) cameraInput.addEventListener('change', handleFileSelect);

    if(clearBtn) clearBtn.addEventListener('click', () => {
        selectedFile = null;
        previewContainer.classList.add('hidden');
        initialActions.classList.remove('hidden');
        scanNowBtn.classList.add('hidden');
        if(retakePrompt) retakePrompt.classList.add('hidden');
    });

    // --- Scanner Logic ---

    if(scanNowBtn) scanNowBtn.addEventListener('click', async () => {
        if (!selectedFile) return;
        scanNowBtn.classList.add('hidden');
        loadingSpinner.classList.remove('hidden');
        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await fetch('/scan/ocr', { method: 'POST', body: formData });
            const data = await response.json();
            if (data.success === false) retakePrompt.classList.remove('hidden');
            else retakePrompt.classList.add('hidden');
            populateResults(data);
        } catch (error) { alert('Scanner Error'); }
        finally {
            loadingSpinner.classList.add('hidden');
            scanNowBtn.classList.remove('hidden');
        }
    });

    function populateResults(data) {
        if (data.annotated_image) imagePreview.src = "data:image/jpeg;base64," + data.annotated_image;
        if(foodNameInput) foodNameInput.value = data.suggested_name || '';
        
        nutrientTableBody.innerHTML = '';
        const nutrients = data.nutrients || {};
        
        VALID_NUTRIENTS.forEach(name => {
            // Keys match ocr_engine.py exactly
            const val = nutrients[name] || 0;
            let unit = (name === 'Energy') ? 'kcal' : (name === 'Sodium' ? 'mg' : 'g');
            nutrientTableBody.innerHTML += createRow(name, val, unit, false);
        });

        attachTableListeners();
        validateFormState();
    }

    function createRow(label, value, unit, isNew = false) {
        let labelHtml = `<strong>${label}</strong>`;
        if (isNew) {
            const available = getAvailableNutrients();
            if (available.length === 0) return null;
            labelHtml = `<select class="table-input nutrient-name-select">
                ${available.map(n => `<option value="${n}">${n}</option>`).join('')}
            </select>`;
        }
        // min="0" ensures no negative values
        return `<tr>
            <td>${labelHtml}</td>
            <td><input type="number" min="0" step="0.1" class="table-input nutrient-val" value="${value||0}"></td>
            <td><input type="text" class="table-input nutrient-unit" value="${unit}" style="text-align:center;"></td>
            <td style="text-align:right;"><button class="delete-row-btn" title="Remove field">×</button></td>
        </tr>`;
    }

    if(addRowBtn) addRowBtn.addEventListener('click', () => {
        const available = getAvailableNutrients();
        if (available.length === 0) return alert("All nutrients present.");
        const rowHtml = createRow(available[0], 0, 'g', true);
        if (rowHtml) {
            const empty = document.querySelector('.empty-state-row');
            if(empty) empty.remove();
            nutrientTableBody.insertAdjacentHTML('beforeend', rowHtml);
            attachTableListeners();
        }
    });

    function attachTableListeners() {
        document.querySelectorAll('.nutrient-val, .nutrient-name-select').forEach(input => {
            input.oninput = (e) => {
                // Negative value handling
                if (e.target.type === 'number' && parseFloat(e.target.value) < 0) {
                    e.target.value = 0;
                }
                giPredicted = false;
                if(giResultArea) giResultArea.classList.add('hidden');
                validateFormState();
            };
        });
        document.querySelectorAll('.delete-row-btn').forEach(btn => {
            btn.onclick = (e) => { 
                e.target.closest('tr').remove(); 
                giPredicted = false; 
                if(giResultArea) giResultArea.classList.add('hidden');
                validateFormState(); 
            };
        });
    }

    // --- AI Prediction Logic ---

    if(predictGiBtn) predictGiBtn.addEventListener('click', async () => {
        if (!hasNutrientData()) {
            alert("Please provide nutrient values before predicting GI.");
            return;
        }

        const nutrientData = {};
        document.querySelectorAll('#nutrient-table-body tr').forEach(row => {
            const sel = row.querySelector('.nutrient-name-select');
            const lab = row.querySelector('td strong');
            let name = sel ? sel.value : (lab ? lab.innerText : "");
            if (name) {
                // Standardize keys for backend models
                const dbKey = name.toLowerCase().replace("total fat", "fat").replace("carbohydrate", "carbs");
                nutrientData[dbKey] = parseFloat(row.querySelector('.nutrient-val').value) || 0;
            }
        });

        predictGiBtn.textContent = "Analyzing...";
        try {
            const res = await fetch('/scan/predict_gi', {
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    food_name: foodNameInput.value || "Scanned Food", 
                    nutrients: nutrientData 
                })
            });
            const data = await res.json();
            if (res.ok) {
                // Display GI Result
                giValueDisplay.textContent = data.gi;
                giValueDisplay.style.color = data.gi_color;

                // Display GL Result
                if (glValueDisplay) glValueDisplay.textContent = data.gl;

                document.querySelector('.ai-message').innerHTML = `💡 ${data.ai_message || 'Balanced meal.'}`;
                
                if (document.getElementById('insulin-hint')) {
                    document.getElementById('insulin-hint').classList.remove('hidden');
                    document.getElementById('insulin-hint').innerHTML = `🤖 AI Suggests: ${data.insulin_suggestion} units`;
                }
                
                giResultArea.classList.remove('hidden');
                giPredicted = true;
            }
        } finally { 
            predictGiBtn.textContent = "Predict GI & GL"; 
            validateFormState(); 
        }
    });

    // --- Save Logic ---

    if(saveEntryBtn) saveEntryBtn.addEventListener('click', async () => {
        const nutrientData = {};
        document.querySelectorAll('#nutrient-table-body tr').forEach(row => {
            const sel = row.querySelector('.nutrient-name-select');
            const lab = row.querySelector('td strong');
            let name = sel ? sel.value : (lab ? lab.innerText : "");
            const dbKey = name.toLowerCase().replace("total fat", "fat").replace("carbohydrate", "carbs");
            nutrientData[dbKey] = parseFloat(row.querySelector('.nutrient-val').value) || 0;
        });

        const payload = {
            foodname: foodNameInput.value,
            mealtype: mealTypeSelect.value,
            insulin: parseFloat(document.getElementById('insulin-input').value) || 0,
            carbs: nutrientData.carbs || 0,
            protein: nutrientData.protein || 0,
            fat: nutrientData.fat || 0,
            sodium: nutrientData.sodium || 0,
            fiber: nutrientData.fiber || 0
        };

        try {
            const res = await fetch('/scan/save_entry', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if ((await res.json()).status === "success") window.location.href = "/";
        } catch (e) { alert("Error saving."); }
    });

    // --- Form State Management ---

    function validateFormState() {
        const nameFilled = foodNameInput.value.trim() !== '';
        const dataPresent = hasNutrientData(); 
        
        // Predict button only needs nutrient data
        predictGiBtn.disabled = !dataPresent;

        // Save button requires name and prediction
        saveEntryBtn.disabled = !(nameFilled && giPredicted);
        saveEntryBtn.textContent = saveEntryBtn.disabled ? "Complete all fields to save" : "Save Entry";
    }

    foodNameInput.addEventListener('input', validateFormState);
});