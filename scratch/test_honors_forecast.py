from utils.db import get_db
from utils.attendance_engine import compute_attendance_predictions

db = get_db()
rec = db.attendance_records.find_one({'student_prn': '241106058'})
forecast = compute_attendance_predictions('241106058', rec)
print('honors_names:', forecast.get('honors_names'))
print('honors_list length:', len(forecast.get('honors_list', [])))
for h in forecast.get('honors_list', []):
    print(f"Honors: {h['subject']}, Teacher: {h['teacher']}, Attended: {h['total_attended']}/{h['total_conducted']}, Pct: {h['current_pct']}%, Status: {h['status']}, Can Miss: {h['can_miss_now']}, Must Attend: {h['must_attend_now']}")
print('Core subjects:', list(forecast['subjects'].keys()))
print('Overall core attendance:', forecast['overall']['current_pct'], '%')
