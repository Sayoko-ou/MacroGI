// Dashboard JavaScript

let charts = {};

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
    
    // Initialize charts for the active view
    setTimeout(() => {
        if (activeView) {
            const viewId = activeView.id;
            if (viewId === 'overall-view') {
                renderOverallCharts();
            } else if (viewId === 'weekly-view') {
                renderWeeklyCharts();
            } else if (viewId === 'daily-view') {
                renderDailyCharts();
            }
        }
    }, 100);
});

// View Switching
function initializeViewSwitching() {
    const viewButtons = document.querySelectorAll('.view-btn');
    const views = document.querySelectorAll('.dashboard-view');

    viewButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const targetView = this.getAttribute('data-view');
            
            // Update buttons
            viewButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            // Update views
            views.forEach(v => v.classList.remove('active'));
            document.getElementById(targetView + '-view').classList.add('active');
            
            // Show/hide date selectors based on view
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
            
            // Reinitialize charts for the active view
            setTimeout(() => {
                if (targetView === 'overall') {
                    renderOverallCharts();
                } else if (targetView === 'weekly') {
                    renderWeeklyCharts();
                } else if (targetView === 'daily') {
                    renderDailyCharts();
                }
            }, 100);
        });
    });
}

// Week Selector
function initializeWeekSelector() {
    const weekButtons = document.querySelectorAll('.week-btn');
    weekButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const weekNum = this.getAttribute('data-week');
            const startDate = this.getAttribute('data-start');
            const endDate = this.getAttribute('data-end');
            
            // Update active state
            weekButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            // Reload weekly data
            loadWeeklyData(weekNum, startDate, endDate);
        });
    });
}

// Day Selector
function initializeDaySelector() {
    const dayButtons = document.querySelectorAll('.day-btn');
    dayButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const date = this.getAttribute('data-date');
            
            // Reload daily data with new date
            window.location.href = '/dashboard?view=daily&date=' + date;
        });
    });
}

// Unified Navigation for Weekly and Daily
function navigatePeriod(direction) {
    const activeView = document.querySelector('.dashboard-view.active');
    if (!activeView) return;
    
    const viewId = activeView.id;
    
    if (viewId === 'weekly-view') {
        // Navigate weeks
        const activeBtn = document.querySelector('.week-btn.active');
        if (!activeBtn) return;
        
        const weekNum = parseInt(activeBtn.getAttribute('data-week'));
        const newWeekNum = weekNum + direction;
        
        if (newWeekNum < 1 || newWeekNum > 7) return;
        
        const targetBtn = document.querySelector(`.week-btn[data-week="${newWeekNum}"]`);
        if (targetBtn) {
            targetBtn.click();
        }
    } else if (viewId === 'daily-view') {
        // Navigate days
        const activeBtn = document.querySelector('.day-btn.active');
        if (!activeBtn) return;
        
        const currentDate = activeBtn.getAttribute('data-date');
        const date = new Date(currentDate);
        date.setDate(date.getDate() + direction);
        
        const newDateStr = date.toISOString().split('T')[0];
        window.location.href = '/dashboard?view=daily&date=' + newDateStr;
    }
}

// Load Weekly Data
function loadWeeklyData(weekNum, startDate, endDate) {
    fetch(`/api/dashboard/weekly?week=${weekNum}&start=${startDate}&end=${endDate}`)
        .then(response => response.json())
        .then(data => {
            updateWeeklySummary(data);
            renderWeeklyCharts(data);
        })
        .catch(error => console.error('Error loading weekly data:', error));
}

// Update Weekly Summary
function updateWeeklySummary(data) {
    document.querySelector('.summary-cards .summary-card:nth-child(1) .summary-value').textContent = data.glycaemic_load || 100;
    document.querySelector('.summary-cards .summary-card:nth-child(2) .summary-value').textContent = data.carbohydrates || 100;
    document.querySelector('.summary-cards .summary-card:nth-child(3) .summary-value').textContent = data.calories || 100;
}

// Initialize Charts
function initializeCharts() {
    if (document.getElementById('overall-view').classList.contains('active')) {
        renderOverallCharts();
    } else if (document.getElementById('weekly-view').classList.contains('active')) {
        renderWeeklyCharts();
    } else if (document.getElementById('daily-view').classList.contains('active')) {
        renderDailyCharts();
    }
}

// Overall Charts
function renderOverallCharts() {
    // Destroy existing charts
    Object.values(charts).forEach(chart => {
        if (chart && typeof chart.destroy === 'function') {
            chart.destroy();
        }
    });
    charts = {};

    // Line Chart - Monthly Trends
    const lineCtx = document.getElementById('overall-line-chart');
    if (lineCtx) {
        charts.overallLine = new Chart(lineCtx, {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'],
                datasets: [
                    {
                        label: 'Carb',
                        data: [25, 30, 28, 35, 32, 38, 40],
                        borderColor: '#5B9BD5',
                        backgroundColor: 'rgba(91, 155, 213, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'GL',
                        data: [20, 25, 22, 28, 26, 30, 32],
                        borderColor: '#70AD47',
                        backgroundColor: 'rgba(112, 173, 71, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Calories',
                        data: [30, 35, 32, 40, 38, 42, 45],
                        borderColor: '#4472C4',
                        backgroundColor: 'rgba(68, 114, 196, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 50
                    }
                }
            }
        });
    }

    // Pie Chart - Meal Types
    const pieCtx = document.getElementById('overall-pie-chart');
    if (pieCtx) {
        charts.overallPie = new Chart(pieCtx, {
            type: 'pie',
            data: {
                labels: ['Breakfast', 'Lunch', 'Dinner', 'Snack'],
                datasets: [{
                    data: [35, 30, 25, 10],
                    backgroundColor: ['#5B9BD5', '#70AD47', '#FFC000', '#ED7D31']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    // Bar Chart - GI Values
    const giCtx = document.getElementById('overall-gi-chart');
    if (giCtx) {
        charts.overallGI = new Chart(giCtx, {
            type: 'bar',
            data: {
                labels: ['Bread', 'Luncheon Meat', 'Sweets', 'Jaggery', 'Milk'],
                datasets: [{
                    label: 'GI',
                    data: [20, 15, 18, 22, 12],
                    backgroundColor: '#5B9BD5'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 25
                    }
                }
            }
        });
    }

    // Bar Chart - Carb Values
    const carbCtx = document.getElementById('overall-carb-chart');
    if (carbCtx) {
        charts.overallCarb = new Chart(carbCtx, {
            type: 'bar',
            data: {
                labels: ['Bread', 'Luncheon Meat', 'Sweets', 'Jaggery', 'Milk'],
                datasets: [{
                    label: 'Carb',
                    data: [40, 30, 35, 45, 25],
                    backgroundColor: '#5B9BD5'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 50
                    }
                }
            }
        });
    }
}

// Weekly Charts
function renderWeeklyCharts(data) {
    // Destroy existing charts
    if (charts.weeklyLine) charts.weeklyLine.destroy();
    if (charts.weeklyBar) charts.weeklyBar.destroy();
    if (charts.weeklyPie) charts.weeklyPie.destroy();
    if (charts.weeklyBreakdown) charts.weeklyBreakdown.destroy();

    // Line Chart
    const lineCtx = document.getElementById('weekly-line-chart');
    if (lineCtx) {
        charts.weeklyLine = new Chart(lineCtx, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [
                    {
                        label: 'Carb',
                        data: [30, 35, 28, 40, 32, 38, 35],
                        borderColor: '#5B9BD5',
                        backgroundColor: 'rgba(91, 155, 213, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'GL',
                        data: [25, 30, 22, 35, 28, 32, 30],
                        borderColor: '#70AD47',
                        backgroundColor: 'rgba(112, 173, 71, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Calories',
                        data: [35, 40, 32, 45, 38, 42, 40],
                        borderColor: '#4472C4',
                        backgroundColor: 'rgba(68, 114, 196, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 50
                    }
                }
            }
        });
    }

    // Bar Chart - Top 5 GL Foods
    const barCtx = document.getElementById('weekly-bar-chart');
    if (barCtx) {
        charts.weeklyBar = new Chart(barCtx, {
            type: 'bar',
            data: {
                labels: ['Bread', 'Luncheon Meat', 'Sweets', 'Jaggery', 'Milk'],
                datasets: [{
                    label: 'GL',
                    data: [20, 15, 18, 22, 12],
                    backgroundColor: '#5B9BD5'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    // Pie Chart - Meal Types
    const pieCtx = document.getElementById('weekly-pie-chart');
    if (pieCtx) {
        charts.weeklyPie = new Chart(pieCtx, {
            type: 'pie',
            data: {
                labels: ['Breakfast', 'Lunch', 'Dinner', 'Snack'],
                datasets: [{
                    data: [35, 30, 25, 10],
                    backgroundColor: ['#5B9BD5', '#70AD47', '#FFC000', '#ED7D31']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    // Daily Breakdown Chart
    const breakdownCtx = document.getElementById('weekly-daily-breakdown');
    if (breakdownCtx) {
        if (charts.weeklyBreakdown) charts.weeklyBreakdown.destroy();
        
        charts.weeklyBreakdown = new Chart(breakdownCtx, {
            type: 'bar',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [
                    {
                        label: 'Glycaemic Load',
                        data: [85, 92, 78, 95, 88, 102, 90],
                        backgroundColor: '#5B9BD5'
                    },
                    {
                        label: 'Carbohydrates',
                        data: [120, 135, 110, 140, 125, 150, 130],
                        backgroundColor: '#70AD47'
                    },
                    {
                        label: 'Calories',
                        data: [1800, 2000, 1700, 2100, 1900, 2200, 2000],
                        backgroundColor: '#FFC000'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

// Daily Charts
function renderDailyCharts() {
    // Destroy existing chart
    if (charts.dailyLine) charts.dailyLine.destroy();

    // Line Chart
    const lineCtx = document.getElementById('daily-line-chart');
    if (lineCtx) {
        charts.dailyLine = new Chart(lineCtx, {
            type: 'line',
            data: {
                labels: ['09:00', '12:00', '19:00'],
                datasets: [
                    {
                        label: 'Carb',
                        data: [25, 40, 20],
                        borderColor: '#5B9BD5',
                        backgroundColor: 'rgba(91, 155, 213, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'GL',
                        data: [20, 35, 15],
                        borderColor: '#70AD47',
                        backgroundColor: 'rgba(112, 173, 71, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Calories',
                        data: [30, 45, 25],
                        borderColor: '#4472C4',
                        backgroundColor: 'rgba(68, 114, 196, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
}
