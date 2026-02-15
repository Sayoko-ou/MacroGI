// 1. Declare globally at the top
let glucoseChart;
let shapChart;

document.addEventListener('DOMContentLoaded', function() {
    const ctx = document.getElementById('glucoseChart').getContext('2d');

    // 2. Initialize the chart with two datasets: actual + forecast
    glucoseChart = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [
                {
                    label: 'Glucose Level',
                    data: [],
                    borderColor: '#4e73df',
                    backgroundColor: 'rgba(78, 115, 223, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0
                },
                {
                    label: 'Forecast',
                    data: [],
                    borderColor: '#e74a3b',
                    backgroundColor: 'rgba(231, 74, 59, 0.08)',
                    borderDash: [8, 4],
                    fill: true,
                    tension: 0.3,
                    pointRadius: 5,
                    pointBackgroundColor: '#e74a3b',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'time',
                    time: { unit: 'hour' },
                    title: { display: true, text: 'Time' }
                },
                y: {
                    beginAtZero: false,
                    title: { display: true, text: 'mg/dL' }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                }
            }
        }
    });

    // 3. Now that the chart exists, fetch the data
    refreshDashboard();
});


async function refreshDashboard() {
    const userId = "2";

    try {
        const response = await fetch(`/api/glucose-stats?user_id=${userId}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log("Data received:", data);

        if (data.error) {
            console.log("Backend returned error:", data.error);
            return;
        }

        // 1. Update the Big Chart — actual readings
        if (glucoseChart && data.chart_data) {
            glucoseChart.data.datasets[0].data = data.chart_data;

            // 2. Update forecast line if available
            if (data.forecast_data) {
                glucoseChart.data.datasets[1].data = data.forecast_data;
            } else {
                glucoseChart.data.datasets[1].data = [];
            }

            glucoseChart.update();
        }

        // 3. Update the Current Glucose Card
        const valEl = document.getElementById('current-glucose-value');
        if (valEl && data.latest) {
            valEl.innerText = Math.round(data.latest.value);
            document.getElementById('last-reading-time').innerText = `Last read: ${data.latest.time}`;

            // Color coding
            if (data.latest.value > 180) valEl.style.color = "#e74a3b";
            else if (data.latest.value < 70) valEl.style.color = "#f6c23e";
            else valEl.style.color = "#1cc88a";
        }

        // 4. Update Forecast Cards
        if (data.forecast_data && data.forecast_data.length === 4) {
            const preds = data.forecast_data;
            updateForecastCard('pred-30', preds[1].y);
            updateForecastCard('pred-60', preds[2].y);
            updateForecastCard('pred-90', preds[3].y);
        }

        // 5. Update AI Insights
        const insightEl = document.getElementById('ai-insights-content');
        if (insightEl) {
            insightEl.innerHTML = `<p>${data.insights}</p>`;
        }

        // 6. Update SHAP Explainability Chart
        if (data.explanations && data.explanations["60min"]) {
            renderShapChart(data.explanations);
        }

    } catch (err) {
        console.error("Error fetching stats:", err);
    }
}

function updateForecastCard(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    const rounded = Math.round(value);
    el.innerText = rounded;
    // Color code the prediction
    if (rounded > 180) el.style.color = "#e74a3b";
    else if (rounded < 70) el.style.color = "#f6c23e";
    else el.style.color = "#1cc88a";
}

function renderShapChart(explanations) {
    const horizon = explanations["60min"];
    if (!horizon) return;

    // Sort features by absolute contribution
    const entries = Object.entries(horizon)
        .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

    const labels = entries.map(e => e[0]);
    const values = entries.map(e => e[1]);
    const colors = values.map(v => v > 0 ? 'rgba(231, 74, 59, 0.8)' : 'rgba(28, 200, 138, 0.8)');
    const borderColors = values.map(v => v > 0 ? '#e74a3b' : '#1cc88a');

    const canvas = document.getElementById('shapChart');
    if (!canvas) return;

    // Show the container
    const container = document.getElementById('shap-container');
    if (container) container.style.display = 'block';

    // Update summary text
    const summaryEl = document.getElementById('shap-summary');
    if (summaryEl && explanations.summary) {
        summaryEl.innerText = explanations.summary;
    }

    if (shapChart) shapChart.destroy();

    shapChart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Feature Contribution (60-min)',
                data: values,
                backgroundColor: colors,
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: { display: true, text: 'SHAP Contribution' },
                    grid: { color: 'rgba(0,0,0,0.05)' }
                },
                y: {
                    grid: { display: false }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const val = ctx.raw;
                            const dir = val > 0 ? 'pushes glucose UP' : 'pushes glucose DOWN';
                            return `${Math.abs(val).toFixed(4)} — ${dir}`;
                        }
                    }
                }
            }
        }
    });
}

// Run on load and every 5 minutes
refreshDashboard();
setInterval(refreshDashboard, 300000);
