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
    
    // Use .scanner-wrapper for 2-column layout, fallback to #results-container if using old layout
    const resultsContainer = document.querySelector('.scanner-wrapper') || document.getElementById('results-container');
    
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
        fileInput.value = '';
        cameraInput.value = '';
        previewContainer.classList.add('hidden');
        initialActions.classList.remove('hidden');
        scanNowBtn.classList.add('hidden');
    });

    // --- 2. OCR Scan Logic ---
    if(scanNowBtn) scanNowBtn.addEventListener('click', async () => {
        if (!selectedFile) return;

        // UI State: Loading
        scanNowBtn.classList.add('hidden');
        loadingSpinner.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await fetch('/api/ocr', { method: 'POST', body: formData });
            
            // READ JSON SAFELY
            let data;
            try {
                data = await response.json();
            } catch (e) {
                throw new Error("Server returned invalid JSON");
            }

            if (response.ok) {
                // CHECK FOR LOGICAL ERRORS FROM BACKEND
                if (data.error) {
                    alert("Scanner Error: " + data.error);
                    // Don't crash, just let them try again
                } else if (!data.nutrients) {
                    alert("No nutrition data found. Please enter manually.");
                    // Still populate what we can
                    populateResults({ nutrients: {}, suggested_name: "" });
                } else {
                    // SUCCESS
                    populateResults(data);
                }
            } else {
                alert('Server Error: ' + (data.error || response.statusText));
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Could not connect to scanner. Check console for details.');
        } finally {
            loadingSpinner.classList.add('hidden');
            scanNowBtn.classList.remove('hidden');
        }
    });

    function populateResults(data) {
        if (data.annotated_image) {
            // Update the preview image source with the base64 string
            imagePreview.src = "data:image/jpeg;base64," + data.annotated_image;
        }
        
        if(foodNameInput) foodNameInput.value = data.suggested_name || '';
        
        // Clear existing table
        if(nutrientTableBody) {
            nutrientTableBody.innerHTML = '';
            
            // Handle empty nutrients gracefully
            const nutrients = data.nutrients || {};
            const keys = Object.keys(nutrients);

            if (keys.length === 0) {
                 nutrientTableBody.innerHTML = `
                    <tr><td colspan="3" style="text-align:center; padding:15px; color:#888;">
                        No text detected. Type values manually.
                    </td></tr>
                    ${createRow('Energy', 0, 'kcal')}
                    ${createRow('Carbohydrate', 0, 'g')}
                    ${createRow('Sugar', 0, 'g')}
                    ${createRow('Fiber', 0, 'g')}
                    ${createRow('Protein', 0, 'g')}
                    ${createRow('Fat', 0, 'g')}
                 `;
            } else {
                for (const [nutrient, value] of Object.entries(nutrients)) {
                    // Guess unit
                    let unit = 'g';
                    if(['sodium', 'cholesterol', 'calcium'].includes(nutrient.toLowerCase())) unit = 'mg';
                    if(['energy', 'calories'].includes(nutrient.toLowerCase())) unit = 'kcal';
                    
                    nutrientTableBody.innerHTML += createRow(nutrient, value, unit);
                }
            }

            // Re-attach listeners to new inputs
            attachTableListeners();
        }
        
        validateFormState();
    }

    function createRow(label, value, unit) {
        // capitalize label
        const niceLabel = label.charAt(0).toUpperCase() + label.slice(1);
        return `
            <tr>
                <td>${niceLabel}</td>
                <td><input type="number" step="0.1" class="table-input nutrient-val" data-nutrient="${label.toLowerCase()}" value="${value}"></td>
                <td><input type="text" class="table-input nutrient-unit" value="${unit}" style="text-align:center;"></td>
            </tr>
        `;
    }

    function attachTableListeners() {
        document.querySelectorAll('.nutrient-val').forEach(input => {
            input.addEventListener('input', () => {
                giPredicted = false;
                if(giResultArea) giResultArea.classList.add('hidden');
                validateFormState();
            });
        });
    }

    // --- 3. GI Prediction Logic ---
    if(predictGiBtn) predictGiBtn.addEventListener('click', async () => {
        const nutrientData = {};
        document.querySelectorAll('.nutrient-val').forEach(input => {
            nutrientData[input.dataset.nutrient] = input.value;
        });

        predictGiBtn.textContent = "Calculating...";
        predictGiBtn.disabled = true;

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
                if(giValueDisplay) {
                    giValueDisplay.textContent = data.gi;
                    giValueDisplay.style.color = data.gi_color;
                }
                
                // Update AI Message safely
                const aiMsgBox = document.querySelector('.ai-message');
                if(aiMsgBox) {
                    aiMsgBox.innerHTML = `💡 <strong>Tip:</strong> ${data.ai_message || 'No tip available.'}`;
                }
                
                if(giResultArea) giResultArea.classList.remove('hidden');
                giPredicted = true;
            } else {
               alert("Prediction Failed: " + (data.error || "Unknown error"));
            }
        } catch (e) {
            console.error(e);
            alert("Could not connect to GI service.");
        } finally {
            predictGiBtn.textContent = "Predict GI";
            predictGiBtn.disabled = false;
            validateFormState();
        }
    });

    // --- 4. Validation ---
    function validateFormState() {
        if(!saveEntryBtn) return;
        const nameFilled = foodNameInput && foodNameInput.value.trim() !== '';
        const typeFilled = mealTypeSelect && mealTypeSelect.value !== '';
        
        if (nameFilled && typeFilled && giPredicted) {
            saveEntryBtn.disabled = false;
            saveEntryBtn.textContent = "Save Entry";
            if(saveHelperText) saveHelperText.classList.add('hidden');
        } else {
            saveEntryBtn.disabled = true;
            saveEntryBtn.textContent = "Complete all fields to save";
            if(saveHelperText) saveHelperText.classList.remove('hidden');
        }
    }

    if(foodNameInput) foodNameInput.addEventListener('input', validateFormState);
    if(mealTypeSelect) mealTypeSelect.addEventListener('change', validateFormState);
});