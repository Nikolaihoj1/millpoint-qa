#!/usr/bin/env python3
"""
Seed script to populate development database with sample data.
Run with: python seed_dev_db.py
"""

import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'qa.db')


def seed_database():
    """Seed the database with sample data."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print("Seeding database...")
    
    # Create admin user if not exists
    cur.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        cur.execute('''
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', ['admin', 'admin@millpoint.dk', generate_password_hash('admin'), 'admin'])
        print("  Created admin user (password: admin)")
    
    # Create sample users
    sample_users = [
        ('inspector1', 'inspector1@millpoint.dk', 'inspector', 'inspector123'),
        ('operator1', 'operator1@millpoint.dk', 'operator', 'operator123'),
        ('qm', 'quality@millpoint.dk', 'quality_manager', 'quality123'),
    ]
    
    for username, email, role, password in sample_users:
        cur.execute("SELECT id FROM users WHERE username = ?", [username])
        if not cur.fetchone():
            cur.execute('''
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, ?)
            ''', [username, email, generate_password_hash(password), role])
            print(f"  Created user: {username} (password: {password})")
    
    # Create sample customers
    sample_customers = [
        ('Acme Manufacturing', 'John Smith', 'john@acme.com', '+45 12 34 56 78'),
        ('Nordic Parts A/S', 'Erik Hansen', 'erik@nordicparts.dk', '+45 22 33 44 55'),
        ('TechCorp Industries', 'Maria Jensen', 'maria@techcorp.com', '+45 33 44 55 66'),
    ]
    
    for name, contact, email, phone in sample_customers:
        cur.execute("SELECT id FROM customers WHERE name = ?", [name])
        if not cur.fetchone():
            cur.execute('''
                INSERT INTO customers (name, contact_person, email, phone)
                VALUES (?, ?, ?, ?)
            ''', [name, contact, email, phone])
            print(f"  Created customer: {name}")
    
    # Create sample suppliers
    sample_suppliers = [
        ('Steel Supply Co', 'material', 'Lars Berg', 'lars@steelsupply.dk', '+45 44 55 66 77', None),
        ('Metal Masters', 'material', 'Peter Holm', 'peter@metalmasters.dk', '+45 55 66 77 88', None),
        ('Anodize Denmark', 'external_process', 'Anna Skov', 'anna@anodizedk.dk', '+45 66 77 88 99', 'anodize, hard anodize'),
        ('Paint Pro ApS', 'external_process', 'Niels Lund', 'niels@paintpro.dk', '+45 77 88 99 00', 'paint, powder coat'),
        ('Heat Treat Solutions', 'external_process', 'Karen Møller', 'karen@heattreat.dk', '+45 88 99 00 11', 'heat treatment, hardening'),
    ]
    
    for name, stype, contact, email, phone, processes in sample_suppliers:
        cur.execute("SELECT id FROM suppliers WHERE name = ?", [name])
        if not cur.fetchone():
            cur.execute('''
                INSERT INTO suppliers (name, supplier_type, contact_person, email, phone, processes_offered)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', [name, stype, contact, email, phone, processes])
            print(f"  Created supplier: {name}")
    
    # Create sample equipment
    sample_equipment = [
        ('Digital Caliper 150mm', 'caliper', 'CAL-001', 'Mitutoyo', 365),
        ('Micrometer 0-25mm', 'micrometer', 'MIC-001', 'Mitutoyo', 365),
        ('Micrometer 25-50mm', 'micrometer', 'MIC-002', 'Mitutoyo', 365),
        ('Height Gauge', 'gauge', 'HG-001', 'Tesa', 365),
        ('Thread Gauge M6', 'gauge', 'TG-M6', 'Generic', 730),
        ('Thread Gauge M8', 'gauge', 'TG-M8', 'Generic', 730),
        ('Surface Roughness Tester', 'other', 'SRT-001', 'Mitutoyo', 365),
    ]
    
    today = datetime.now().date()
    for name, etype, serial, manufacturer, interval in sample_equipment:
        cur.execute("SELECT id FROM equipment WHERE serial_number = ?", [serial])
        if not cur.fetchone():
            last_cal = today - timedelta(days=180)  # 6 months ago
            due_date = last_cal + timedelta(days=interval)
            status = 'ok' if due_date > today else 'overdue'
            if due_date <= today + timedelta(days=30):
                status = 'due_soon'
            
            cur.execute('''
                INSERT INTO equipment (name, equipment_type, serial_number, manufacturer, 
                                      calibration_interval_days, last_calibration_date, 
                                      calibration_due_date, calibration_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', [name, etype, serial, manufacturer, interval, 
                  last_cal.isoformat(), due_date.isoformat(), status])
            print(f"  Created equipment: {name}")
    
    # Get IDs for foreign keys
    cur.execute("SELECT id FROM customers WHERE name = 'Acme Manufacturing'")
    customer1_id = cur.fetchone()['id']
    cur.execute("SELECT id FROM customers WHERE name = 'Nordic Parts A/S'")
    customer2_id = cur.fetchone()['id']
    cur.execute("SELECT id FROM customers WHERE name = 'TechCorp Industries'")
    customer3_id = cur.fetchone()['id']
    
    # Create sample jobs
    sample_jobs = [
        ('PO-2024-001', 'JOB00001', customer1_id, 'SHAFT-100', 'C', 'Drive Shaft Assembly', 50, 
         (today - timedelta(days=5)).isoformat(), 'in_process', 'DWG-SHAFT-100'),
        ('PO-2024-002', 'JOB00002', customer2_id, 'BRACKET-200', 'A', 'Mounting Bracket', 100,
         (today + timedelta(days=3)).isoformat(), 'material_control', 'DWG-BRKT-200'),
        ('PO-2024-003', 'JOB00003', customer1_id, 'PIN-050', 'B', 'Locating Pin', 200,
         (today + timedelta(days=10)).isoformat(), 'po_receipt', 'DWG-PIN-050'),
        ('PO-2024-004', 'JOB00004', customer3_id, 'HOUSING-300', 'D', 'Bearing Housing', 25,
         (today - timedelta(days=2)).isoformat(), 'external_process', 'DWG-HSG-300'),
        ('PO-2024-005', 'JOB00005', customer2_id, 'COVER-150', 'A', 'End Cover', 75,
         (today + timedelta(days=7)).isoformat(), 'revision_check', 'DWG-CVR-150'),
    ]
    
    for po, job_num, cust_id, part, rev, desc, qty, due, stage, dwg in sample_jobs:
        cur.execute("SELECT id FROM jobs WHERE internal_job_number = ?", [job_num])
        if not cur.fetchone():
            cur.execute('''
                INSERT INTO jobs (po_number, internal_job_number, customer_id, part_number, 
                                 part_revision, part_description, quantity, due_date, workflow_stage,
                                 drawing_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [po, job_num, cust_id, part, rev, desc, qty, due, stage, dwg])
            print(f"  Created job: {job_num} ({part} Rev {rev})")
    
    # Add dimensions to first job (SHAFT-100)
    cur.execute("SELECT id FROM jobs WHERE internal_job_number = 'JOB00001'")
    job1_id = cur.fetchone()['id']
    
    sample_dimensions = [
        (1, 'Ø25 h7', 25.0, 0, -0.021, 'mm', 'Dim #1', 1),
        (2, 'Ø20 h6', 20.0, 0, -0.013, 'mm', 'Dim #2', 1),
        (3, 'Length A', 150.0, 0.1, -0.1, 'mm', 'Dim #3', 0),
        (4, 'Length B', 75.0, 0.05, -0.05, 'mm', 'Dim #4', 0),
        (5, 'Thread M8x1.25', 0, 0, 0, 'go/nogo', 'Dim #5', 1),
    ]
    
    cur.execute("SELECT id FROM job_dimensions WHERE job_id = ?", [job1_id])
    if not cur.fetchone():
        for num, name, nominal, tol_plus, tol_minus, unit, ref, critical in sample_dimensions:
            cur.execute('''
                INSERT INTO job_dimensions (job_id, dimension_number, dimension_name, 
                                           nominal_value, tolerance_plus, tolerance_minus,
                                           unit, drawing_reference, critical)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [job1_id, num, name, nominal, tol_plus, tol_minus, unit, ref, critical])
        print(f"  Added {len(sample_dimensions)} dimensions to JOB00001")
    
    # Create a sample error report
    cur.execute("SELECT id FROM error_reports WHERE job_id = ?", [job1_id])
    if not cur.fetchone():
        cur.execute("SELECT id FROM users WHERE username = 'inspector1'")
        inspector_id = cur.fetchone()['id']
        
        cur.execute('''
            INSERT INTO error_reports (job_id, reported_by, workflow_stage, severity, 
                                      description, affected_quantity, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', [job1_id, inspector_id, 'in_process', 'minor', 
              'Surface scratch on 3 parts - cosmetic only, does not affect function', 
              3, 'open'])
        print("  Created sample error report")
    
    conn.commit()
    conn.close()
    
    print("\nDatabase seeded successfully!")
    print("\nSample login credentials:")
    print("  admin / admin (Admin)")
    print("  inspector1 / inspector123 (Inspector)")
    print("  operator1 / operator123 (Operator)")
    print("  qm / quality123 (Quality Manager)")


if __name__ == '__main__':
    seed_database()
