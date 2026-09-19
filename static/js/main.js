/**
 * main.js - Core UI Interactions, AJAX Forms, Modals & Dynamic Grade Inputs
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Auto-dismiss alerts after 5 seconds
  const alerts = document.querySelectorAll('.flash-alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 400);
    }, 5000);
  });

  // 2. Faculty Live Grade Input Calculators
  initFacultyGradeCalculators();
});

function initFacultyGradeCalculators() {
  const studentRows = document.querySelectorAll('.grade-row');
  studentRows.forEach(row => {
    const tt1Input = row.querySelector('.input-tt1');
    const tt2Input = row.querySelector('.input-tt2');
    const ttConvDisplay = row.querySelector('.display-tt-conv');
    const aptInput = row.querySelector('.input-apt');
    const skatInput = row.querySelector('.input-skat');
    const taInput = row.querySelector('.input-ta');
    const mockInput = row.querySelector('.input-mock');
    const presInput = row.querySelector('.input-pres');
    const internalDisplay = row.querySelector('.display-internal');
    const eseInput = row.querySelector('.input-ese');
    const totalDisplay = row.querySelector('.display-total');
    const gradeBadge = row.querySelector('.display-grade');
    const saveBtn = row.querySelector('.btn-save-grade');

    function updateRowTotal() {
      const tt1 = Math.min(30, Math.max(0, parseFloat(tt1Input?.value || 0)));
      const tt2 = Math.min(30, Math.max(0, parseFloat(tt2Input?.value || 0)));
      const ttConv = (tt1 + tt2) / 4.0;
      if (ttConvDisplay) ttConvDisplay.innerText = ttConv.toFixed(1);

      const apt = Math.min(5, Math.max(0, parseFloat(aptInput?.value || 0)));
      const skat = Math.min(5, Math.max(0, parseFloat(skatInput?.value || 0)));
      const ta = Math.min(5, Math.max(0, parseFloat(taInput?.value || 0)));
      const mock = Math.min(5, Math.max(0, parseFloat(mockInput?.value || 0)));
      const pres = Math.min(5, Math.max(0, parseFloat(presInput?.value || 0)));

      const internal = Math.min(40, ttConv + apt + skat + ta + mock + pres);
      if (internalDisplay) internalDisplay.innerText = internal.toFixed(1);

      const ese = Math.min(60, Math.max(0, parseFloat(eseInput?.value || 0)));
      const total = Math.min(100, Math.max(0, internal + ese));
      
      if (totalDisplay) totalDisplay.innerText = total.toFixed(1);

      // Grade calculation (>=80 O, >=75 A+, >=70 A, >=60 B+, >=50 B, >=45 C, >=40 P, <40 F)
      const sem = parseInt(row.dataset.sem || 5);
      if (sem === 5 && ese === 0) {
        if (gradeBadge) {
          gradeBadge.innerText = 'Ongoing (Feeds ML)';
          gradeBadge.className = 'display-grade text-[11px] font-bold px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 border border-amber-200';
        }
      } else {
        let grade = 'F';
        let badgeClass = 'bg-red-100 text-red-700';
        if (total >= 80) { grade = 'O (10)'; badgeClass = 'bg-emerald-100 text-emerald-700'; }
        else if (total >= 75) { grade = 'A+ (9)'; badgeClass = 'bg-teal-100 text-teal-700'; }
        else if (total >= 70) { grade = 'A (8)'; badgeClass = 'bg-blue-100 text-blue-700'; }
        else if (total >= 60) { grade = 'B+ (7)'; badgeClass = 'bg-indigo-100 text-indigo-700'; }
        else if (total >= 50) { grade = 'B (6)'; badgeClass = 'bg-yellow-100 text-yellow-700'; }
        else if (total >= 45) { grade = 'C (5)'; badgeClass = 'bg-orange-100 text-orange-700'; }
        else if (total >= 40) { grade = 'P (4)'; badgeClass = 'bg-amber-100 text-amber-700'; }

        if (gradeBadge) {
          gradeBadge.innerText = grade;
          gradeBadge.className = `display-grade text-xs font-bold px-2 py-0.5 rounded-full ${badgeClass}`;
        }
      }
    }

    [tt1Input, tt2Input, aptInput, skatInput, taInput, mockInput, presInput, eseInput].forEach(inp => {
      if (inp) inp.addEventListener('input', updateRowTotal);
    });

    if (saveBtn) {
      saveBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        const prn = row.dataset.prn;
        const sem = parseInt(row.dataset.sem);
        const subCode = row.dataset.subCode;

        saveBtn.disabled = true;
        saveBtn.innerHTML = `<span class="animate-spin inline-block mr-1">⌛</span> Saving...`;

        try {
          const res = await fetch('/faculty/submit-grade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              student_prn: prn,
              semester: sem,
              subject_code: subCode,
              tt1_score: parseFloat(tt1Input?.value || 0),
              tt2_score: parseFloat(tt2Input?.value || 0),
              aptitude_score: parseFloat(aptInput?.value || 0),
              skat_score: parseFloat(skatInput?.value || 0),
              teacher_assessment_score: parseFloat(taInput?.value || 0),
              mock_interview_score: parseFloat(mockInput?.value || 0),
              presentation_score: parseFloat(presInput?.value || 0),
              ese_score: parseFloat(eseInput?.value || 0)
            })
          });

          const data = await res.json();
          if (res.ok) {
            saveBtn.className = 'btn-save-grade bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-all';
            saveBtn.innerHTML = `✓ Saved`;
            setTimeout(() => {
              saveBtn.disabled = false;
              saveBtn.className = 'btn-save-grade bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3.5 py-1.5 rounded-lg shadow-sm transition-all flex items-center gap-1.5 ml-auto';
              saveBtn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i><span>Save</span>`;
            }, 2000);
          } else {
            alert(data.error || 'Failed to update marks.');
            saveBtn.disabled = false;
            saveBtn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i><span>Save</span>`;
          }
        } catch (err) {
          alert('Network error while submitting grade.');
          saveBtn.disabled = false;
          saveBtn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i><span>Save</span>`;
        }
      });
    }
  });
}
    }
  });
}

// Modal helper
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('hidden');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('hidden');
}
