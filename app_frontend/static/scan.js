// static/scan.js

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
    const resultsContainer = document.getElementById('results-container');
    
    // Form Elements
    const foodNameInput = document.getElementById('food-name');
    const mealTypeSelect = document.getElementById('meal-type');
    const nutrientTableBody = document.getElementById('nutrient-table-body');
    const predictGiBtn = document.getElementById('predict-gi-btn');
    const giResultArea = document.getElementById('gi-result-area');
    const giValueDisplay = document.getElementById('gi-value-display');
    const saveEntryBtn = document.getElementById('save-entry-btn');
    const saveHelperText = document.getElementById('save-helper-text');

    let selectedFile = null;
    let giPredicted = false;

    // --- 1. Image Selection Logic ---

    function handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            selectedFile = file;
            // Show preview
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                previewContainer.classList.remove('hidden');
                initialActions.classList.add('hidden');
                scanNowBtn.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
            // Reset results if they were open
            resultsContainer.classList.add('hidden');
        }
    }

    fileInput.addEventListener('change', handleFileSelect);
    cameraInput.addEventListener('change', handleFileSelect);

    clearBtn.addEventListener('click', () => {
        selectedFile = null;
        fileInput.value = '';
        cameraInput.value = '';
        previewContainer.classList.add('hidden');
        initialActions.classList.remove('hidden');
        scanNowBtn.classList.add('hidden');
        resultsContainer.classList.add('hidden');
    });


    // --- 2. OCR Scan Logic (Call API) ---

    scanNowBtn.addEventListener('click', async () => {
        if (!selectedFile) return;

        // UI State: Loading
        scanNowBtn.classList.add('hidden');
        loadingSpinner.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await fetch('/api/ocr', { method: 'POST', body: formData });
            const data = await response.json();

            if (response.ok) {
                populateResults(data);
                loadingSpinner.classList.add('hidden');
                resultsContainer.classList.remove('hidden');
                // Scroll down to results
                resultsContainer.scrollIntoView({ behavior: 'smooth' });
                validateFormState(); // Check initial state
            } else {
                alert('OCR Error: ' + data.error);
                loadingSpinner.classList.add('hidden');
                scanNowBtn.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to connect to scanner service.');
            loadingSpinner.classList.add('hidden');
            scanNowBtn.classList.remove('hidden');
        }
    });

function populateResults(data) {
        foodNameInput.value = data.suggested_name || '';
        
        // Clear existing table
        nutrientTableBody.innerHTML = '';
        
        // Populate Table items dynamically
        for (const [nutrient, value] of Object.entries(data.nutrients)) {
            const row = document.createElement('tr');
            
            // Capitalize first letter
            const label = nutrient.charAt(0).toUpperCase() + nutrient.slice(1);
            
            // Logic to guess default unit (Sodium/Cholesterol usually mg, others g)
            let defaultUnit = 'g';
            if (['sodium', 'cholesterol'].includes(nutrient.toLowerCase())) {
                defaultUnit = 'mg';
            }

            row.innerHTML = `
                <td>${label}</td>
                <td>
                    <input type="number" step="0.1" class="table-input nutrient-val" 
                           data-nutrient="${nutrient}" value="${value}">
                </td>
                <td>
                    <input type="text" class="table-input nutrient-unit" 
                           value="${defaultUnit}" style="text-align: center;">
                </td>
            `;
            nutrientTableBody.appendChild(row);
        }

        // Add listeners to new inputs
        document.querySelectorAll('.nutrient-val').forEach(input => {
            input.addEventListener('input', () => {
                giPredicted = false;
                giResultArea.classList.add('hidden');
                validateFormState();
            });
        });
    }


    // --- 3. GI Prediction Logic ---

    predictGiBtn.addEventListener('click', async () => {
        // Gather current values from table inputs
        const nutrientData = {};
        document.querySelectorAll('.nutrient-val').forEach(input => {
            nutrientData[input.dataset.nutrient] = input.value;
        });

        predictGiBtn.textContent = "Calculating...";
        predictGiBtn.disabled = true;

        /* Implement actual GI model here 
        try {
        const response = await fetch('/api/predict_gi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                food_name: foodNameInput.value,
                nutrients: nutrientData
            })
        });
        const data = await response.json();

        if (response.ok) {
            // 1. Update GI Number
            giValueDisplay.textContent = data.gi;
            giValueDisplay.style.color = data.gi_color;
            
            // 2. Update GenAI Text
            const messageBox = document.querySelector('.ai-message');
            messageBox.innerHTML = `💡 <strong>Tip:</strong> ${data.ai_message}`;
            
            giResultArea.classList.remove('hidden');
            giPredicted = true;
        }
    } catch (e) {
            alert("Could not connect to GI service.");
        } finally {
            predictGiBtn.textContent = "Run GI Prediction";
            predictGiBtn.disabled = false;
            validateFormState(); // Re-check save button status
        }
    }); */

        try {
            const response = await fetch('/api/predict_gi', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(nutrientData)
            });
            const data = await response.json();

            if (response.ok) {
                giValueDisplay.textContent = data.gi;
                giValueDisplay.style.color = data.gi_color;
                giResultArea.classList.remove('hidden');
                giPredicted = true;
            } else {
               alert("GI Prediction Failed: " + data.error);
            }
        } catch (e) {
            alert("Could not connect to GI service.");
        } finally {
            predictGiBtn.textContent = "Run GI Prediction";
            predictGiBtn.disabled = false;
            validateFormState(); // Re-check save button status
        }
    });


    // --- 4. Validation & Saving Logic ---

    function validateFormState() {
        const nameFilled = foodNameInput.value.trim() !== '';
        const typeFilled = mealTypeSelect.value !== '';
        
        if (nameFilled && typeFilled && giPredicted) {
            saveEntryBtn.disabled = false;
            saveEntryBtn.textContent = "Save Entry to Diary";
            saveHelperText.classList.add('hidden');
        } else {
            saveEntryBtn.disabled = true;
            saveEntryBtn.textContent = "Requirements not met yet";
            saveHelperText.classList.remove('hidden');
        }
    }

    // Listen for changes on required fields
    foodNameInput.addEventListener('input', validateFormState);
    mealTypeSelect.addEventListener('change', validateFormState);


    saveEntryBtn.addEventListener('click', async () => {
        // Gather final data bundle
        const finalData = {
            food_name: foodNameInput.value,
            meal_type: mealTypeSelect.value,
            nutrients: {},
            gi_result: parseInt(giValueDisplay.textContent),
            date: new Date().toISOString()
        };
        document.querySelectorAll('.nutrient-val').forEach(input => {
            finalData.nutrients[input.dataset.nutrient] = parseFloat(input.value);
        });

        // Send to save API
        saveEntryBtn.textContent = "Saving...";
        saveEntryBtn.disabled = true;

        try {
             const response = await fetch('/api/save_entry', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(finalData)
            });
            
            if(response.ok) {
                // Success! Redirect home or show message.
                window.location.href = "/?saved=true";
            } else {
                 alert("Failed to save entry.");
                 saveEntryBtn.textContent = "Save Entry to Diary";
                 saveEntryBtn.disabled = false;
            }
        } catch(e) {
             alert("Connection Error during save.");
        }
    });

});