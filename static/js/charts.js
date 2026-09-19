/**
 * charts.js - Chart.js Initializers & Real-time Update Handlers
 */

// 1. Initialize Student SGPA Trend Line Chart with Forecast & Benchmark
function initSgpaTrendChart(canvasId, dataPoints, targetNextSgpa = null, targetBenchmark = 8.5) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !dataPoints || dataPoints.length === 0) return null;

  const labels = dataPoints.map(d => `Sem ${d.semester}`);
  const sgpaValues = dataPoints.map(d => Number(d.sgpa));

  // Determine last semester number
  const lastSemNum = dataPoints[dataPoints.length - 1].semester;
  const lastSgpa = sgpaValues[sgpaValues.length - 1];

  // If AI prediction exists, add next semester label
  if (targetNextSgpa !== null && targetNextSgpa !== undefined) {
    labels.push(`Sem ${lastSemNum + 1} (AI Forecast)`);
  }

  const grad = ctx.getContext('2d').createLinearGradient(0, 0, 0, 320);
  grad.addColorStop(0, 'rgba(59, 130, 246, 0.32)');
  grad.addColorStop(0.75, 'rgba(59, 130, 246, 0.05)');
  grad.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

  // Build audited SGPA series (null for prediction slot)
  const auditedSeries = dataPoints.map(d => Number(d.sgpa));
  if (targetNextSgpa !== null && targetNextSgpa !== undefined) {
    auditedSeries.push(null);
  }

  // Build forecast series: nulls for previous semesters, connected from last audited point
  let forecastSeries = [];
  if (targetNextSgpa !== null && targetNextSgpa !== undefined) {
    forecastSeries = Array(dataPoints.length - 1).fill(null);
    forecastSeries.push(lastSgpa); // bridge point so line connects
    forecastSeries.push(Number(targetNextSgpa));
  }

  // Build horizontal target benchmark series
  const benchmarkSeries = labels.map(() => targetBenchmark);

  const datasets = [
    {
      label: 'Audited SGPA',
      data: auditedSeries,
      borderColor: '#2563EB',
      backgroundColor: grad,
      fill: true,
      tension: 0.35,
      borderWidth: 3,
      pointBackgroundColor: '#1D4ED8',
      pointBorderColor: '#FFFFFF',
      pointBorderWidth: 2.5,
      pointRadius: 6,
      pointHoverRadius: 8,
      zIndex: 10
    }
  ];

  if (targetNextSgpa !== null && targetNextSgpa !== undefined) {
    datasets.push({
      label: 'ML Forecast',
      data: forecastSeries,
      borderColor: '#10B981',
      borderDash: [6, 6],
      borderWidth: 2.5,
      pointBackgroundColor: '#059669',
      pointBorderColor: '#FFFFFF',
      pointBorderWidth: 2.5,
      pointRadius: 6,
      pointHoverRadius: 8,
      fill: false,
      zIndex: 9
    });
  }

  if (targetBenchmark) {
    datasets.push({
      label: `Target Goal (${targetBenchmark})`,
      data: benchmarkSeries,
      borderColor: '#94A3B8',
      borderDash: [3, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      pointHoverRadius: 0,
      fill: false,
      zIndex: 1
    });
  }

  const minVal = Math.min(...sgpaValues, targetNextSgpa || 10);
  const yMin = Math.max(0, Math.floor(minVal - 1.5));

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            font: { family: 'Inter', size: 12, weight: '600' },
            boxWidth: 14,
            usePointStyle: true
          }
        },
        tooltip: {
          backgroundColor: '#0F172A',
          titleFont: { family: 'Outfit', size: 13, weight: '700' },
          bodyFont: { family: 'Inter', size: 12 },
          padding: 12,
          cornerRadius: 10,
          callbacks: {
            label: function(ctx) {
              if (ctx.raw === null || ctx.raw === undefined) return null;
              if (ctx.dataset.label.includes('Target Goal')) {
                return ` Target Goal: ${ctx.raw} CGPA`;
              }
              if (ctx.dataset.label.includes('ML Forecast')) {
                return ` ML Forecast SGPA: ${Number(ctx.raw).toFixed(2)}`;
              }
              const idx = ctx.dataIndex;
              let extra = '';
              if (idx > 0 && dataPoints[idx - 1]) {
                const diff = (ctx.raw - dataPoints[idx - 1].sgpa).toFixed(2);
                extra = diff >= 0 ? ` (+${diff} vs Sem ${dataPoints[idx - 1].semester})` : ` (${diff} vs Sem ${dataPoints[idx - 1].semester})`;
              }
              return ` Audited SGPA: ${Number(ctx.raw).toFixed(2)}${extra}`;
            }
          }
        }
      },
      scales: {
        y: {
          min: yMin,
          max: 10,
          grid: { color: '#E2E8F0', drawBorder: false },
          ticks: {
            stepSize: 1,
            font: { family: 'Inter', size: 11 },
            callback: (val) => Number(val).toFixed(1)
          }
        },
        x: {
          grid: { display: false },
          ticks: { font: { family: 'Inter', weight: '600', size: 12 } }
        }
      }
    }
  });
}

// 2. Initialize Subject Competency Radar Chart (Student vs Class Benchmark)
function initSubjectRadarChart(canvasId, subjectData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !subjectData || subjectData.length === 0) return null;

  // Format clean labels: Code + truncated title
  const labels = subjectData.map(s => {
    const code = s.subject_code ? `${s.subject_code}` : '';
    const name = s.subject_name ? (s.subject_name.length > 16 ? s.subject_name.substring(0, 14) + '..' : s.subject_name) : '';
    return code ? `${code}: ${name}` : name;
  });

  const studentScores = subjectData.map(s => Number(s.score_pct || 0));
  const classAvgScores = subjectData.map(s => Number(s.class_avg || 65.0));

  return new Chart(ctx, {
    type: 'radar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Your Score (%)',
          data: studentScores,
          fill: true,
          backgroundColor: 'rgba(79, 70, 229, 0.22)',
          borderColor: '#4F46E5',
          borderWidth: 2.5,
          pointBackgroundColor: '#4338CA',
          pointBorderColor: '#FFFFFF',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6
        },
        {
          label: 'Class Benchmark (%)',
          data: classAvgScores,
          fill: true,
          backgroundColor: 'rgba(148, 163, 184, 0.12)',
          borderColor: '#94A3B8',
          borderWidth: 2,
          borderDash: [4, 4],
          pointBackgroundColor: '#64748B',
          pointBorderColor: '#FFFFFF',
          pointBorderWidth: 1.5,
          pointRadius: 3,
          pointHoverRadius: 5
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            boxWidth: 12,
            font: { family: 'Inter', size: 11, weight: '600' }
          }
        },
        tooltip: {
          backgroundColor: '#0F172A',
          titleFont: { family: 'Outfit', size: 12, weight: '700' },
          bodyFont: { family: 'Inter', size: 11 },
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            title: function(items) {
              if (!items.length) return '';
              const item = subjectData[items[0].dataIndex];
              return `${item.subject_code || ''} ${item.subject_name || ''}`;
            },
            label: function(context) {
              const item = subjectData[context.dataIndex];
              const score = Number(context.raw).toFixed(1);
              if (context.datasetIndex === 0) {
                const diff = (item.score_pct - item.class_avg).toFixed(1);
                const diffSign = diff >= 0 ? `+${diff}%` : `${diff}%`;
                return ` You: ${score}% (Grade ${item.grade_letter || 'P'}) [${diffSign} vs avg]`;
              } else {
                return ` Class Peer Avg: ${score}%`;
              }
            }
          }
        }
      },
      scales: {
        r: {
          min: 0,
          max: 100,
          ticks: {
            stepSize: 25,
            display: true,
            font: { size: 9, family: 'Inter' },
            backdropColor: 'transparent'
          },
          pointLabels: {
            font: { family: 'Inter', size: 10.5, weight: '600' },
            color: '#334155'
          },
          grid: { color: '#E2E8F0' },
          angleLines: { color: '#E2E8F0' }
        }
      }
    }
  });
}

// 3. Initialize Department Rank Movement Chart (Inverted Y-Axis)
function initRankMovementChart(canvasId, rankHistory) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !rankHistory || rankHistory.length === 0) return null;

  const labels = rankHistory.map(r => `Sem ${r.semester}`);
  const ranks = rankHistory.map(r => r.rank);
  const totalPeers = Math.max(...rankHistory.map(r => r.total || 66), 10);

  const grad = ctx.getContext('2d').createLinearGradient(0, 0, 0, 260);
  grad.addColorStop(0, 'rgba(245, 158, 11, 0.28)');
  grad.addColorStop(0.8, 'rgba(245, 158, 11, 0.04)');
  grad.addColorStop(1, 'rgba(245, 158, 11, 0.0)');

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Department Rank',
        data: ranks,
        borderColor: '#F59E0B',
        backgroundColor: grad,
        fill: true,
        tension: 0.32,
        borderWidth: 3,
        pointBackgroundColor: '#D97706',
        pointBorderColor: '#FFFFFF',
        pointBorderWidth: 2.5,
        pointRadius: 6,
        pointHoverRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0F172A',
          titleFont: { family: 'Outfit', size: 13, weight: '700' },
          bodyFont: { family: 'Inter', size: 12 },
          padding: 12,
          cornerRadius: 10,
          callbacks: {
            title: function(items) {
              const sem = rankHistory[items[0].dataIndex];
              return `Semester ${sem.semester} Standing`;
            },
            label: function(context) {
              const sem = rankHistory[context.dataIndex];
              const lines = [
                ` Department Standing: Rank #${context.raw} of ${sem.total} students`,
                ` Percentile: ${sem.percentile}th (Top ${(100 - sem.percentile).toFixed(1)}%)`
              ];
              if (sem.cgpa) {
                lines.push(` Cumulative CGPA: ${Number(sem.cgpa).toFixed(2)}`);
              }
              return lines;
            }
          }
        }
      },
      scales: {
        y: {
          reverse: true, // Lower rank number (e.g. #1) is at the top
          min: 1,
          max: totalPeers,
          grid: { color: '#E2E8F0', drawBorder: false },
          ticks: {
            stepSize: Math.max(5, Math.round(totalPeers / 6)),
            font: { family: 'Inter', size: 11 },
            callback: (v) => `#${v}`
          }
        },
        x: {
          grid: { display: false },
          ticks: { font: { family: 'Inter', weight: '600', size: 12 } }
        }
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
