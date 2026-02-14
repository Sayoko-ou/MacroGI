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
    const giValueDisplay = document.getElementById('gi');
    const glValueDisplay = document.getElementById('gl');
    const saveEntryBtn = document.getElementById('save-entry-btn');
    const addRowBtn = document.getElementById('add-row-btn');
    const retakePrompt = document.getElementById('retake-prompt');

    // CONFIG: Calories enabled, Sugar excluded
    const VALID_NUTRIENTS = ["Calories", "Protein", "Total Fat", "Carbohydrate", "Fiber", "Sodium", "Salt"];
    let selectedFile = null;
    let giPredicted = false;

    // --- Validation Helpers ---

    function hasNutrientData() {
        const values = document.querySelectorAll('.nutrient-val');
        if (values.length === 0) return false;
        // Ensure at least one value is > 0
        return Array.from(values).some(input => parseFloat(input.value) > 0);
    }

    function getAvailableNutrients() {
        const currentLabels = [];
        
        // 1. Gather all currently displayed nutrients
        document.querySelectorAll('#nutrient-table-body tr').forEach(row => {
            const staticLabel = row.querySelector('td strong');
            const select = row.querySelector('.nutrient-name-select');
            if (staticLabel) currentLabels.push(staticLabel.innerText.trim());
            if (select) currentLabels.push(select.value.trim());
        });

        // 2. Filter out what is already in the table
        let available = VALID_NUTRIENTS.filter(n => !currentLabels.includes(n));

        // 3. MUTUAL EXCLUSION: Prevent having both Salt and Sodium
        if (currentLabels.includes("Salt")) {
            available = available.filter(n => n !== "Sodium");
        }
        if (currentLabels.includes("Sodium")) {
            available = available.filter(n => n !== "Salt");
        }

        return available;
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
        
        // Build the table ONLY with what the AI found
        VALID_NUTRIENTS.forEach(name => {
            const val = nutrients[name];
            // Only show row if AI found a value > 0
            if (val && val > 0) {
                let unit = 'g';
                if (name === 'Calories') unit = 'kcal';
                if (name === 'Sodium') unit = 'mg';
                nutrientTableBody.innerHTML += createRow(name, val, unit, false);
            }
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
                // Prevent negative values
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
                giValueDisplay.textContent = data.gi;
                giValueDisplay.style.color = data.gi_color;
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

    // --- Save Logic (THE CORRECT ONE) ---

    if(saveEntryBtn) saveEntryBtn.addEventListener('click', async () => {
    // 1. Initialize payload with 0s
    const payload = {
        foodname: foodNameInput.value,
        mealtype: mealTypeSelect.value,
        insulin: parseFloat(document.getElementById('insulin-input').value) || 0,
        calories: 0, carbs: 0, protein: 0, fat: 0, sodium: 0, fiber: 0,
        gi: parseFloat(document.getElementById('gi').textContent) || 0,
        gl: parseFloat(document.getElementById('gl').textContent) || 0
    };

    let saltValue = 0;

    // 2. Scrape the table
    document.querySelectorAll('#nutrient-table-body tr').forEach(row => {
        const sel = row.querySelector('.nutrient-name-select');
        const lab = row.querySelector('td strong');
        let name = sel ? sel.value : (lab ? lab.innerText : "");
        let val = parseFloat(row.querySelector('.nutrient-val').value) || 0;

        if (name === "Salt") {
            saltValue = val;
        } else {
            const keyMap = {
                "Calories": "calories",
                "Protein": "protein",
                "Total Fat": "fat",
                "Carbohydrate": "carbs",
                "Fiber": "fiber",
                "Sodium": "sodium"
            };
            const dbKey = keyMap[name];
            if (dbKey) payload[dbKey] = val;
        }
    });

    // 3. CONVERSION: If Salt was provided and Sodium is 0, convert it.
    // Formula: Salt (g) / 2.5 * 1000 = Sodium (mg)
    if (saltValue > 0 && payload.sodium === 0) {
        payload.sodium = Math.round((saltValue / 2.5) * 1000);
    }

    // 4. Send to backend
    try {
        const res = await fetch('/scan/save_entry', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        // ... rest of your save logic
            const result = await res.json();
            
            if (result.status === "success") {
                alert("Entry Saved Successfully!");
                window.location.href = "/";
            } else {
                alert("Error: " + result.error);
            }
        } catch (e) { 
            alert("Network Error: " + e.message); 
        }
    });

    // --- Form State Management ---

    function validateFormState() {
        const nameFilled = foodNameInput.value.trim() !== '';
        const dataPresent = hasNutrientData(); 
        
        predictGiBtn.disabled = !dataPresent;
        saveEntryBtn.disabled = !(nameFilled && giPredicted);
        saveEntryBtn.textContent = saveEntryBtn.disabled ? "Complete all fields to save" : "Save Entry";
    }

    foodNameInput.addEventListener('input', validateFormState);
});