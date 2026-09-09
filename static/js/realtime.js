/**
 * realtime.js - SocketIO Real-time Academic Grade & Prediction Updates
 */

let socket = null;

function initRealtimeUpdates(studentPrn) {
  if (!studentPrn || typeof io === 'undefined') return;

  try {
    socket = io();

    socket.on('connect', () => {
      console.log('[SocketIO] Connected to live channel.');
      socket.emit('join_student_room', { student_prn: studentPrn });
    });

    socket.on('academic_update', (data) => {
      console.log('[SocketIO] Academic Update Received:', data);
      showLiveToast(`Faculty submitted new marks for ${data.subject_code}. New SGPA: ${data.new_sgpa.toFixed(2)}`);
      
      // Update DOM values dynamically
      updateStudentDashboardMetrics(data);
    });

    socket.on('disconnect', () => {
      console.log('[SocketIO] Disconnected.');
    });
  } catch (err) {
    console.warn('[SocketIO] Real-time setup note:', err);
  }
}

function showLiveToast(message) {
  const toastContainer = document.getElementById('toast-container');
  if (!toastContainer) {
    const div = document.createElement('div');
    div.id = 'toast-container';
    div.className = 'fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none';
    document.body.appendChild(div);
  }

  const toast = document.createElement('div');
  toast.className = 'pointer-events-auto bg-slate-900 text-white px-5 py-3 rounded-xl shadow-2xl border border-blue-500/50 flex items-center gap-3 transform transition-all duration-300 translate-y-4 opacity-0';
  toast.innerHTML = `
    <span class="w-3 h-3 rounded-full bg-emerald-400 animate-ping"></span>
    <span class="text-sm font-medium">${message}</span>
    <button onclick="this.parentElement.remove()" class="ml-2 text-slate-400 hover:text-white">&times;</button>
  `;

  document.getElementById('toast-container').appendChild(toast);

  // Animate in
  setTimeout(() => {
    toast.classList.remove('translate-y-4', 'opacity-0');
  }, 50);

  // Auto remove after 6s
  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-4');
    setTimeout(() => toast.remove(), 300);
  }, 6000);
}

function updateStudentDashboardMetrics(data) {
  const sgpaEl = document.getElementById('metric-current-sgpa');
  if (sgpaEl) sgpaEl.innerText = data.new_sgpa.toFixed(2);

  if (data.predictions) {
    const predEl = document.getElementById('metric-pred-sgpa');
    if (predEl && data.predictions.predicted_next_sgpa) {
      predEl.innerText = data.predictions.predicted_next_sgpa.toFixed(2);
    }
    const placeEl = document.getElementById('metric-placement-score');
    if (placeEl && data.predictions.placement_readiness_score) {
      placeEl.innerText = `${data.predictions.placement_readiness_score}%`;
    }
  }
}
