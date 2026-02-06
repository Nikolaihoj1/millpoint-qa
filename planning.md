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

## Quality Control Workflow

The system follows a **workflow-based approach** tracking quality through the complete manufacturing cycle. Each job/PO progresses through defined stages with quality gates.

### Workflow Stages

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  1. PO      │───▶│ 2. Revision │───▶│ 3. Material │───▶│ 4. In-      │
│  Receipt    │    │    Check    │    │   Control   │    │   Process   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                               │
       ┌───────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 5. External │───▶│ 6. Exit     │───▶│ 7. Complete │
│   Process   │    │   Control   │    │   /Ship     │
│  (optional) │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘

   [Error/NCR can be raised at any stage with PO reference and images]
```

**Note:** External Process stage is optional - only used when parts are sent out for coating, plating, etc.

### Stage 1: PO Receipt
- **Purpose**: Log incoming production order, verify customer specs
- **Actions**: 
  - Record PO number, customer, part number, quantity
  - Attach customer drawings/specifications
  - Note any special requirements
- **Gate**: PO registered and ready for revision check

### Stage 2: Revision Check
- **Purpose**: Verify correct drawing revision before production starts
- **Actions**:
  - Compare customer-provided drawing revision with internal records
  - Confirm material specifications match
  - Check for any engineering change notices (ECN)
  - Sign-off that correct revision is being used
- **Gate**: Revision verified and approved to proceed

### Stage 3: Material Control (Incoming Inspection)
- **Purpose**: Verify raw material before production starts
- **Actions**:
  - Record material received (from stock or supplier delivery)
  - Verify material certificate/test report matches spec
  - Check material identification (heat number, batch, grade)
  - Visual inspection (surface condition, damage)
  - Dimensional check if applicable (bar stock diameter, plate thickness)
  - Upload material certificate/mill cert
  - Record supplier and batch/lot number
- **Gate**: Material approved for use in production
- **Traceability**: Link material batch to job for full traceability

### Stage 4: In-Process Quality Control
- **Purpose**: Monitor quality during manufacturing
- **Actions**:
  - **Measurement Reports**: Record dimensional measurements during production
    - Dimension name, nominal value, tolerance, actual measured value
    - Pass/fail determination
    - Measurement equipment used
  - **First Article Inspection (FAI)**: Detailed check of first piece
  - Periodic in-process checks
  - Upload photos of parts/measurements
- **Gate**: In-process measurements within tolerance

### Stage 5: External Process Control (Optional)
- **Purpose**: Quality control when parts return from subcontractors
- **Applies to**: Paint, powder coating, anodizing, plating, heat treatment, etc.
- **Actions**:
  - Record which external process was performed
  - Record supplier/subcontractor name
  - Verify coating thickness, color, adhesion (as applicable)
  - Visual inspection for defects, coverage, masking issues
  - Check certification/test reports from supplier
  - Upload supplier COC or test report
  - Pass/fail determination
- **Gate**: External process meets specification
- **Note**: Can have multiple external processes per job (e.g., machining → anodize → paint)

### Stage 6: Exit Control (Final Inspection)
- **Purpose**: Sample testing after all processing complete
- **Sampling Rule**: First 5 parts, then every 10th part after that
  - Example: 50 parts → inspect #1, 2, 3, 4, 5, 15, 25, 35, 45 (9 samples)
  - Example: 100 parts → inspect #1, 2, 3, 4, 5, 15, 25, 35, 45, 55, 65, 75, 85, 95 (14 samples)
- **Actions**:
  - System calculates required sample quantity based on lot size
  - Final dimensional inspection (against job dimensions)
  - Visual inspection checklist
  - Surface finish/cosmetic checks
  - Record pass/fail for each sample
- **Gate**: All samples pass exit control criteria

### Stage 7: Complete/Ship
- **Purpose**: Mark job complete and ready for delivery
- **Actions**:
  - Generate quality documentation (if required)
  - Certificate of Conformance (CoC)
  - Archive all quality records
- **Status**: Job closed

---

## Core Features

### 1. Job/PO Management
- **Job Registry**: Track all production jobs with PO reference
- **Customer Information**: Customer name, contact, requirements
- **Part Information**: Part number, description, quantity, due date
- **Drawing Management**: Upload and track drawing files with revision numbers
- **Status Tracking**: Visual workflow status (color-coded badges)
- **Job History**: Complete audit trail of all quality activities per job

### 2. Material Control (Incoming Inspection)
- **Material Receipt**: Log incoming material (from stock or supplier)
- **Material Details**:
  - Material type/grade (e.g., "SS316L", "Aluminium 6082-T6")
  - Supplier name
  - Batch/heat number for traceability
  - Quantity received
- **Certificate Upload**: Attach material certificate / mill test report
- **Verification Checks**:
  - Certificate matches specification
  - Visual inspection (damage, surface condition)
  - Dimensional check if applicable
- **Pass/Fail**: Approve material for production or reject
- **Traceability**: Link material batch to job

### 3. Measurement Reports

**Two-step process:**

#### Step 1: Define Critical Dimensions (when creating PO/Job)
- When a job is created, define which dimensions must be measured
- For each dimension specify:
  - Dimension name/ID (e.g., "Ø25 H7", "Length A", "Thread M8")
  - Nominal value
  - Tolerance (+/- or upper/lower limits)
  - Unit (mm, inch, degree)
  - Optional: reference to drawing (e.g., "See dim #3 on drawing")
- These become the **required measurements** for this job
- Can copy dimensions from a previous similar job (template feature)

#### Step 2: Record Measurements (during manufacturing)
- Inspectors see the list of required dimensions for the job
- For each dimension, record:
  - Actual measured value
  - Pass/Fail auto-calculated based on tolerance
  - Equipment used (optional)
  - Sample number (for multiple samples)
- **Report Types**:
  - First Article Inspection (FAI) - detailed check of first piece
  - In-Process - periodic checks during production
  - Final - last check before exit control
- **Photo Attachments**: Upload images of measurements/parts
- **Print-Friendly**: Generate measurement report PDFs/printouts
- **Progress Tracking**: See which dimensions have been measured vs pending

### 4. External Process Control
- **Process Types**: Paint, powder coating, anodizing, plating, heat treatment, etc.
- **Subcontractor Tracking**: Which supplier performed the process
- **Inspection Checks**:
  - Visual inspection (coverage, defects, masking)
  - Coating thickness measurement (if applicable)
  - Color verification
  - Adhesion test results
- **Documentation**: Upload supplier COC or test reports
- **Pass/Fail**: Accept or reject returned parts
- **Multiple Processes**: Support multiple external processes per job
- **Link to NCR**: Create error report if process fails inspection

### 5. Error Reports / Non-Conformance (NCR)
- **PO Link**: Every error report linked to specific PO/job
- **Description**: Detailed description of the issue
- **Image Upload**: Attach photos showing the defect/issue
- **Severity**: Critical, Major, Minor classification
- **Stage**: At which workflow stage the error was found
- **Root Cause**: Simple root cause documentation
- **Corrective Action**: What was done to fix it
- **Disposition**: Scrap, Rework, Use-As-Is, Return to Supplier
- **Status Tracking**: Open → Investigating → Resolved → Closed

### 6. Exit Control / Final Inspection
- **Sampling Rule**: First 5 parts + every 10th part after
  - Auto-calculated based on lot quantity
  - Shows which part numbers to inspect
- **Inspection Checklist**: 
  - Dimensional checks (against job dimensions)
  - Visual inspection
  - Surface finish/cosmetic checks
- **Per-Sample Recording**: Pass/fail for each inspected part
- **Overall Result**: Lot accepted/rejected based on all samples
- **Rejection Handling**: Link to NCR if sample fails

### 7. Revision Control
- **Drawing Registry**: Track all drawings with revision history
- **Revision Verification**: Sign-off that correct revision is used
- **Change Tracking**: Log when revisions change mid-production
- **Alert System**: Flag if drawing revision doesn't match customer PO

### 8. Supplier Management (Simple)
- **Supplier List**: Material suppliers and subcontractors
- **Supplier Type**: Raw material, external process, or both
- **Contact Info**: Name, contact person, email, phone
- **Process Capabilities**: What processes each subcontractor offers
- **Performance Notes**: Simple notes field for tracking quality history

### 9. Equipment & Calibration (Simple)
- **Equipment List**: Measurement tools (calipers, micrometers, CMM, etc.)
- **Calibration Status**: Due date, last calibration date
- **Status Indicator**: Green (OK), Yellow (Due Soon), Red (Overdue)
- **Link to Measurements**: Track which equipment was used

### 10. Dashboard & Reports
- **Job Overview**: All active jobs with workflow status
- **Overdue Items**: Jobs/inspections past due date
- **Error Summary**: Open NCRs, error trends
- **Material Pending**: Materials awaiting inspection
- **External Process Status**: Parts out for coating/treatment
- **Quality Metrics**: Pass rate, defect rate by period
- **Export**: CSV export for all data

### 11. User Management
- **Roles**: Admin, Quality Manager, Inspector, Operator
- **Activity Log**: Who did what, when
- **Simple Auth**: Username/password login

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
├── qa.db                   # SQLite database (auto-created)
├── seed_dev_db.py          # Seed script for development data
├── templates/
│   ├── base.html           # Base template with nav, theme toggle
│   ├── index.html          # Main dashboard
│   ├── login.html          # Login page
│   ├── jobs.html           # Job listing page
│   ├── job_detail.html     # Single job view with all related data
│   ├── job_form.html       # Create/edit job form
│   ├── material_control.html    # Material inspection form/view
│   ├── external_process.html    # External process form/view
│   ├── measurement_report.html  # Measurement report form/view
│   ├── error_report.html   # Error report form/view
│   ├── errors.html         # Error reports listing
│   ├── exit_control.html   # Exit control form/view
│   ├── suppliers.html      # Supplier management
│   ├── equipment.html      # Equipment/calibration list
│   └── admin.html          # User management
└── static/
    ├── styles.css          # Application styles (CSS variables for theming)
    ├── app.js              # Main/shared JavaScript
    ├── jobs.js             # Job listing page JS
    ├── job_detail.js       # Job detail page JS
    ├── measurements.js     # Measurement report JS
    ├── errors.js           # Error report JS
    └── uploads/            # File uploads directory
        ├── drawings/       # Customer drawings
        ├── photos/         # Measurement/defect photos
        ├── certificates/   # Material certs, supplier COCs
        └── documents/      # Other documents
```

### Database Schema (Key Entities)

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'admin', 'quality_manager', 'inspector', 'operator'
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customers table
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_person TEXT,
    email TEXT,
    phone TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Jobs table (central entity - represents a production order)
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT NOT NULL,           -- Customer PO number
    internal_job_number TEXT UNIQUE,   -- Internal reference (auto-generated)
    customer_id INTEGER,
    part_number TEXT NOT NULL,
    part_description TEXT,
    quantity INTEGER NOT NULL,
    due_date DATE,
    
    -- Workflow status
    workflow_stage TEXT NOT NULL DEFAULT 'po_receipt',  
    -- 'po_receipt', 'revision_check', 'material_control', 'in_process', 
    -- 'external_process', 'exit_control', 'complete', 'on_hold'
    
    -- Drawing/revision info
    drawing_number TEXT,
    drawing_revision TEXT,
    revision_verified INTEGER DEFAULT 0,  -- 0=not verified, 1=verified
    revision_verified_by INTEGER,
    revision_verified_at TIMESTAMP,
    
    -- Special requirements
    special_requirements TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (revision_verified_by) REFERENCES users(id)
);

-- Drawings/Documents attached to jobs
CREATE TABLE job_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,  -- 'drawing', 'specification', 'po', 'other'
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    revision TEXT,
    uploaded_by INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

-- Suppliers (material suppliers and subcontractors)
CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    supplier_type TEXT NOT NULL,  -- 'material', 'external_process', 'both'
    contact_person TEXT,
    email TEXT,
    phone TEXT,
    processes_offered TEXT,       -- For external process suppliers (comma-separated or JSON)
    notes TEXT,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Material Control (incoming material inspection)
CREATE TABLE material_controls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    inspector_id INTEGER,
    inspection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Material details
    material_type TEXT NOT NULL,      -- e.g., "SS316L", "Aluminium 6082-T6", "Steel 4140"
    supplier_id INTEGER,
    batch_number TEXT,                -- Heat number / lot number for traceability
    quantity_received TEXT,           -- e.g., "2 bars", "1 plate 500x300x20"
    
    -- Verification
    certificate_matches INTEGER DEFAULT 0,  -- Does cert match spec? 0=no, 1=yes
    visual_ok INTEGER DEFAULT 0,            -- Visual inspection passed? 0=no, 1=yes
    dimensions_ok INTEGER,                  -- Dimensional check (if applicable)
    
    -- Result
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (inspector_id) REFERENCES users(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- External Process Control (paint, anodizing, plating, etc.)
CREATE TABLE external_processes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    inspector_id INTEGER,
    
    -- Process details
    process_type TEXT NOT NULL,       -- 'paint', 'powder_coat', 'anodize', 'plate', 'heat_treat', 'other'
    process_description TEXT,         -- Specific details (e.g., "Red RAL 3000", "Clear anodize")
    supplier_id INTEGER,              -- Which subcontractor
    
    -- Dates
    sent_date DATE,                   -- When parts were sent out
    received_date DATE,               -- When parts returned
    inspection_date TIMESTAMP,
    
    -- Inspection results
    visual_ok INTEGER DEFAULT 0,      -- Visual inspection passed?
    thickness_ok INTEGER,             -- Coating thickness OK? (if applicable)
    color_ok INTEGER,                 -- Color matches spec? (if applicable)
    adhesion_ok INTEGER,              -- Adhesion test passed? (if applicable)
    
    -- Result
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'sent', 'received', 'inspecting', 'approved', 'rejected'
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (inspector_id) REFERENCES users(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- Job Dimensions (critical dimensions to be measured for each job)
-- Defined when job is created
CREATE TABLE job_dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    dimension_number INTEGER NOT NULL,  -- Sequence number (1, 2, 3...)
    dimension_name TEXT NOT NULL,       -- e.g., "Ø25 H7", "Length A", "Thread M8"
    nominal_value REAL NOT NULL,        -- Target value
    tolerance_plus REAL,                -- Upper tolerance (e.g., +0.02)
    tolerance_minus REAL,               -- Lower tolerance (e.g., -0.02)
    unit TEXT DEFAULT 'mm',             -- 'mm', 'inch', 'degree', etc.
    drawing_reference TEXT,             -- Optional: "See dim #3 on drawing"
    critical INTEGER DEFAULT 0,         -- Is this a critical dimension? 0=no, 1=yes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

-- Measurement Reports (in-process quality control)
CREATE TABLE measurement_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    report_type TEXT NOT NULL,  -- 'first_article', 'in_process', 'final'
    inspector_id INTEGER,
    inspection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    overall_status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'pass', 'fail'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (inspector_id) REFERENCES users(id)
);

-- Individual measurements within a report (references job_dimensions)
CREATE TABLE measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    job_dimension_id INTEGER NOT NULL,  -- Links to the pre-defined dimension
    actual_value REAL NOT NULL,         -- Measured value
    pass_fail TEXT,                     -- 'pass', 'fail' (auto-calculated)
    equipment_id INTEGER,               -- Which tool was used
    sample_number INTEGER DEFAULT 1,    -- For multiple samples of same dimension
    measured_by INTEGER,                -- Who took this measurement
    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (report_id) REFERENCES measurement_reports(id),
    FOREIGN KEY (job_dimension_id) REFERENCES job_dimensions(id),
    FOREIGN KEY (equipment_id) REFERENCES equipment(id),
    FOREIGN KEY (measured_by) REFERENCES users(id)
);

-- Exit Control / Final Inspection
CREATE TABLE exit_controls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    inspector_id INTEGER,
    inspection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Lot info
    lot_quantity INTEGER NOT NULL,      -- Total parts in lot
    -- Sample size auto-calculated: first 5 + every 10th after
    
    -- Overall result
    overall_status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'accepted', 'rejected'
    
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (inspector_id) REFERENCES users(id)
);

-- Exit Control Samples (individual part inspections)
CREATE TABLE exit_control_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exit_control_id INTEGER NOT NULL,
    part_number INTEGER NOT NULL,       -- Which part (1, 2, 3, 4, 5, 15, 25, etc.)
    
    -- Inspection results
    dimensions_ok INTEGER,              -- All dimensions pass? 0=no, 1=yes
    visual_ok INTEGER,                  -- Visual inspection pass? 0=no, 1=yes
    surface_ok INTEGER,                 -- Surface finish OK? 0=no, 1=yes
    
    overall_pass INTEGER,               -- This sample pass? 0=no, 1=yes
    notes TEXT,
    inspected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (exit_control_id) REFERENCES exit_controls(id)
);

-- Error Reports / Non-Conformances (NCR)
CREATE TABLE error_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,            -- Always linked to a job/PO
    reported_by INTEGER,
    
    -- When/where found
    workflow_stage TEXT NOT NULL,       -- At which stage error was found
    found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Error details
    severity TEXT NOT NULL,             -- 'critical', 'major', 'minor'
    description TEXT NOT NULL,          -- Detailed description of the issue
    affected_quantity INTEGER,          -- How many parts affected
    
    -- Disposition
    disposition TEXT,                   -- 'scrap', 'rework', 'use_as_is', 'return_supplier', 'pending'
    
    -- Root cause & corrective action
    root_cause TEXT,
    corrective_action TEXT,
    
    -- Status tracking
    status TEXT NOT NULL DEFAULT 'open',  -- 'open', 'investigating', 'resolved', 'closed'
    assigned_to INTEGER,
    resolved_date TIMESTAMP,
    closed_date TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (reported_by) REFERENCES users(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id)
);

-- File Attachments (for error reports, measurement reports, etc.)
CREATE TABLE attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,          -- 'error_report', 'measurement_report', 'exit_control', 'job'
    entity_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,                     -- 'image', 'pdf', 'other'
    uploaded_by INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

-- Equipment (measurement tools)
CREATE TABLE equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                 -- e.g., "Digital Caliper", "Micrometer 0-25mm"
    equipment_type TEXT,                -- 'caliper', 'micrometer', 'cmm', 'gauge', 'other'
    serial_number TEXT,
    manufacturer TEXT,
    
    -- Calibration info
    calibration_interval_days INTEGER DEFAULT 365,
    last_calibration_date DATE,
    calibration_due_date DATE,
    calibration_status TEXT DEFAULT 'ok',  -- 'ok', 'due_soon', 'overdue', 'out_of_service'
    
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit Logs (track all changes)
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,               -- 'create', 'update', 'delete', 'status_change'
    entity_type TEXT NOT NULL,          -- 'job', 'measurement_report', 'error_report', etc.
    entity_id INTEGER NOT NULL,
    description TEXT,                   -- Human-readable description
    changes TEXT,                       -- JSON of what changed
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes for performance
CREATE INDEX idx_jobs_workflow_stage ON jobs(workflow_stage);
CREATE INDEX idx_jobs_po_number ON jobs(po_number);
CREATE INDEX idx_jobs_due_date ON jobs(due_date);
CREATE INDEX idx_jobs_customer ON jobs(customer_id);
CREATE INDEX idx_job_dimensions_job ON job_dimensions(job_id);
CREATE INDEX idx_material_controls_job ON material_controls(job_id);
CREATE INDEX idx_material_controls_status ON material_controls(status);
CREATE INDEX idx_external_processes_job ON external_processes(job_id);
CREATE INDEX idx_external_processes_status ON external_processes(status);
CREATE INDEX idx_measurement_reports_job ON measurement_reports(job_id);
CREATE INDEX idx_measurements_dimension ON measurements(job_dimension_id);
CREATE INDEX idx_error_reports_job ON error_reports(job_id);
CREATE INDEX idx_error_reports_status ON error_reports(status);
CREATE INDEX idx_exit_controls_job ON exit_controls(job_id);
CREATE INDEX idx_exit_control_samples ON exit_control_samples(exit_control_id);
CREATE INDEX idx_attachments_entity ON attachments(entity_type, entity_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
```

---

## Implementation Phases

### Phase 1: Foundation
- [ ] Project setup and Flask application structure
- [ ] Database schema and SQLite setup
- [ ] Basic authentication (Flask-Login)
- [ ] User management (simple CRUD)
- [ ] CSS styling with theme variables (dark/light mode)
- [ ] Base templates and layout

### Phase 2: Job/PO Management (Core Workflow)
- [ ] Job creation form (PO number, customer, part info, quantity)
- [ ] **Define critical dimensions** when creating job:
  - Add dimension rows (name, nominal, tolerance +/-, unit)
  - Mark critical dimensions
  - Optional drawing reference
- [ ] Copy dimensions from previous job (template feature)
- [ ] Customer management (simple list)
- [ ] Job listing page with workflow status badges
- [ ] Job detail view (shows all related QC activities)
- [ ] Drawing/document upload to jobs
- [ ] Workflow stage progression (advance job through stages)
- [ ] Revision check sign-off functionality

### Phase 3: Material Control
- [ ] Supplier management (simple list with type: material/process/both)
- [ ] Material control form for a job
- [ ] Material details (type, supplier, batch number)
- [ ] Certificate upload (mill cert / material cert)
- [ ] Verification checklist (cert matches, visual OK, dimensions OK)
- [ ] Approve/reject material
- [ ] Material traceability link to job

### Phase 4: Measurement Reports
- [ ] Create measurement report for a job
- [ ] **Show pre-defined dimensions** from job setup
- [ ] Inspector enters actual measured values
- [ ] Auto-calculate pass/fail based on tolerance
- [ ] Multiple samples per dimension
- [ ] Progress indicator (X of Y dimensions measured)
- [ ] Report types: First Article, In-Process, Final
- [ ] Photo upload for measurements
- [ ] Print-friendly measurement report view
- [ ] Link measurements to equipment (optional)

### Phase 5: External Process Control
- [ ] External process record for a job
- [ ] Process type selection (paint, anodize, plate, heat treat, etc.)
- [ ] Subcontractor selection (from suppliers)
- [ ] Track sent/received dates
- [ ] Inspection checklist (visual, thickness, color, adhesion)
- [ ] Certificate/report upload from subcontractor
- [ ] Approve/reject returned parts
- [ ] Support multiple processes per job

### Phase 6: Error Reports (NCR)
- [ ] Create error report linked to job/PO
- [ ] Error description with severity
- [ ] Image upload for defect photos
- [ ] Disposition selection (scrap, rework, use-as-is, return to supplier)
- [ ] Root cause and corrective action fields
- [ ] Status workflow (open → investigating → resolved → closed)
- [ ] Error report listing with filters

### Phase 7: Exit Control / Final Inspection
- [ ] Exit control form for job
- [ ] Enter lot quantity → auto-calculate samples (first 5 + every 10th)
- [ ] Display which part numbers to inspect
- [ ] Per-sample inspection form (dimensions OK, visual OK, surface OK)
- [ ] Track progress (X of Y samples inspected)
- [ ] Overall lot accept/reject based on all samples
- [ ] Link to NCR if any sample fails

### Phase 8: Dashboard & Reports
- [ ] Main dashboard with:
  - Active jobs by workflow stage
  - Jobs due soon / overdue
  - Material awaiting inspection
  - Parts out for external process
  - Open error reports
  - Recent activity
- [ ] Quality metrics (pass rate, defect trends)
- [ ] Simple charts with Chart.js
- [ ] CSV export for jobs, measurements, errors

### Phase 9: Equipment & Calibration (Simple)
- [ ] Equipment list with calibration dates
- [ ] Calibration status indicator (OK/Due Soon/Overdue)
- [ ] Link equipment to measurements
- [ ] Calibration due alerts on dashboard

### Phase 10: Polish & Deploy
- [ ] Mobile responsive improvements
- [ ] Print stylesheets for reports
- [ ] Audit log viewing
- [ ] Basic pytest tests
- [ ] Production deployment (Gunicorn + Nginx)
- [ ] Backup script for database

---

## API Endpoints (Planned)

### Jobs/POs
- `GET /api/jobs` - List jobs (with filters: status, customer, date range)
- `POST /api/jobs` - Create new job (with dimensions array)
- `GET /api/jobs/<id>` - Get job details with all related data
- `PUT /api/jobs/<id>` - Update job
- `PATCH /api/jobs/<id>/stage` - Advance/change workflow stage
- `PATCH /api/jobs/<id>/revision-verify` - Mark revision as verified
- `DELETE /api/jobs/<id>` - Delete job (soft delete)

### Job Dimensions (critical measurements)
- `GET /api/jobs/<id>/dimensions` - Get dimensions for job
- `POST /api/jobs/<id>/dimensions` - Add dimension to job
- `PUT /api/dimensions/<id>` - Update dimension
- `DELETE /api/dimensions/<id>` - Delete dimension
- `POST /api/jobs/<id>/copy-dimensions/<source_job_id>` - Copy dimensions from another job

### Job Documents
- `POST /api/jobs/<id>/documents` - Upload document/drawing to job
- `GET /api/jobs/<id>/documents` - List documents for job
- `DELETE /api/documents/<id>` - Delete document

### Material Control
- `GET /api/jobs/<job_id>/material-control` - Get material control for job
- `POST /api/jobs/<job_id>/material-control` - Create material control record
- `PUT /api/material-control/<id>` - Update material control
- `PATCH /api/material-control/<id>/status` - Approve/reject material

### External Processes
- `GET /api/jobs/<job_id>/external-processes` - List external processes for job
- `POST /api/jobs/<job_id>/external-processes` - Create external process record
- `GET /api/external-processes/<id>` - Get external process details
- `PUT /api/external-processes/<id>` - Update external process
- `PATCH /api/external-processes/<id>/status` - Update status (sent/received/approved/rejected)

### Measurement Reports
- `GET /api/jobs/<job_id>/measurements` - List measurement reports for job
- `POST /api/jobs/<job_id>/measurements` - Create measurement report
- `GET /api/measurement-reports/<id>` - Get report with all measurements
- `PUT /api/measurement-reports/<id>` - Update report
- `POST /api/measurement-reports/<id>/measurements` - Add measurement to report
- `PUT /api/measurements/<id>` - Update individual measurement
- `DELETE /api/measurements/<id>` - Delete measurement

### Error Reports (NCR)
- `GET /api/errors` - List all error reports (with filters)
- `GET /api/jobs/<job_id>/errors` - List errors for specific job
- `POST /api/jobs/<job_id>/errors` - Create error report for job
- `GET /api/errors/<id>` - Get error report details
- `PUT /api/errors/<id>` - Update error report
- `PATCH /api/errors/<id>/status` - Update error status

### Exit Control
- `GET /api/jobs/<job_id>/exit-control` - Get exit control for job
- `POST /api/jobs/<job_id>/exit-control` - Create exit control record
- `PUT /api/exit-control/<id>` - Update exit control

### Attachments (Images/Files)
- `POST /api/attachments` - Upload file (with entity_type, entity_id)
- `GET /api/attachments/<id>` - Get/download attachment
- `DELETE /api/attachments/<id>` - Delete attachment

### Suppliers
- `GET /api/suppliers` - List suppliers (filter by type: material/external_process)
- `POST /api/suppliers` - Add supplier
- `PUT /api/suppliers/<id>` - Update supplier
- `DELETE /api/suppliers/<id>` - Deactivate supplier

### Equipment
- `GET /api/equipment` - List equipment
- `POST /api/equipment` - Add equipment
- `PUT /api/equipment/<id>` - Update equipment
- `GET /api/equipment/due-calibration` - Get equipment due for calibration

### Customers
- `GET /api/customers` - List customers
- `POST /api/customers` - Add customer
- `PUT /api/customers/<id>` - Update customer

### Dashboard/Reports
- `GET /api/dashboard/stats` - Get dashboard statistics
- `GET /api/reports/export/jobs` - Export jobs to CSV
- `GET /api/reports/export/errors` - Export errors to CSV

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

### Clarified ✓
- **Core Workflow**: PO Receipt → Revision Check → Material Control → In-Process → External Process → Exit Control → Complete
- **Key Features**: Measurement reports, Error reports with images, PO-linked workflow
- **Material Control**: Incoming inspection for raw materials with certificate verification
- **External Process**: QC for paint, anodizing, plating, heat treatment, etc.
- **Measurement Dimensions**: Defined per job when PO is created; inspectors measure against these pre-defined dimensions
- **Exit Control Sampling**: First 5 parts + every 10th part after that
- **Tech Stack**: Flask + SQLite + Vanilla JS (same as rfq-tracker)

### Still to Decide
1. **User Roles**: How many people will use this? What access levels needed?
2. **Certificate of Conformance**: Need to generate CoC documents automatically?
3. **Notifications**: Email alerts for overdue items, or just dashboard warnings?
4. **Integration**: Any need to import data from ERP or other systems?
5. **Multi-site**: Single facility or multiple locations?

---

## Quick Wins (Easy to Implement)

These features can be implemented quickly:
1. ✅ Dark/Light theme toggle (CSS variables)
2. ✅ Print-friendly measurement reports (CSS print media queries)
3. ✅ Client-side search/filter on job list
4. ✅ Export to CSV (Python built-in `csv` module)
5. ✅ Workflow status color-coding (like rfq-tracker)
6. ✅ Due date highlighting (overdue = red, due soon = yellow)
7. ✅ Pass/fail auto-calculation for measurements

---

## Future Considerations

- Migration to PostgreSQL for better scalability (if needed)
- Automatic Certificate of Conformance (CoC) generation
- Email notifications for overdue items
- Import from ERP/spreadsheets
- Docker containerization
- Barcode/QR code scanning for job lookup
- Statistical Process Control (SPC) charts

---

## Next Steps

1. ~~Review and clarify core workflow~~ ✓
2. Answer remaining open questions
3. **Start Phase 1**: Set up Flask app structure
4. Implement database schema
5. Build job/PO management first (core of the system)
6. Add measurement reports
7. Add error reports with image upload

---

*Document Version: 1.4*  
*Last Updated: February 6, 2026*  
*Based on rfq-tracker architecture and design philosophy*
