"""
Millpoint QC - Ravnsgaard Metal A/S
Flask application with SQLite database
"""

import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, g, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['DATABASE'] = os.path.join(app.root_path, 'qa.db')

# Upload configuration
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Ensure upload directories exist
for subdir in ['drawings', 'photos', 'certificates', 'documents']:
    os.makedirs(os.path.join(UPLOAD_FOLDER, subdir), exist_ok=True)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Log ind for at få adgang til denne side.'


# =============================================================================
# Database Helpers
# =============================================================================

def get_db():
    """Get database connection for current request."""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Close database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


app.teardown_appcontext(close_db)


def query_db(query, args=(), one=False):
    """Query database and return results."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """Execute a database command (insert, update, delete)."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    lastrowid = cur.lastrowid
    cur.close()
    return lastrowid


def get_or_create_part(part_number, part_revision='', part_description=None):
    """Get existing part or create new one. Returns (part_id, was_created)."""
    # Normalize: treat empty string and None as same for revision
    part_revision = part_revision or ''
    
    # Try to find existing part
    existing = query_db(
        'SELECT id FROM parts WHERE part_number = ? AND part_revision = ?',
        [part_number, part_revision],
        one=True
    )
    
    if existing:
        # Update description if provided and different
        if part_description:
            execute_db(
                'UPDATE parts SET part_description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                [part_description, existing['id']]
            )
        return (existing['id'], False)
    
    # Create new part
    part_id = execute_db(
        'INSERT INTO parts (part_number, part_revision, part_description) VALUES (?, ?, ?)',
        [part_number, part_revision, part_description]
    )
    return (part_id, True)


# =============================================================================
# Database Schema
# =============================================================================

def init_db():
    """Initialize database with schema."""
    db = get_db()
    
    # Users table
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'operator',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Customers table
    db.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Suppliers table (material suppliers and subcontractors)
    db.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            supplier_type TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            processes_offered TEXT,
            notes TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Jobs table (central entity)
    db.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL,
            part_revision TEXT NOT NULL DEFAULT '',
            part_description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(part_number, part_revision)
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT NOT NULL,
            internal_job_number TEXT UNIQUE,
            customer_id INTEGER,
            part_id INTEGER,
            part_number TEXT NOT NULL,
            part_revision TEXT,
            part_description TEXT,
            quantity INTEGER NOT NULL,
            due_date DATE,
            workflow_stage TEXT NOT NULL DEFAULT 'po_receipt',
            drawing_number TEXT,
            revision_verified INTEGER DEFAULT 0,
            revision_verified_by INTEGER,
            revision_verified_at TIMESTAMP,
            special_requirements TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (part_id) REFERENCES parts(id),
            FOREIGN KEY (revision_verified_by) REFERENCES users(id)
        )
    ''')
    
    # Job Documents
    db.execute('''
        CREATE TABLE IF NOT EXISTS job_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            revision TEXT,
            uploaded_by INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        )
    ''')
    
    # Job Dimensions (critical dimensions to measure)
    db.execute('''
        CREATE TABLE IF NOT EXISTS job_dimensions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            dimension_number INTEGER NOT NULL,
            dimension_name TEXT NOT NULL,
            nominal_value REAL NOT NULL,
            tolerance_plus REAL,
            tolerance_minus REAL,
            unit TEXT DEFAULT 'mm',
            drawing_reference TEXT,
            critical INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    ''')
    
    # Material Controls (incoming inspection)
    db.execute('''
        CREATE TABLE IF NOT EXISTS material_controls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            inspector_id INTEGER,
            inspection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            material_type TEXT NOT NULL,
            supplier_id INTEGER,
            batch_number TEXT,
            quantity_received TEXT,
            certificate_matches INTEGER DEFAULT 0,
            visual_ok INTEGER DEFAULT 0,
            dimensions_ok INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (inspector_id) REFERENCES users(id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    ''')
    
    # External Processes (paint, anodizing, etc.)
    db.execute('''
        CREATE TABLE IF NOT EXISTS external_processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            inspector_id INTEGER,
            process_type TEXT NOT NULL,
            process_description TEXT,
            supplier_id INTEGER,
            sent_date DATE,
            received_date DATE,
            inspection_date TIMESTAMP,
            visual_ok INTEGER DEFAULT 0,
            thickness_ok INTEGER,
            color_ok INTEGER,
            adhesion_ok INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (inspector_id) REFERENCES users(id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    ''')
    
    # Measurement Reports
    db.execute('''
        CREATE TABLE IF NOT EXISTS measurement_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            report_type TEXT NOT NULL,
            inspector_id INTEGER,
            inspection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            overall_status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (inspector_id) REFERENCES users(id)
        )
    ''')
    
    # Individual Measurements
    db.execute('''
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            job_dimension_id INTEGER NOT NULL,
            actual_value REAL NOT NULL,
            pass_fail TEXT,
            equipment_id INTEGER,
            sample_number INTEGER DEFAULT 1,
            measured_by INTEGER,
            measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (report_id) REFERENCES measurement_reports(id),
            FOREIGN KEY (job_dimension_id) REFERENCES job_dimensions(id),
            FOREIGN KEY (equipment_id) REFERENCES equipment(id),
            FOREIGN KEY (measured_by) REFERENCES users(id)
        )
    ''')
    
    # Exit Controls
    db.execute('''
        CREATE TABLE IF NOT EXISTS exit_controls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            inspector_id INTEGER,
            inspection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            lot_quantity INTEGER NOT NULL,
            overall_status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (inspector_id) REFERENCES users(id)
        )
    ''')
    
    # Exit Control Samples
    db.execute('''
        CREATE TABLE IF NOT EXISTS exit_control_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exit_control_id INTEGER NOT NULL,
            part_number INTEGER NOT NULL,
            dimensions_ok INTEGER,
            visual_ok INTEGER,
            surface_ok INTEGER,
            overall_pass INTEGER,
            notes TEXT,
            inspected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exit_control_id) REFERENCES exit_controls(id)
        )
    ''')
    
    # Error Reports (NCR)
    db.execute('''
        CREATE TABLE IF NOT EXISTS error_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            reported_by INTEGER,
            workflow_stage TEXT NOT NULL,
            found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            affected_quantity INTEGER,
            disposition TEXT,
            root_cause TEXT,
            corrective_action TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            assigned_to INTEGER,
            resolved_date TIMESTAMP,
            closed_date TIMESTAMP,
            error_type TEXT DEFAULT 'internal',
            supplier_id INTEGER,
            material_control_id INTEGER,
            external_process_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (reported_by) REFERENCES users(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY (material_control_id) REFERENCES material_controls(id),
            FOREIGN KEY (external_process_id) REFERENCES external_processes(id)
        )
    ''')
    
    # Add columns to existing error_reports table if they don't exist (migration)
    try:
        db.execute('ALTER TABLE error_reports ADD COLUMN error_type TEXT DEFAULT "internal"')
    except:
        pass
    try:
        db.execute('ALTER TABLE error_reports ADD COLUMN supplier_id INTEGER')
    except:
        pass
    try:
        db.execute('ALTER TABLE error_reports ADD COLUMN material_control_id INTEGER')
    except:
        pass
    try:
        db.execute('ALTER TABLE error_reports ADD COLUMN external_process_id INTEGER')
    except:
        pass
    
    # Add part_revision to jobs table if it doesn't exist (migration)
    try:
        db.execute('ALTER TABLE jobs ADD COLUMN part_revision TEXT')
    except:
        pass
    
    # Add part_id to jobs table if it doesn't exist (migration)
    try:
        db.execute('ALTER TABLE jobs ADD COLUMN part_id INTEGER REFERENCES parts(id)')
    except:
        pass
    
    # Migrate existing jobs to use parts table
    try:
        # Get all jobs without part_id
        jobs_without_part = db.execute('''
            SELECT DISTINCT part_number, part_revision FROM jobs 
            WHERE part_id IS NULL AND part_number IS NOT NULL AND part_number != ''
        ''').fetchall()
        
        for job_row in jobs_without_part:
            part_number = job_row[0]
            part_revision = job_row[1] or ''
            
            # Get or create part
            part = db.execute('''
                SELECT id FROM parts WHERE part_number = ? AND part_revision = ?
            ''', [part_number, part_revision]).fetchone()
            
            if part:
                part_id = part[0]
            else:
                # Create part
                cursor = db.execute('''
                    INSERT INTO parts (part_number, part_revision) VALUES (?, ?)
                ''', [part_number, part_revision])
                part_id = cursor.lastrowid
            
            # Update all jobs with this part_number/revision
            db.execute('''
                UPDATE jobs SET part_id = ? 
                WHERE part_number = ? AND (part_revision = ? OR (part_revision IS NULL AND ? = ''))
            ''', [part_id, part_number, part_revision, part_revision])
        
        db.commit()
    except Exception as e:
        # Migration failed, but continue
        print(f"Migration warning: {e}")
        pass

    # Attachments
    db.execute('''
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT,
            uploaded_by INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        )
    ''')
    
    # Equipment
    db.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            equipment_type TEXT,
            serial_number TEXT,
            manufacturer TEXT,
            calibration_interval_days INTEGER DEFAULT 365,
            last_calibration_date DATE,
            calibration_due_date DATE,
            calibration_status TEXT DEFAULT 'ok',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Audit Logs
    db.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            description TEXT,
            changes TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Notifications
    db.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            entity_type TEXT,
            entity_id INTEGER,
            read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create indexes
    db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_workflow_stage ON jobs(workflow_stage)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_po_number ON jobs(po_number)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_due_date ON jobs(due_date)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_customer ON jobs(customer_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_job_dimensions_job ON job_dimensions(job_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_material_controls_job ON material_controls(job_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_external_processes_job ON external_processes(job_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_measurement_reports_job ON measurement_reports(job_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_measurements_dimension ON measurements(job_dimension_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_error_reports_job ON error_reports(job_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_error_reports_status ON error_reports(status)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_error_reports_supplier ON error_reports(supplier_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(user_id, read)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_parts_number_revision ON parts(part_number, part_revision)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_part ON jobs(part_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_exit_controls_job ON exit_controls(job_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_attachments_entity ON attachments(entity_type, entity_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id)')
    
    db.commit()


# =============================================================================
# User Model for Flask-Login
# =============================================================================

class User(UserMixin):
    def __init__(self, id, username, email, role, active):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.active = active
    
    @staticmethod
    def get(user_id):
        user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)
        if user:
            return User(user['id'], user['username'], user['email'], user['role'], user['active'])
        return None
    
    @staticmethod
    def get_by_username(username):
        user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        if user:
            return user
        return None


@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))


# =============================================================================
# Authentication Routes
# =============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.get_by_username(username)
        
        if user and check_password_hash(user['password_hash'], password):
            if user['active']:
                user_obj = User(user['id'], user['username'], user['email'], user['role'], user['active'])
                login_user(user_obj)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                flash('Din konto er inaktiv. Kontakt en administrator.', 'error')
        else:
            flash('Forkert brugernavn eller adgangskode.', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Du er nu logget ud.', 'info')
    return redirect(url_for('login'))


# =============================================================================
# Role-based Access Control
# =============================================================================

def role_required(*roles):
    """Decorator to require specific roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.role not in roles:
                flash('Du har ikke tilladelse til at åbne denne side.', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# =============================================================================
# Main Routes
# =============================================================================

@app.route('/')
@login_required
def index():
    """Main dashboard."""
    # Job counts by stage
    stage_counts = {
        'po_receipt': query_db("SELECT COUNT(*) as count FROM jobs WHERE workflow_stage = 'po_receipt'", one=True)['count'],
        'revision_check': query_db("SELECT COUNT(*) as count FROM jobs WHERE workflow_stage = 'revision_check'", one=True)['count'],
        'material_control': query_db("SELECT COUNT(*) as count FROM jobs WHERE workflow_stage = 'material_control'", one=True)['count'],
        'in_process': query_db("SELECT COUNT(*) as count FROM jobs WHERE workflow_stage = 'in_process'", one=True)['count'],
        'external_process': query_db("SELECT COUNT(*) as count FROM jobs WHERE workflow_stage = 'external_process'", one=True)['count'],
        'exit_control': query_db("SELECT COUNT(*) as count FROM jobs WHERE workflow_stage = 'exit_control'", one=True)['count'],
        'complete': query_db("SELECT COUNT(*) as count FROM jobs WHERE workflow_stage = 'complete'", one=True)['count'],
    }
    
    # Key metrics
    stats = {
        'active_jobs': query_db("SELECT COUNT(*) as count FROM jobs WHERE workflow_stage != 'complete'", one=True)['count'],
        'completed_jobs': stage_counts['complete'],
        'overdue_count': query_db("SELECT COUNT(*) as count FROM jobs WHERE due_date < date('now') AND workflow_stage != 'complete'", one=True)['count'],
        'open_errors': query_db("SELECT COUNT(*) as count FROM error_reports WHERE status = 'open'", one=True)['count'],
        'pending_material': query_db("SELECT COUNT(*) as count FROM material_controls WHERE status = 'pending'", one=True)['count'],
        'pending_external': query_db("SELECT COUNT(*) as count FROM external_processes WHERE status IN ('sent', 'received')", one=True)['count'],
    }
    
    # Quality metrics (last 30 days)
    quality_stats = query_db('''
        SELECT 
            (SELECT COUNT(*) FROM error_reports WHERE found_date >= date('now', '-30 days')) as errors_30d,
            (SELECT COUNT(*) FROM error_reports WHERE found_date >= date('now', '-30 days') AND error_type = 'material_supplier') as material_errors_30d,
            (SELECT COUNT(*) FROM error_reports WHERE found_date >= date('now', '-30 days') AND error_type = 'external_supplier') as external_errors_30d,
            (SELECT COUNT(*) FROM exit_controls WHERE inspection_date >= date('now', '-30 days') AND overall_status = 'passed') as exit_passed_30d,
            (SELECT COUNT(*) FROM exit_controls WHERE inspection_date >= date('now', '-30 days') AND overall_status = 'failed') as exit_failed_30d,
            (SELECT COUNT(*) FROM jobs WHERE completed_at >= date('now', '-30 days')) as completed_30d
    ''', one=True)
    
    # Jobs completed per week (last 8 weeks) for chart
    weekly_completions = query_db('''
        SELECT 
            strftime('%Y-%W', completed_at) as week,
            COUNT(*) as count
        FROM jobs 
        WHERE completed_at >= date('now', '-56 days') AND workflow_stage = 'complete'
        GROUP BY week
        ORDER BY week
    ''')
    
    # Errors by type for chart
    errors_by_type_rows = query_db('''
        SELECT 
            COALESCE(error_type, 'internal') as error_type,
            COUNT(*) as count
        FROM error_reports
        WHERE found_date >= date('now', '-90 days')
        GROUP BY error_type
    ''')
    # Convert to list of dicts for JSON serialization
    errors_by_type = [{'error_type': row['error_type'], 'count': row['count']} for row in errors_by_type_rows]
    
    # Top suppliers with issues
    problem_suppliers = query_db('''
        SELECT s.name, s.supplier_type, COUNT(er.id) as error_count,
               SUM(CASE WHEN er.status = 'open' THEN 1 ELSE 0 END) as open_count
        FROM error_reports er
        JOIN suppliers s ON er.supplier_id = s.id
        WHERE er.found_date >= date('now', '-90 days')
        GROUP BY s.id
        ORDER BY error_count DESC
        LIMIT 5
    ''')
    
    # Equipment calibration alerts
    equipment_alerts_rows = query_db('''
        SELECT id, name, equipment_type, calibration_due_date,
            CASE 
                WHEN calibration_due_date IS NULL THEN 'ok'
                WHEN calibration_due_date < date('now') THEN 'overdue'
                ELSE 'due_soon'
            END as status
        FROM equipment
        WHERE active = 1 
          AND (calibration_due_date IS NULL OR calibration_due_date <= date('now', '+30 days'))
        ORDER BY 
            CASE 
                WHEN calibration_due_date IS NULL THEN 1
                ELSE 0
            END,
            calibration_due_date ASC
        LIMIT 5
    ''')
    equipment_alerts = equipment_alerts_rows if equipment_alerts_rows else []
    
    # Get recent jobs
    recent_jobs = query_db('''
        SELECT j.*, c.name as customer_name 
        FROM jobs j 
        LEFT JOIN customers c ON j.customer_id = c.id 
        ORDER BY j.created_at DESC 
        LIMIT 8
    ''')
    
    # Get overdue jobs
    overdue_jobs = query_db('''
        SELECT j.*, c.name as customer_name 
        FROM jobs j 
        LEFT JOIN customers c ON j.customer_id = c.id 
        WHERE j.due_date < date('now') AND j.workflow_stage != 'complete'
        ORDER BY j.due_date ASC
        LIMIT 5
    ''')
    
    # Get open error reports
    open_errors = query_db('''
        SELECT e.*, j.po_number, j.part_number, s.name as supplier_name
        FROM error_reports e 
        JOIN jobs j ON e.job_id = j.id 
        LEFT JOIN suppliers s ON e.supplier_id = s.id
        WHERE e.status = 'open'
        ORDER BY e.found_date DESC
        LIMIT 5
    ''')
    
    return render_template('index.html', 
                          stats=stats,
                          stage_counts=stage_counts,
                          quality_stats=quality_stats,
                          weekly_completions=weekly_completions,
                          errors_by_type=errors_by_type,
                          problem_suppliers=problem_suppliers,
                          equipment_alerts=equipment_alerts,
                          recent_jobs=recent_jobs,
                          overdue_jobs=overdue_jobs,
                          open_errors=open_errors)


# =============================================================================
# Reports Routes
# =============================================================================

@app.route('/reports')
@login_required
def reports():
    """Reports and analytics page."""
    # Date range from query params (default last 30 days)
    from_date = request.args.get('from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    to_date = request.args.get('to', datetime.now().strftime('%Y-%m-%d'))
    
    # Job completion stats
    job_stats = query_db('''
        SELECT 
            COUNT(*) as total_completed,
            SUM(quantity) as total_parts
        FROM jobs
        WHERE completed_at BETWEEN ? AND date(?, '+1 day')
    ''', [from_date, to_date], one=True)
    
    # Error stats
    error_stats = query_db('''
        SELECT 
            COUNT(*) as total_errors,
            SUM(CASE WHEN error_type = 'material_supplier' THEN 1 ELSE 0 END) as material_errors,
            SUM(CASE WHEN error_type = 'external_supplier' THEN 1 ELSE 0 END) as external_errors,
            SUM(CASE WHEN error_type = 'internal' OR error_type IS NULL THEN 1 ELSE 0 END) as internal_errors,
            SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical_errors,
            SUM(CASE WHEN severity = 'major' THEN 1 ELSE 0 END) as major_errors,
            SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_errors
        FROM error_reports
        WHERE found_date BETWEEN ? AND date(?, '+1 day')
    ''', [from_date, to_date], one=True)
    
    # Exit control stats
    exit_stats = query_db('''
        SELECT 
            COUNT(*) as total_inspections,
            SUM(CASE WHEN overall_status = 'passed' THEN 1 ELSE 0 END) as passed,
            SUM(CASE WHEN overall_status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM exit_controls
        WHERE inspection_date BETWEEN ? AND date(?, '+1 day')
    ''', [from_date, to_date], one=True)
    
    # Top parts with errors
    parts_with_errors = query_db('''
        SELECT j.part_number, j.part_revision, COUNT(er.id) as error_count
        FROM error_reports er
        JOIN jobs j ON er.job_id = j.id
        WHERE er.found_date BETWEEN ? AND date(?, '+1 day')
        GROUP BY j.part_number, j.part_revision
        ORDER BY error_count DESC
        LIMIT 10
    ''', [from_date, to_date])
    
    # Supplier performance
    supplier_performance = query_db('''
        SELECT s.name, s.supplier_type,
               COUNT(er.id) as error_count,
               SUM(CASE WHEN er.severity = 'critical' THEN 1 ELSE 0 END) as critical_count
        FROM suppliers s
        LEFT JOIN error_reports er ON er.supplier_id = s.id 
            AND er.found_date BETWEEN ? AND date(?, '+1 day')
        WHERE s.active = 1
        GROUP BY s.id
        ORDER BY error_count DESC
    ''', [from_date, to_date])
    
    # Jobs by customer
    jobs_by_customer = query_db('''
        SELECT c.name, COUNT(j.id) as job_count, SUM(j.quantity) as total_qty
        FROM jobs j
        JOIN customers c ON j.customer_id = c.id
        WHERE j.created_at BETWEEN ? AND date(?, '+1 day')
        GROUP BY c.id
        ORDER BY job_count DESC
    ''', [from_date, to_date])
    
    return render_template('reports.html',
                          from_date=from_date, to_date=to_date,
                          job_stats=job_stats, error_stats=error_stats,
                          exit_stats=exit_stats, parts_with_errors=parts_with_errors,
                          supplier_performance=supplier_performance,
                          jobs_by_customer=jobs_by_customer)


@app.route('/reports/export/jobs')
@login_required
def export_jobs_csv():
    """Export jobs to CSV."""
    from_date = request.args.get('from', '2000-01-01')
    to_date = request.args.get('to', '2099-12-31')
    
    jobs = query_db('''
        SELECT j.internal_job_number, j.po_number, j.part_number, j.part_revision,
               j.quantity, j.due_date, j.workflow_stage, j.created_at, j.completed_at,
               c.name as customer_name
        FROM jobs j
        LEFT JOIN customers c ON j.customer_id = c.id
        WHERE j.created_at BETWEEN ? AND date(?, '+1 day')
        ORDER BY j.created_at DESC
    ''', [from_date, to_date])
    
    # Generate CSV
    import io
    output = io.StringIO()
    output.write('Job Number,PO Number,Part Number,Revision,Quantity,Due Date,Stage,Created,Completed,Customer\n')
    
    for job in jobs:
        row = [
            job['internal_job_number'] or '',
            job['po_number'] or '',
            job['part_number'] or '',
            job['part_revision'] or '',
            str(job['quantity'] or ''),
            job['due_date'] or '',
            job['workflow_stage'] or '',
            (job['created_at'] or '')[:10],
            (job['completed_at'] or '')[:10] if job['completed_at'] else '',
            job['customer_name'] or ''
        ]
        output.write(','.join(f'"{v}"' for v in row) + '\n')
    
    response = app.response_class(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=jobs_{from_date}_to_{to_date}.csv'}
    )
    return response


@app.route('/reports/export/errors')
@login_required
def export_errors_csv():
    """Export error reports to CSV."""
    from_date = request.args.get('from', '2000-01-01')
    to_date = request.args.get('to', '2099-12-31')
    
    errors = query_db('''
        SELECT er.id, er.found_date, er.severity, er.error_type, er.status,
               er.description, er.disposition, er.root_cause, er.corrective_action,
               j.internal_job_number, j.part_number, j.part_revision,
               s.name as supplier_name
        FROM error_reports er
        JOIN jobs j ON er.job_id = j.id
        LEFT JOIN suppliers s ON er.supplier_id = s.id
        WHERE er.found_date BETWEEN ? AND date(?, '+1 day')
        ORDER BY er.found_date DESC
    ''', [from_date, to_date])
    
    import io
    output = io.StringIO()
    output.write('ID,Date,Job,Part,Revision,Supplier,Type,Severity,Status,Description,Disposition,Root Cause,Corrective Action\n')
    
    for err in errors:
        row = [
            f'ER-{err["id"]:04d}',
            (err['found_date'] or '')[:10],
            err['internal_job_number'] or '',
            err['part_number'] or '',
            err['part_revision'] or '',
            err['supplier_name'] or 'Internal',
            (err['error_type'] or 'internal').replace('_', ' ').title(),
            err['severity'] or '',
            err['status'] or '',
            (err['description'] or '').replace('"', "'").replace('\n', ' ')[:100],
            err['disposition'] or '',
            (err['root_cause'] or '').replace('"', "'").replace('\n', ' ')[:100],
            (err['corrective_action'] or '').replace('"', "'").replace('\n', ' ')[:100]
        ]
        output.write(','.join(f'"{v}"' for v in row) + '\n')
    
    response = app.response_class(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=errors_{from_date}_to_{to_date}.csv'}
    )
    return response


# =============================================================================
# Equipment Routes
# =============================================================================

@app.route('/equipment')
@login_required
def equipment_list():
    """List all equipment with calibration status."""
    equipment = query_db('''
        SELECT *,
            CASE 
                WHEN calibration_due_date IS NULL THEN 'ok'
                WHEN calibration_due_date < date('now') THEN 'overdue'
                WHEN calibration_due_date <= date('now', '+30 days') THEN 'due_soon'
                ELSE 'ok'
            END as cal_status
        FROM equipment
        WHERE active = 1
        ORDER BY 
            CASE 
                WHEN calibration_due_date IS NULL THEN 1
                ELSE 0
            END,
            calibration_due_date ASC
    ''')
    
    # Stats
    stats = {
        'total': len(equipment),
        'overdue': sum(1 for e in equipment if e['cal_status'] == 'overdue'),
        'due_soon': sum(1 for e in equipment if e['cal_status'] == 'due_soon'),
        'ok': sum(1 for e in equipment if e['cal_status'] == 'ok')
    }
    
    return render_template('equipment.html', equipment=equipment, stats=stats, mode='list')


@app.route('/equipment/create', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'quality_manager'])
def equipment_create():
    """Create new equipment."""
    if request.method == 'POST':
        name = request.form.get('name')
        equipment_type = request.form.get('equipment_type')
        serial_number = request.form.get('serial_number')
        manufacturer = request.form.get('manufacturer')
        calibration_interval = int(request.form.get('calibration_interval', 365))
        last_calibration = request.form.get('last_calibration_date')
        
        # Calculate due date
        if last_calibration:
            due_date = query_db(
                "SELECT date(?, '+' || ? || ' days') as due",
                [last_calibration, calibration_interval], one=True
            )['due']
        else:
            due_date = None
        
        db = get_db()
        cursor = db.execute('''
            INSERT INTO equipment (name, equipment_type, serial_number, manufacturer,
                                  calibration_interval_days, last_calibration_date, calibration_due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', [name, equipment_type, serial_number, manufacturer, calibration_interval, last_calibration, due_date])
        db.commit()
        
        flash(f'Udstyr "{name}" oprettet.', 'success')
        return redirect(url_for('equipment_detail', equip_id=cursor.lastrowid))
    
    return render_template('equipment.html', mode='create')


@app.route('/equipment/<int:equip_id>')
@login_required
def equipment_detail(equip_id):
    """View equipment details and calibration history."""
    equipment = query_db('SELECT * FROM equipment WHERE id = ?', [equip_id], one=True)
    if not equipment:
        flash('Udstyr blev ikke fundet.', 'error')
        return redirect(url_for('equipment_list'))
    
    # Get measurement reports using this equipment (via measurements table)
    reports = query_db('''
        SELECT DISTINCT mr.*, j.internal_job_number, j.part_number
        FROM measurement_reports mr
        JOIN jobs j ON mr.job_id = j.id
        JOIN measurements m ON m.report_id = mr.id
        WHERE m.equipment_id = ?
        ORDER BY mr.created_at DESC
        LIMIT 20
    ''', [equip_id])
    
    # Calculate status
    cal_status = 'ok'
    if equipment['calibration_due_date']:
        due = equipment['calibration_due_date']
        today = datetime.now().strftime('%Y-%m-%d')
        if due < today:
            cal_status = 'overdue'
        elif due <= (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'):
            cal_status = 'due_soon'
    
    return render_template('equipment.html', equipment=equipment, reports=reports, 
                          cal_status=cal_status, mode='view')


@app.route('/equipment/<int:equip_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'quality_manager'])
def equipment_edit(equip_id):
    """Edit equipment."""
    equipment = query_db('SELECT * FROM equipment WHERE id = ?', [equip_id], one=True)
    if not equipment:
        flash('Udstyr blev ikke fundet.', 'error')
        return redirect(url_for('equipment_list'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        equipment_type = request.form.get('equipment_type')
        serial_number = request.form.get('serial_number')
        manufacturer = request.form.get('manufacturer')
        calibration_interval = int(request.form.get('calibration_interval', 365))
        last_calibration = request.form.get('last_calibration_date')
        active = 1 if request.form.get('active') else 0
        
        # Calculate due date
        if last_calibration:
            due_date = query_db(
                "SELECT date(?, '+' || ? || ' days') as due",
                [last_calibration, calibration_interval], one=True
            )['due']
        else:
            due_date = None
        
        db = get_db()
        db.execute('''
            UPDATE equipment SET name = ?, equipment_type = ?, serial_number = ?,
                   manufacturer = ?, calibration_interval_days = ?, 
                   last_calibration_date = ?, calibration_due_date = ?,
                   active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', [name, equipment_type, serial_number, manufacturer, calibration_interval,
              last_calibration, due_date, active, equip_id])
        db.commit()
        
        flash('Udstyr opdateret.', 'success')
        return redirect(url_for('equipment_detail', equip_id=equip_id))
    
    return render_template('equipment.html', equipment=equipment, mode='edit')


@app.route('/equipment/<int:equip_id>/calibrate', methods=['POST'])
@login_required
@role_required(['admin', 'quality_manager', 'inspector'])
def equipment_calibrate(equip_id):
    """Record a calibration for equipment."""
    equipment = query_db('SELECT * FROM equipment WHERE id = ?', [equip_id], one=True)
    if not equipment:
        flash('Udstyr blev ikke fundet.', 'error')
        return redirect(url_for('equipment_list'))
    
    calibration_date = request.form.get('calibration_date', datetime.now().strftime('%Y-%m-%d'))
    interval = equipment['calibration_interval_days'] or 365
    
    # Calculate new due date
    due_date = query_db(
        "SELECT date(?, '+' || ? || ' days') as due",
        [calibration_date, interval], one=True
    )['due']
    
    db = get_db()
    db.execute('''
        UPDATE equipment SET last_calibration_date = ?, calibration_due_date = ?,
               calibration_status = 'ok', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', [calibration_date, due_date, equip_id])
    db.commit()
    
    flash(f'Kalibrering registreret. Næste kalibrering: {due_date}', 'success')
    return redirect(url_for('equipment_detail', equip_id=equip_id))


# =============================================================================
# Parts Management Routes
# =============================================================================

@app.route('/parts')
@login_required
def parts_list():
    """List all parts."""
    search = request.args.get('search', '').strip()
    
    if search:
        parts = query_db('''
            SELECT p.*, COUNT(j.id) as job_count
            FROM parts p
            LEFT JOIN jobs j ON j.part_id = p.id
            WHERE p.part_number LIKE ? OR p.part_revision LIKE ?
            GROUP BY p.id
            ORDER BY p.part_number, p.part_revision
        ''', [f'%{search}%', f'%{search}%'])
    else:
        parts = query_db('''
            SELECT p.*, COUNT(j.id) as job_count
            FROM parts p
            LEFT JOIN jobs j ON j.part_id = p.id
            GROUP BY p.id
            ORDER BY p.part_number, p.part_revision
            LIMIT 100
        ''')
    
    return render_template('parts.html', parts=parts, search=search)


@app.route('/parts/<int:part_id>')
@login_required
def part_detail(part_id):
    """View part details and associated jobs."""
    part = query_db('SELECT * FROM parts WHERE id = ?', [part_id], one=True)
    if not part:
        flash('Delen blev ikke fundet.', 'error')
        return redirect(url_for('parts_list'))
    
    # Get all jobs using this part
    jobs = query_db('''
        SELECT j.*, c.name as customer_name
        FROM jobs j
        LEFT JOIN customers c ON j.customer_id = c.id
        WHERE j.part_id = ?
        ORDER BY j.created_at DESC
    ''', [part_id])
    
    # Get error reports for this part
    errors = query_db('''
        SELECT er.*, j.po_number, j.internal_job_number
        FROM error_reports er
        JOIN jobs j ON er.job_id = j.id
        WHERE j.part_id = ?
        ORDER BY er.found_date DESC
    ''', [part_id])
    
    return render_template('part_detail.html', part=part, jobs=jobs, errors=errors)


# =============================================================================
# Notification Routes
# =============================================================================

def create_notification(user_id, notification_type, title, message, entity_type=None, entity_id=None):
    """Helper function to create a notification."""
    execute_db('''
        INSERT INTO notifications (user_id, notification_type, title, message, entity_type, entity_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', [user_id, notification_type, title, message, entity_type, entity_id])


def get_quality_notification_users():
    """Users to notify for quality issues (QM + admin). Under development: includes admin."""
    qm = query_db('SELECT id FROM users WHERE role = ? AND active = 1', ['quality_manager'])
    admin = query_db('SELECT id FROM users WHERE role = ? AND active = 1', ['admin'])
    seen = set()
    users = []
    for u in qm + admin:
        if u['id'] not in seen:
            seen.add(u['id'])
            users.append(u)
    return users


@app.route('/notifications')
@login_required
def notifications_list():
    """List all notifications for current user."""
    notifications = query_db('''
        SELECT * FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 50
    ''', [current_user.id])
    
    unread_count = query_db('''
        SELECT COUNT(*) as count FROM notifications
        WHERE user_id = ? AND read = 0
    ''', [current_user.id], one=True)['count']
    
    return render_template('notifications.html', notifications=notifications, unread_count=unread_count)


@app.route('/notifications/count')
@login_required
def notifications_count():
    """Get unread notification count (for AJAX)."""
    try:
        row = query_db('''
            SELECT COUNT(*) as count FROM notifications
            WHERE user_id = ? AND read = 0
        ''', [current_user.id], one=True)
        count = row['count'] if row else 0
    except Exception:
        count = 0
    return jsonify({'count': count})


@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def notification_mark_read(notification_id):
    """Mark a notification as read."""
    notification = query_db('SELECT * FROM notifications WHERE id = ? AND user_id = ?', 
                           [notification_id, current_user.id], one=True)
    if not notification:
        flash('Notifikation blev ikke fundet.', 'error')
        return redirect(url_for('notifications_list'))
    
    execute_db('UPDATE notifications SET read = 1 WHERE id = ?', [notification_id])
    
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'success': True}
    
    return redirect(url_for('notifications_list'))


@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def notifications_mark_all_read():
    """Mark all notifications as read."""
    execute_db('UPDATE notifications SET read = 1 WHERE user_id = ? AND read = 0', [current_user.id])
    
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'success': True}
    
    flash('Alle notifikationer markeret som læst.', 'success')
    return redirect(url_for('notifications_list'))


@app.route('/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
def notification_delete(notification_id):
    """Delete a notification."""
    notification = query_db('SELECT * FROM notifications WHERE id = ? AND user_id = ?', 
                         [notification_id, current_user.id], one=True)
    if not notification:
        flash('Notifikation blev ikke fundet.', 'error')
        return redirect(url_for('notifications_list'))
    
    execute_db('DELETE FROM notifications WHERE id = ?', [notification_id])
    
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'success': True}
    
    flash('Notifikation slettet.', 'success')
    return redirect(url_for('notifications_list'))


@app.route('/notifications/recent')
@login_required
def notifications_recent():
    """Get recent unread notifications (for dropdown)."""
    notifications = query_db('''
        SELECT * FROM notifications
        WHERE user_id = ? AND read = 0
        ORDER BY created_at DESC
        LIMIT 10
    ''', [current_user.id])
    
    # Convert to list of dicts for JSON
    result = []
    for n in notifications:
        result.append({
            'id': n['id'],
            'type': n['notification_type'],
            'title': n['title'],
            'message': n['message'],
            'entity_type': n['entity_type'],
            'entity_id': n['entity_id'],
            'created_at': n['created_at']
        })
    
    return {'notifications': result}


# =============================================================================
# User Management Routes
# =============================================================================

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    """User management page."""
    users = query_db('SELECT * FROM users ORDER BY username')
    return render_template('admin.html', users=users)


@app.route('/admin/users/add', methods=['POST'])
@login_required
@role_required('admin')
def admin_add_user():
    """Add a new user."""
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'operator')
    
    if not username or not password:
        flash('Brugernavn og adgangskode skal udfyldes.', 'error')
        return redirect(url_for('admin_users'))
    
    # Check if username exists
    existing = query_db('SELECT id FROM users WHERE username = ?', [username], one=True)
    if existing:
        flash('Brugernavnet findes allerede.', 'error')
        return redirect(url_for('admin_users'))
    
    password_hash = generate_password_hash(password)
    execute_db('''
        INSERT INTO users (username, email, password_hash, role) 
        VALUES (?, ?, ?, ?)
    ''', [username, email, password_hash, role])
    
    flash(f'Bruger "{username}" oprettet.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def admin_toggle_user(user_id):
    """Toggle user active status."""
    user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)
    if user:
        new_status = 0 if user['active'] else 1
        execute_db('UPDATE users SET active = ? WHERE id = ?', [new_status, user_id])
        status_text = 'aktiveret' if new_status else 'deaktiveret'
        flash(f'Bruger "{user["username"]}" {status_text}.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@role_required('admin')
def admin_reset_password(user_id):
    """Reset user password."""
    new_password = request.form.get('new_password', '')
    if not new_password:
        flash('Adgangskode må ikke være tom.', 'error')
        return redirect(url_for('admin_users'))
    
    password_hash = generate_password_hash(new_password)
    execute_db('UPDATE users SET password_hash = ? WHERE id = ?', [password_hash, user_id])
    
    user = query_db('SELECT username FROM users WHERE id = ?', [user_id], one=True)
    flash(f'Adgangskode nulstillet for bruger "{user["username"]}".', 'success')
    return redirect(url_for('admin_users'))


# =============================================================================
# Audit Logging Helper
# =============================================================================

def log_audit(action, entity_type, entity_id, description=None, changes=None):
    """Log an audit entry."""
    user_id = current_user.id if current_user.is_authenticated else None
    execute_db('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, description, changes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', [user_id, action, entity_type, entity_id, description, changes])


# =============================================================================
# Utility Functions
# =============================================================================

def generate_job_number():
    """Generate next internal job number."""
    result = query_db("SELECT MAX(CAST(SUBSTR(internal_job_number, 4) AS INTEGER)) as max_num FROM jobs WHERE internal_job_number LIKE 'JOB%'", one=True)
    next_num = (result['max_num'] or 0) + 1
    return f"JOB{next_num:05d}"


def calculate_exit_control_samples(lot_quantity):
    """Calculate which parts to sample: first 5 + every 10th after."""
    samples = []
    # First 5 parts
    for i in range(1, min(6, lot_quantity + 1)):
        samples.append(i)
    # Every 10th after part 5
    if lot_quantity > 5:
        part = 15
        while part <= lot_quantity:
            samples.append(part)
            part += 10
    return samples


# =============================================================================
# Template Context Processors
# =============================================================================

@app.context_processor
def utility_processor():
    """Add utility functions to template context."""
    return {
        'now': datetime.now(),
        'timedelta': timedelta,
        'workflow_stages': [
            ('po_receipt', 'Ordremodtagelse'),
            ('revision_check', 'Revisionskontrol'),
            ('material_control', 'Materialekontrol'),
            ('in_process', 'I produktion'),
            ('external_process', 'Ekstern proces'),
            ('exit_control', 'Slutkontrol'),
            ('complete', 'Færdig'),
        ],
        'workflow_stage_labels_da': {
            'po_receipt': 'Ordremodtagelse',
            'revision_check': 'Revisionskontrol',
            'material_control': 'Materialekontrol',
            'in_process': 'I produktion',
            'external_process': 'Ekstern proces',
            'exit_control': 'Slutkontrol',
            'complete': 'Færdig',
            'on_hold': 'På hold',
        },
        'severity_labels_da': {
            'critical': 'Kritisk',
            'major': 'Alvorlig',
            'minor': 'Mindre',
        },
        'error_type_labels_da': {
            'internal': 'Intern',
            'material_supplier': 'Materialeleverandør',
            'external_supplier': 'Ekstern leverandør',
        },
        'workflow_stage_colors': {
            'po_receipt': 'blue',
            'revision_check': 'purple',
            'material_control': 'orange',
            'in_process': 'yellow',
            'external_process': 'cyan',
            'exit_control': 'pink',
            'complete': 'green',
            'on_hold': 'red',
        }
    }


# =============================================================================
# Job Routes
# =============================================================================

@app.route('/jobs')
@login_required
def jobs_list():
    """List all jobs with filtering."""
    # Get filter parameters
    stage = request.args.get('stage', '')
    customer_id = request.args.get('customer', '')
    search = request.args.get('search', '')
    
    # Build query
    query = '''
        SELECT j.*, c.name as customer_name,
               (SELECT COUNT(*) FROM job_dimensions WHERE job_id = j.id) as dimension_count,
               (SELECT COUNT(*) FROM error_reports WHERE job_id = j.id AND status IN ('open', 'investigating')) as open_errors
        FROM jobs j
        LEFT JOIN customers c ON j.customer_id = c.id
        WHERE 1=1
    '''
    params = []
    
    if stage:
        query += ' AND j.workflow_stage = ?'
        params.append(stage)
    
    if customer_id:
        query += ' AND j.customer_id = ?'
        params.append(customer_id)
    
    if search:
        query += ' AND (j.po_number LIKE ? OR j.part_number LIKE ? OR j.internal_job_number LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])
    
    query += ' ORDER BY j.created_at DESC'
    
    jobs = query_db(query, params)
    customers = query_db('SELECT * FROM customers ORDER BY name')
    
    return render_template('jobs.html', jobs=jobs, customers=customers,
                          current_stage=stage, current_customer=customer_id, search=search)


# =============================================================================
# Job Form API (part revisions, last setup)
# =============================================================================

@app.route('/api/part-revisions')
@login_required
def api_part_revisions():
    """Return revisions for a part number (for dropdown)."""
    part_number = request.args.get('part_number', '').strip()
    if not part_number:
        return jsonify([])
    
    parts = query_db('''
        SELECT id, part_number, part_revision, part_description
        FROM parts
        WHERE part_number = ?
        ORDER BY part_revision
    ''', [part_number])
    
    return jsonify([{
        'part_id': p['id'],
        'part_number': p['part_number'],
        'part_revision': p['part_revision'] or '',
        'part_description': p['part_description'] or ''
    } for p in parts])


@app.route('/api/part-last-setup')
@login_required
def api_part_last_setup():
    """Return last job setup (dimensions, description, etc.) for a part - for re-runs."""
    part_id = request.args.get('part_id', type=int)
    if not part_id:
        return jsonify(None)
    
    # Get the most recent job for this part that has dimensions
    job = query_db('''
        SELECT j.id, j.internal_job_number, j.part_description, j.drawing_number, j.special_requirements
        FROM jobs j
        WHERE j.part_id = ?
        ORDER BY j.created_at DESC
        LIMIT 1
    ''', [part_id], one=True)
    
    if not job:
        return jsonify(None)
    
    dimensions = query_db('''
        SELECT dimension_number, dimension_name, nominal_value, tolerance_plus, tolerance_minus,
               unit, drawing_reference, critical
        FROM job_dimensions
        WHERE job_id = ?
        ORDER BY dimension_number
    ''', [job['id']])
    
    return jsonify({
        'job_number': job['internal_job_number'],
        'part_description': job['part_description'] or '',
        'drawing_number': job['drawing_number'] or '',
        'special_requirements': job['special_requirements'] or '',
        'dimensions': [{
            'dimension_name': d['dimension_name'],
            'nominal_value': d['nominal_value'],
            'tolerance_plus': d['tolerance_plus'],
            'tolerance_minus': d['tolerance_minus'],
            'unit': d['unit'] or 'mm',
            'drawing_reference': d['drawing_reference'] or '',
            'critical': bool(d['critical'])
        } for d in dimensions]
    })


@app.route('/jobs/new', methods=['GET', 'POST'])
@login_required
def job_create():
    """Create a new job."""
    if request.method == 'POST':
        # Get form data
        po_number = request.form.get('po_number', '').strip()
        customer_id = request.form.get('customer_id') or None
        part_number = request.form.get('part_number', '').strip()
        part_revision = request.form.get('part_revision', '').strip()
        part_description = request.form.get('part_description', '').strip()
        quantity = request.form.get('quantity', type=int)
        due_date = request.form.get('due_date') or None
        drawing_number = request.form.get('drawing_number', '').strip()
        special_requirements = request.form.get('special_requirements', '').strip()
        
        if not po_number or not part_number or not quantity:
            flash('Ordrenummer, delenummer og antal skal udfyldes.', 'error')
            return redirect(url_for('job_create'))
        
        # Get or create part (ensures no duplicates; new parts created automatically)
        part_id, part_was_created = get_or_create_part(part_number, part_revision, part_description)
        
        # Generate internal job number
        internal_job_number = generate_job_number()
        
        # Create job
        job_id = execute_db('''
            INSERT INTO jobs (po_number, internal_job_number, customer_id, part_id,
                            part_number, part_revision, part_description, quantity, due_date, drawing_number,
                            special_requirements)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [po_number, internal_job_number, customer_id, part_id, part_number,
              part_revision, part_description, quantity, due_date, drawing_number,
              special_requirements])
        
        # Add dimensions if provided
        dimension_names = request.form.getlist('dimension_name[]')
        dimension_nominals = request.form.getlist('dimension_nominal[]')
        dimension_tol_plus = request.form.getlist('dimension_tol_plus[]')
        dimension_tol_minus = request.form.getlist('dimension_tol_minus[]')
        dimension_units = request.form.getlist('dimension_unit[]')
        dimension_refs = request.form.getlist('dimension_ref[]')
        dimension_critical = request.form.getlist('dimension_critical[]')
        
        for i, name in enumerate(dimension_names):
            if name.strip():
                nominal = float(dimension_nominals[i]) if dimension_nominals[i] else 0
                tol_plus = float(dimension_tol_plus[i]) if dimension_tol_plus[i] else None
                tol_minus = float(dimension_tol_minus[i]) if dimension_tol_minus[i] else None
                unit = dimension_units[i] if i < len(dimension_units) else 'mm'
                ref = dimension_refs[i] if i < len(dimension_refs) else ''
                critical = 1 if str(i) in dimension_critical else 0
                
                execute_db('''
                    INSERT INTO job_dimensions (job_id, dimension_number, dimension_name,
                                               nominal_value, tolerance_plus, tolerance_minus,
                                               unit, drawing_reference, critical)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', [job_id, i + 1, name.strip(), nominal, tol_plus, tol_minus, unit, ref, critical])
        
        log_audit('create', 'job', job_id, f'Created job {internal_job_number}')
        if part_was_created:
            flash(f'Ordre {internal_job_number} oprettet. Del "{part_number}"' + (f' rev. {part_revision}' if part_revision else '') + ' er tilføjet til deloversigten.', 'success')
        else:
            flash(f'Ordre {internal_job_number} oprettet.', 'success')
        return redirect(url_for('job_detail', job_id=job_id))
    
    # GET request - show form
    customers = query_db('SELECT * FROM customers ORDER BY name')
    # Get recent jobs for copying dimensions
    recent_jobs = query_db('''
        SELECT id, internal_job_number, part_number, 
               (SELECT COUNT(*) FROM job_dimensions WHERE job_id = jobs.id) as dim_count
        FROM jobs 
        WHERE id IN (SELECT DISTINCT job_id FROM job_dimensions)
        ORDER BY created_at DESC 
        LIMIT 20
    ''')
    # Get existing parts for autocomplete (new part numbers can still be typed and will be created)
    existing_parts = query_db('''
        SELECT part_number, part_revision FROM parts ORDER BY part_number, part_revision
    ''')
    
    return render_template('job_form.html', job=None, customers=customers, 
                          recent_jobs=recent_jobs, existing_parts=existing_parts, edit_mode=False)


@app.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    """View job details with all related QC data."""
    job = query_db('''
        SELECT j.*, c.name as customer_name, c.email as customer_email,
               u.username as verified_by_username
        FROM jobs j
        LEFT JOIN customers c ON j.customer_id = c.id
        LEFT JOIN users u ON j.revision_verified_by = u.id
        WHERE j.id = ?
    ''', [job_id], one=True)
    
    if not job:
        flash('Ordren blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    # Get dimensions
    dimensions = query_db('''
        SELECT * FROM job_dimensions WHERE job_id = ? ORDER BY dimension_number
    ''', [job_id])
    
    # Get documents
    documents = query_db('''
        SELECT d.*, u.username as uploaded_by_username
        FROM job_documents d
        LEFT JOIN users u ON d.uploaded_by = u.id
        WHERE d.job_id = ?
        ORDER BY d.uploaded_at DESC
    ''', [job_id])
    
    # Get material controls
    material_controls = query_db('''
        SELECT mc.*, u.username as inspector_username, s.name as supplier_name
        FROM material_controls mc
        LEFT JOIN users u ON mc.inspector_id = u.id
        LEFT JOIN suppliers s ON mc.supplier_id = s.id
        WHERE mc.job_id = ?
        ORDER BY mc.created_at DESC
    ''', [job_id])
    
    # Get measurement reports
    measurement_reports = query_db('''
        SELECT mr.*, u.username as inspector_username,
               (SELECT COUNT(*) FROM measurements WHERE report_id = mr.id) as measurement_count
        FROM measurement_reports mr
        LEFT JOIN users u ON mr.inspector_id = u.id
        WHERE mr.job_id = ?
        ORDER BY mr.created_at DESC
    ''', [job_id])
    
    # Get external processes
    external_processes = query_db('''
        SELECT ep.*, u.username as inspector_username, s.name as supplier_name
        FROM external_processes ep
        LEFT JOIN users u ON ep.inspector_id = u.id
        LEFT JOIN suppliers s ON ep.supplier_id = s.id
        WHERE ep.job_id = ?
        ORDER BY ep.created_at DESC
    ''', [job_id])
    
    # Get exit controls
    exit_controls = query_db('''
        SELECT ec.*, u.username as inspector_username,
               (SELECT COUNT(*) FROM exit_control_samples WHERE exit_control_id = ec.id) as sample_count
        FROM exit_controls ec
        LEFT JOIN users u ON ec.inspector_id = u.id
        WHERE ec.job_id = ?
        ORDER BY ec.created_at DESC
    ''', [job_id])
    
    # Get error reports
    error_reports = query_db('''
        SELECT er.*, u.username as reported_by_username, a.username as assigned_to_username
        FROM error_reports er
        LEFT JOIN users u ON er.reported_by = u.id
        LEFT JOIN users a ON er.assigned_to = a.id
        WHERE er.job_id = ?
        ORDER BY er.created_at DESC
    ''', [job_id])
    
    # Get audit log for this job
    audit_log = query_db('''
        SELECT al.*, u.username
        FROM audit_logs al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE al.entity_type = 'job' AND al.entity_id = ?
        ORDER BY al.timestamp DESC
        LIMIT 20
    ''', [job_id])
    
    return render_template('job_detail.html', job=job, dimensions=dimensions,
                          documents=documents, material_controls=material_controls,
                          measurement_reports=measurement_reports,
                          external_processes=external_processes,
                          exit_controls=exit_controls, error_reports=error_reports,
                          audit_log=audit_log)


@app.route('/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
def job_edit(job_id):
    """Edit an existing job."""
    job = query_db('SELECT * FROM jobs WHERE id = ?', [job_id], one=True)
    if not job:
        flash('Ordren blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if request.method == 'POST':
        # Update job
        po_number = request.form.get('po_number', '').strip()
        customer_id = request.form.get('customer_id') or None
        part_number = request.form.get('part_number', '').strip()
        part_revision = request.form.get('part_revision', '').strip()
        part_description = request.form.get('part_description', '').strip()
        quantity = request.form.get('quantity', type=int)
        due_date = request.form.get('due_date') or None
        drawing_number = request.form.get('drawing_number', '').strip()
        special_requirements = request.form.get('special_requirements', '').strip()
        
        # Get or create part (ensures no duplicates; new parts created automatically)
        part_id, part_was_created = get_or_create_part(part_number, part_revision, part_description)
        
        execute_db('''
            UPDATE jobs SET 
                po_number = ?, customer_id = ?, part_id = ?, part_number = ?, part_revision = ?,
                part_description = ?, quantity = ?, due_date = ?, drawing_number = ?,
                special_requirements = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', [po_number, customer_id, part_id, part_number, part_revision, part_description, quantity,
              due_date, drawing_number, special_requirements, job_id])
        
        log_audit('update', 'job', job_id, f'Updated job {job["internal_job_number"]}')
        if part_was_created:
            flash(f'Ordre opdateret. Del "{part_number}"' + (f' rev. {part_revision}' if part_revision else '') + ' er tilføjet til deloversigten.', 'success')
        else:
            flash('Ordre opdateret.', 'success')
        return redirect(url_for('job_detail', job_id=job_id))
    
    customers = query_db('SELECT * FROM customers ORDER BY name')
    dimensions = query_db('SELECT * FROM job_dimensions WHERE job_id = ? ORDER BY dimension_number', [job_id])
    existing_parts = query_db('SELECT part_number, part_revision FROM parts ORDER BY part_number, part_revision')
    
    return render_template('job_form.html', job=job, customers=customers, 
                          dimensions=dimensions, existing_parts=existing_parts, edit_mode=True, recent_jobs=[])


@app.route('/jobs/<int:job_id>/stage', methods=['POST'])
@login_required
def job_update_stage(job_id):
    """Update job workflow stage."""
    job = query_db('SELECT * FROM jobs WHERE id = ?', [job_id], one=True)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    new_stage = request.form.get('stage')
    valid_stages = ['po_receipt', 'revision_check', 'material_control', 'in_process', 
                    'external_process', 'exit_control', 'complete', 'on_hold']
    
    if new_stage not in valid_stages:
        flash('Ugyldigt arbejdsgangstrin.', 'error')
        return redirect(url_for('job_detail', job_id=job_id))
    
    old_stage = job['workflow_stage']
    
    # Update stage
    if new_stage == 'complete':
        execute_db('''
            UPDATE jobs SET workflow_stage = ?, completed_at = CURRENT_TIMESTAMP, 
                           updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', [new_stage, job_id])
    else:
        execute_db('''
            UPDATE jobs SET workflow_stage = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', [new_stage, job_id])
    
    log_audit('status_change', 'job', job_id, 
              f'Changed stage from {old_stage} to {new_stage}')
    
    flash(f'Ordrestadie opdateret til {new_stage.replace("_", " ").title()}.', 'success')
    return redirect(url_for('job_detail', job_id=job_id))


@app.route('/jobs/<int:job_id>/verify-revision', methods=['POST'])
@login_required
def job_verify_revision(job_id):
    """Mark drawing revision as verified."""
    job = query_db('SELECT * FROM jobs WHERE id = ?', [job_id], one=True)
    if not job:
        flash('Ordren blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    execute_db('''
        UPDATE jobs SET revision_verified = 1, revision_verified_by = ?,
                       revision_verified_at = CURRENT_TIMESTAMP,
                       updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', [current_user.id, job_id])
    
    log_audit('update', 'job', job_id, 'Verified drawing revision')
    flash('Tegningsrevision bekræftet.', 'success')
    return redirect(url_for('job_detail', job_id=job_id))


@app.route('/jobs/<int:job_id>/dimensions', methods=['POST'])
@login_required
def job_add_dimension(job_id):
    """Add a dimension to a job."""
    job = query_db('SELECT * FROM jobs WHERE id = ?', [job_id], one=True)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Get next dimension number
    result = query_db('SELECT MAX(dimension_number) as max_num FROM job_dimensions WHERE job_id = ?', [job_id], one=True)
    next_num = (result['max_num'] or 0) + 1
    
    name = request.form.get('dimension_name', '').strip()
    nominal = request.form.get('nominal_value', type=float) or 0
    tol_plus = request.form.get('tolerance_plus', type=float)
    tol_minus = request.form.get('tolerance_minus', type=float)
    unit = request.form.get('unit', 'mm')
    ref = request.form.get('drawing_reference', '')
    critical = 1 if request.form.get('critical') else 0
    
    if not name:
        flash('Dimensionsnavn skal udfyldes.', 'error')
        return redirect(url_for('job_detail', job_id=job_id))
    
    execute_db('''
        INSERT INTO job_dimensions (job_id, dimension_number, dimension_name,
                                   nominal_value, tolerance_plus, tolerance_minus,
                                   unit, drawing_reference, critical)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [job_id, next_num, name, nominal, tol_plus, tol_minus, unit, ref, critical])
    
    flash('Dimension tilføjet.', 'success')
    return redirect(url_for('job_detail', job_id=job_id))


@app.route('/jobs/<int:job_id>/dimensions/<int:dim_id>/delete', methods=['POST'])
@login_required
def job_delete_dimension(job_id, dim_id):
    """Delete a dimension from a job."""
    execute_db('DELETE FROM job_dimensions WHERE id = ? AND job_id = ?', [dim_id, job_id])
    flash('Dimension slettet.', 'success')
    return redirect(url_for('job_detail', job_id=job_id))


@app.route('/jobs/<int:job_id>/copy-dimensions/<int:source_job_id>', methods=['POST'])
@login_required
def job_copy_dimensions(job_id, source_job_id):
    """Copy dimensions from another job."""
    # Get source dimensions
    source_dims = query_db('SELECT * FROM job_dimensions WHERE job_id = ? ORDER BY dimension_number', [source_job_id])
    
    if not source_dims:
        flash('Kildeordren har ingen dimensioner.', 'error')
        return redirect(url_for('job_detail', job_id=job_id))
    
    # Delete existing dimensions
    execute_db('DELETE FROM job_dimensions WHERE job_id = ?', [job_id])
    
    # Copy dimensions
    for dim in source_dims:
        execute_db('''
            INSERT INTO job_dimensions (job_id, dimension_number, dimension_name,
                                       nominal_value, tolerance_plus, tolerance_minus,
                                       unit, drawing_reference, critical)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [job_id, dim['dimension_number'], dim['dimension_name'],
              dim['nominal_value'], dim['tolerance_plus'], dim['tolerance_minus'],
              dim['unit'], dim['drawing_reference'], dim['critical']])
    
    flash(f'{len(source_dims)} dimensioner kopieret fra kildeordren.', 'success')
    return redirect(url_for('job_detail', job_id=job_id))


# =============================================================================
# Document Upload Routes
# =============================================================================

from werkzeug.utils import secure_filename

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/jobs/<int:job_id>/documents', methods=['POST'])
@login_required
def job_upload_document(job_id):
    """Upload a document to a job."""
    job = query_db('SELECT * FROM jobs WHERE id = ?', [job_id], one=True)
    if not job:
        flash('Ordren blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if 'file' not in request.files:
        flash('Vælg en fil.', 'error')
        return redirect(url_for('job_detail', job_id=job_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('Vælg en fil.', 'error')
        return redirect(url_for('job_detail', job_id=job_id))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to filename to avoid collisions
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{job['internal_job_number']}_{timestamp}_{filename}"
        
        doc_type = request.form.get('document_type', 'other')
        subdir = 'drawings' if doc_type == 'drawing' else 'documents'
        
        file_path = os.path.join(subdir, filename)
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], file_path)
        file.save(full_path)
        
        revision = request.form.get('revision', '')
        
        execute_db('''
            INSERT INTO job_documents (job_id, document_type, file_name, file_path, revision, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', [job_id, doc_type, file.filename, file_path, revision, current_user.id])
        
        log_audit('create', 'job', job_id, f'Uploaded document: {file.filename}')
        flash('Dokument uploadet.', 'success')
    else:
        flash('Ugyldig filtype.', 'error')
    
    return redirect(url_for('job_detail', job_id=job_id))


@app.route('/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(doc_id):
    """Delete a document."""
    doc = query_db('SELECT * FROM job_documents WHERE id = ?', [doc_id], one=True)
    if doc:
        # Delete file
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], doc['file_path'])
        if os.path.exists(full_path):
            os.remove(full_path)
        
        execute_db('DELETE FROM job_documents WHERE id = ?', [doc_id])
        flash('Dokument slettet.', 'success')
        return redirect(url_for('job_detail', job_id=doc['job_id']))
    
    flash('Dokument blev ikke fundet.', 'error')
    return redirect(url_for('jobs_list'))


# =============================================================================
# Customer Routes
# =============================================================================

@app.route('/customers')
@login_required
def customers_list():
    """List all customers."""
    customers = query_db('''
        SELECT c.*, 
               (SELECT COUNT(*) FROM jobs WHERE customer_id = c.id) as job_count
        FROM customers c
        ORDER BY c.name
    ''')
    return render_template('customers.html', customers=customers)


@app.route('/customers/add', methods=['POST'])
@login_required
def customer_add():
    """Add a new customer."""
    name = request.form.get('name', '').strip()
    contact_person = request.form.get('contact_person', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    notes = request.form.get('notes', '').strip()
    
    if not name:
        flash('Kundenavn skal udfyldes.', 'error')
        return redirect(url_for('customers_list'))
    
    execute_db('''
        INSERT INTO customers (name, contact_person, email, phone, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', [name, contact_person, email, phone, notes])
    
    flash(f'Kunde "{name}" tilføjet.', 'success')
    return redirect(url_for('customers_list'))


@app.route('/customers/<int:customer_id>/edit', methods=['POST'])
@login_required
def customer_edit(customer_id):
    """Edit a customer."""
    name = request.form.get('name', '').strip()
    contact_person = request.form.get('contact_person', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    notes = request.form.get('notes', '').strip()
    
    if not name:
        flash('Kundenavn skal udfyldes.', 'error')
        return redirect(url_for('customers_list'))
    
    execute_db('''
        UPDATE customers SET name = ?, contact_person = ?, email = ?, phone = ?, notes = ?
        WHERE id = ?
    ''', [name, contact_person, email, phone, notes, customer_id])
    
    flash('Kunde opdateret.', 'success')
    return redirect(url_for('customers_list'))


# =============================================================================
# Supplier Routes
# =============================================================================

@app.route('/suppliers')
@login_required
def suppliers_list():
    """List all suppliers."""
    suppliers = query_db('''
        SELECT s.*,
               (SELECT COUNT(*) FROM material_controls WHERE supplier_id = s.id) as material_count,
               (SELECT COUNT(*) FROM external_processes WHERE supplier_id = s.id) as process_count,
               (SELECT COUNT(*) FROM error_reports WHERE supplier_id = s.id) as error_count,
               (SELECT COUNT(*) FROM error_reports WHERE supplier_id = s.id AND status = 'open') as open_error_count
        FROM suppliers s
        WHERE s.active = 1
        ORDER BY s.name
    ''')
    return render_template('suppliers.html', suppliers=suppliers)


@app.route('/suppliers/add', methods=['POST'])
@login_required
def supplier_add():
    """Add a new supplier."""
    name = request.form.get('name', '').strip()
    supplier_type = request.form.get('supplier_type', 'material')
    contact_person = request.form.get('contact_person', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    processes_offered = request.form.get('processes_offered', '').strip()
    notes = request.form.get('notes', '').strip()
    
    if not name:
        flash('Leverandørnavn skal udfyldes.', 'error')
        return redirect(url_for('suppliers_list'))
    
    execute_db('''
        INSERT INTO suppliers (name, supplier_type, contact_person, email, phone, processes_offered, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', [name, supplier_type, contact_person, email, phone, processes_offered, notes])
    
    flash(f'Leverandør "{name}" tilføjet.', 'success')
    return redirect(url_for('suppliers_list'))


@app.route('/suppliers/<int:supplier_id>/edit', methods=['POST'])
@login_required
def supplier_edit(supplier_id):
    """Edit a supplier."""
    name = request.form.get('name', '').strip()
    supplier_type = request.form.get('supplier_type', 'material')
    contact_person = request.form.get('contact_person', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    processes_offered = request.form.get('processes_offered', '').strip()
    notes = request.form.get('notes', '').strip()
    
    if not name:
        flash('Leverandørnavn skal udfyldes.', 'error')
        return redirect(url_for('suppliers_list'))
    
    execute_db('''
        UPDATE suppliers SET name = ?, supplier_type = ?, contact_person = ?, 
               email = ?, phone = ?, processes_offered = ?, notes = ?
        WHERE id = ?
    ''', [name, supplier_type, contact_person, email, phone, processes_offered, notes, supplier_id])
    
    flash('Leverandør opdateret.', 'success')
    return redirect(url_for('suppliers_list'))


@app.route('/suppliers/<int:supplier_id>/delete', methods=['POST'])
@login_required
def supplier_delete(supplier_id):
    """Deactivate a supplier (soft delete)."""
    execute_db('UPDATE suppliers SET active = 0 WHERE id = ?', [supplier_id])
    flash('Leverandør deaktiveret.', 'success')
    return redirect(url_for('suppliers_list'))


# =============================================================================
# Material Control Routes
# =============================================================================

@app.route('/jobs/<int:job_id>/material/new', methods=['GET', 'POST'])
@login_required
def material_control_create(job_id):
    """Create a new material control record for a job."""
    job = query_db('SELECT * FROM jobs WHERE id = ?', [job_id], one=True)
    if not job:
        flash('Ordren blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if request.method == 'POST':
        material_type = request.form.get('material_type', '').strip()
        supplier_id = request.form.get('supplier_id') or None
        batch_number = request.form.get('batch_number', '').strip()
        quantity_received = request.form.get('quantity_received', '').strip()
        certificate_matches = 1 if request.form.get('certificate_matches') else 0
        visual_ok = 1 if request.form.get('visual_ok') else 0
        dimensions_ok = 1 if request.form.get('dimensions_ok') else 0 if request.form.get('dimensions_checked') else None
        notes = request.form.get('notes', '').strip()
        status = request.form.get('status', 'pending')
        
        if not material_type:
            flash('Materialetype skal udfyldes.', 'error')
            return redirect(url_for('material_control_create', job_id=job_id))
        
        mc_id = execute_db('''
            INSERT INTO material_controls (job_id, inspector_id, material_type, supplier_id,
                                          batch_number, quantity_received, certificate_matches,
                                          visual_ok, dimensions_ok, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [job_id, current_user.id, material_type, supplier_id, batch_number,
              quantity_received, certificate_matches, visual_ok, dimensions_ok, status, notes])
        
        log_audit('create', 'material_control', mc_id, 
                 f'Created material control for job {job["internal_job_number"]}')
        
        flash('Materialekontrol oprettet.', 'success')
        return redirect(url_for('material_control_detail', mc_id=mc_id))
    
    # GET request
    suppliers = query_db("SELECT * FROM suppliers WHERE active = 1 AND supplier_type IN ('material', 'both') ORDER BY name")
    return render_template('material_control.html', job=job, mc=None, suppliers=suppliers, 
                          attachments=None, edit_mode=False, view_mode=False)


@app.route('/material/<int:mc_id>')
@login_required
def material_control_detail(mc_id):
    """View a material control record."""
    mc = query_db('''
        SELECT mc.*, j.internal_job_number, j.po_number, j.part_number, j.id as job_id,
               u.username as inspector_username, s.name as supplier_name
        FROM material_controls mc
        JOIN jobs j ON mc.job_id = j.id
        LEFT JOIN users u ON mc.inspector_id = u.id
        LEFT JOIN suppliers s ON mc.supplier_id = s.id
        WHERE mc.id = ?
    ''', [mc_id], one=True)
    
    if not mc:
        flash('Materialekontrol blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    # Get attachments (certificates)
    attachments = query_db('''
        SELECT a.*, u.username as uploaded_by_username
        FROM attachments a
        LEFT JOIN users u ON a.uploaded_by = u.id
        WHERE a.entity_type = 'material_control' AND a.entity_id = ?
        ORDER BY a.uploaded_at DESC
    ''', [mc_id])
    
    job = query_db('SELECT * FROM jobs WHERE id = ?', [mc['job_id']], one=True)
    suppliers = query_db("SELECT * FROM suppliers WHERE active = 1 AND supplier_type IN ('material', 'both') ORDER BY name")
    
    return render_template('material_control.html', job=job, mc=mc, suppliers=suppliers,
                          attachments=attachments, edit_mode=False, view_mode=True)


@app.route('/material/<int:mc_id>/edit', methods=['GET', 'POST'])
@login_required
def material_control_edit(mc_id):
    """Edit a material control record."""
    mc = query_db('''
        SELECT mc.*, j.id as job_id, j.internal_job_number
        FROM material_controls mc
        JOIN jobs j ON mc.job_id = j.id
        WHERE mc.id = ?
    ''', [mc_id], one=True)
    
    if not mc:
        flash('Materialekontrol blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if request.method == 'POST':
        material_type = request.form.get('material_type', '').strip()
        supplier_id = request.form.get('supplier_id') or None
        batch_number = request.form.get('batch_number', '').strip()
        quantity_received = request.form.get('quantity_received', '').strip()
        certificate_matches = 1 if request.form.get('certificate_matches') else 0
        visual_ok = 1 if request.form.get('visual_ok') else 0
        dimensions_ok = 1 if request.form.get('dimensions_ok') else 0 if request.form.get('dimensions_checked') else None
        notes = request.form.get('notes', '').strip()
        status = request.form.get('status', 'pending')
        
        execute_db('''
            UPDATE material_controls SET material_type = ?, supplier_id = ?, batch_number = ?,
                   quantity_received = ?, certificate_matches = ?, visual_ok = ?, dimensions_ok = ?,
                   status = ?, notes = ?
            WHERE id = ?
        ''', [material_type, supplier_id, batch_number, quantity_received, certificate_matches,
              visual_ok, dimensions_ok, status, notes, mc_id])
        
        flash('Materialekontrol opdateret.', 'success')
        return redirect(url_for('material_control_detail', mc_id=mc_id))
    
    job = query_db('SELECT * FROM jobs WHERE id = ?', [mc['job_id']], one=True)
    suppliers = query_db("SELECT * FROM suppliers WHERE active = 1 AND supplier_type IN ('material', 'both') ORDER BY name")
    attachments = query_db('''
        SELECT * FROM attachments WHERE entity_type = 'material_control' AND entity_id = ?
    ''', [mc_id])
    
    return render_template('material_control.html', job=job, mc=mc, suppliers=suppliers,
                          attachments=attachments, edit_mode=True, view_mode=False)


@app.route('/material/<int:mc_id>/status', methods=['POST'])
@login_required
def material_control_status(mc_id):
    """Update material control status (approve/reject)."""
    mc = query_db('SELECT * FROM material_controls WHERE id = ?', [mc_id], one=True)
    if not mc:
        flash('Materialekontrol blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    new_status = request.form.get('status')
    if new_status in ['pending', 'approved', 'rejected']:
        execute_db('UPDATE material_controls SET status = ?, inspector_id = ? WHERE id = ?',
                  [new_status, current_user.id, mc_id])
        flash(f'Materialestatus opdateret til {new_status}.', 'success')
        
        # Notify QM + Admin when material is rejected
        if new_status == 'rejected':
            job = query_db('SELECT po_number, part_number, internal_job_number FROM jobs WHERE id = ?', [mc['job_id']], one=True)
            if job:
                for u in get_quality_notification_users():
                    create_notification(
                        u['id'],
                        'material_rejected',
                        f'Material Rejected: {job["part_number"]}',
                        f'Material control for Job {job["internal_job_number"]} (PO {job["po_number"]}) was rejected.',
                        'material_control',
                        mc_id
                    )
    
    return redirect(url_for('material_control_detail', mc_id=mc_id))


@app.route('/material/<int:mc_id>/upload', methods=['POST'])
@login_required
def material_control_upload(mc_id):
    """Upload a material certificate."""
    mc = query_db('SELECT * FROM material_controls WHERE id = ?', [mc_id], one=True)
    if not mc:
        flash('Materialekontrol blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if 'file' not in request.files:
        flash('Vælg en fil.', 'error')
        return redirect(url_for('material_control_detail', mc_id=mc_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('Vælg en fil.', 'error')
        return redirect(url_for('material_control_detail', mc_id=mc_id))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"MC{mc_id}_{timestamp}_{filename}"
        
        file_path = os.path.join('certificates', filename)
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], file_path)
        file.save(full_path)
        
        ext = filename.rsplit('.', 1)[1].lower()
        file_type = 'image' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'pdf' if ext == 'pdf' else 'other'
        
        execute_db('''
            INSERT INTO attachments (entity_type, entity_id, file_name, file_path, file_type, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ['material_control', mc_id, file.filename, file_path, file_type, current_user.id])
        
        flash('Materialecertifikat uploadet.', 'success')
    else:
        flash('Ugyldig filtype.', 'error')
    
    return redirect(url_for('material_control_detail', mc_id=mc_id))


@app.route('/material/<int:mc_id>/attachment/<int:attachment_id>/delete', methods=['POST'])
@login_required
def material_attachment_delete(mc_id, attachment_id):
    """Delete an attachment from material control."""
    attachment = query_db('SELECT * FROM attachments WHERE id = ? AND entity_type = ? AND entity_id = ?',
                         [attachment_id, 'material_control', mc_id], one=True)
    if attachment:
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment['file_path'])
        if os.path.exists(full_path):
            os.remove(full_path)
        execute_db('DELETE FROM attachments WHERE id = ?', [attachment_id])
        flash('Vedhæftning slettet.', 'success')
    
    return redirect(url_for('material_control_detail', mc_id=mc_id))


# =============================================================================
# Supplier Error Reports
# =============================================================================

@app.route('/suppliers/<int:supplier_id>/errors')
@login_required
def supplier_error_history(supplier_id):
    """View all error reports for a supplier."""
    supplier = query_db('SELECT * FROM suppliers WHERE id = ?', [supplier_id], one=True)
    if not supplier:
        flash('Leverandør blev ikke fundet.', 'error')
        return redirect(url_for('suppliers_list'))
    
    errors = query_db('''
        SELECT er.*, j.internal_job_number as job_number, j.part_number, u.username as reported_by_name
        FROM error_reports er
        JOIN jobs j ON er.job_id = j.id
        LEFT JOIN users u ON er.reported_by = u.id
        WHERE er.supplier_id = ?
        ORDER BY er.found_date DESC
    ''', [supplier_id])
    
    # Stats
    total = len(errors)
    open_count = len([e for e in errors if e['status'] == 'open'])
    resolved_count = len([e for e in errors if e['status'] == 'resolved'])
    
    return render_template('supplier_errors.html', supplier=supplier, errors=errors,
                         total=total, open_count=open_count, resolved_count=resolved_count)


@app.route('/supplier-errors')
@login_required
def all_supplier_errors():
    """View all supplier error reports across all suppliers."""
    error_type = request.args.get('type', '')  # 'material' or 'external'
    status = request.args.get('status', '')
    part = request.args.get('part', '')
    
    query = '''
        SELECT er.*, j.internal_job_number as job_number, j.part_number, j.part_revision,
               s.name as supplier_name, s.supplier_type,
               u.username as reported_by_name
        FROM error_reports er
        JOIN jobs j ON er.job_id = j.id
        LEFT JOIN suppliers s ON er.supplier_id = s.id
        LEFT JOIN users u ON er.reported_by = u.id
        WHERE er.supplier_id IS NOT NULL
    '''
    params = []
    
    if error_type == 'material':
        query += ' AND er.error_type = ?'
        params.append('material_supplier')
    elif error_type == 'external':
        query += ' AND er.error_type = ?'
        params.append('external_supplier')
    
    if status:
        query += ' AND er.status = ?'
        params.append(status)
    
    if part:
        query += ' AND j.part_number = ?'
        params.append(part)
    
    query += ' ORDER BY er.found_date DESC'
    
    errors = query_db(query, params)
    
    # Get suppliers for filter dropdown
    suppliers = query_db('SELECT id, name, supplier_type FROM suppliers WHERE active = 1 ORDER BY name')
    
    # Get unique part numbers for filter
    parts = query_db('SELECT DISTINCT part_number FROM jobs WHERE part_number IS NOT NULL AND part_number != "" ORDER BY part_number')
    
    return render_template('all_supplier_errors.html', errors=errors, suppliers=suppliers, parts=parts,
                         filter_type=error_type, filter_status=status, filter_part=part)


@app.route('/quality-by-part')
@login_required
def quality_by_part():
    """View all quality issues grouped by part number and revision (database-driven)."""
    part_id = request.args.get('part_id', type=int)
    part_number = request.args.get('part', '')
    part_revision = request.args.get('rev', '')
    
    # Get part from database - use part_id if provided, otherwise lookup by part_number
    part = None
    if part_id:
        part = query_db('SELECT * FROM parts WHERE id = ?', [part_id], one=True)
    elif part_number:
        # Lookup part by part_number and optionally revision
        if part_revision:
            part = query_db('SELECT * FROM parts WHERE part_number = ? AND part_revision = ?', 
                          [part_number, part_revision], one=True)
        else:
            # If no revision specified, get the first matching part_number (or most recent)
            part = query_db('SELECT * FROM parts WHERE part_number = ? ORDER BY created_at DESC LIMIT 1', 
                          [part_number], one=True)
    
    if part:
        # Use part_id for all queries to ensure database-driven accuracy
        if part_revision and part['part_revision'] != part_revision:
            # If specific revision requested, get that part
            part = query_db('SELECT * FROM parts WHERE part_number = ? AND part_revision = ?', 
                          [part['part_number'], part_revision], one=True)
            if not part:
                flash('Delrevision blev ikke fundet.', 'error')
                return redirect(url_for('quality_by_part'))
        
        # Show errors for this specific part (using part_id)
        errors = query_db('''
            SELECT er.*, j.internal_job_number as job_number, p.part_number, p.part_revision, j.drawing_number,
                   j.po_number, s.name as supplier_name,
                   u.username as reported_by_name
            FROM error_reports er
            JOIN jobs j ON er.job_id = j.id
            JOIN parts p ON j.part_id = p.id
            LEFT JOIN suppliers s ON er.supplier_id = s.id
            LEFT JOIN users u ON er.reported_by = u.id
            WHERE p.id = ?
            ORDER BY er.found_date DESC
        ''', [part['id']])
        
        # Show all jobs for this part
        jobs = query_db('''
            SELECT j.*, c.name as customer_name,
                   (SELECT COUNT(*) FROM error_reports WHERE job_id = j.id) as error_count
            FROM jobs j
            JOIN parts p ON j.part_id = p.id
            LEFT JOIN customers c ON j.customer_id = c.id
            WHERE p.id = ?
            ORDER BY j.created_at DESC
        ''', [part['id']])
        
        # Get all revisions for this part number (from parts table)
        revisions = query_db('''
            SELECT p.part_revision, 
                   COUNT(DISTINCT j.id) as job_count,
                   (SELECT COUNT(*) FROM error_reports er 
                    JOIN jobs j2 ON er.job_id = j2.id 
                    JOIN parts p2 ON j2.part_id = p2.id
                    WHERE p2.part_number = ? AND p2.part_revision = p.part_revision) as error_count
            FROM parts p
            LEFT JOIN jobs j ON j.part_id = p.id
            WHERE p.part_number = ?
            GROUP BY p.part_revision
            ORDER BY p.part_revision DESC
        ''', [part['part_number'], part['part_number']])
        
        return render_template('quality_by_part.html', part=part, part_number=part['part_number'], 
                             part_revision=part['part_revision'], errors=errors, jobs=jobs, revisions=revisions)
    
    # Show summary of all parts with error counts (from parts table)
    parts = query_db('''
        SELECT p.id, p.part_number, p.part_revision, p.part_description,
               COUNT(DISTINCT j.id) as job_count,
               COUNT(DISTINCT p2.id) as revision_count,
               (SELECT COUNT(*) FROM error_reports er 
                JOIN jobs j2 ON er.job_id = j2.id 
                JOIN parts p3 ON j2.part_id = p3.id
                WHERE p3.part_number = p.part_number) as error_count,
               (SELECT COUNT(*) FROM error_reports er 
                JOIN jobs j2 ON er.job_id = j2.id 
                JOIN parts p3 ON j2.part_id = p3.id
                WHERE p3.part_number = p.part_number AND er.status = 'open') as open_error_count,
               MAX(j.created_at) as last_used
        FROM parts p
        LEFT JOIN jobs j ON j.part_id = p.id
        LEFT JOIN parts p2 ON p2.part_number = p.part_number
        WHERE p.part_number IS NOT NULL AND p.part_number != ''
        GROUP BY p.part_number
        ORDER BY error_count DESC, p.part_number
    ''')
    
    return render_template('quality_by_part.html', parts=parts)


@app.route('/jobs/<int:job_id>/report-internal-error', methods=['GET', 'POST'])
@login_required
def internal_error_report(job_id):
    """Create an internal quality/error report for a job."""
    job = query_db('''
        SELECT j.*, c.name as customer_name
        FROM jobs j
        LEFT JOIN customers c ON j.customer_id = c.id
        WHERE j.id = ?
    ''', [job_id], one=True)
    
    if not job:
        flash('Ordren blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if request.method == 'POST':
        severity = request.form.get('severity', 'minor')
        description = request.form.get('description', '').strip()
        if not description:
            flash('Beskrivelse skal udfyldes.', 'error')
            return render_template('internal_error_form.html', job=job)
        
        affected_quantity = request.form.get('affected_quantity', type=int)
        workflow_stage = request.form.get('workflow_stage', job['workflow_stage'])
        
        error_id = execute_db('''
            INSERT INTO error_reports (job_id, reported_by, workflow_stage, severity, description,
                                      affected_quantity, error_type, status)
            VALUES (?, ?, ?, ?, ?, ?, 'internal', 'open')
        ''', [job_id, current_user.id, workflow_stage, severity, description, affected_quantity])
        
        # Notify Quality Managers + Admin
        for u in get_quality_notification_users():
            create_notification(
                u['id'],
                'error_report',
                f'Internal Quality Issue: {job["part_number"]}',
                f'Internal issue reported for Job {job["internal_job_number"]} (PO {job["po_number"]}). Severity: {severity}',
                'error_report',
                error_id
            )
        
        log_audit(current_user.id, 'error_report', error_id, 'created', f'Internal error for job {job["internal_job_number"]}')
        flash('Intern kvalitetsrapport oprettet. Admin og kvalitetsansvarlig er notificeret.', 'success')
        return redirect(url_for('error_report_detail', error_id=error_id))
    
    return render_template('internal_error_form.html', job=job)


@app.route('/material-control/<int:mc_id>/report-error', methods=['GET', 'POST'])
@login_required
def material_error_report(mc_id):
    """Create an error report for material from a supplier."""
    mc = query_db('''
        SELECT mc.*, s.name as supplier_name, j.internal_job_number as job_number, j.part_number as part_name
        FROM material_controls mc
        LEFT JOIN suppliers s ON mc.supplier_id = s.id
        JOIN jobs j ON mc.job_id = j.id
        WHERE mc.id = ?
    ''', [mc_id], one=True)
    
    if not mc:
        flash('Materialekontrol blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if request.method == 'POST':
        error_id = execute_db('''
            INSERT INTO error_reports (job_id, reported_by, workflow_stage, severity, description,
                                      affected_quantity, error_type, supplier_id, material_control_id, status)
            VALUES (?, ?, 'material_control', ?, ?, ?, 'material_supplier', ?, ?, 'open')
        ''', [
            mc['job_id'],
            current_user.id,
            request.form['severity'],
            request.form['description'],
            request.form.get('affected_quantity') or None,
            mc['supplier_id'],
            mc_id
        ])
        
        # Notify Quality Managers + Admin (under development)
        job = query_db('SELECT po_number, part_number FROM jobs WHERE id = ?', [mc['job_id']], one=True)
        for u in get_quality_notification_users():
            create_notification(
                u['id'],
                'error_report',
                f'New Quality Issue: {job["part_number"]}',
                f'Material supplier issue reported for PO {job["po_number"]}. Severity: {request.form["severity"]}',
                'error_report',
                error_id
            )
        
        # Update material control status to rejected if not already
        if mc['status'] != 'rejected':
            execute_db('UPDATE material_controls SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                      ['rejected', mc_id])
        
        log_audit(current_user.id, 'error_report', error_id, 'created', f'Material supplier error for MC#{mc_id}')
        flash('Leverandørfejlrapport oprettet.', 'success')
        return redirect(url_for('error_report_detail', error_id=error_id))
    
    return render_template('supplier_error_form.html', mc=mc, error_type='material')


@app.route('/external-process/<int:ep_id>/report-error', methods=['GET', 'POST'])
@login_required
def external_error_report(ep_id):
    """Create an error report for external process supplier."""
    ep = query_db('''
        SELECT ep.*, s.name as supplier_name, j.internal_job_number as job_number, j.part_number as part_name
        FROM external_processes ep
        LEFT JOIN suppliers s ON ep.supplier_id = s.id
        JOIN jobs j ON ep.job_id = j.id
        WHERE ep.id = ?
    ''', [ep_id], one=True)
    
    if not ep:
        flash('Ekstern proces blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if request.method == 'POST':
        error_id = execute_db('''
            INSERT INTO error_reports (job_id, reported_by, workflow_stage, severity, description,
                                      affected_quantity, error_type, supplier_id, external_process_id, status)
            VALUES (?, ?, 'external_process', ?, ?, ?, 'external_supplier', ?, ?, 'open')
        ''', [
            ep['job_id'],
            current_user.id,
            request.form['severity'],
            request.form['description'],
            request.form.get('affected_quantity') or None,
            ep['supplier_id'],
            ep_id
        ])
        
        # Notify Quality Managers + Admin (under development)
        job = query_db('SELECT po_number, part_number FROM jobs WHERE id = ?', [ep['job_id']], one=True)
        for u in get_quality_notification_users():
            create_notification(
                u['id'],
                'error_report',
                f'New Quality Issue: {job["part_number"]}',
                f'External process supplier issue reported for PO {job["po_number"]}. Severity: {request.form["severity"]}',
                'error_report',
                error_id
            )
        
        # Update external process status to rejected if not already
        if ep['status'] != 'rejected':
            execute_db('UPDATE external_processes SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                      ['rejected', ep_id])
        
        log_audit(current_user.id, 'error_report', error_id, 'created', f'External supplier error for EP#{ep_id}')
        flash('Leverandørfejlrapport oprettet.', 'success')
        return redirect(url_for('error_report_detail', error_id=error_id))
    
    return render_template('supplier_error_form.html', ep=ep, error_type='external')


@app.route('/error-report/<int:error_id>')
@login_required
def error_report_detail(error_id):
    """View error report details."""
    error = query_db('''
        SELECT er.*, j.internal_job_number as job_number, j.part_number as part_name, j.customer_id,
               s.name as supplier_name, s.supplier_type,
               u.username as reported_by_name,
               a.username as assigned_to_name
        FROM error_reports er
        JOIN jobs j ON er.job_id = j.id
        LEFT JOIN suppliers s ON er.supplier_id = s.id
        LEFT JOIN users u ON er.reported_by = u.id
        LEFT JOIN users a ON er.assigned_to = a.id
        WHERE er.id = ?
    ''', [error_id], one=True)
    
    if not error:
        flash('Fejlrapport blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    # Get attachments
    attachments = query_db('SELECT * FROM attachments WHERE entity_type = ? AND entity_id = ?',
                          ['error_report', error_id])
    
    # Get users for assignment
    users = query_db('SELECT id, username as full_name FROM users WHERE active = 1 ORDER BY username')
    
    return render_template('error_report_detail.html', error=error, attachments=attachments, users=users)


@app.route('/error-report/<int:error_id>/update', methods=['POST'])
@login_required
def error_report_update(error_id):
    """Update error report (disposition, root cause, corrective action, status)."""
    error = query_db('SELECT * FROM error_reports WHERE id = ?', [error_id], one=True)
    if not error:
        flash('Fejlrapport blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    action = request.form.get('action')
    
    if action == 'update':
        execute_db('''
            UPDATE error_reports SET
                disposition = ?,
                root_cause = ?,
                corrective_action = ?,
                assigned_to = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', [
            request.form.get('disposition'),
            request.form.get('root_cause'),
            request.form.get('corrective_action'),
            request.form.get('assigned_to') or None,
            error_id
        ])
        flash('Fejlrapport opdateret.', 'success')
    
    elif action == 'resolve':
        execute_db('''
            UPDATE error_reports SET status = 'resolved', resolved_date = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', [error_id])
        flash('Fejlrapport markeret som løst.', 'success')
    
    elif action == 'close':
        execute_db('''
            UPDATE error_reports SET status = 'closed', closed_date = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', [error_id])
        flash('Fejlrapport lukket.', 'success')
    
    elif action == 'reopen':
        execute_db('''
            UPDATE error_reports SET status = 'open', resolved_date = NULL, closed_date = NULL,
                   updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', [error_id])
        flash('Fejlrapport genåbnet.', 'success')
    
    log_audit(current_user.id, 'error_report', error_id, action, f'Error report {action}')
    return redirect(url_for('error_report_detail', error_id=error_id))


@app.route('/error-report/<int:error_id>/upload', methods=['POST'])
@login_required
def error_report_upload(error_id):
    """Upload attachment to error report (photos, documents)."""
    error = query_db('SELECT * FROM error_reports WHERE id = ?', [error_id], one=True)
    if not error:
        flash('Fejlrapport blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if 'file' not in request.files:
        flash('Vælg en fil.', 'error')
        return redirect(url_for('error_report_detail', error_id=error_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('Vælg en fil.', 'error')
        return redirect(url_for('error_report_detail', error_id=error_id))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        upload_path = os.path.join('photos', filename)
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_path)
        file.save(full_path)
        
        execute_db('''
            INSERT INTO attachments (entity_type, entity_id, file_path, file_name, file_type, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ['error_report', error_id, upload_path, file.filename, request.form.get('file_type', 'photo'),
              current_user.id])
        
        flash('Fil uploadet.', 'success')
    else:
        flash('Ugyldig filtype.', 'error')
    
    return redirect(url_for('error_report_detail', error_id=error_id))


# =============================================================================
# External Process Routes
# =============================================================================

@app.route('/jobs/<int:job_id>/external-process/new', methods=['GET', 'POST'])
@login_required
def external_process_create(job_id):
    """Create a new external process record for a job."""
    job = query_db('SELECT * FROM jobs WHERE id = ?', [job_id], one=True)
    if not job:
        flash('Ordren blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    suppliers = query_db("SELECT * FROM suppliers WHERE active = 1 AND (supplier_type = 'external' OR supplier_type = 'both') ORDER BY name")
    
    if request.method == 'POST':
        ep_id = execute_db('''
            INSERT INTO external_processes (job_id, supplier_id, process_type, quantity_sent, sent_date,
                                          expected_return_date, po_number, notes, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'sent', ?)
        ''', [
            job_id,
            request.form.get('supplier_id') or None,
            request.form['process_type'],
            request.form.get('quantity_sent') or None,
            request.form.get('sent_date') or None,
            request.form.get('expected_return_date') or None,
            request.form.get('po_number'),
            request.form.get('notes'),
            current_user.id
        ])
        
        log_audit(current_user.id, 'external_process', ep_id, 'created', f'External process for job {job["job_number"]}')
        flash('Ekstern proces oprettet.', 'success')
        return redirect(url_for('external_process_detail', ep_id=ep_id))
    
    return render_template('external_process.html', job=job, ep=None, suppliers=suppliers, edit_mode=False, view_mode=False)


@app.route('/external-process/<int:ep_id>')
@login_required
def external_process_detail(ep_id):
    """View external process details."""
    ep = query_db('''
        SELECT ep.*, s.name as supplier_name, j.internal_job_number as job_number, j.part_number, j.po_number as job_po,
               u.username as created_by_username, ui.username as inspected_by_username
        FROM external_processes ep
        LEFT JOIN suppliers s ON ep.supplier_id = s.id
        JOIN jobs j ON ep.job_id = j.id
        LEFT JOIN users u ON ep.created_by = u.id
        LEFT JOIN users ui ON ep.inspected_by = ui.id
        WHERE ep.id = ?
    ''', [ep_id], one=True)
    
    if not ep:
        flash('Ekstern proces blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    job = query_db('SELECT * FROM jobs WHERE id = ?', [ep['job_id']], one=True)
    attachments = query_db('''
        SELECT a.*, u.username as uploaded_by_username
        FROM attachments a
        LEFT JOIN users u ON a.uploaded_by = u.id
        WHERE a.entity_type = 'external_process' AND a.entity_id = ?
        ORDER BY a.uploaded_at DESC
    ''', [ep_id])
    
    # Get any error reports linked to this external process
    errors = query_db('SELECT * FROM error_reports WHERE external_process_id = ? ORDER BY found_date DESC', [ep_id])
    
    return render_template('external_process.html', job=job, ep=ep, attachments=attachments, errors=errors,
                         view_mode=True, edit_mode=False)


@app.route('/external-process/<int:ep_id>/edit', methods=['GET', 'POST'])
@login_required
def external_process_edit(ep_id):
    """Edit external process record."""
    ep = query_db('SELECT * FROM external_processes WHERE id = ?', [ep_id], one=True)
    if not ep:
        flash('Ekstern proces blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    job = query_db('SELECT * FROM jobs WHERE id = ?', [ep['job_id']], one=True)
    suppliers = query_db("SELECT * FROM suppliers WHERE active = 1 AND (supplier_type = 'external' OR supplier_type = 'both') ORDER BY name")
    
    if request.method == 'POST':
        execute_db('''
            UPDATE external_processes SET
                supplier_id = ?, process_type = ?, quantity_sent = ?, sent_date = ?,
                expected_return_date = ?, po_number = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', [
            request.form.get('supplier_id') or None,
            request.form['process_type'],
            request.form.get('quantity_sent') or None,
            request.form.get('sent_date') or None,
            request.form.get('expected_return_date') or None,
            request.form.get('po_number'),
            request.form.get('notes'),
            ep_id
        ])
        
        log_audit(current_user.id, 'external_process', ep_id, 'updated', 'External process updated')
        flash('Ekstern proces opdateret.', 'success')
        return redirect(url_for('external_process_detail', ep_id=ep_id))
    
    return render_template('external_process.html', job=job, ep=ep, suppliers=suppliers, 
                         edit_mode=True, view_mode=False)


@app.route('/external-process/<int:ep_id>/receive', methods=['POST'])
@login_required
def external_process_receive(ep_id):
    """Record receipt of parts from external process."""
    ep = query_db('SELECT * FROM external_processes WHERE id = ?', [ep_id], one=True)
    if not ep:
        flash('Ekstern proces blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    execute_db('''
        UPDATE external_processes SET
            status = 'received',
            actual_return_date = CURRENT_TIMESTAMP,
            quantity_received = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', [request.form.get('quantity_received') or ep['quantity_sent'], ep_id])
    
    flash('Dele modtaget fra ekstern proces.', 'success')
    return redirect(url_for('external_process_detail', ep_id=ep_id))


@app.route('/external-process/<int:ep_id>/inspect', methods=['POST'])
@login_required
def external_process_inspect(ep_id):
    """Record inspection of returned parts."""
    ep = query_db('SELECT * FROM external_processes WHERE id = ?', [ep_id], one=True)
    if not ep:
        flash('Ekstern proces blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    status = request.form.get('status')  # 'approved' or 'rejected'
    
    execute_db('''
        UPDATE external_processes SET
            status = ?,
            inspected_by = ?,
            inspection_date = CURRENT_TIMESTAMP,
            inspection_notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', [status, current_user.id, request.form.get('inspection_notes'), ep_id])
    
    # Notify QM + Admin when external process is rejected
    if status == 'rejected':
        job = query_db('SELECT po_number, part_number, internal_job_number FROM jobs WHERE id = ?', [ep['job_id']], one=True)
        if job:
            for u in get_quality_notification_users():
                create_notification(
                    u['id'],
                    'external_rejected',
                    f'External Process Rejected: {job["part_number"]}',
                    f'External process for Job {job["internal_job_number"]} (PO {job["po_number"]}) was rejected after inspection.',
                    'external_process',
                    ep_id
                )
    
    flash(f'Ekstern proces {status}.', 'success')
    return redirect(url_for('external_process_detail', ep_id=ep_id))


@app.route('/external-process/<int:ep_id>/upload', methods=['POST'])
@login_required
def external_process_upload(ep_id):
    """Upload attachment to external process (certificates, photos)."""
    ep = query_db('SELECT * FROM external_processes WHERE id = ?', [ep_id], one=True)
    if not ep:
        flash('Ekstern proces blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if 'file' not in request.files:
        flash('Vælg en fil.', 'error')
        return redirect(url_for('external_process_detail', ep_id=ep_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('Vælg en fil.', 'error')
        return redirect(url_for('external_process_detail', ep_id=ep_id))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        file_type = 'image' if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) else 'pdf'
        upload_path = os.path.join('certificates', filename)
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_path)
        file.save(full_path)
        
        execute_db('''
            INSERT INTO attachments (entity_type, entity_id, file_path, file_name, file_type, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ['external_process', ep_id, upload_path, file.filename, file_type, current_user.id])
        
        flash('Fil uploadet.', 'success')
    else:
        flash('Ugyldig filtype.', 'error')
    
    return redirect(url_for('external_process_detail', ep_id=ep_id))


# =============================================================================
# Exit Control Routes
# =============================================================================

@app.route('/jobs/<int:job_id>/exit-control/new', methods=['GET', 'POST'])
@login_required
def exit_control_create(job_id):
    """Create a new exit control inspection for a job."""
    job = query_db('SELECT * FROM jobs WHERE id = ?', [job_id], one=True)
    if not job:
        flash('Ordren blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if request.method == 'POST':
        lot_quantity = request.form.get('lot_quantity', type=int) or job['quantity']
        
        # Create exit control record
        ec_id = execute_db('''
            INSERT INTO exit_controls (job_id, inspector_id, lot_quantity, overall_status, notes)
            VALUES (?, ?, ?, 'in_progress', ?)
        ''', [job_id, current_user.id, lot_quantity, request.form.get('notes', '')])
        
        # Calculate and create sample records
        samples = calculate_exit_control_samples(lot_quantity)
        for part_num in samples:
            execute_db('''
                INSERT INTO exit_control_samples (exit_control_id, part_number)
                VALUES (?, ?)
            ''', [ec_id, part_num])
        
        log_audit(current_user.id, 'exit_control', ec_id, 'created', 
                 f'Exit control for job {job["internal_job_number"]}, {len(samples)} samples')
        flash(f'Slutkontrol oprettet med {len(samples)} prøver at inspicere.', 'success')
        return redirect(url_for('exit_control_detail', ec_id=ec_id))
    
    # Calculate preview of samples
    preview_samples = calculate_exit_control_samples(job['quantity'])
    
    return render_template('exit_control.html', job=job, ec=None, 
                         preview_samples=preview_samples, view_mode=False)


@app.route('/exit-control/<int:ec_id>')
@login_required
def exit_control_detail(ec_id):
    """View exit control details and record sample inspections."""
    ec = query_db('''
        SELECT ec.*, j.internal_job_number as job_number, j.part_number, j.part_revision,
               j.quantity as job_quantity, j.po_number, u.username as inspector_name
        FROM exit_controls ec
        JOIN jobs j ON ec.job_id = j.id
        LEFT JOIN users u ON ec.inspector_id = u.id
        WHERE ec.id = ?
    ''', [ec_id], one=True)
    
    if not ec:
        flash('Slutkontrol blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    job = query_db('SELECT * FROM jobs WHERE id = ?', [ec['job_id']], one=True)
    
    # Get all samples
    samples = query_db('''
        SELECT * FROM exit_control_samples 
        WHERE exit_control_id = ? 
        ORDER BY part_number
    ''', [ec_id])
    
    # Calculate stats
    total_samples = len(samples)
    inspected = len([s for s in samples if s['overall_pass'] is not None])
    passed = len([s for s in samples if s['overall_pass'] == 1])
    failed = len([s for s in samples if s['overall_pass'] == 0])
    
    return render_template('exit_control.html', job=job, ec=ec, samples=samples,
                         total_samples=total_samples, inspected=inspected,
                         passed=passed, failed=failed, view_mode=True)


@app.route('/exit-control/<int:ec_id>/sample/<int:sample_id>', methods=['POST'])
@login_required
def exit_control_record_sample(ec_id, sample_id):
    """Record inspection result for a single sample."""
    sample = query_db('SELECT * FROM exit_control_samples WHERE id = ? AND exit_control_id = ?',
                     [sample_id, ec_id], one=True)
    if not sample:
        flash('Prøve blev ikke fundet.', 'error')
        return redirect(url_for('exit_control_detail', ec_id=ec_id))
    
    dimensions_ok = 1 if request.form.get('dimensions_ok') else 0
    visual_ok = 1 if request.form.get('visual_ok') else 0
    surface_ok = 1 if request.form.get('surface_ok') else 0
    overall_pass = 1 if (dimensions_ok and visual_ok and surface_ok) else 0
    
    execute_db('''
        UPDATE exit_control_samples SET
            dimensions_ok = ?, visual_ok = ?, surface_ok = ?,
            overall_pass = ?, notes = ?, inspected_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', [dimensions_ok, visual_ok, surface_ok, overall_pass, 
          request.form.get('notes', ''), sample_id])
    
    # Check if all samples are inspected and update overall status
    samples = query_db('SELECT * FROM exit_control_samples WHERE exit_control_id = ?', [ec_id])
    all_inspected = all(s['overall_pass'] is not None for s in samples)
    
    if all_inspected:
        all_passed = all(s['overall_pass'] == 1 for s in samples)
        status = 'passed' if all_passed else 'failed'
        execute_db('UPDATE exit_controls SET overall_status = ? WHERE id = ?', [status, ec_id])
        
        # Update job stage if passed
        if all_passed:
            ec = query_db('SELECT job_id FROM exit_controls WHERE id = ?', [ec_id], one=True)
            execute_db('''
                UPDATE jobs SET workflow_stage = 'complete', completed_at = CURRENT_TIMESTAMP 
                WHERE id = ? AND workflow_stage = 'exit_control'
            ''', [ec['job_id']])
    
    flash(f'Del #{sample["part_number"]} registreret som {"OK" if overall_pass else "FEJL"}.', 
          'success' if overall_pass else 'warning')
    return redirect(url_for('exit_control_detail', ec_id=ec_id))


@app.route('/exit-control/<int:ec_id>/complete', methods=['POST'])
@login_required
def exit_control_complete(ec_id):
    """Mark exit control as complete and update job status."""
    ec = query_db('SELECT * FROM exit_controls WHERE id = ?', [ec_id], one=True)
    if not ec:
        flash('Slutkontrol blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    # Check all samples inspected
    samples = query_db('SELECT * FROM exit_control_samples WHERE exit_control_id = ?', [ec_id])
    uninspected = [s for s in samples if s['overall_pass'] is None]
    
    if uninspected:
        flash(f'{len(uninspected)} prøver mangler endnu inspektion.', 'error')
        return redirect(url_for('exit_control_detail', ec_id=ec_id))
    
    # Determine overall result
    all_passed = all(s['overall_pass'] == 1 for s in samples)
    status = 'passed' if all_passed else 'failed'
    
    execute_db('UPDATE exit_controls SET overall_status = ? WHERE id = ?', [status, ec_id])
    
    if all_passed:
        execute_db('''
            UPDATE jobs SET workflow_stage = 'complete', completed_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', [ec['job_id']])
        flash('Slutkontrol bestået. Ordre markeret som færdig.', 'success')
    else:
        flash('Slutkontrol ikke bestået. Gennemgå fejlede prøver og opret fejlrapporter.', 'warning')
    
    log_audit(current_user.id, 'exit_control', ec_id, 'completed', f'Status: {status}')
    return redirect(url_for('exit_control_detail', ec_id=ec_id))


@app.route('/exit-control/<int:ec_id>/add-samples', methods=['POST'])
@login_required
def exit_control_add_samples(ec_id):
    """Add additional sample parts to inspect."""
    ec = query_db('SELECT * FROM exit_controls WHERE id = ?', [ec_id], one=True)
    if not ec:
        flash('Slutkontrol blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    part_numbers = request.form.get('part_numbers', '').strip()
    if not part_numbers:
        flash('Ingen delenumre angivet.', 'error')
        return redirect(url_for('exit_control_detail', ec_id=ec_id))
    
    added = 0
    for num in part_numbers.replace(',', ' ').split():
        try:
            part_num = int(num.strip())
            # Check if already exists
            existing = query_db('''
                SELECT id FROM exit_control_samples 
                WHERE exit_control_id = ? AND part_number = ?
            ''', [ec_id, part_num], one=True)
            
            if not existing and 1 <= part_num <= ec['lot_quantity']:
                execute_db('''
                    INSERT INTO exit_control_samples (exit_control_id, part_number)
                    VALUES (?, ?)
                ''', [ec_id, part_num])
                added += 1
        except ValueError:
            continue
    
    if added:
        flash(f'{added} ekstra prøve(r) tilføjet.', 'success')
    else:
        flash('Ingen nye prøver tilføjet.', 'warning')
    
    return redirect(url_for('exit_control_detail', ec_id=ec_id))


# =============================================================================
# Measurement Report Routes
# =============================================================================

@app.route('/jobs/<int:job_id>/measurements/new', methods=['GET', 'POST'])
@login_required
def measurement_report_create(job_id):
    """Create a new measurement report for a job."""
    job = query_db('SELECT * FROM jobs WHERE id = ?', [job_id], one=True)
    if not job:
        flash('Ordren blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    # Get dimensions for this job
    dimensions = query_db('SELECT * FROM job_dimensions WHERE job_id = ? ORDER BY dimension_number', [job_id])
    
    if not dimensions:
        flash('Ingen dimensioner defineret for ordren. Tilføj dimensioner før du opretter en målerapport.', 'error')
        return redirect(url_for('job_detail', job_id=job_id))
    
    if request.method == 'POST':
        report_type = request.form.get('report_type', 'in_process')
        notes = request.form.get('notes', '').strip()
        
        # Create the report
        report_id = execute_db('''
            INSERT INTO measurement_reports (job_id, report_type, inspector_id, notes)
            VALUES (?, ?, ?, ?)
        ''', [job_id, report_type, current_user.id, notes])
        
        # Process measurements
        overall_pass = True
        for dim in dimensions:
            actual_value_str = request.form.get(f'actual_{dim["id"]}', '').strip()
            if actual_value_str:
                try:
                    actual_value = float(actual_value_str)
                    
                    # Calculate pass/fail
                    pass_fail = calculate_pass_fail(dim, actual_value)
                    if pass_fail == 'fail':
                        overall_pass = False
                    
                    equipment_id = request.form.get(f'equipment_{dim["id"]}') or None
                    sample_num = request.form.get(f'sample_{dim["id"]}', 1, type=int)
                    measurement_notes = request.form.get(f'notes_{dim["id"]}', '').strip()
                    
                    execute_db('''
                        INSERT INTO measurements (report_id, job_dimension_id, actual_value, 
                                                 pass_fail, equipment_id, sample_number, 
                                                 measured_by, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', [report_id, dim['id'], actual_value, pass_fail, equipment_id, 
                          sample_num, current_user.id, measurement_notes])
                except ValueError:
                    pass  # Skip invalid values
        
        # Update overall status
        overall_status = 'pass' if overall_pass else 'fail'
        # Check if any measurements were recorded
        measurement_count = query_db('SELECT COUNT(*) as count FROM measurements WHERE report_id = ?', 
                                    [report_id], one=True)['count']
        if measurement_count == 0:
            overall_status = 'pending'
        
        execute_db('UPDATE measurement_reports SET overall_status = ? WHERE id = ?', 
                  [overall_status, report_id])
        
        log_audit('create', 'measurement_report', report_id, 
                 f'Created {report_type} measurement report for job {job["internal_job_number"]}')
        
        flash('Målerapport oprettet.', 'success')
        return redirect(url_for('measurement_report_detail', report_id=report_id))
    
    # GET request - show form
    equipment = query_db('SELECT * FROM equipment WHERE active = 1 ORDER BY name')
    return render_template('measurement_report.html', job=job, dimensions=dimensions, 
                          equipment=equipment, report=None, measurements=None, edit_mode=False)


def calculate_pass_fail(dimension, actual_value):
    """Calculate if a measurement passes or fails based on tolerances."""
    nominal = dimension['nominal_value']
    tol_plus = dimension['tolerance_plus']
    tol_minus = dimension['tolerance_minus']
    
    # Handle go/no-go or other non-numeric checks
    if dimension['unit'] == 'go/nogo':
        return 'pass' if actual_value == 1 else 'fail'
    
    # Calculate upper and lower limits
    if tol_plus is not None and tol_minus is not None:
        upper_limit = nominal + tol_plus
        lower_limit = nominal + tol_minus  # tol_minus is typically negative
        
        if lower_limit <= actual_value <= upper_limit:
            return 'pass'
        else:
            return 'fail'
    
    return 'pass'  # If no tolerances defined, assume pass


@app.route('/measurements/<int:report_id>')
@login_required
def measurement_report_detail(report_id):
    """View a measurement report."""
    report = query_db('''
        SELECT mr.*, j.internal_job_number, j.po_number, j.part_number, j.quantity,
               u.username as inspector_username
        FROM measurement_reports mr
        JOIN jobs j ON mr.job_id = j.id
        LEFT JOIN users u ON mr.inspector_id = u.id
        WHERE mr.id = ?
    ''', [report_id], one=True)
    
    if not report:
        flash('Målerapport blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    # Get dimensions with their measurements
    dimensions = query_db('''
        SELECT jd.*, 
               m.id as measurement_id, m.actual_value, m.pass_fail, m.sample_number, m.notes as measurement_notes,
               e.name as equipment_name
        FROM job_dimensions jd
        LEFT JOIN measurements m ON jd.id = m.job_dimension_id AND m.report_id = ?
        LEFT JOIN equipment e ON m.equipment_id = e.id
        WHERE jd.job_id = ?
        ORDER BY jd.dimension_number, m.sample_number
    ''', [report_id, report['job_id']])
    
    # Get attachments (scanned sheets)
    attachments = query_db('''
        SELECT a.*, u.username as uploaded_by_username
        FROM attachments a
        LEFT JOIN users u ON a.uploaded_by = u.id
        WHERE a.entity_type = 'measurement_report' AND a.entity_id = ?
        ORDER BY a.uploaded_at DESC
    ''', [report_id])
    
    job = query_db('SELECT * FROM jobs WHERE id = ?', [report['job_id']], one=True)
    equipment = query_db('SELECT * FROM equipment WHERE active = 1 ORDER BY name')
    
    return render_template('measurement_report.html', job=job, report=report, 
                          dimensions=dimensions, attachments=attachments,
                          equipment=equipment, edit_mode=False, view_mode=True)


@app.route('/measurements/<int:report_id>/edit', methods=['GET', 'POST'])
@login_required
def measurement_report_edit(report_id):
    """Edit a measurement report - add or update measurements."""
    report = query_db('''
        SELECT mr.*, j.internal_job_number, j.id as job_id
        FROM measurement_reports mr
        JOIN jobs j ON mr.job_id = j.id
        WHERE mr.id = ?
    ''', [report_id], one=True)
    
    if not report:
        flash('Målerapport blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    job = query_db('SELECT * FROM jobs WHERE id = ?', [report['job_id']], one=True)
    dimensions = query_db('SELECT * FROM job_dimensions WHERE job_id = ? ORDER BY dimension_number', 
                         [report['job_id']])
    
    if request.method == 'POST':
        notes = request.form.get('notes', '').strip()
        
        # Update report notes
        execute_db('UPDATE measurement_reports SET notes = ? WHERE id = ?', [notes, report_id])
        
        # Process measurements
        overall_pass = True
        has_measurements = False
        
        for dim in dimensions:
            actual_value_str = request.form.get(f'actual_{dim["id"]}', '').strip()
            if actual_value_str:
                has_measurements = True
                try:
                    actual_value = float(actual_value_str)
                    pass_fail = calculate_pass_fail(dim, actual_value)
                    if pass_fail == 'fail':
                        overall_pass = False
                    
                    equipment_id = request.form.get(f'equipment_{dim["id"]}') or None
                    sample_num = request.form.get(f'sample_{dim["id"]}', 1, type=int)
                    measurement_notes = request.form.get(f'notes_{dim["id"]}', '').strip()
                    
                    # Check if measurement exists for this dimension
                    existing = query_db('''
                        SELECT id FROM measurements 
                        WHERE report_id = ? AND job_dimension_id = ? AND sample_number = ?
                    ''', [report_id, dim['id'], sample_num], one=True)
                    
                    if existing:
                        execute_db('''
                            UPDATE measurements SET actual_value = ?, pass_fail = ?, 
                                   equipment_id = ?, notes = ?, measured_by = ?, 
                                   measured_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', [actual_value, pass_fail, equipment_id, measurement_notes, 
                              current_user.id, existing['id']])
                    else:
                        execute_db('''
                            INSERT INTO measurements (report_id, job_dimension_id, actual_value, 
                                                     pass_fail, equipment_id, sample_number, 
                                                     measured_by, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', [report_id, dim['id'], actual_value, pass_fail, equipment_id, 
                              sample_num, current_user.id, measurement_notes])
                except ValueError:
                    pass
        
        # Update overall status
        if has_measurements:
            overall_status = 'pass' if overall_pass else 'fail'
        else:
            overall_status = 'pending'
        
        execute_db('UPDATE measurement_reports SET overall_status = ? WHERE id = ?', 
                  [overall_status, report_id])
        
        flash('Målerapport opdateret.', 'success')
        return redirect(url_for('measurement_report_detail', report_id=report_id))
    
    # GET - get existing measurements
    measurements = {}
    existing_measurements = query_db('''
        SELECT * FROM measurements WHERE report_id = ?
    ''', [report_id])
    for m in existing_measurements:
        measurements[m['job_dimension_id']] = dict(m)
    
    equipment = query_db('SELECT * FROM equipment WHERE active = 1 ORDER BY name')
    
    return render_template('measurement_report.html', job=job, report=report,
                          dimensions=dimensions, measurements=measurements,
                          equipment=equipment, edit_mode=True, view_mode=False)


@app.route('/measurements/<int:report_id>/upload', methods=['POST'])
@login_required
def measurement_report_upload(report_id):
    """Upload a scanned measurement sheet to a report."""
    report = query_db('SELECT * FROM measurement_reports WHERE id = ?', [report_id], one=True)
    if not report:
        flash('Målerapport blev ikke fundet.', 'error')
        return redirect(url_for('jobs_list'))
    
    if 'file' not in request.files:
        flash('Vælg en fil.', 'error')
        return redirect(url_for('measurement_report_detail', report_id=report_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('Vælg en fil.', 'error')
        return redirect(url_for('measurement_report_detail', report_id=report_id))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"MR{report_id}_{timestamp}_{filename}"
        
        file_path = os.path.join('photos', filename)
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], file_path)
        file.save(full_path)
        
        # Determine file type
        ext = filename.rsplit('.', 1)[1].lower()
        file_type = 'image' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'pdf' if ext == 'pdf' else 'other'
        
        execute_db('''
            INSERT INTO attachments (entity_type, entity_id, file_name, file_path, file_type, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ['measurement_report', report_id, file.filename, file_path, file_type, current_user.id])
        
        flash('Måleark uploadet.', 'success')
    else:
        flash('Ugyldig filtype. Tilladte: billeder og PDF.', 'error')
    
    return redirect(url_for('measurement_report_detail', report_id=report_id))


@app.route('/measurements/<int:report_id>/attachment/<int:attachment_id>/delete', methods=['POST'])
@login_required
def measurement_attachment_delete(report_id, attachment_id):
    """Delete an attachment from a measurement report."""
    attachment = query_db('SELECT * FROM attachments WHERE id = ? AND entity_type = ? AND entity_id = ?',
                         [attachment_id, 'measurement_report', report_id], one=True)
    if attachment:
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment['file_path'])
        if os.path.exists(full_path):
            os.remove(full_path)
        execute_db('DELETE FROM attachments WHERE id = ?', [attachment_id])
        flash('Vedhæftning slettet.', 'success')
    
    return redirect(url_for('measurement_report_detail', report_id=report_id))


# =============================================================================
# API Endpoints for AJAX
# =============================================================================

@app.route('/api/jobs/<int:job_id>/dimensions')
@login_required
def api_get_dimensions(job_id):
    """Get dimensions for a job (for copying)."""
    dimensions = query_db('SELECT * FROM job_dimensions WHERE job_id = ? ORDER BY dimension_number', [job_id])
    return jsonify([dict(d) for d in dimensions])


# =============================================================================
# CLI Commands
# =============================================================================

@app.cli.command('init-db')
def init_db_command():
    """Initialize the database."""
    init_db()
    print('Database initialized.')


@app.cli.command('create-admin')
def create_admin_command():
    """Create default admin user."""
    init_db()
    existing = query_db('SELECT id FROM users WHERE username = ?', ['admin'], one=True)
    if existing:
        print('Admin user already exists.')
        return
    
    password_hash = generate_password_hash('admin')
    execute_db('''
        INSERT INTO users (username, email, password_hash, role) 
        VALUES (?, ?, ?, ?)
    ''', ['admin', 'admin@localhost', password_hash, 'admin'])
    print('Admin user created. Username: admin, Password: admin')
    print('IMPORTANT: Change the password after first login!')


# =============================================================================
# Run Application
# =============================================================================

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, port=5000)
