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
    const liveCameraContainer = document.getElementById('live-camera-container');
    const liveVideo = document.getElementById('live-video');
    const snapPhotoBtn = document.getElementById('snap-photo-btn');
    const cancelCameraBtn = document.getElementById('cancel-camera-btn');
    const cameraCanvas = document.getElementById('camera-canvas');
    let stream = null; // Holds the live video feed

    // 1. Turn on the camera
    window.startCamera = async () => {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ 
                video: { facingMode: 'environment' } 
            });
            liveVideo.srcObject = stream;
            
            initialActions.classList.add('hidden');
            liveCameraContainer.classList.remove('hidden');
        } catch (err) {
            alert("Camera access denied or unavailable on this device.");
            console.error(err);
        }
    };

    // 2. Snap the photo
    if (snapPhotoBtn) {
        snapPhotoBtn.addEventListener('click', () => {
            cameraCanvas.width = liveVideo.videoWidth;
            cameraCanvas.height = liveVideo.videoHeight;
            
            const context = cameraCanvas.getContext('2d');
            context.drawImage(liveVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);
            
            cameraCanvas.toBlob((blob) => {
                selectedFile = new File([blob], "webcam-snapshot.jpg", { type: "image/jpeg" });
                
                const reader = new FileReader();
                reader.onload = (e) => {
                    imagePreview.src = e.target.result;
                    previewContainer.classList.remove('hidden');
                    liveCameraContainer.classList.add('hidden');
                    scanNowBtn.classList.remove('hidden');
                };
                reader.readAsDataURL(selectedFile);
                
                stopCamera();
            }, 'image/jpeg');
        });
    }

    // 3. Helper to stop the camera
    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
        }
    }

    // 4. Handle Cancel Button
    if (cancelCameraBtn) {
        cancelCameraBtn.addEventListener('click', () => {
            stopCamera();
            liveCameraContainer.classList.add('hidden');
            initialActions.classList.remove('hidden');
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            selectedFile = null;
            stopCamera(); 
            previewContainer.classList.add('hidden');
            initialActions.classList.remove('hidden');
            scanNowBtn.classList.add('hidden');
            if(retakePrompt) retakePrompt.classList.add('hidden');
        });
    }

    const VALID_NUTRIENTS = ["Calories", "Protein", "Total Fat", "Carbohydrate", "Fiber", "Sodium", "Salt"];
    let selectedFile = null;
    let giPredicted = false;

    // --- Validation Helpers ---

    function hasNutrientData() {
        const values = document.querySelectorAll('.nutrient-val');
        return values.length > 0;
    }

    function getAvailableNutrients() {
        const currentLabels = [];
        
        document.querySelectorAll('#nutrient-table-body tr').forEach(row => {
            const staticLabel = row.querySelector('td strong');
            const select = row.querySelector('.nutrient-name-select');
            if (staticLabel) currentLabels.push(staticLabel.innerText.trim());
            if (select) currentLabels.push(select.value.trim());
        });

        let available = VALID_NUTRIENTS.filter(n => !currentLabels.includes(n));

        if (currentLabels.includes("Salt")) available = available.filter(n => n !== "Sodium");
        if (currentLabels.includes("Sodium")) available = available.filter(n => n !== "Salt");

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
        } catch (error) { 
            alert('Scanner Error: Could not reach the AI microservice.'); }
        finally {
            loadingSpinner.classList.add('hidden');
            scanNowBtn.classList.remove('hidden');
        }
    });

    // Dynamic Strict Unit Generation
    function generateUnitHtml(nutrientName) {
        if (nutrientName === 'Calories') {
            return `<select class="table-input nutrient-unit" style="text-align:center; cursor:pointer;">
                <option value="kcal">kcal</option>
                <option value="kJ">kJ</option>
            </select>`;
        } else if (nutrientName === 'Sodium') {
            return `<input type="text" class="table-input nutrient-unit" value="mg" readonly style="text-align:center; color:#888; background:transparent; border:none; outline:none; cursor:default;">`;
        } else {
            return `<input type="text" class="table-input nutrient-unit" value="g" readonly style="text-align:center; color:#888; background:transparent; border:none; outline:none; cursor:default;">`;
        }
    }

    function populateResults(data) {
        if (data.annotated_image) imagePreview.src = "data:image/jpeg;base64," + data.annotated_image;
        if(foodNameInput) foodNameInput.value = data.suggested_name || '';
        
        nutrientTableBody.innerHTML = '';
        const nutrients = data.nutrients || {};
        
        VALID_NUTRIENTS.forEach(name => {
            const val = nutrients[name];
            if (val !== undefined && val !== null) { 
                nutrientTableBody.innerHTML += createRow(name, val, false);
            }
        });

        attachTableListeners();
        validateFormState();
    }

    function createRow(label, value, isNew = false) {
        let labelHtml = `<strong>${label}</strong>`;
        let unitHtml = generateUnitHtml(label); // Auto-generate unit based on label

        if (isNew) {
            const available = getAvailableNutrients();
            if (available.length === 0) return null;
            
            labelHtml = `<select class="table-input nutrient-name-select">
                ${available.map(n => `<option value="${n}">${n}</option>`).join('')}
            </select>`;
            unitHtml = generateUnitHtml(available[0]); // Generate unit for the first available dropdown option
        }

        return `<tr>
            <td>${labelHtml}</td>
            <td><input type="number" min="0" step="0.1" class="table-input nutrient-val" value="${value||0}"></td>
            <td style="vertical-align: middle;">${unitHtml}</td>
            <td style="text-align:right;"><button class="delete-row-btn" title="Remove field">×</button></td>
        </tr>`;
    }

    if(addRowBtn) addRowBtn.addEventListener('click', () => {
        const available = getAvailableNutrients();
        if (available.length === 0) return alert("All nutrients present.");
        const rowHtml = createRow(available[0], 0, true);
        if (rowHtml) {
            const empty = document.querySelector('.empty-state-row');
            if(empty) empty.remove();
            nutrientTableBody.insertAdjacentHTML('beforeend', rowHtml);
            attachTableListeners();
        }
    });

    function attachTableListeners() {
        document.querySelectorAll('.nutrient-val').forEach(input => {
            input.oninput = (e) => {
                if (e.target.type === 'number' && parseFloat(e.target.value) < 0) e.target.value = 0;
                giPredicted = false;
                if(giResultArea) giResultArea.classList.add('hidden');
                validateFormState();
            };
        });

        //  Update the unit dynamically if they change the dropdown name
        document.querySelectorAll('.nutrient-name-select').forEach(select => {
            select.addEventListener('change', (e) => {
                const tr = e.target.closest('tr');
                const unitTd = tr.querySelectorAll('td')[2];
                unitTd.innerHTML = generateUnitHtml(e.target.value); // Swap the unit HTML
                
                giPredicted = false;
                if(giResultArea) giResultArea.classList.add('hidden');
                validateFormState();
            });
        });

        // If they change Calories from kJ to kcal (or vice versa), prediction resets
        document.querySelectorAll('.nutrient-unit').forEach(select => {
            select.addEventListener('change', () => {
                giPredicted = false;
                if(giResultArea) giResultArea.classList.add('hidden');
                validateFormState();
            });
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
                let val = parseFloat(row.querySelector('.nutrient-val').value) || 0;
                const unit = row.querySelector('.nutrient-unit').value;

                // Convert kJ to kcal before sending to AI Model
                if (name === "Calories" && unit === "kJ") {
                    val = Math.round(val / 4.184); 
                }

                const dbKey = name.toLowerCase().replace("total fat", "fat").replace("carbohydrate", "carbs");
                nutrientData[dbKey] = val;
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

                giResultArea.classList.remove('hidden');
                giPredicted = true;

                fetchInsulinAdvice(nutrientData);
            }
        } finally { 
            predictGiBtn.textContent = "Predict GI & GL"; 
            validateFormState(); 
        }
    });

    // --- Save Logic ---

    if(saveEntryBtn) saveEntryBtn.addEventListener('click', async () => {
        const payload = {
            foodname: foodNameInput.value,
            mealtype: mealTypeSelect.value,
            insulin: parseFloat(document.getElementById('insulin-input').value) || 0,
            calories: 0, carbs: 0, protein: 0, fat: 0, sodium: 0, fiber: 0,
            gi: parseFloat(document.getElementById('gi').textContent) || 0,
            gl: parseFloat(document.getElementById('gl').textContent) || 0
        };

        let saltValue = 0;

        document.querySelectorAll('#nutrient-table-body tr').forEach(row => {
            const sel = row.querySelector('.nutrient-name-select');
            const lab = row.querySelector('td strong');
            let name = sel ? sel.value : (lab ? lab.innerText : "");
            let val = parseFloat(row.querySelector('.nutrient-val').value) || 0;
            const unit = row.querySelector('.nutrient-unit').value; // Read the strictly locked unit

            if (name === "Calories") {
                // Convert kJ to kcal before saving to DB
                if (unit === "kJ") {
                    val = Math.round(val / 4.184);
                }
                payload.calories = val;
            } else if (name === "Salt") {
                saltValue = val;
            } else {
                const keyMap = {
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

        // Convert Salt to Sodium
        if (saltValue > 0 && payload.sodium === 0) {
            payload.sodium = Math.round((saltValue / 2.5) * 1000);
        }

        try {
            const res = await fetch('/scan/save_entry', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
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

    // --- Insulin Advisor ---

    (async function loadAutoISFICR() {
        try {
            const res = await fetch('/scan/auto-isf-icr');
            const data = await res.json();
            if (data.error) return;

            const isfInput = document.getElementById('isf-input');
            const icrInput = document.getElementById('icr-input');
            const isfHint = document.getElementById('isf-scan-hint');
            const icrHint = document.getElementById('icr-scan-hint');

            if (isfInput) isfInput.placeholder = data.isf;
            if (icrInput) icrInput.placeholder = data.icr;

            if (data.source === 'calculated') {
                if (isfHint) isfHint.textContent = `Auto: ${data.isf} (TDD ${data.tdd}u/day)`;
                if (icrHint) icrHint.textContent = `Auto: ${data.icr} (TDD ${data.tdd}u/day)`;
            }
        } catch (err) {
            console.log("Auto ISF/ICR unavailable:", err);
        }
    })();

    async function fetchInsulinAdvice(nutrientData) {
        const carbs = parseFloat(nutrientData.carbs || nutrientData.carbohydrate || 0);
        if (carbs <= 0) return;

        const hintDiv = document.getElementById('insulin-advisor-hint');
        const totalSpan = document.getElementById('advisor-total');
        const breakdownDiv = document.getElementById('advisor-breakdown');

        const body = { planned_carbs: carbs };
        const isfVal = document.getElementById('isf-input').value;
        const icrVal = document.getElementById('icr-input').value;
        if (isfVal) body.isf = parseFloat(isfVal);
        if (icrVal) body.icr = parseFloat(icrVal);

        try {
            const res = await fetch('/scan/insulin-advice', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();

            if (data.error) {
                console.log("Insulin advisor:", data.error);
                return;
            }

            totalSpan.textContent = data.total_dose.toFixed(1);

            const parts = [];
            if (data.meal_dose > 0) parts.push(`Meal: ${data.meal_dose.toFixed(1)}u`);
            if (data.correction_dose > 0) parts.push(`Correction: ${data.correction_dose.toFixed(1)}u`);
            if (data.iob_adjustment > 0) parts.push(`IOB: -${data.iob_adjustment.toFixed(1)}u`);
            parts.push(`BG: ${Math.round(data.current_bg)} mg/dL`);
            breakdownDiv.textContent = parts.join(' | ');

            hintDiv.classList.remove('hidden');

            const insulinInput = document.getElementById('insulin-input');
            if (insulinInput && !insulinInput.value) {
                insulinInput.value = data.total_dose.toFixed(1);
            }
        } catch (err) {
            console.error("Insulin advice error:", err);
        }
    }
});