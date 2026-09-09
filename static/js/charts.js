/**
 * charts.js - Chart.js Initializers & Real-time Update Handlers
 */

// 1. Initialize Student SGPA Trend Line Chart
function initSgpaTrendChart(canvasId, dataPoints, targetNextSgpa = null) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  const labels = dataPoints.map(d => `Sem ${d.semester}`);
  const sgpaValues = dataPoints.map(d => d.sgpa);

  // Extend with predicted next SGPA if provided
  if (targetNextSgpa && dataPoints.length > 0) {
    const nextSem = dataPoints[dataPoints.length - 1].semester + 1;
    labels.push(`Sem ${nextSem} (Pred)`);
  }

  const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, 'rgba(59, 130, 246, 0.35)');
  gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Semester SGPA',
          data: dataPoints.map(d => d.sgpa),
          borderColor: '#3B82F6',
          backgroundColor: gradient,
          fill: true,
          tension: 0.35,
          borderWidth: 3,
          pointBackgroundColor: '#1D4ED8',
          pointBorderColor: '#FFFFFF',
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7
        },
        ...(targetNextSgpa ? [{
          label: 'ML Forecast',
          data: [...Array(dataPoints.length - 1).fill(null), dataPoints[dataPoints.length - 1]?.sgpa, targetNextSgpa],
          borderColor: '#10B981',
          borderDash: [5, 5],
          borderWidth: 2.5,
          pointBackgroundColor: '#10B981',
          pointRadius: 6,
          fill: false
        }] : [])
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: { font: { family: 'Inter', size: 12, weight: '600' } }
        },
        tooltip: {
          backgroundColor: '#0F172A',
          titleFont: { family: 'Outfit', size: 13 },
          bodyFont: { family: 'Inter', size: 12 },
          padding: 10,
          cornerRadius: 8
        }
      },
      scales: {
        y: {
          min: 0,
          max: 10,
          grid: { color: '#E2E8F0', drawBorder: false },
          ticks: { stepSize: 2, font: { family: 'Inter' } }
        },
        x: {
          grid: { display: false },
          ticks: { font: { family: 'Inter', weight: '500' } }
        }
      }
    }
  });
}

// 2. Initialize Subject Competency Radar Chart
function initSubjectRadarChart(canvasId, subjectData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !subjectData || subjectData.length === 0) return null;

  const labels = subjectData.map(s => s.subject_name.length > 18 ? s.subject_name.substring(0, 15) + '...' : s.subject_name);
  const scores = subjectData.map(s => s.score_pct);

  return new Chart(ctx, {
    type: 'radar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Competency (%)',
        data: scores,
        fill: true,
        backgroundColor: 'rgba(99, 102, 241, 0.25)',
        borderColor: '#6366F1',
        pointBackgroundColor: '#4F46E5',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: '#4F46E5',
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0F172A',
          callbacks: {
            label: function(context) {
              const item = subjectData[context.dataIndex];
              return `${item.subject_name}: ${context.raw}% (Grade: ${item.grade_letter})`;
            }
          }
        }
      },
      scales: {
        r: {
          min: 0,
          max: 100,
          ticks: { stepSize: 25, display: true, font: { size: 9 } },
          pointLabels: { font: { family: 'Inter', size: 11, weight: '500' } },
          grid: { color: '#E2E8F0' },
          angleLines: { color: '#E2E8F0' }
        }
      }
    }
  });
}

// 3. Initialize Department Rank Movement Chart
function initRankMovementChart(canvasId, rankHistory) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !rankHistory || rankHistory.length === 0) return null;

  const labels = rankHistory.map(r => `Sem ${r.semester}`);
  const ranks = rankHistory.map(r => r.rank);

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Department Rank',
        data: ranks,
        borderColor: '#F59E0B',
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        fill: true,
        tension: 0.3,
        borderWidth: 2.5,
        pointBackgroundColor: '#D97706',
        pointRadius: 5
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const sem = rankHistory[ctx.dataIndex];
              return `Rank #${ctx.raw} out of ${sem.total} students`;
            }
          }
        }
      },
      scales: {
        y: {
          reverse: true, // Lower rank number is better (top of chart)
          ticks: { stepSize: 5, font: { family: 'Inter' } },
          grid: { color: '#E2E8F0' }
        },
        x: { grid: { display: false } }
      }
    }
  });
}

// 4. Initialize Branch CGPA Distribution Bar Chart for Admin
function initBranchDistributionChart(canvasId, branchData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !branchData) return null;

  const branches = Object.keys(branchData);
  const distinctions = branches.map(b => branchData[b]?.cgpa_distribution?.distinction_9_plus || 0);
  const firstClasses = branches.map(b => branchData[b]?.cgpa_distribution?.first_class_7_5_to_9 || 0);
  const secondClasses = branches.map(b => branchData[b]?.cgpa_distribution?.second_class_6_to_7_5 || 0);
  const passClasses = branches.map(b => branchData[b]?.cgpa_distribution?.pass_class_4_to_6 || 0);
  const fails = branches.map(b => branchData[b]?.cgpa_distribution?.fail_below_4 || 0);

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: branches,
      datasets: [
        { label: 'Distinction (9+)', data: distinctions, backgroundColor: '#10B981' },
        { label: 'First Class (7.5-9)', data: firstClasses, backgroundColor: '#3B82F6' },
        { label: 'Second Class (6-7.5)', data: secondClasses, backgroundColor: '#F59E0B' },
        { label: 'Pass (4-6)', data: passClasses, backgroundColor: '#8B5CF6' },
        { label: 'Fail (<4)', data: fails, backgroundColor: '#EF4444' }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: { stacked: true, grid: { color: '#E2E8F0' } }
      },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, font: { family: 'Inter', size: 11 } } }
      }
    }
  });
}
