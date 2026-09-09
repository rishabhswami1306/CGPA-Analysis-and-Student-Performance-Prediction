# Intelligent Student Academic Analytics & Placement Prediction System

An end-to-end, production-ready, high-performance web platform for academic performance analytics, ML-driven SGPA forecasting, detention risk classification, placement readiness scoring with SHAP explainability, deterministic what-if analysis, real-time grade updates via WebSockets, and role-based access control (Admin, Faculty, Student).

---

## 🌟 Key Features

1. **Deterministic Grade & Goal Engine**:
   - Auditable, exact university SGPA/CGPA formulas and attendance shortfall math ($3T - 4A$ required classes).
   - Algebraic "What-If" goal simulator solving for minimum End Semester Exam (ESE) marks.
2. **Machine Learning & Explainable AI**:
   - **Pipeline 1 (SGPA Regressor)**: Linear Regression baseline vs XGBoost / Random Forest Regressor ($R^2 \approx 0.69$).
   - **Pipeline 2 (Detention Classifier)**: Class-balanced Random Forest classifier for $<75\%$ attendance risks.
   - **Pipeline 3 (Placement Predictor)**: Employability readiness score ($0-100\%$) and Tier 1/2/3 categorization trained on historical placement records.
   - **Explainability**: Plain-language actionable feedback derived from SHAP/tree feature importances.
   - **Cold Start Handling**: Graceful fallback using branch baselines for 1st-semester students.
   - **Leakage Prevention**: GroupKFold cross-validation grouped strictly by `student_prn`.
3. **Role-Based Access Control (RBAC)**:
   - **Admin**: Bulk CSV/Excel upload with dry-run error preview, account management, audit log viewer, and model retrain trigger.
   - **Faculty**: Scoped grading interface restricted server-side to `assigned_subjects`.
   - **Student**: Personal performance dashboard, anonymized department rank movement, and official ReportLab PDF transcript downloads.
4. **Real-time Live Grade Propagation**:
   - Flask-SocketIO pushes instant updates to student dashboards the moment faculty submit marks.
5. **Cryptographic QR-Verified Transcripts**:
   - Official ReportLab mark-sheet transcripts embedded with cryptographic HMAC-SHA256 signatures and scannable QR codes.
   - Public institutional verification endpoint (`/auth/verify-transcript`) to instantly authenticate student academic records.
6. **Company Eligibility Matrix & Dream Target Simulator**:
   - Live campus placement eligibility engine filtering top recruiters (Google, Microsoft, Amazon, Goldman Sachs, TCS, Infosys, Deloitte, etc.).
   - Interactive Dream Company Target Simulator solving exact next-semester SGPA targets required to unlock locked dream companies.
7. **Resume ATS & Skill-Gap Matcher**:
   - Automated PDF resume text extraction via `pypdf` with domain-specific keyword benchmarking (Full Stack, Data Science/ML, DevOps, Core CS).
   - Generates ATS compatibility percentage (0–100%), detected vs missing competencies, and curriculum-aligned remedial coursework recommendations.
8. **Zero-Config Demo Fallback**:
   - Auto-detects MongoDB and Redis; seamlessly falls back to `mongomock` and in-memory caching if local instances are unavailable.

---

## 🚀 Quick Start (One-Command Demo)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Seed Database & Train ML Models
```bash
python scripts/seed_data.py
```

### 3. Start Application
```bash
python app.py
```
Open **`http://localhost:5000`** in your browser.
Open **`http://localhost:5000/apidocs/`** for interactive Swagger API documentation.

---

## 🔑 Demo Credentials

| Role | Email | Password | Scope & Key Features |
|---|---|---|---|
| **Admin** | `admin@institute.edu` | `Admin@12345` | Bulk upload, Audit logs, Institute analytics, ML retraining |
| **Faculty** | `faculty.sharma@institute.edu` | `Faculty@12345` | Grading assigned subjects (`CS301`, `CS302`, `CS401`, `DS501`) |
| **Student** | `student1@institute.edu` | `Student@12345` | Semester 4 CSE-DS student, SGPA trajectory, What-If engine |
| **At-Risk Student** | `student.atrisk@institute.edu` | `Student@12345` | Attendance $<75\%$, detention warning with lecture calculator |
| **Cold-Start Student** | `student.sem1@institute.edu` | `Student@12345` | Semester 1 student, provisional baseline forecast |

---

## 🧪 Running Automated Tests

Run the complete 18-test unit and integration test suite:
```bash
pytest -v
```

---

## 🏗️ Project Architecture

```text
cgpa-analytics-system/
├── app.py                      # Application factory & SocketIO server
├── config.py                   # Environment configurations
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── .env                        # Local configurations
│
├── ml_engine/                  # ML training, preprocessing, & inference
│   ├── preprocessor.py         # GroupKFold & cold-start feature extraction
│   ├── train_models.py         # Pipeline training & model comparison
│   ├── inference.py            # Real-time scoring functions & cache
│   ├── explainability.py       # SHAP / feature-importance recommendations
│   ├── model_registry.py       # Versioning, metadata, regression-guarded promotion
│   └── saved_models/           # .joblib model artifacts & metadata
│
├── routes/                     # Blueprint controllers
│   ├── auth_routes.py          # Login, lockout protection, JWT cookies
│   ├── admin_routes.py         # Bulk upload dry-run, CRUD, audit logs
│   ├── faculty_routes.py       # Scoped grading for assigned subjects
│   ├── student_routes.py       # Dashboard, predictions, PDF transcripts
│   └── api_routes.py           # REST endpoints with Swagger annotations
│
├── utils/                      # Shared helpers
│   ├── db.py                   # MongoDB & Redis connector with fallback
│   ├── decorators.py           # @role_required, @student_ownership_required
│   ├── validators.py           # Marshmallow request schemas
│   ├── audit_logger.py         # Audit logging to MongoDB
│   ├── grade_calculator.py     # Deterministic SGPA, CGPA, shortfall math
│   ├── what_if_solver.py       # Algebraic goal engine
│   └── pdf_generator.py        # ReportLab official mark-sheet transcript
│
├── static/
│   ├── css/style.css           # Glassmorphism, animations, styling
│   └── js/
│       ├── charts.js           # Chart.js initialization & dynamic updates
│       ├── realtime.js         # SocketIO client for live grade updates
│       └── main.js             # Live grade row calculators & AJAX
│
├── templates/
│   ├── base.html               # Base layout template
│   ├── auth/                   # login.html, change_password.html
│   ├── admin/                  # admin_dashboard.html, users_list.html, bulk_upload.html
│   ├── faculty/                # faculty_dashboard.html, grade_entry.html
│   └── student/                # student_dashboard.html, goal_planner.html
│
├── scripts/
│   └── seed_data.py            # Multi-branch synthetic seed data generator
│
├── tests/
│   ├── conftest.py             # Test client & mongomock fixtures
│   ├── test_auth.py            # JWT, lockout, and RBAC tests
│   ├── test_grade_calc.py      # Exhaustive grade math & algebra tests
│   ├── test_ml_pipelines.py    # GroupKFold, ML inference & explainability
│   └── test_integration.py     # End-to-end grading & PDF export tests
│
└── docs/
    └── api_reference.md        # REST API endpoint reference
```
