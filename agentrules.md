# Millpoint QC - Agent Rules

Agent rules for the Millpoint QC (Ravnsgaard Metal A/S) quality control system. Follow these guidelines when making changes to the codebase.

---

## Tech Stack

### Backend
- **Framework**: Flask 3.x (Python)
- **Database**: SQLite (`qa.db`), with future consideration for PostgreSQL migration
- **Authentication**: Flask-Login with role-based access (admin, quality_manager, inspector, operator)
- **API Style**: RESTful-style endpoints; JSON via `jsonify` for API responses
- **File Storage**: Local filesystem (`static/uploads/` with subdirs: drawings, photos, certificates, documents)
- **Deployment**: Gunicorn + Nginx

### Frontend
- **Technology**: Vanilla JavaScript, HTML, CSS — no build step
- **No Frameworks**: Keep it simple and lightweight (no React, Vue, etc.)
- **Charts**: Chart.js (CDN) for dashboards and reports
- **Styling**: CSS with CSS variables for theming (light/dark mode)
- **Templates**: Jinja2
- **Language**: Danish (da) for all user-facing strings

### Development
- **Python**: 3.8+
- **Virtual Environment**: Standard Python venv
- **Dependencies**: `requirements.txt` (Flask, Flask-Login, Werkzeug, gunicorn)
- **Type Hints**: Use Python type hints and docstrings
- **Testing**: pytest (optional)

---

## Project Structure

```
millpoint-qa/
├── app.py              # Main Flask app, routes, DB schema, helpers
├── requirements.txt    # Python dependencies
├── seed_dev_db.py      # Dev seed data
├── agentrules.md       # This file
├── .gitignore
├── static/
│   ├── styles.css      # Global styles, theme variables
│   └── uploads/        # User uploads (gitignored)
└── templates/          # Jinja2 HTML templates
```

---

## Conventions

### Code Style
- Use parameterized SQL queries; never concatenate user input into SQL
- Prefer `query_db()` and `execute_db()` for database access
- Use `@login_required` and `@role_required(['admin', 'quality_manager'])` for protected routes
- Flash messages in Danish

### Templates
- Extend `base.html` for all pages
- Use `{% block title %}`, `{% block content %}`, `{% block extra_css %}`, `{% block extra_js %}`
- Use `workflow_stage_labels_da`, `severity_labels_da`, `error_type_labels_da` for Danish labels
- Set `lang="da"` on HTML root

### Database
- Schema managed in `init_db()`; migrations via `ALTER TABLE` in init
- Use `sqlite3.Row` for query results; convert to dict when passing to JSON
- Tables: users, customers, suppliers, parts, jobs, job_dimensions, job_documents, material_controls, external_processes, measurement_reports, measurements, exit_controls, exit_control_samples, error_reports, attachments, equipment, notifications, audit_logs

### Files & Uploads
- Validate file type with `ALLOWED_EXTENSIONS`
- Store in `static/uploads/<subdir>/`; subdirs by entity type
- Use `secure_filename()` or equivalent for upload paths

---

## Design Principles

1. **Simplicity**: No heavy frameworks; minimal dependencies
2. **Practical**: Focus on solving real QC workflow problems
3. **Danish UI**: All user-facing text in Danish
4. **Audit Trail**: Log important actions via `audit_logs` and `log_audit()`
5. **Security**: Input validation, parameterized queries, role-based access

---

## Workflow Stages (Danish)

- `po_receipt` → Ordremodtagelse
- `revision_check` → Revisionskontrol
- `material_control` → Materialekontrol
- `in_process` → I produktion
- `external_process` → Ekstern proces
- `exit_control` → Slutkontrol
- `complete` → Færdig
- `on_hold` → På hold

---

## Do Not

- Add React, Vue, or other frontend frameworks
- Use raw SQL string concatenation
- Commit `qa.db` or `static/uploads/` contents
- Expose `.env` or secrets in code
- Default to English for new UI strings (use Danish)
