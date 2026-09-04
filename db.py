import os
import sqlite3
from config import Config

try:
    import mysql.connector
    from mysql.connector import errorcode
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

_USING_SQLITE = False

def get_mysql_connection():
    if not MYSQL_AVAILABLE:
        return None
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            autocommit=True
        )
        return conn
    except Exception as e:
        return None

def get_sqlite_connection():
    os.makedirs(os.path.dirname(Config.SQLITE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(Config.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def get_db():
    global _USING_SQLITE
    if not _USING_SQLITE:
        conn = get_mysql_connection()
        if conn:
            return conn, 'mysql'
        if Config.AUTO_FALLBACK_SQLITE:
            _USING_SQLITE = True
    
    return get_sqlite_connection(), 'sqlite'

def is_using_sqlite():
    global _USING_SQLITE
    return _USING_SQLITE

def query_db(query, args=(), one=False):
    """Executes a SELECT query and returns list of dictionary records."""
    conn, engine = get_db()
    
    if engine == 'mysql':
        cursor = conn.cursor(dictionary=True)
        # Adapt SQLite queries if necessary
        clean_query = query.replace('CURRENT_DATE', 'CURDATE()')
        cursor.execute(clean_query, args)
        rv = cursor.fetchall()
        cursor.close()
        conn.close()
        return (rv[0] if rv else None) if one else rv
    else:
        # SQLite
        # Convert %s placeholders to ? for SQLite
        sqlite_query = query.replace('%s', '?')
        # Adapt MySQL specific functions to SQLite equivalents
        sqlite_query = sqlite_query.replace('CURDATE()', 'date("now")')
        sqlite_query = sqlite_query.replace('CURRENT_DATE', 'date("now")')
        sqlite_query = sqlite_query.replace('DATEDIFF(date("now"),', 'julianday("now") - julianday(')
        sqlite_query = sqlite_query.replace('DATEDIFF(', 'julianday(')
        
        cursor = conn.cursor()
        cursor.execute(sqlite_query, args)
        rv = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    """Executes INSERT/UPDATE/DELETE queries and returns lastrowid or affected rows."""
    conn, engine = get_db()
    
    if engine == 'mysql':
        cursor = conn.cursor()
        clean_query = query.replace('CURRENT_DATE', 'CURDATE()')
        cursor.execute(clean_query, args)
        last_id = cursor.lastrowid
        row_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return last_id or row_count
    else:
        sqlite_query = query.replace('%s', '?')
        sqlite_query = sqlite_query.replace('CURDATE()', 'date("now")')
        sqlite_query = sqlite_query.replace('CURRENT_DATE', 'date("now")')
        cursor = conn.cursor()
        cursor.execute(sqlite_query, args)
        last_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return last_id

def init_sqlite_database():
    """Initializes SQLite database with schema and seed data when falling back."""
    os.makedirs(os.path.dirname(Config.SQLITE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(Config.SQLITE_DB_PATH)
    cursor = conn.cursor()

    # Create tables for SQLite
    cursor.executescript("""
    PRAGMA foreign_keys = ON;

    DROP TABLE IF EXISTS NOTIFICATIONS;
    DROP TABLE IF EXISTS CALIBRATIONS;
    DROP TABLE IF EXISTS MAINTENANCE_JOBS;
    DROP TABLE IF EXISTS BREAKDOWNS;
    DROP TABLE IF EXISTS RETURNS;
    DROP TABLE IF EXISTS USAGE_LOGS;
    DROP TABLE IF EXISTS EQUIPMENT_ALLOCATION;
    DROP TABLE IF EXISTS BOOKINGS;
    DROP TABLE IF EXISTS PROJECT_MEMBERS;
    DROP TABLE IF EXISTS PROJECTS;
    DROP TABLE IF EXISTS COMPONENTS;
    DROP TABLE IF EXISTS COMPONENT_CATEGORIES;
    DROP TABLE IF EXISTS EQUIPMENT;
    DROP TABLE IF EXISTS EQUIPMENT_CATEGORIES;
    DROP TABLE IF EXISTS LABORATORIES;
    DROP TABLE IF EXISTS VENDORS;
    DROP TABLE IF EXISTS USERS;
    DROP TABLE IF EXISTS ROLES;

    CREATE TABLE ROLES (
        role_id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_name TEXT NOT NULL UNIQUE,
        description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE USERS (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_id INTEGER NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT DEFAULT 'pbkdf2:sha256:default_hash',
        roll_number TEXT UNIQUE,
        phone TEXT,
        department TEXT DEFAULT 'Robotics & Automation',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (role_id) REFERENCES ROLES(role_id)
    );

    CREATE TABLE LABORATORIES (
        lab_id INTEGER PRIMARY KEY AUTOINCREMENT,
        lab_name TEXT NOT NULL UNIQUE,
        location_code TEXT NOT NULL,
        incharge_id INTEGER,
        contact_number TEXT,
        FOREIGN KEY (incharge_id) REFERENCES USERS(user_id)
    );

    CREATE TABLE EQUIPMENT_CATEGORIES (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name TEXT NOT NULL UNIQUE,
        description TEXT
    );

    CREATE TABLE EQUIPMENT (
        equipment_id TEXT PRIMARY KEY,
        equipment_name TEXT NOT NULL,
        category_id INTEGER NOT NULL,
        laboratory_id INTEGER NOT NULL,
        serial_number TEXT UNIQUE,
        purchase_date TEXT NOT NULL,
        warranty_end TEXT,
        status TEXT CHECK(status IN ('Available', 'In Use', 'Maintenance', 'Decommissioned')) DEFAULT 'Available',
        location TEXT NOT NULL,
        description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES EQUIPMENT_CATEGORIES(category_id),
        FOREIGN KEY (laboratory_id) REFERENCES LABORATORIES(lab_id)
    );

    CREATE TABLE COMPONENT_CATEGORIES (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name TEXT NOT NULL UNIQUE,
        description TEXT
    );

    CREATE TABLE COMPONENTS (
        component_id TEXT PRIMARY KEY,
        component_name TEXT NOT NULL,
        category_id INTEGER NOT NULL,
        total_quantity INTEGER NOT NULL CHECK (total_quantity >= 0),
        available_quantity INTEGER NOT NULL CHECK (available_quantity >= 0),
        minimum_stock INTEGER NOT NULL DEFAULT 5 CHECK (minimum_stock >= 0),
        unit_cost REAL DEFAULT 0.00 CHECK (unit_cost >= 0),
        storage_bin TEXT,
        specifications TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES COMPONENT_CATEGORIES(category_id)
    );

    CREATE TABLE PROJECTS (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT NOT NULL,
        guide_faculty_id INTEGER,
        start_date TEXT NOT NULL,
        end_date TEXT,
        status TEXT CHECK(status IN ('Active', 'Completed', 'On Hold')) DEFAULT 'Active',
        description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guide_faculty_id) REFERENCES USERS(user_id)
    );

    CREATE TABLE PROJECT_MEMBERS (
        project_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role_in_project TEXT DEFAULT 'Team Member',
        joined_date TEXT DEFAULT (date('now')),
        PRIMARY KEY (project_id, user_id),
        FOREIGN KEY (project_id) REFERENCES PROJECTS(project_id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES USERS(user_id) ON DELETE CASCADE
    );

    CREATE TABLE BOOKINGS (
        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        project_id INTEGER,
        booking_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        purpose TEXT NOT NULL,
        status TEXT CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED', 'IN_USE', 'RETURNED', 'CANCELLED')) DEFAULT 'PENDING',
        approved_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (equipment_id) REFERENCES EQUIPMENT(equipment_id),
        FOREIGN KEY (user_id) REFERENCES USERS(user_id),
        FOREIGN KEY (project_id) REFERENCES PROJECTS(project_id),
        FOREIGN KEY (approved_by) REFERENCES USERS(user_id)
    );

    CREATE TABLE EQUIPMENT_ALLOCATION (
        allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        component_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        project_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        issue_date TEXT NOT NULL,
        expected_return_date TEXT NOT NULL,
        actual_return_date TEXT,
        status TEXT CHECK(status IN ('Issued', 'Returned', 'Partially Returned', 'Overdue', 'Lost')) DEFAULT 'Issued',
        remarks TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (component_id) REFERENCES COMPONENTS(component_id),
        FOREIGN KEY (user_id) REFERENCES USERS(user_id),
        FOREIGN KEY (project_id) REFERENCES PROJECTS(project_id)
    );

    CREATE TABLE USAGE_LOGS (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        project_id INTEGER,
        start_timestamp TEXT NOT NULL,
        end_timestamp TEXT,
        log_notes TEXT,
        FOREIGN KEY (equipment_id) REFERENCES EQUIPMENT(equipment_id),
        FOREIGN KEY (user_id) REFERENCES USERS(user_id),
        FOREIGN KEY (project_id) REFERENCES PROJECTS(project_id)
    );

    CREATE TABLE RETURNS (
        return_id INTEGER PRIMARY KEY AUTOINCREMENT,
        allocation_id INTEGER NOT NULL,
        return_date TEXT NOT NULL,
        returned_quantity INTEGER NOT NULL CHECK (returned_quantity > 0),
        condition_status TEXT CHECK(condition_status IN ('Good', 'Damaged', 'Burnt/Faulty', 'Missing Parts')) DEFAULT 'Good',
        verified_by INTEGER,
        penalty_or_notes TEXT,
        FOREIGN KEY (allocation_id) REFERENCES EQUIPMENT_ALLOCATION(allocation_id) ON DELETE CASCADE,
        FOREIGN KEY (verified_by) REFERENCES USERS(user_id)
    );

    CREATE TABLE VENDORS (
        vendor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_name TEXT NOT NULL,
        contact_person TEXT,
        phone TEXT NOT NULL,
        email TEXT,
        address TEXT,
        service_type TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE BREAKDOWNS (
        breakdown_id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT NOT NULL,
        reported_by INTEGER NOT NULL,
        reported_date TEXT NOT NULL,
        problem_description TEXT NOT NULL,
        severity TEXT CHECK(severity IN ('Low', 'Medium', 'High', 'Critical')) DEFAULT 'Medium',
        status TEXT CHECK(status IN ('Reported', 'Under Review', 'In Maintenance', 'Resolved')) DEFAULT 'Reported',
        FOREIGN KEY (equipment_id) REFERENCES EQUIPMENT(equipment_id),
        FOREIGN KEY (reported_by) REFERENCES USERS(user_id)
    );

    CREATE TABLE MAINTENANCE_JOBS (
        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT NOT NULL,
        breakdown_id INTEGER,
        vendor_id INTEGER,
        start_date TEXT NOT NULL,
        completion_date TEXT,
        cost REAL DEFAULT 0.00 CHECK (cost >= 0),
        problem_description TEXT NOT NULL,
        action_taken TEXT,
        status TEXT CHECK(status IN ('Scheduled', 'In Progress', 'Completed', 'Cannot Repair')) DEFAULT 'Scheduled',
        FOREIGN KEY (equipment_id) REFERENCES EQUIPMENT(equipment_id),
        FOREIGN KEY (breakdown_id) REFERENCES BREAKDOWNS(breakdown_id),
        FOREIGN KEY (vendor_id) REFERENCES VENDORS(vendor_id)
    );

    CREATE TABLE CALIBRATIONS (
        calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT NOT NULL,
        last_calibration_date TEXT NOT NULL,
        next_due_date TEXT NOT NULL,
        certified_by TEXT,
        status TEXT CHECK(status IN ('Valid', 'Due Soon', 'Overdue')) DEFAULT 'Valid',
        remarks TEXT,
        FOREIGN KEY (equipment_id) REFERENCES EQUIPMENT(equipment_id)
    );

    CREATE TABLE NOTIFICATIONS (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        notification_type TEXT CHECK(notification_type IN ('Booking', 'Allocation', 'Return_Due', 'Breakdown', 'Maintenance', 'Stock_Alert')) DEFAULT 'Booking',
        is_read INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES USERS(user_id)
    );
    """)

    # Seed data
    cursor.executescript("""
    INSERT INTO ROLES (role_id, role_name, description) VALUES
    (1, 'Admin', 'System Administrator with full lab oversight'),
    (2, 'Lab Technician', 'Manages physical equipment, issues/returns, and maintenance'),
    (3, 'Faculty', 'Academic guides, approves student bookings and evaluates projects'),
    (4, 'Student', 'Lab member requesting components and equipment for projects');

    INSERT INTO USERS (user_id, role_id, full_name, email, roll_number, phone, department) VALUES
    (1, 1, 'Dr. Rajesh Sharma', 'admin.rajesh@robolab.edu', 'STAFF001', '+91 9876543210', 'Robotics & Automation'),
    (2, 2, 'Vikram Verma', 'tech.vikram@robolab.edu', 'TECH002', '+91 9876543211', 'Robotics & Automation'),
    (3, 3, 'Dr. Ananya Iyer', 'faculty.ananya@robolab.edu', 'FAC003', '+91 9876543212', 'Electronics & Mechatronics'),
    (4, 3, 'Prof. Arvind Menon', 'faculty.arvind@robolab.edu', 'FAC004', '+91 9876543213', 'Computer Science & AI'),
    (5, 4, 'Sufiyan Khan', 'sufiyan.k@student.robolab.edu', 'RA21110030101', '+91 9876543220', 'Robotics Engineering'),
    (6, 4, 'Pooja Nair', 'pooja.n@student.robolab.edu', 'RA21110030102', '+91 9876543221', 'Robotics Engineering'),
    (7, 4, 'Rahul Sundaram', 'rahul.s@student.robolab.edu', 'RA21110030103', '+91 9876543222', 'Mechatronics'),
    (8, 4, 'Sneha Patel', 'sneha.p@student.robolab.edu', 'RA21110030104', '+91 9876543223', 'AI & Data Science');

    INSERT INTO LABORATORIES (lab_id, lab_name, location_code, incharge_id, contact_number) VALUES
    (1, 'Central Robotics & Automation Lab', 'LAB-301, Block B', 1, '+91 44 27417001'),
    (2, 'Advanced Mechatronics & Drones Lab', 'LAB-304, Block B', 2, '+91 44 27417002'),
    (3, 'Rapid Prototyping & Fabrication Lab', 'LAB-102, Block A', 2, '+91 44 27417003');

    INSERT INTO EQUIPMENT_CATEGORIES (category_id, category_name, description) VALUES
    (1, 'Robotic Arms & Manipulators', 'Multi-axis industrial and educational articulated arms'),
    (2, 'Additive Manufacturing', '3D Printers, Resin printers, Filament extruders'),
    (3, 'Autonomous Mobile Robots', 'Line followers, AGVs, ROS-based mobile bases, Quadcopters'),
    (4, 'Test & Measurement', 'Oscilloscopes, Logic Analyzers, Spectrum Analyzers, Power Supplies'),
    (5, 'Subtractive Fabrication', 'Desktop CNC routers, PCB milling machines');

    INSERT INTO EQUIPMENT (equipment_id, equipment_name, category_id, laboratory_id, serial_number, purchase_date, warranty_end, status, location, description) VALUES
    ('EQ001', '6-DOF Articulated Robotic Arm', 1, 1, 'ARM-2024-X600', '2024-03-15', '2027-03-15', 'Available', 'Workstation 1, Lab 301', 'High-precision 6-axis robotic arm with pneumatic suction gripper and ROS2 integration.'),
    ('EQ002', 'Prusa MK4 3D Printer', 2, 3, 'PRUSA-MK4-9821', '2024-01-10', '2026-01-10', 'Maintenance', 'Print Bay 2, Lab 102', 'Direct-drive extrusion 3D printer for rapid prototyping of custom robotic chassis.'),
    ('EQ003', 'Rigol 100MHz Digital Oscilloscope', 4, 1, 'RIGOL-DS1104Z', '2023-08-20', '2026-08-20', 'Available', 'Test Bench 3, Lab 301', '4-channel digital storage oscilloscope with protocol decoding for SPI/I2C/UART.'),
    ('EQ004', 'TurtleBot4 ROS2 Mobile Robot', 3, 2, 'TB4-NAV-0042', '2024-05-12', '2026-05-12', 'In Use', 'Arena Floor, Lab 304', 'Autonomous mobile robot platform built on iRobot Create3 with OAK-D Pro camera and 2D LiDAR.'),
    ('EQ005', 'Bantam PCB Milling Machine', 5, 3, 'BANT-CNC-3011', '2023-11-05', '2025-11-05', 'Available', 'CNC Booth, Lab 102', 'Precision desktop CNC for double-sided custom PCB prototyping.'),
    ('EQ006', 'DJI Matrice Autonomous Drone Base', 3, 2, 'DJI-M300-RTK', '2024-02-18', '2027-02-18', 'Available', 'Flight Cage, Lab 304', 'Industrial research drone platform with onboard RTK and thermal imaging.'),
    ('EQ007', 'Delta High-Speed Pick & Place Robot', 1, 1, 'DLT-800-ROBO', '2023-09-30', '2026-09-30', 'Available', 'Workstation 4, Lab 301', '3-axis delta robot for conveyor sorting and high-speed pick and place vision tasks.');

    INSERT INTO COMPONENT_CATEGORIES (category_id, category_name, description) VALUES
    (1, 'Microcontrollers & SBCs', 'Development boards, compute modules, single board computers'),
    (2, 'Sensors', 'Distance, environmental, inertial, visual and gas sensors'),
    (3, 'Motors & Actuators', 'Servos, steppers, BLDC, DC motors and linear actuators'),
    (4, 'Power & Motor Drivers', 'H-Bridge drivers, ESCs, step-down buck converters, LiPo batteries'),
    (5, 'Prototyping & Consumables', 'Breadboards, jumper wires, passive components, hardware kits');

    INSERT INTO COMPONENTS (component_id, component_name, category_id, total_quantity, available_quantity, minimum_stock, unit_cost, storage_bin, specifications) VALUES
    ('C001', 'Arduino UNO R3', 1, 35, 20, 8, 450.00, 'BIN-A1', 'ATmega328P 16MHz, 14 Digital I/O, 6 Analog inputs, 5V operating'),
    ('C002', 'ESP32 Dual-Core DevKit V1', 1, 30, 14, 6, 380.00, 'BIN-A2', 'Xtensa Dual-Core 240MHz, 2.4GHz Wi-Fi + BLE, 38-Pin Module'),
    ('C003', 'Raspberry Pi 4 Model B (4GB)', 1, 12, 4, 3, 4800.00, 'BIN-A3', 'Quad core Cortex-A72 1.5GHz, 4GB LPDDR4, Gigabit Ethernet, Dual 4K HDMI'),
    ('C004', 'HC-SR04 Ultrasonic Distance Sensor', 2, 40, 22, 10, 85.00, 'BIN-S1', '2cm - 400cm range, 5V DC, 15 degree measuring angle'),
    ('C005', 'MPU-6050 6-DOF IMU (Gyro + Accel)', 2, 25, 8, 8, 160.00, 'BIN-S2', '3-axis accelerometer and 3-axis gyroscope with I2C digital interface'),
    ('C006', 'RPLiDAR A1M8 360 Degree Laser Scanner', 2, 6, 2, 2, 8500.00, 'BIN-S3', '12m radius 360-degree laser range scanner, 8000 samples/sec'),
    ('C007', 'MG996R High Torque Metal Gear Servo', 3, 28, 12, 6, 340.00, 'BIN-M1', '11kg-cm torque at 6V, 180-degree rotation, metal gearing'),
    ('C008', 'NEMA 17 Stepper Motor 1.8 Deg', 3, 18, 10, 4, 650.00, 'BIN-M2', '42x42mm, 4.2 kg-cm holding torque, 4-wire bipolar'),
    ('C009', 'L298N Dual H-Bridge Motor Driver', 4, 25, 15, 6, 120.00, 'BIN-P1', 'Dual channel 2A max per bridge, 5V-35V input, heatsink included'),
    ('C010', 'OAK-D Spatial AI Camera Module', 2, 5, 1, 2, 18500.00, 'BIN-S4', 'Stereo depth camera with 4K color sensor and onboard Myriad X AI accelerator'),
    ('C011', 'Robotic Gripper with MG996R', 3, 10, 4, 3, 950.00, 'BIN-M3', 'Aluminum 2-finger claw gripper driven by metal gear servo'),
    ('C012', 'MQ-2 Gas / Smoke Sensor', 2, 20, 16, 5, 95.00, 'BIN-S5', 'Detects LPG, Smoke, Alcohol, Propane, Hydrogen, Methane');

    INSERT INTO PROJECTS (project_id, project_name, guide_faculty_id, start_date, end_date, status, description) VALUES
    (1, 'Autonomous Line & Maze Following Robot', 3, '2026-08-01', '2026-11-30', 'Active', 'High-speed autonomous PID line follower with obstacle evasion and intersection maze solving.'),
    (2, 'Vision Guided 6-DOF Pick & Place Robotic Arm', 4, '2026-07-15', '2026-12-15', 'Active', 'Industrial object sorting system utilizing OpenCV and YOLO object detection for pick-and-place manipulation.'),
    (3, 'Autonomous Mobile Delivery Robot (ROS2)', 4, '2026-08-10', '2026-12-20', 'Active', 'Indoor autonomous navigation robot using 2D LiDAR SLAM and Nav2 stack on TurtleBot.'),
    (4, 'Quadrotor Drone Indoor Obstacle Avoidance', 3, '2026-08-15', '2026-11-20', 'Active', 'Autonomous flight stabilization using optical flow sensors and ultrasonic altitude lock.');

    INSERT INTO PROJECT_MEMBERS (project_id, user_id, role_in_project, joined_date) VALUES
    (1, 5, 'Project Lead / Firmware', '2026-08-01'),
    (1, 6, 'Hardware & Circuit Designer', '2026-08-01'),
    (2, 5, 'Kinematics & Control', '2026-08-10'),
    (2, 7, 'Computer Vision Specialist', '2026-07-15'),
    (3, 7, 'SLAM & Navigation Lead', '2026-08-10'),
    (3, 8, 'Perception & ROS2 Engineer', '2026-08-12'),
    (4, 8, 'Flight Controller Specialist', '2026-08-15');

    INSERT INTO BOOKINGS (booking_id, equipment_id, user_id, project_id, booking_date, start_time, end_time, purpose, status, approved_by) VALUES
    (1, 'EQ001', 5, 2, '2026-09-01', '10:00:00', '12:00:00', 'Inverse kinematics calibration and gripper testing with vision pipeline', 'APPROVED', 4),
    (2, 'EQ004', 7, 3, '2026-09-01', '14:00:00', '17:00:00', 'SLAM map generation in lab corridor using LiDAR', 'IN_USE', 4),
    (3, 'EQ003', 6, 1, '2026-09-02', '11:00:00', '13:00:00', 'PWM frequency and motor back-EMF analysis on oscilloscope', 'PENDING', NULL),
    (4, 'EQ001', 7, 2, '2026-08-25', '09:00:00', '11:30:00', 'Repeatability and precision test for pick and place', 'RETURNED', 3),
    (5, 'EQ005', 6, 1, '2026-08-28', '14:00:00', '16:00:00', 'Milling motor driver custom shield PCB', 'RETURNED', 3);

    INSERT INTO EQUIPMENT_ALLOCATION (allocation_id, component_id, user_id, project_id, quantity, issue_date, expected_return_date, actual_return_date, status, remarks) VALUES
    (1, 'C001', 5, 1, 1, '2026-08-15', '2026-09-15', NULL, 'Issued', 'Main controller for PID line following algorithm'),
    (2, 'C004', 5, 1, 2, '2026-08-15', '2026-09-15', NULL, 'Issued', 'Front and diagonal obstacle sensing'),
    (3, 'C007', 5, 1, 2, '2026-08-15', '2026-09-15', NULL, 'Issued', 'Steering / angle adjusting mechanism'),
    (4, 'C009', 5, 1, 1, '2026-08-15', '2026-09-15', NULL, 'Issued', 'Dual DC motor drive module'),
    (5, 'C003', 7, 3, 1, '2026-08-20', '2026-09-20', NULL, 'Issued', 'Onboard ROS2 navigation processor'),
    (6, 'C006', 7, 3, 1, '2026-08-20', '2026-09-20', NULL, 'Issued', 'Laser scan provider for Cartographer SLAM'),
    (7, 'C002', 8, 4, 2, '2026-08-22', '2026-09-05', NULL, 'Issued', 'Telemetry transmitter and receiver unit'),
    (8, 'C005', 6, 1, 1, '2026-08-10', '2026-08-24', '2026-08-24', 'Returned', 'Gyro balancing test completed successfully');

    INSERT INTO RETURNS (return_id, allocation_id, return_date, returned_quantity, condition_status, verified_by, penalty_or_notes) VALUES
    (1, 8, '2026-08-24', 1, 'Good', 2, 'Returned in working condition without damage');

    INSERT INTO USAGE_LOGS (log_id, equipment_id, user_id, project_id, start_timestamp, end_timestamp, log_notes) VALUES
    (1, 'EQ001', 5, 2, '2026-08-25 09:05:00', '2026-08-25 11:25:00', 'Ran 50 cycles of object classification sorting. All servo axes normal.'),
    (2, 'EQ005', 6, 1, '2026-08-28 14:10:00', '2026-08-28 15:50:00', 'Milled 2 PCB layers on FR4 board with 0.4mm endmill.'),
    (3, 'EQ004', 7, 3, '2026-09-01 14:00:00', NULL, 'Active SLAM corridor mapping in progress');

    INSERT INTO VENDORS (vendor_id, vendor_name, contact_person, phone, email, address, service_type) VALUES
    (1, 'RoboTech Automation & Spares', 'Anil Mehta', '+91 9445123456', 'support@robotechindia.com', 'Plot 45, Guindy Industrial Estate, Chennai', 'Robotic Arm Servicing & Servo Spares'),
    (2, '3D Maker Solutions Ltd.', 'Deepak Kumar', '+91 9840234567', 'service@3dmaker.in', '12, Electronic City Phase 1, Bangalore', '3D Printer & Extruder Maintenance'),
    (3, 'Apex Calibration & Metrology Labs', 'Kavitha R.', '+91 9791345678', 'certs@apexcalibration.com', 'SIDCO Industrial Complex, Coimbatore', 'Precision Test Bench Calibration');

    INSERT INTO BREAKDOWNS (breakdown_id, equipment_id, reported_by, reported_date, problem_description, severity, status) VALUES
    (1, 'EQ002', 6, '2026-08-29', 'Hotend heating failure and thermal runaway error on extruder 1.', 'High', 'In Maintenance'),
    (2, 'EQ001', 5, '2026-08-10', 'Joint 3 servo jitter and minor angle offset during payload lift.', 'Medium', 'Resolved');

    INSERT INTO MAINTENANCE_JOBS (job_id, equipment_id, breakdown_id, vendor_id, start_date, completion_date, cost, problem_description, action_taken, status) VALUES
    (1, 'EQ001', 2, 1, '2026-08-11', '2026-08-13', 2400.00, 'Servo jitter on Joint 3 gear set', 'Replaced feedback potentiometer and re-calibrated harmonic gear backlash.', 'Completed'),
    (2, 'EQ002', 1, 2, '2026-08-30', NULL, 1500.00, 'Extruder thermal runaway and thermistor open-circuit', 'Thermistor replaced, firmware PID autotuning in progress', 'In Progress');

    INSERT INTO CALIBRATIONS (calibration_id, equipment_id, last_calibration_date, next_due_date, certified_by, status, remarks) VALUES
    (1, 'EQ001', '2026-03-15', '2026-09-15', 'Apex Calibration & Metrology Labs', 'Valid', 'Kinematic repeatability within +/- 0.05 mm.'),
    (2, 'EQ003', '2025-09-10', '2026-09-10', 'Apex Calibration & Metrology Labs', 'Due Soon', 'Bandwidth and timebase calibration due within 10 days.'),
    (3, 'EQ005', '2025-08-01', '2026-08-01', 'Internal Lab Tech (Vikram)', 'Overdue', 'Spindle runout calibration expired. Needs re-verification.');

    INSERT INTO NOTIFICATIONS (notification_id, user_id, message, notification_type, is_read, created_at) VALUES
    (1, 5, 'Your booking request for 6-DOF Robotic Arm (EQ001) has been approved by Dr. Arvind Menon.', 'Booking', 1, '2026-08-31 16:30:00'),
    (2, 2, 'Low stock alert: OAK-D Spatial AI Camera Module has only 1 available unit left (Min stock: 2).', 'Stock_Alert', 0, '2026-08-31 09:15:00'),
    (3, 6, 'Calibration due soon for Rigol 100MHz Oscilloscope (EQ003) on 10-Sep-2026.', 'Maintenance', 0, '2026-09-01 08:00:00');
    """)
    conn.commit()
    conn.close()

# Auto-seed SQLite file if needed
if not os.path.exists(Config.SQLITE_DB_PATH):
    init_sqlite_database()
