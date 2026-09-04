-- ==============================================================================
-- RoboLab: Robotics Laboratory Equipment & Component Management System
-- Relational Database Schema (MySQL Compatible)
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS robotics_lab;
USE robotics_lab;

-- ------------------------------------------------------------------------------
-- 1. ROLES TABLE
-- ------------------------------------------------------------------------------
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
    role_id INT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 2. USERS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE USERS (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    role_id INT NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) DEFAULT 'pbkdf2:sha256:default_hash',
    roll_number VARCHAR(30) UNIQUE,
    phone VARCHAR(20),
    department VARCHAR(80) DEFAULT 'Robotics & Automation',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES ROLES(role_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ------------------------------------------------------------------------------
-- 3. LABORATORIES TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE LABORATORIES (
    lab_id INT AUTO_INCREMENT PRIMARY KEY,
    lab_name VARCHAR(100) NOT NULL UNIQUE,
    location_code VARCHAR(50) NOT NULL,
    incharge_id INT,
    contact_number VARCHAR(20),
    FOREIGN KEY (incharge_id) REFERENCES USERS(user_id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- ------------------------------------------------------------------------------
-- 4. EQUIPMENT CATEGORIES
-- ------------------------------------------------------------------------------
CREATE TABLE EQUIPMENT_CATEGORIES (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- ------------------------------------------------------------------------------
-- 5. EQUIPMENT TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE EQUIPMENT (
    equipment_id VARCHAR(20) PRIMARY KEY,
    equipment_name VARCHAR(120) NOT NULL,
    category_id INT NOT NULL,
    laboratory_id INT NOT NULL,
    serial_number VARCHAR(100) UNIQUE,
    purchase_date DATE NOT NULL,
    warranty_end DATE,
    status ENUM('Available', 'In Use', 'Maintenance', 'Decommissioned') DEFAULT 'Available',
    location VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES EQUIPMENT_CATEGORIES(category_id) ON UPDATE CASCADE,
    FOREIGN KEY (laboratory_id) REFERENCES LABORATORIES(lab_id) ON UPDATE CASCADE
);

-- ------------------------------------------------------------------------------
-- 6. COMPONENT CATEGORIES
-- ------------------------------------------------------------------------------
CREATE TABLE COMPONENT_CATEGORIES (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- ------------------------------------------------------------------------------
-- 7. COMPONENTS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE COMPONENTS (
    component_id VARCHAR(20) PRIMARY KEY,
    component_name VARCHAR(120) NOT NULL,
    category_id INT NOT NULL,
    total_quantity INT NOT NULL CHECK (total_quantity >= 0),
    available_quantity INT NOT NULL CHECK (available_quantity >= 0),
    minimum_stock INT NOT NULL DEFAULT 5 CHECK (minimum_stock >= 0),
    unit_cost DECIMAL(10, 2) DEFAULT 0.00 CHECK (unit_cost >= 0),
    storage_bin VARCHAR(50),
    specifications TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES COMPONENT_CATEGORIES(category_id) ON UPDATE CASCADE
);

-- ------------------------------------------------------------------------------
-- 8. PROJECTS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE PROJECTS (
    project_id INT AUTO_INCREMENT PRIMARY KEY,
    project_name VARCHAR(150) NOT NULL,
    guide_faculty_id INT,
    start_date DATE NOT NULL,
    end_date DATE,
    status ENUM('Active', 'Completed', 'On Hold') DEFAULT 'Active',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guide_faculty_id) REFERENCES USERS(user_id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- ------------------------------------------------------------------------------
-- 9. PROJECT MEMBERS TABLE (Associative Entity)
-- ------------------------------------------------------------------------------
CREATE TABLE PROJECT_MEMBERS (
    project_id INT NOT NULL,
    user_id INT NOT NULL,
    role_in_project VARCHAR(50) DEFAULT 'Team Member',
    joined_date DATE DEFAULT (CURRENT_DATE),
    PRIMARY KEY (project_id, user_id),
    FOREIGN KEY (project_id) REFERENCES PROJECTS(project_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES USERS(user_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------------------------
-- 10. BOOKINGS TABLE (Slot Booking for Heavy Equipment)
-- ------------------------------------------------------------------------------
CREATE TABLE BOOKINGS (
    booking_id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id VARCHAR(20) NOT NULL,
    user_id INT NOT NULL,
    project_id INT,
    booking_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    purpose TEXT NOT NULL,
    status ENUM('PENDING', 'APPROVED', 'REJECTED', 'IN_USE', 'RETURNED', 'CANCELLED') DEFAULT 'PENDING',
    approved_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipment_id) REFERENCES EQUIPMENT(equipment_id) ON UPDATE CASCADE,
    FOREIGN KEY (user_id) REFERENCES USERS(user_id) ON UPDATE CASCADE,
    FOREIGN KEY (project_id) REFERENCES PROJECTS(project_id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (approved_by) REFERENCES USERS(user_id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- ------------------------------------------------------------------------------
-- 11. EQUIPMENT ALLOCATION (Component Issuance to Students/Projects)
-- ------------------------------------------------------------------------------
CREATE TABLE EQUIPMENT_ALLOCATION (
    allocation_id INT AUTO_INCREMENT PRIMARY KEY,
    component_id VARCHAR(20) NOT NULL,
    user_id INT NOT NULL,
    project_id INT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    issue_date DATE NOT NULL,
    expected_return_date DATE NOT NULL,
    actual_return_date DATE,
    status ENUM('Issued', 'Returned', 'Partially Returned', 'Overdue', 'Lost') DEFAULT 'Issued',
    remarks TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (component_id) REFERENCES COMPONENTS(component_id) ON UPDATE CASCADE,
    FOREIGN KEY (user_id) REFERENCES USERS(user_id) ON UPDATE CASCADE,
    FOREIGN KEY (project_id) REFERENCES PROJECTS(project_id) ON UPDATE CASCADE
);

-- ------------------------------------------------------------------------------
-- 12. USAGE LOGS TABLE (Detailed time logs for equipment)
-- ------------------------------------------------------------------------------
CREATE TABLE USAGE_LOGS (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id VARCHAR(20) NOT NULL,
    user_id INT NOT NULL,
    project_id INT,
    start_timestamp DATETIME NOT NULL,
    end_timestamp DATETIME,
    log_notes TEXT,
    FOREIGN KEY (equipment_id) REFERENCES EQUIPMENT(equipment_id) ON UPDATE CASCADE,
    FOREIGN KEY (user_id) REFERENCES USERS(user_id) ON UPDATE CASCADE,
    FOREIGN KEY (project_id) REFERENCES PROJECTS(project_id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- ------------------------------------------------------------------------------
-- 13. RETURNS TABLE (Record of component returns)
-- ------------------------------------------------------------------------------
CREATE TABLE RETURNS (
    return_id INT AUTO_INCREMENT PRIMARY KEY,
    allocation_id INT NOT NULL,
    return_date DATE NOT NULL,
    returned_quantity INT NOT NULL CHECK (returned_quantity > 0),
    condition_status ENUM('Good', 'Damaged', 'Burnt/Faulty', 'Missing Parts') DEFAULT 'Good',
    verified_by INT,
    penalty_or_notes TEXT,
    FOREIGN KEY (allocation_id) REFERENCES EQUIPMENT_ALLOCATION(allocation_id) ON DELETE CASCADE,
    FOREIGN KEY (verified_by) REFERENCES USERS(user_id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- ------------------------------------------------------------------------------
-- 14. VENDORS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE VENDORS (
    vendor_id INT AUTO_INCREMENT PRIMARY KEY,
    vendor_name VARCHAR(120) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(25) NOT NULL,
    email VARCHAR(120),
    address TEXT,
    service_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 15. BREAKDOWNS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE BREAKDOWNS (
    breakdown_id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id VARCHAR(20) NOT NULL,
    reported_by INT NOT NULL,
    reported_date DATE NOT NULL,
    problem_description TEXT NOT NULL,
    severity ENUM('Low', 'Medium', 'High', 'Critical') DEFAULT 'Medium',
    status ENUM('Reported', 'Under Review', 'In Maintenance', 'Resolved') DEFAULT 'Reported',
    FOREIGN KEY (equipment_id) REFERENCES EQUIPMENT(equipment_id) ON UPDATE CASCADE,
    FOREIGN KEY (reported_by) REFERENCES USERS(user_id) ON UPDATE CASCADE
);

-- ------------------------------------------------------------------------------
-- 16. MAINTENANCE JOBS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE MAINTENANCE_JOBS (
    job_id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id VARCHAR(20) NOT NULL,
    breakdown_id INT,
    vendor_id INT,
    start_date DATE NOT NULL,
    completion_date DATE,
    cost DECIMAL(10, 2) DEFAULT 0.00 CHECK (cost >= 0),
    problem_description TEXT NOT NULL,
    action_taken TEXT,
    status ENUM('Scheduled', 'In Progress', 'Completed', 'Cannot Repair') DEFAULT 'Scheduled',
    FOREIGN KEY (equipment_id) REFERENCES EQUIPMENT(equipment_id) ON UPDATE CASCADE,
    FOREIGN KEY (breakdown_id) REFERENCES BREAKDOWNS(breakdown_id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (vendor_id) REFERENCES VENDORS(vendor_id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- ------------------------------------------------------------------------------
-- 17. CALIBRATIONS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE CALIBRATIONS (
    calibration_id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id VARCHAR(20) NOT NULL,
    last_calibration_date DATE NOT NULL,
    next_due_date DATE NOT NULL,
    certified_by VARCHAR(120),
    status ENUM('Valid', 'Due Soon', 'Overdue') DEFAULT 'Valid',
    remarks TEXT,
    FOREIGN KEY (equipment_id) REFERENCES EQUIPMENT(equipment_id) ON UPDATE CASCADE
);

-- ------------------------------------------------------------------------------
-- 18. NOTIFICATIONS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE NOTIFICATIONS (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message TEXT NOT NULL,
    notification_type ENUM('Booking', 'Allocation', 'Return_Due', 'Breakdown', 'Maintenance', 'Stock_Alert') DEFAULT 'Booking',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES USERS(user_id) ON UPDATE CASCADE ON DELETE CASCADE
);

-- ==============================================================================
-- SQL VIEWS FOR DBMS REVIEW & APPLICATION QUERIES
-- ==============================================================================

-- View 1: Available Equipment Overview
CREATE OR REPLACE VIEW vw_available_equipment AS
SELECT 
    e.equipment_id,
    e.equipment_name,
    ec.category_name,
    l.lab_name,
    e.location,
    e.status
FROM EQUIPMENT e
JOIN EQUIPMENT_CATEGORIES ec ON e.category_id = ec.category_id
JOIN LABORATORIES l ON e.laboratory_id = l.lab_id
WHERE e.status = 'Available';

-- View 2: Active Component Allocations to Students & Projects
CREATE OR REPLACE VIEW vw_active_allocations AS
SELECT 
    ea.allocation_id,
    u.user_id,
    u.full_name AS student_name,
    u.roll_number,
    c.component_id,
    c.component_name,
    p.project_id,
    p.project_name,
    ea.quantity,
    ea.issue_date,
    ea.expected_return_date,
    ea.status,
    DATEDIFF(CURRENT_DATE, ea.expected_return_date) AS days_overdue
FROM EQUIPMENT_ALLOCATION ea
JOIN USERS u ON ea.user_id = u.user_id
JOIN COMPONENTS c ON ea.component_id = c.component_id
JOIN PROJECTS p ON ea.project_id = p.project_id
WHERE ea.status IN ('Issued', 'Overdue');

-- View 3: Low Stock Components Alert
CREATE OR REPLACE VIEW vw_low_stock_components AS
SELECT 
    c.component_id,
    c.component_name,
    cc.category_name,
    c.total_quantity,
    c.available_quantity,
    c.minimum_stock,
    (c.minimum_stock - c.available_quantity) AS shortage_count,
    c.storage_bin
FROM COMPONENTS c
JOIN COMPONENT_CATEGORIES cc ON c.category_id = cc.category_id
WHERE c.available_quantity <= c.minimum_stock;

-- View 4: Equipment Maintenance & Breakdown History
CREATE OR REPLACE VIEW vw_equipment_maintenance_history AS
SELECT 
    m.job_id,
    e.equipment_id,
    e.equipment_name,
    m.problem_description,
    m.action_taken,
    m.start_date,
    m.completion_date,
    m.cost,
    m.status AS maintenance_status,
    v.vendor_name
FROM MAINTENANCE_JOBS m
JOIN EQUIPMENT e ON m.equipment_id = e.equipment_id
LEFT JOIN VENDORS v ON m.vendor_id = v.vendor_id;

-- View 5: Booking Summary with Approvals
CREATE OR REPLACE VIEW vw_booking_summary AS
SELECT 
    b.booking_id,
    b.booking_date,
    b.start_time,
    b.end_time,
    e.equipment_id,
    e.equipment_name,
    u.full_name AS student_name,
    u.roll_number,
    p.project_name,
    b.purpose,
    b.status,
    approver.full_name AS approved_by_name
FROM BOOKINGS b
JOIN EQUIPMENT e ON b.equipment_id = e.equipment_id
JOIN USERS u ON b.user_id = u.user_id
LEFT JOIN PROJECTS p ON b.project_id = p.project_id
LEFT JOIN USERS approver ON b.approved_by = approver.user_id;

-- ==============================================================================
-- SQL TRIGGERS (Automating Stock and Status Updates)
-- ==============================================================================

DELIMITER $$

-- Trigger 1: Deduct Component Available Quantity on Allocation
DROP TRIGGER IF EXISTS trg_after_allocation_insert$$
CREATE TRIGGER trg_after_allocation_insert
AFTER INSERT ON EQUIPMENT_ALLOCATION
FOR EACH ROW
BEGIN
    UPDATE COMPONENTS
    SET available_quantity = available_quantity - NEW.quantity
    WHERE component_id = NEW.component_id;
END$$

-- Trigger 2: Restore Component Available Quantity on Return
DROP TRIGGER IF EXISTS trg_after_return_insert$$
CREATE TRIGGER trg_after_return_insert
AFTER INSERT ON RETURNS
FOR EACH ROW
BEGIN
    DECLARE v_comp_id VARCHAR(20);
    
    SELECT component_id INTO v_comp_id
    FROM EQUIPMENT_ALLOCATION
    WHERE allocation_id = NEW.allocation_id;
    
    -- Only restore to available stock if not destroyed/lost
    IF NEW.condition_status IN ('Good', 'Damaged') THEN
        UPDATE COMPONENTS
        SET available_quantity = available_quantity + NEW.returned_quantity
        WHERE component_id = v_comp_id;
    END IF;
    
    -- Update allocation status
    UPDATE EQUIPMENT_ALLOCATION
    SET status = 'Returned', actual_return_date = NEW.return_date
    WHERE allocation_id = NEW.allocation_id;
END$$

-- Trigger 3: Set Equipment status to Maintenance when Breakdown is filed
DROP TRIGGER IF EXISTS trg_after_breakdown_insert$$
CREATE TRIGGER trg_after_breakdown_insert
AFTER INSERT ON BREAKDOWNS
FOR EACH ROW
BEGIN
    IF NEW.severity IN ('High', 'Critical') THEN
        UPDATE EQUIPMENT
        SET status = 'Maintenance'
        WHERE equipment_id = NEW.equipment_id;
    END IF;
END$$

DELIMITER ;
