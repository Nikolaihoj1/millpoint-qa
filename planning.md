# Internal Quality Control Tool - Planning Document

## Overview

An internal quality control tool for manufacturing operations that enables systematic tracking, documentation, and analysis of quality inspections, non-conformances, corrective actions, and continuous improvement initiatives.

**Design Philosophy:** Simple, practical, and straightforward - following the same lightweight approach as rfq-tracker.

---

## Objectives

- **Centralized Quality Management**: Single source of truth for all quality-related data
- **Real-time Tracking**: Monitor inspection status, defects, and corrective actions in real-time
- **Compliance & Traceability**: Maintain complete audit trails and compliance documentation
- **Data-Driven Decisions**: Analytics and reporting for quality trends and improvement opportunities
- **Workflow Automation**: Streamline inspection workflows and reduce manual paperwork

---

## Tech Stack

### Backend
- **Framework**: Flask (Python)
- **Database**: SQLite (with future consideration for PostgreSQL migration)
- **API Style**: RESTful API endpoints
- **File Storage**: Local filesystem (`static/uploads/` directory)
- **Deployment**: Gunicorn + Nginx

### Frontend
- **Technology**: Vanilla JavaScript, HTML, CSS
- **No Frameworks**: Keep it simple and lightweight
- **Charts/Visualizations**: Chart.js (lightweight library)
- **Styling**: CSS with CSS variables for theming (dark/light mode support)

### Development Tools
- **Python Version**: Python 3.8+
- **Virtual Environment**: Standard Python venv
- **Dependencies**: `requirements.txt` with Flask and SQLite support
- **Type Hints**: Use Python type hints throughout codebase

### Testing
- **Unit Tests**: pytest
- **Integration Tests**: Test API endpoints with pytest
- **Code Quality**: Type hints and docstrings

---

## Design Philosophy

### 1. **Simplicity First**
- No heavy frameworks or unnecessary complexity
- Direct database access with SQLite
- Vanilla JavaScript - no build step required
- Easy to understand, maintain, and deploy

### 2. **Practical & Functional**
- Focus on solving real problems, not showcasing technology
- Fast development cycles
- Easy to modify and extend
- Straightforward deployment (single server, simple setup)

### 3. **User-Centric Design**
- Clean, intuitive interfaces
- Mobile-responsive design for shop floor access
- Color-coded status indicators (similar to rfq-tracker)
- Progressive enhancement - works without JavaScript where possible

### 4. **Data Integrity & Auditability**
- Immutable audit logs for all critical actions
- Complete traceability with timestamps and user attribution
- SQLite database with proper indexes for performance
- Simple backup strategy (copy database file)

### 5. **Security & Compliance**
- Input validation and sanitization
- SQL injection prevention (parameterized queries)
- CSRF protection for forms
- Role-based access control (simple user roles)
- Compliance with ISO 9001, AS9100, or industry-specific standards

### 6. **Performance**
- Efficient database queries with proper indexing
- Pagination for large datasets
- Client-side filtering where appropriate
- Minimal dependencies for fast load times

---

## Core Features

### 1. Inspection Management
- **Inspection Plans**: Create and manage inspection plans by product/process
- **Inspection Execution**: Digital inspection forms with photos, measurements, notes
- **Checklist Templates**: Reusable inspection checklists
- **Results Recording**: Pass/fail with detailed findings
- **Status Tracking**: Color-coded status badges (similar to rfq-tracker)

### 2. Non-Conformance Management (NCR)
- **NCR Creation**: Capture non-conformances with severity classification
- **Root Cause Analysis**: Structured RCA forms (5 Why, Fishbone, etc.)
- **Corrective Actions**: Track CAPA (Corrective and Preventive Actions)
- **Action Items**: Assign and track action items with due dates
- **Status Workflow**: Track NCR status through lifecycle

### 3. Document Control
- **Quality Documents**: Specifications, procedures, work instructions
- **Version Control**: Track document revisions
- **File Storage**: Store documents in `static/uploads/documents/`
- **Document Metadata**: Track document number, version, approval status

### 4. Supplier Quality
- **Supplier Inspections**: Incoming inspection records
- **Supplier Scorecards**: Performance metrics and ratings
- **Supplier Corrective Actions**: SCAR (Supplier Corrective Action Request) tracking
- **Certificates of Conformance**: Digital COC management

### 5. Calibration & Equipment Management
- **Equipment Registry**: Track measurement equipment and tools
- **Calibration Schedule**: Track calibration due dates
- **Calibration Records**: Document calibration results
- **Equipment Status**: Available/Calibrated/Out of Service tracking

### 6. Analytics & Reporting
- **Quality Metrics Dashboard**: Key KPIs (First Pass Yield, Defect Rate, etc.)
- **Trend Analysis**: Quality trends over time using Chart.js
- **Export Capabilities**: CSV export using Python's `csv` module
- **Print-Friendly Views**: CSS print stylesheets

### 7. User Management & Permissions
- **Role-Based Access**: Admin, Quality Manager, Inspector, Operator, Viewer
- **User Profiles**: User management with department/team assignment
- **Activity Logs**: User activity tracking
- **Simple Authentication**: Flask-Login or Flask-Security

---

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Web Client    │  (Vanilla JavaScript, HTML, CSS)
│   (Browser)     │
└────────┬────────┘
         │ HTTP
         │
┌────────▼────────┐
│   Flask App     │  (Python)
│   (app.py)      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼──────────┐
│SQLite │ │File Storage │  (static/uploads/)
│Database│ └─────────────┘
└────────┘
```

### Project Structure

```
millpoint-qa/
├── app.py                  # Flask application and database helpers
├── requirements.txt        # Python dependencies
├── qa.db                  # SQLite database (auto-created)
├── seed_dev_db.py         # Seed script for development data
├── templates/
│   ├── index.html         # Main dashboard/homepage
│   ├── inspections.html   # Inspection management page
│   ├── ncr.html          # Non-conformance management page
│   ├── documents.html    # Document control page
│   └── admin.html        # Admin management page
└── static/
    ├── styles.css        # Application styles (CSS variables for theming)
    ├── app.js           # Main page JavaScript
    ├── inspections.js   # Inspection page JavaScript
    ├── ncr.js          # NCR page JavaScript
    └── uploads/         # File uploads directory
        ├── documents/   # Quality documents
        ├── photos/      # Inspection photos
        └── attachments/ # NCR attachments
```

### Database Schema (Key Entities)

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'admin', 'quality_manager', 'inspector', 'operator', 'viewer'
    department TEXT,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inspections table
CREATE TABLE inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_plan_id INTEGER,
    inspector_id INTEGER,
    product_id TEXT,
    batch_lot TEXT,
    status TEXT NOT NULL,  -- 'pending', 'in_progress', 'passed', 'failed', 'on_hold'
    inspection_date DATE,
    results TEXT,  -- JSON or TEXT field for inspection results
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inspector_id) REFERENCES users(id),
    FOREIGN KEY (inspection_plan_id) REFERENCES inspection_plans(id)
);

-- Inspection Plans table
CREATE TABLE inspection_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    product_id TEXT,
    checklist_template_id INTEGER,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Non-Conformances table
CREATE TABLE non_conformances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER,
    severity TEXT NOT NULL,  -- 'critical', 'major', 'minor'
    description TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'open', 'investigating', 'corrective_action', 'closed', 'rejected'
    root_cause TEXT,
    corrective_action_id INTEGER,
    assigned_to INTEGER,
    due_date DATE,
    closed_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inspection_id) REFERENCES inspections(id),
    FOREIGN KEY (corrective_action_id) REFERENCES corrective_actions(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id)
);

-- Corrective Actions table
CREATE TABLE corrective_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ncr_id INTEGER NOT NULL,
    assigned_to INTEGER,
    due_date DATE,
    status TEXT NOT NULL,  -- 'assigned', 'in_progress', 'completed', 'verified', 'rejected'
    action_description TEXT NOT NULL,
    verification_date DATE,
    verification_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ncr_id) REFERENCES non_conformances(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id)
);

-- Documents table
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    document_number TEXT UNIQUE NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'draft', 'pending_approval', 'approved', 'obsolete'
    file_path TEXT NOT NULL,
    approved_by INTEGER,
    effective_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (approved_by) REFERENCES users(id)
);

-- Equipment table
CREATE TABLE equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    serial_number TEXT UNIQUE,
    calibration_due_date DATE,
    status TEXT NOT NULL,  -- 'available', 'calibrated', 'out_of_service', 'calibration_due'
    last_calibration_date DATE,
    calibration_certificate_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit Logs table
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,  -- 'CREATE', 'UPDATE', 'DELETE'
    entity_type TEXT NOT NULL,  -- 'inspection', 'ncr', 'document', etc.
    entity_id INTEGER NOT NULL,
    changes TEXT,  -- JSON field for tracking what changed
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- File Attachments table
CREATE TABLE file_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,  -- 'inspection', 'ncr', 'document'
    entity_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,
    file_size INTEGER,
    uploaded_by INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

-- Indexes for performance
CREATE INDEX idx_inspections_status ON inspections(status);
CREATE INDEX idx_inspections_date ON inspections(inspection_date);
CREATE INDEX idx_ncr_status ON non_conformances(status);
CREATE INDEX idx_ncr_assigned_to ON non_conformances(assigned_to);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
```

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-3)
- [ ] Project setup and Flask application structure
- [ ] Database schema design and SQLite setup
- [ ] Basic authentication system (Flask-Login)
- [ ] User management (CRUD operations)
- [ ] Basic API endpoints structure
- [ ] Homepage/dashboard template
- [ ] CSS styling foundation with theme variables

### Phase 2: Inspection Management (Weeks 4-6)
- [ ] Inspection plan management (CRUD)
- [ ] Inspection execution forms
- [ ] Checklist templates
- [ ] Photo/document upload functionality
- [ ] Inspection results recording
- [ ] Inspection listing page with filtering
- [ ] Status update functionality (similar to rfq-tracker)

### Phase 3: Non-Conformance Management (Weeks 7-9)
- [ ] NCR creation and tracking
- [ ] Root cause analysis forms
- [ ] Corrective action assignment and tracking
- [ ] Action item management
- [ ] NCR workflow and status management
- [ ] NCR listing page with filters

### Phase 4: Document Control (Weeks 10-12)
- [ ] Document upload and storage
- [ ] Version control system
- [ ] Document approval workflow (simple)
- [ ] Document search and listing
- [ ] Document metadata management

### Phase 5: Reporting & Analytics (Weeks 13-15)
- [ ] Dashboard with key metrics
- [ ] Quality trend charts (Chart.js)
- [ ] CSV export functionality
- [ ] Print-friendly views (CSS print stylesheets)
- [ ] Basic reporting page

### Phase 6: Advanced Features (Weeks 16-18)
- [ ] Supplier quality management
- [ ] Equipment/calibration management
- [ ] Advanced filtering and search
- [ ] Activity log/audit trail display
- [ ] Mobile responsive improvements

### Phase 7: Testing & Deployment (Weeks 19-20)
- [ ] Unit tests with pytest
- [ ] Integration tests for API endpoints
- [ ] Code documentation (docstrings)
- [ ] Performance optimization (database indexes)
- [ ] Security review
- [ ] Production deployment setup (Gunicorn + Nginx)
- [ ] User documentation

---

## API Endpoints (Planned)

### Inspections
- `GET /api/inspections` - List inspections (with sorting, filtering, pagination)
- `POST /api/inspections` - Create new inspection
- `GET /api/inspections/<id>` - Get inspection details
- `PUT /api/inspections/<id>` - Update inspection
- `PATCH /api/inspections/<id>/status` - Update inspection status
- `DELETE /api/inspections/<id>` - Delete inspection

### Non-Conformances
- `GET /api/ncr` - List NCRs
- `POST /api/ncr` - Create new NCR
- `GET /api/ncr/<id>` - Get NCR details
- `PUT /api/ncr/<id>` - Update NCR
- `PATCH /api/ncr/<id>/status` - Update NCR status

### Documents
- `GET /api/documents` - List documents
- `POST /api/documents` - Upload new document
- `GET /api/documents/<id>` - Get document details
- `GET /api/documents/<id>/download` - Download document file

### Equipment
- `GET /api/equipment` - List equipment
- `POST /api/equipment` - Add new equipment
- `PUT /api/equipment/<id>` - Update equipment
- `PATCH /api/equipment/<id>/calibration` - Update calibration info

### Reports
- `GET /api/reports/metrics` - Get quality metrics
- `GET /api/reports/export` - Export data to CSV

---

## Key Considerations

### Data Migration
- Plan for importing existing quality data (spreadsheets)
- Simple CSV import scripts
- Data validation procedures

### Deployment
- Similar to rfq-tracker: Gunicorn + Nginx
- Systemd service for Linux
- NSSM or Task Scheduler for Windows
- Simple update script (like rfq-tracker's `update.sh`)

### Backup Strategy
- Regular SQLite database backups
- File uploads backup
- Simple backup script

### Security
- Input validation and sanitization
- SQL injection prevention (parameterized queries)
- CSRF protection
- File upload validation (file type, size limits)
- Secure password hashing (bcrypt)

### Performance
- Database indexes on frequently queried fields
- Pagination for large datasets
- Client-side filtering where appropriate
- Efficient file storage organization

---

## Success Metrics

- **Adoption Rate**: % of inspections conducted through the system
- **Time Savings**: Reduction in time spent on quality documentation
- **Data Quality**: Completeness and accuracy of quality records
- **Response Time**: Average time to resolve non-conformances
- **User Satisfaction**: User feedback and feature requests
- **Compliance**: Audit readiness and compliance score

---

## Open Questions & Decisions Needed

1. **Specific Industry Standards**: Which quality standards must we comply with?
2. **User Authentication**: Simple Flask-Login or more robust Flask-Security?
3. **File Storage**: Local filesystem sufficient, or need cloud storage?
4. **Mobile Requirements**: Responsive web app sufficient, or need native mobile?
5. **Offline Capability**: Do inspectors need offline access?
6. **Reporting Requirements**: What specific reports are needed?
7. **User Count**: Expected number of concurrent users?
8. **Data Retention**: How long should quality records be retained?
9. **Multi-site**: Single location or multiple manufacturing sites?

---

## Quick Wins (Easy to Implement)

These features could be implemented quickly:
1. ✅ Dark/Light theme toggle (CSS variables)
2. ✅ Print-friendly views (CSS print media queries)
3. ✅ Client-side search/filter (no backend changes needed)
4. ✅ Export to CSV (Python built-in `csv` module)
5. ✅ Status color-coding (similar to rfq-tracker)
6. ✅ Due date reminders (date comparison logic)

---

## Future Considerations

- Migration to PostgreSQL for better scalability (if needed)
- REST API versioning (if external integrations required)
- Docker containerization (for easier deployment)
- CI/CD pipeline (if team grows)
- Automated testing in deployment
- Email notifications (SMTP integration)
- Advanced analytics and reporting

---

## Next Steps

1. Review and refine this planning document with stakeholders
2. Answer open questions and make key decisions
3. Set up development environment and repository
4. Create initial Flask app structure
5. Design and implement database schema
6. Begin Phase 1 implementation

---

*Document Version: 1.0*  
*Last Updated: February 5, 2026*  
*Based on rfq-tracker architecture and design philosophy*
