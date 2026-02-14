// Dashboard JavaScript - Fetches data from Supabase via API, auto-refreshes

let charts = {};
const AUTO_REFRESH_INTERVAL_MS = 60000; // 60 seconds
let refreshTimer = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeViewSwitching();
    initializeWeekSelector();
    initializeDaySelector();
    
    // Show/hide date selectors based on initial view
    const activeView = document.querySelector('.dashboard-view.active');
    if (activeView) {
        const viewId = activeView.id;
        const weekSelector = document.querySelector('.week-selector-wrapper');
        const daySelector = document.querySelector('.day-selector-wrapper');
        
        if (viewId === 'weekly-view') {
            if (weekSelector) weekSelector.classList.remove('hidden');
            if (daySelector) daySelector.classList.add('hidden');
        } else if (viewId === 'daily-view') {
            if (weekSelector) weekSelector.classList.add('hidden');
            if (daySelector) daySelector.classList.remove('hidden');
        } else {
            if (weekSelector) weekSelector.classList.add('hidden');
            if (daySelector) daySelector.classList.add('hidden');
        }
    }
    
    // Load data from Supabase API and render charts
    refreshCurrentView();
    
    // After a "shift" navigation we pass scroll=left; align the visible set to the left and clean URL
    applyScrollAlignFromUrl();
    
    // Auto-refresh: fetch fresh data from Supabase periodically
    refreshTimer = setInterval(refreshCurrentView, AUTO_REFRESH_INTERVAL_MS);
});

// Update month/year in the nav box (weekly/daily only)
function updatePeriodLabel() {
    const labelEl = document.getElementById('dashboard-period-label');
    if (!labelEl) return;
    const activeView = document.querySelector('.dashboard-view.active');
    if (!activeView) return;
    const viewId = activeView.id;
    if (viewId === 'overall-view') {
        labelEl.classList.add('hidden');
        labelEl.textContent = '';
        return;
    }
    if (viewId === 'weekly-view') {
        const activeWeek = document.querySelector('.week-btn.active');
        if (activeWeek) {
            const startIso = activeWeek.getAttribute('data-start-iso');
            if (startIso) {
                const d = new Date(startIso + 'T12:00:00');
                labelEl.textContent = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
                labelEl.classList.remove('hidden');
            }
        }
        return;
    }
    if (viewId === 'daily-view') {
        const activeDay = document.querySelector('.day-btn.active');
        if (activeDay) {
            const dateStr = activeDay.getAttribute('data-date');
            if (dateStr) {
                const d = new Date(dateStr + 'T12:00:00');
                labelEl.textContent = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
                labelEl.classList.remove('hidden');
            }
        }
    }
}

// Refresh the currently active view with data from Supabase
function refreshCurrentView() {
    const activeView = document.querySelector('.dashboard-view.active');
    if (!activeView) return;
    
    const viewId = activeView.id;
    if (viewId === 'overall-view') {
        loadOverallData();
    } else if (viewId === 'weekly-view') {
        const activeWeek = document.querySelector('.week-btn.active');
        if (activeWeek) {
            const startIso = activeWeek.getAttribute('data-start-iso');
            const endIso = activeWeek.getAttribute('data-end-iso');
            loadWeeklyData(null, startIso, endIso);
        } else {
            renderWeeklyCharts({});
        }
    } else if (viewId === 'daily-view') {
        const activeDay = document.querySelector('.day-btn.active');
        const dateStr = activeDay ? activeDay.getAttribute('data-date') : null;
        loadDailyData(dateStr);
    }
}

// View Switching
function initializeViewSwitching() {
    const viewButtons = document.querySelectorAll('.view-btn');
    const views = document.querySelectorAll('.dashboard-view');

    viewButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const targetView = this.getAttribute('data-view');
            
            viewButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            views.forEach(v => v.classList.remove('active'));
            document.getElementById(targetView + '-view').classList.add('active');
            
            const weekSelector = document.querySelector('.week-selector-wrapper');
            const daySelector = document.querySelector('.day-selector-wrapper');
            
            if (targetView === 'weekly') {
                if (weekSelector) weekSelector.classList.remove('hidden');
                if (daySelector) daySelector.classList.add('hidden');
            } else if (targetView === 'daily') {
                if (weekSelector) weekSelector.classList.add('hidden');
                if (daySelector) daySelector.classList.remove('hidden');
            } else {
                if (weekSelector) weekSelector.classList.add('hidden');
                if (daySelector) daySelector.classList.add('hidden');
            }
            
            updatePeriodLabel();
            setTimeout(() => refreshCurrentView(), 100);
        });
    });
}

// Align period selector to the left when URL has scroll=left (after a "shift" navigation).
function applyScrollAlignFromUrl() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('scroll') !== 'left') return;
    const activeView = document.querySelector('.dashboard-view.active');
    if (!activeView) return;
    const container = activeView.id === 'weekly-view'
        ? document.querySelector('.week-selector')
        : document.querySelector('.day-selector');
    if (container) {
        container.scrollLeft = 0;
    }
    params.delete('scroll');
    const newSearch = params.toString();
    const newUrl = window.location.pathname + (newSearch ? '?' + newSearch : '');
    history.replaceState({}, '', newUrl);
}

// Scroll the period selector so the active button is at left (direction > 0) or right (direction < 0).
function scrollPeriodSelectorIntoView(direction) {
    const activeView = document.querySelector('.dashboard-view.active');
    if (!activeView) return;
    const viewId = activeView.id;
    const container = viewId === 'weekly-view' ? document.querySelector('.week-selector') : document.querySelector('.day-selector');
    const activeBtn = container ? container.querySelector('.week-btn.active, .day-btn.active') : null;
    if (!container || !activeBtn) return;
    const maxScroll = container.scrollWidth - container.clientWidth;
    if (maxScroll <= 0) return;
    if (direction > 0) {
        container.scrollLeft = activeBtn.offsetLeft;
    } else {
        container.scrollLeft = Math.max(0, activeBtn.offsetLeft - (container.clientWidth - activeBtn.offsetWidth));
    }
}

// Week Selector: leftmost/rightmost click = shift to previous/next set (full nav); else in-place select.
function initializeWeekSelector() {
    const weekButtons = Array.from(document.querySelectorAll('.week-btn'));
    const lastIndex = weekButtons.length - 1;
    weekButtons.forEach((btn, index) => {
        btn.addEventListener('click', function() {
            const startIso = this.getAttribute('data-start-iso');
            const endIso = this.getAttribute('data-end-iso');
            if (!startIso || !endIso) return;
            if (index === 0) {
                window.location.href = '/dashboard?view=weekly&week_start=' + startIso + '&week_window=end&scroll=left';
                return;
            }
            if (index === lastIndex) {
                window.location.href = '/dashboard?view=weekly&week_start=' + startIso + '&week_window=start&scroll=left';
                return;
            }
            setActiveWeek(weekButtons, this);
            updatePeriodLabel();
            scrollPeriodSelectorIntoView(1);
            loadWeeklyData(this.getAttribute('data-week'), startIso, endIso);
        });
    });
}

function setActiveWeek(weekButtons, activeBtn) {
    weekButtons.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-pressed', 'false');
    });
    activeBtn.classList.add('active');
    activeBtn.setAttribute('aria-pressed', 'true');
}

// Day Selector: leftmost/rightmost click = shift to previous/next set (full nav); else in-place select.
function initializeDaySelector() {
    const dayButtons = Array.from(document.querySelectorAll('.day-btn'));
    const lastIndex = dayButtons.length - 1;
    const todayStr = new Date().toISOString().split('T')[0];
    dayButtons.forEach((btn, index) => {
        btn.addEventListener('click', function() {
            const date = this.getAttribute('data-date');
            if (!date) return;
            if (index === 0) {
                window.location.href = '/dashboard?view=daily&date=' + date + '&day_window=end&scroll=left';
                return;
            }
            if (index === lastIndex && date < todayStr) {
                window.location.href = '/dashboard?view=daily&date=' + date + '&day_window=start&scroll=left';
                return;
            }
            setActiveDay(dayButtons, this);
            updatePeriodLabel();
            scrollPeriodSelectorIntoView(1);
            loadDailyData(date);
        });
    });
}

function setActiveDay(dayButtons, activeBtn) {
    dayButtons.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-pressed', 'false');
    });
    activeBtn.classList.add('active');
    activeBtn.setAttribute('aria-pressed', 'true');
}

// Arrow navigation: in-place move within list, or full page "shift" at edge (set aligned left).
function navigatePeriod(direction) {
    const activeView = document.querySelector('.dashboard-view.active');
    if (!activeView) return;
    const viewId = activeView.id;

    if (viewId === 'weekly-view') {
        const weekButtons = Array.from(document.querySelectorAll('.week-btn'));
        const activeIndex = weekButtons.findIndex(b => b.classList.contains('active'));
        if (activeIndex === -1) return;
        const nextIndex = activeIndex + direction;
        if (nextIndex >= 0 && nextIndex < weekButtons.length) {
            const btn = weekButtons[nextIndex];
            setActiveWeek(weekButtons, btn);
            updatePeriodLabel();
            scrollPeriodSelectorIntoView(direction);
            const startIso = btn.getAttribute('data-start-iso');
            const endIso = btn.getAttribute('data-end-iso');
            if (startIso && endIso) loadWeeklyData(null, startIso, endIso);
        } else {
            const activeBtn = weekButtons[activeIndex];
            const startIso = activeBtn.getAttribute('data-start-iso');
            if (!startIso) return;
            const d = new Date(startIso + 'T12:00:00');
            d.setDate(d.getDate() + direction * 7);
            const newStartIso = d.toISOString().split('T')[0];
            const windowParam = direction > 0 ? 'week_window=start' : 'week_window=end';
            window.location.href = '/dashboard?view=weekly&week_start=' + newStartIso + '&' + windowParam + '&scroll=left';
        }
    } else if (viewId === 'daily-view') {
        const dayButtons = Array.from(document.querySelectorAll('.day-btn'));
        const activeIndex = dayButtons.findIndex(b => b.classList.contains('active'));
        if (activeIndex === -1) return;
        const nextIndex = activeIndex + direction;
        if (nextIndex >= 0 && nextIndex < dayButtons.length) {
            const btn = dayButtons[nextIndex];
            setActiveDay(dayButtons, btn);
            updatePeriodLabel();
            scrollPeriodSelectorIntoView(direction);
            const dateStr = btn.getAttribute('data-date');
            if (dateStr) loadDailyData(dateStr);
        } else {
            const activeBtn = dayButtons[activeIndex];
            const currentDate = activeBtn.getAttribute('data-date');
            if (!currentDate) return;
            const date = new Date(currentDate + 'T12:00:00');
            date.setDate(date.getDate() + direction);
            const newDateStr = date.toISOString().split('T')[0];
            const windowParam = direction > 0 ? 'day_window=start' : 'day_window=end';
            window.location.href = '/dashboard?view=daily&date=' + newDateStr + '&' + windowParam + '&scroll=left';
        }
    }
}

// Load Overall Data from Supabase
function loadOverallData() {
    fetch('/api/dashboard/overall?days=30')
        .then(response => response.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            renderOverallCharts(data);
        })
        .catch(err => {
            console.error('Error loading overall data:', err);
            renderOverallCharts({});
        });
}

// Load Weekly Data from Supabase
function loadWeeklyData(weekNum, startIso, endIso) {
    const url = `/api/dashboard/weekly?start=${encodeURIComponent(startIso || '')}&end=${encodeURIComponent(endIso || '')}`;
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            console.log('[Dashboard] Weekly data:', data);
            updateWeeklySummary(data);
            renderWeeklyCharts(data);
        })
        .catch(err => {
            console.error('Error loading weekly data:', err);
            updateWeeklySummary({ glycaemic_load: 0, carbohydrates: 0, calories: 0 });
            renderWeeklyCharts({});
        });
}

// Load Daily Data from Supabase
function loadDailyData(dateStr) {
    const url = dateStr ? `/api/dashboard/daily?date=${dateStr}` : '/api/dashboard/daily';
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            console.log('[Dashboard] Daily data:', data);
            updateDailySummary(data);
            updateDailyFoodLog(data.food_entries || []);
            renderDailyCharts(data);
        })
        .catch(err => {
            console.error('Error loading daily data:', err);
            updateDailySummary({ glycaemic_load: 0, carbohydrates: 0, calories: 0 });
            updateDailyFoodLog([]);
            renderDailyCharts({});
        });
}

function updateWeeklySummary(data) {
    const cards = document.querySelectorAll('#weekly-view .summary-cards .summary-card');
    if (cards.length >= 3) {
        cards[0].querySelector('.summary-value').textContent = data.glycaemic_load ?? 0;
        cards[1].querySelector('.summary-value').textContent = data.carbohydrates ?? 0;
        cards[2].querySelector('.summary-value').textContent = data.calories ?? 0;
    }
}

function updateDailySummary(data) {
    const cards = document.querySelectorAll('#daily-view .summary-cards .summary-card');
    if (cards.length >= 3) {
        cards[0].querySelector('.summary-value').textContent = data.glycaemic_load ?? 0;
        cards[1].querySelector('.summary-value').textContent = data.carbohydrates ?? 0;
        cards[2].querySelector('.summary-value').textContent = data.calories ?? 0;
    }
}

function updateDailyFoodLog(entries) {
    const container = document.querySelector('#daily-view .timeline-items');
    if (!container) return;
    container.innerHTML = entries.length ? entries.map(e => `
        <div class="timeline-item">
            <div class="timeline-time">${e.time || '--'}</div>
            <div class="timeline-content">
                <strong>${e.food || 'Unknown'}</strong>
                <span class="timeline-gl">${e.gl ?? 0} GL</span>
            </div>
        </div>
    `).join('') : '<p class="empty-state">No food entries for this day.</p>';
}

// Overall Charts (from Supabase)
function renderOverallCharts(data) {
    Object.values(charts).forEach(chart => {
        if (chart && typeof chart.destroy === 'function') chart.destroy();
    });
    charts = {};

    const lc = data.line_chart || {};
    const labels = lc.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'];
    const carb = lc.carb || Array(labels.length).fill(0);
    const gl = lc.gl || Array(labels.length).fill(0);
    const cal = lc.calories || Array(labels.length).fill(0);

    const lineCtx = document.getElementById('overall-line-chart');
    if (lineCtx) {
        const maxVal = Math.max(...carb, ...gl, ...cal, 1);
        charts.overallLine = new Chart(lineCtx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'Carb', data: carb, borderColor: '#5B9BD5', backgroundColor: 'rgba(91, 155, 213, 0.1)', tension: 0.4 },
                    { label: 'GL', data: gl, borderColor: '#70AD47', backgroundColor: 'rgba(112, 173, 71, 0.1)', tension: 0.4 },
                    { label: 'Calories', data: cal, borderColor: '#4472C4', backgroundColor: 'rgba(68, 114, 196, 0.1)', tension: 0.4 }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true, position: 'top' } }, scales: { y: { beginAtZero: true } } }
        });
    }

    const pc = data.pie_chart || {};
    const pieLabels = pc.labels && pc.labels.length ? pc.labels : ['No data'];
    const pieVals = pc.values && pc.values.length ? pc.values : [1];
    const pieCtx = document.getElementById('overall-pie-chart');
    if (pieCtx) {
        charts.overallPie = new Chart(pieCtx, {
            type: 'pie',
            data: {
                labels: pieLabels,
                datasets: [{ data: pieVals, backgroundColor: ['#5B9BD5', '#70AD47', '#FFC000', '#ED7D31', '#ED7D32'] }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
        });
    }

    const topGi = (data.top_gi || []).slice(0, 20);
    const topCarb = (data.top_carb || []).slice(0, 20);
    const giLabels = topGi.length ? topGi.map(x => (x.name || 'Unknown').substring(0, 12)) : ['No data'];
    const giData = topGi.length ? topGi.map(x => x.gi) : [0];
    const carbLabels = topCarb.length ? topCarb.map(x => (x.name || 'Unknown').substring(0, 12)) : ['No data'];
    const carbData = topCarb.length ? topCarb.map(x => x.carbs) : [0];

    const giCtx = document.getElementById('overall-gi-chart');
    if (giCtx) {
        charts.overallGI = new Chart(giCtx, {
            type: 'bar',
            data: { labels: giLabels, datasets: [{ label: 'GI', data: giData, backgroundColor: '#5B9BD5' }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });
    }
    const carbCtx = document.getElementById('overall-carb-chart');
    if (carbCtx) {
        charts.overallCarb = new Chart(carbCtx, {
            type: 'bar',
            data: { labels: carbLabels, datasets: [{ label: 'Carb', data: carbData, backgroundColor: '#5B9BD5' }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });
    }
}

// Weekly Charts (from Supabase)
function renderWeeklyCharts(data) {
    if (charts.weeklyLine) charts.weeklyLine.destroy();
    if (charts.weeklyBar) charts.weeklyBar.destroy();
    if (charts.weeklyPie) charts.weeklyPie.destroy();
    if (charts.weeklyBreakdown) charts.weeklyBreakdown.destroy();

    const labels = data.line_labels || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const lineCarb = data.line_carb || Array(7).fill(0);
    const lineGl = data.line_gl || Array(7).fill(0);
    const lineCal = data.line_calories || Array(7).fill(0);
    const breakdownGl = data.daily_breakdown_gl || Array(7).fill(0);
    const breakdownCarbs = data.daily_breakdown_carbs || Array(7).fill(0);
    const breakdownCal = data.daily_breakdown_calories || Array(7).fill(0);
    const top5 = data.top5_gl || [];
    const top5Labels = top5.length ? top5.map(x => (x.name || 'Unknown').substring(0, 12)) : ['No data'];
    const top5Data = top5.length ? top5.map(x => x.gl) : [0];
    const pieLabels = data.pie_labels && data.pie_labels.length ? data.pie_labels : ['No data'];
    const pieVals = data.pie_values && data.pie_values.length ? data.pie_values : [1];

    const lineCtx = document.getElementById('weekly-line-chart');
    if (lineCtx) {
        charts.weeklyLine = new Chart(lineCtx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'Carb', data: lineCarb, borderColor: '#5B9BD5', backgroundColor: 'rgba(91, 155, 213, 0.1)', tension: 0.4 },
                    { label: 'GL', data: lineGl, borderColor: '#70AD47', backgroundColor: 'rgba(112, 173, 71, 0.1)', tension: 0.4 },
                    { label: 'Calories', data: lineCal, borderColor: '#4472C4', backgroundColor: 'rgba(68, 114, 196, 0.1)', tension: 0.4 }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true, position: 'top' } }, scales: { y: { beginAtZero: true } } }
        });
    }

    const barCtx = document.getElementById('weekly-bar-chart');
    if (barCtx) {
        charts.weeklyBar = new Chart(barCtx, {
            type: 'bar',
            data: { labels: top5Labels, datasets: [{ label: 'GL', data: top5Data, backgroundColor: '#5B9BD5' }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });
    }

    const pieCtx = document.getElementById('weekly-pie-chart');
    if (pieCtx) {
        charts.weeklyPie = new Chart(pieCtx, {
            type: 'pie',
            data: { labels: pieLabels, datasets: [{ data: pieVals, backgroundColor: ['#5B9BD5', '#70AD47', '#FFC000', '#ED7D31'] }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
        });
    }

    const breakdownCtx = document.getElementById('weekly-daily-breakdown');
    if (breakdownCtx) {
        charts.weeklyBreakdown = new Chart(breakdownCtx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    { label: 'Glycaemic Load', data: breakdownGl, backgroundColor: '#5B9BD5' },
                    { label: 'Carbohydrates', data: breakdownCarbs, backgroundColor: '#70AD47' },
                    { label: 'Calories', data: breakdownCal, backgroundColor: '#FFC000' }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true, position: 'top' } }, scales: { y: { beginAtZero: true } } }
        });
    }
}

// Daily Charts (from Supabase)
function renderDailyCharts(data) {
    if (charts.dailyLine) charts.dailyLine.destroy();

    const labels = data.line_labels && data.line_labels.length ? data.line_labels : ['--'];
    const carb = data.line_carb || [0];
    const gl = data.line_gl || [0];
    const cal = data.line_calories || [0];

    const lineCtx = document.getElementById('daily-line-chart');
    if (lineCtx) {
        charts.dailyLine = new Chart(lineCtx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'Carb', data: carb, borderColor: '#5B9BD5', backgroundColor: 'rgba(91, 155, 213, 0.1)', tension: 0.4 },
                    { label: 'GL', data: gl, borderColor: '#70AD47', backgroundColor: 'rgba(112, 173, 71, 0.1)', tension: 0.4 },
                    { label: 'Calories', data: cal, borderColor: '#4472C4', backgroundColor: 'rgba(68, 114, 196, 0.1)', tension: 0.4 }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true, position: 'top' } }, scales: { y: { beginAtZero: true } } }
        });
    }
}
