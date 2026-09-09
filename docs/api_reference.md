# API Reference Manual

Interactive OpenAPI / Swagger UI is auto-generated and served at:
`http://localhost:5000/apidocs/`

---

## Authentication Endpoints (`/auth`)

### 1. `POST /auth/login`
Authenticates a user and returns an access token along with an `httpOnly` refresh token cookie.
- **Rate Limit**: 5 consecutive failed attempts locks the account for 15 minutes.
- **Request Body**:
```json
{
  "email": "student1@institute.edu",
  "password": "Student@12345"
}
```
- **Response `200 OK`**:
```json
{
  "message": "Login successful",
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "prn_roll": "2022CS001",
    "name": "Rohan Deshmukh",
    "email": "student1@institute.edu",
    "role": "student",
    "branch": "CSE-DS"
  }
}
```

### 2. `POST /auth/refresh`
Refreshes the short-lived access token using the secure `refresh_token_cookie`.
- **Headers**: `Cookie: refresh_token_cookie=...`
- **Response `200 OK`**: Returns new access token.

### 3. `POST /auth/change-password`
Mandatory on first login or after admin reset.
- **Headers**: `Authorization: Bearer <access_token>`
- **Request Body**: `{"old_password": "...", "new_password": "..."}`

---

## Student Analytics Endpoints (`/api/student`)

### 1. `GET /api/student/<student_prn>/academic-summary`
Returns student historical semester records, calculated cumulative CGPA, earned credits, and backlogs.
- **Security**: IDOR protected (`@student_ownership_required`).
- **Response `200 OK`**:
```json
{
  "student_prn": "2022CS001",
  "cumulative_cgpa": 8.42,
  "completed_semesters": 4,
  "total_credits_earned": 80,
  "active_backlogs": 0,
  "records": [...]
}
```

### 2. `GET /api/student/<student_prn>/prediction`
Returns real-time ML forecast for next semester SGPA, detention classification risk, placement readiness score (0-100%), and plain-language SHAP explainability insights.
- **Response `200 OK`**:
```json
{
  "student_prn": "2022CS001",
  "predicted_next_sgpa": 8.65,
  "detention_risk": "LOW",
  "placement_readiness_score": 88.5,
  "placement_tier": "Tier 1 - High CTC / Product Core",
  "improvement_recommendations": [
    "Strong attendance consistency (86.0%) actively supports high retention.",
    "Outstanding CGPA satisfies eligibility criteria for 98%+ of Tier-1 product companies."
  ]
}
```

### 3. `POST /api/student/<student_prn>/what-if`
Prescriptive algebraic goal solver. Computes minimum End Semester Exam (ESE) marks required per subject to achieve target CGPA.
- **Request Body**:
```json
{
  "target_cgpa": 8.5
}
```

---

## Faculty Endpoints (`/faculty`)

### 1. `POST /faculty/submit-grade`
Updates subject scores. Emits a real-time WebSocket event on the student's channel and recalculates prediction caches.
- **Security**: Scoped to faculty's `assigned_subjects` (`@faculty_subject_authorized`).
- **Request Body**:
```json
{
  "student_prn": "2022CS001",
  "semester": 3,
  "subject_code": "CS301",
  "tt1_score": 18.0,
  "tt2_score": 17.5,
  "ese_score": 72.0
}
```

---

## Admin Endpoints (`/admin`, `/api/admin`)

### 1. `GET /api/admin/branch-analytics`
Aggregated grade distributions and KPI counts per department.

### 2. `GET /api/admin/detention-list`
List of all students with critical attendance shortfall (<75%) and exact required lecture count.

### 3. `POST /admin/retrain`
Triggers full end-to-end retraining of ML Regressor, Detention Classifier, and Placement Predictor on updated dataset.
