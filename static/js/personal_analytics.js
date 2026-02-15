// 1. Declare globally at the top
let glucoseChart;
let shapChart;
let currentExplanations = null;
let activeHorizon = "60min";

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

    // 3. Set up SHAP tab click handlers
    document.querySelectorAll('.shap-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.shap-tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            activeHorizon = this.dataset.horizon;
            if (currentExplanations) {
                renderShapChart(currentExplanations, activeHorizon);
            }
        });
    });

    // 4. Now that the chart exists, fetch the data
    refreshDashboard();

    // 5. Auto-refresh every 5 minutes
    setInterval(refreshDashboard, 300000);
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
        renderInsights(data.insights);

        // 6. Update SHAP Explainability Chart
        if (data.explanations && data.explanations["60min"]) {
            currentExplanations = data.explanations;
            renderShapChart(data.explanations, activeHorizon);
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

// Icon map for insight types
const INSIGHT_ICONS = {
    target: "\u{1F3AF}",
    variability: "\u{1F4C9}",
    hypo: "\u{26A0}",
    hyper: "\u{1F525}",
    trend_up: "\u{2B06}",
    trend_down: "\u{2B07}",
    trend_stable: "\u{2705}",
    dawn: "\u{1F305}",
    spike: "\u{26A1}",
    average: "\u{1F4CA}",
    info: "\u{2139}"
};

function renderInsights(insights) {
    const container = document.getElementById('ai-insights-content');
    if (!container) return;

    // Handle legacy string format (fallback)
    if (typeof insights === 'string') {
        container.innerHTML = `<div class="insight-item insight-info">
            <div class="insight-icon insight-icon-info">i</div>
            <div class="insight-text"><strong>Insight</strong><p>${insights}</p></div>
        </div>`;
        return;
    }

    if (!Array.isArray(insights) || insights.length === 0) {
        container.innerHTML = `<div class="insight-item insight-info">
            <div class="insight-icon insight-icon-info">i</div>
            <div class="insight-text"><strong>No Data</strong><p>Not enough readings to generate insights.</p></div>
        </div>`;
        return;
    }

    container.innerHTML = insights.map(ins => {
        const sev = ins.severity || 'info';
        const icon = INSIGHT_ICONS[ins.icon] || INSIGHT_ICONS.info;
        return `<div class="insight-item insight-${sev}">
            <div class="insight-icon insight-icon-${sev}">${icon}</div>
            <div class="insight-text">
                <strong>${ins.title}</strong>
                <p>${ins.body}</p>
            </div>
        </div>`;
    }).join('');
}

function renderShapChart(explanations, horizon) {
    horizon = horizon || "60min";
    const data = explanations[horizon];
    if (!data) return;

    // Sort features by absolute contribution
    const entries = Object.entries(data)
        .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

    // Calculate total absolute contribution for percentages
    const totalAbs = entries.reduce((sum, e) => sum + Math.abs(e[1]), 0);

    const labels = entries.map(e => e[0]);
    const values = entries.map(e => e[1]);
    const percentages = entries.map(e => totalAbs > 0 ? Math.round(Math.abs(e[1]) / totalAbs * 100) : 0);
    const colors = values.map(v => v > 0 ? 'rgba(231, 74, 59, 0.75)' : 'rgba(28, 200, 138, 0.75)');
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
                label: `Feature Contribution (${horizon})`,
                data: values,
                backgroundColor: colors,
                borderColor: borderColors,
                borderWidth: 2,
                borderRadius: 4,
                barPercentage: 0.7
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: { right: 50 }
            },
            scales: {
                x: {
                    title: { display: true, text: 'SHAP Contribution', font: { weight: 'bold', size: 12 } },
                    grid: { color: 'rgba(0,0,0,0.05)' },
                    ticks: { font: { size: 11 } }
                },
                y: {
                    grid: { display: false },
                    ticks: { font: { size: 12, weight: '600' }, color: '#333' }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.85)',
                    titleFont: { size: 13, weight: 'bold' },
                    bodyFont: { size: 12 },
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(ctx) {
                            const val = ctx.raw;
                            const idx = ctx.dataIndex;
                            const pct = percentages[idx];
                            const dir = val > 0 ? 'pushes glucose UP' : 'pushes glucose DOWN';
                            return `${pct}% contribution — ${dir}`;
                        }
                    }
                }
            }
        },
        plugins: [{
            // Custom plugin to draw percentage labels on bars
            id: 'barPercentLabels',
            afterDatasetsDraw(chart) {
                const ctx = chart.ctx;
                chart.data.datasets[0].data.forEach((val, i) => {
                    const meta = chart.getDatasetMeta(0).data[i];
                    const pct = percentages[i];
                    if (pct < 1) return;
                    ctx.save();
                    ctx.font = 'bold 11px sans-serif';
                    ctx.fillStyle = '#555';
                    ctx.textAlign = val >= 0 ? 'left' : 'right';
                    ctx.textBaseline = 'middle';
                    const x = val >= 0 ? meta.x + 6 : meta.x - 6;
                    ctx.fillText(`${pct}%`, x, meta.y);
                    ctx.restore();
                });
            }
        }]
    });
}
