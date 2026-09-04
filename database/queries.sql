-- ==============================================================================
-- RoboLab: DBMS Lab Review SQL Query Bank
-- This file contains all the explicit SQL queries required for academic reviews:
-- 1. DDL & Constraints
-- 2. DML (Insert, Update, Delete)
-- 3. Complex JOINs (3-way and 4-way)
-- 4. Aggregate Functions with GROUP BY & HAVING
-- 5. Subqueries (Nested, Correlated, IN, NOT IN)
-- 6. Set Operations & Views
-- ==============================================================================

USE robotics_lab;

-- ------------------------------------------------------------------------------
-- QUERY 1: Find all available equipment in the Robotics Lab (Basic SELECT + JOIN)
-- ------------------------------------------------------------------------------
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
WHERE e.status = 'Available'
ORDER BY e.equipment_name ASC;

-- ------------------------------------------------------------------------------
-- QUERY 2: Student -> Project -> Component Allocation Tracking (4-Table JOIN)
-- Directly answers: "Who currently has which component for which project?"
-- ------------------------------------------------------------------------------
SELECT 
    u.full_name AS student_name,
    u.roll_number,
    p.project_name,
    c.component_name,
    cc.category_name AS component_type,
    ea.quantity,
    ea.issue_date,
    ea.expected_return_date,
    ea.status
FROM EQUIPMENT_ALLOCATION ea
JOIN USERS u ON ea.user_id = u.user_id
JOIN COMPONENTS c ON ea.component_id = c.component_id
JOIN COMPONENT_CATEGORIES cc ON c.category_id = cc.category_id
JOIN PROJECTS p ON ea.project_id = p.project_id
WHERE ea.status = 'Issued'
ORDER BY ea.issue_date DESC;

-- ------------------------------------------------------------------------------
-- QUERY 3: Low Stock Warning (Components where Available <= Minimum Stock)
-- ------------------------------------------------------------------------------
SELECT 
    c.component_id,
    c.component_name,
    cc.category_name,
    c.total_quantity,
    c.available_quantity,
    c.minimum_stock,
    (c.minimum_stock - c.available_quantity) AS shortage_units,
    c.storage_bin
FROM COMPONENTS c
JOIN COMPONENT_CATEGORIES cc ON c.category_id = cc.category_id
WHERE c.available_quantity <= c.minimum_stock
ORDER BY shortage_units DESC;

-- ------------------------------------------------------------------------------
-- QUERY 4: Equipment Breakdown & Maintenance History with Vendor Details (LEFT JOIN)
-- ------------------------------------------------------------------------------
SELECT 
    e.equipment_id,
    e.equipment_name,
    m.problem_description,
    m.action_taken,
    m.start_date,
    m.completion_date,
    m.cost,
    m.status AS maintenance_status,
    COALESCE(v.vendor_name, 'In-House Service') AS service_vendor,
    v.phone AS vendor_phone
FROM MAINTENANCE_JOBS m
JOIN EQUIPMENT e ON m.equipment_id = e.equipment_id
LEFT JOIN VENDORS v ON m.vendor_id = v.vendor_id
ORDER BY m.start_date DESC;

-- ------------------------------------------------------------------------------
-- QUERY 5: Equipment Utilization & Total Booking Count (GROUP BY & COUNT)
-- ------------------------------------------------------------------------------
SELECT 
    e.equipment_id,
    e.equipment_name,
    ec.category_name,
    COUNT(b.booking_id) AS total_times_booked,
    SUM(CASE WHEN b.status = 'APPROVED' OR b.status = 'RETURNED' OR b.status = 'IN_USE' THEN 1 ELSE 0 END) AS successful_bookings
FROM EQUIPMENT e
JOIN EQUIPMENT_CATEGORIES ec ON e.category_id = ec.category_id
LEFT JOIN BOOKINGS b ON e.equipment_id = b.equipment_id
GROUP BY e.equipment_id, e.equipment_name, ec.category_name
ORDER BY total_times_booked DESC;

-- ------------------------------------------------------------------------------
-- QUERY 6: Total Value of Components Issued per Project (GROUP BY, SUM, HAVING)
-- ------------------------------------------------------------------------------
SELECT 
    p.project_id,
    p.project_name,
    u.full_name AS guide_faculty,
    COUNT(ea.allocation_id) AS total_items_issued,
    SUM(ea.quantity * c.unit_cost) AS total_allocated_value_inr
FROM PROJECTS p
JOIN USERS u ON p.guide_faculty_id = u.user_id
JOIN EQUIPMENT_ALLOCATION ea ON p.project_id = ea.project_id
JOIN COMPONENTS c ON ea.component_id = c.component_id
GROUP BY p.project_id, p.project_name, u.full_name
HAVING total_allocated_value_inr > 500
ORDER BY total_allocated_value_inr DESC;

-- ------------------------------------------------------------------------------
-- QUERY 7: Subquery - Find Students who have NOT returned components past due date
-- ------------------------------------------------------------------------------
SELECT 
    u.user_id,
    u.full_name,
    u.email,
    u.phone,
    u.roll_number
FROM USERS u
WHERE u.user_id IN (
    SELECT ea.user_id
    FROM EQUIPMENT_ALLOCATION ea
    WHERE ea.status = 'Issued' AND ea.expected_return_date < CURRENT_DATE
);

-- ------------------------------------------------------------------------------
-- QUERY 8: Subquery (NOT IN) - Find Equipment that has NEVER experienced a breakdown
-- ------------------------------------------------------------------------------
SELECT 
    e.equipment_id,
    e.equipment_name,
    e.location,
    e.status
FROM EQUIPMENT e
WHERE e.equipment_id NOT IN (
    SELECT DISTINCT b.equipment_id
    FROM BREAKDOWNS b
);

-- ------------------------------------------------------------------------------
-- QUERY 9: Calibration Schedule & Overdue Metrology Alerts
-- ------------------------------------------------------------------------------
SELECT 
    cal.calibration_id,
    e.equipment_id,
    e.equipment_name,
    cal.last_calibration_date,
    cal.next_due_date,
    cal.certified_by,
    cal.status,
    DATEDIFF(cal.next_due_date, CURRENT_DATE) AS days_until_due
FROM CALIBRATIONS cal
JOIN EQUIPMENT e ON cal.equipment_id = e.equipment_id
ORDER BY cal.next_due_date ASC;

-- ------------------------------------------------------------------------------
-- QUERY 10: Complete Audit Log / Timeline for a Specific Equipment (e.g. EQ001)
-- ------------------------------------------------------------------------------
SELECT 
    'Booking' AS event_type,
    b.booking_date AS event_date,
    CONCAT('Booked by ', u.full_name, ' for project: ', COALESCE(p.project_name, 'General')) AS details,
    b.status AS event_status
FROM BOOKINGS b
JOIN USERS u ON b.user_id = u.user_id
LEFT JOIN PROJECTS p ON b.project_id = p.project_id
WHERE b.equipment_id = 'EQ001'

UNION ALL

SELECT 
    'Breakdown' AS event_type,
    brk.reported_date AS event_date,
    CONCAT('Reported issue: ', brk.problem_description, ' (Severity: ', brk.severity, ')') AS details,
    brk.status AS event_status
FROM BREAKDOWNS brk
WHERE brk.equipment_id = 'EQ001'

UNION ALL

SELECT 
    'Maintenance' AS event_type,
    m.start_date AS event_date,
    CONCAT('Maintenance action: ', COALESCE(m.action_taken, m.problem_description), ' [Cost: Rs.', m.cost, ']') AS details,
    m.status AS event_status
FROM MAINTENANCE_JOBS m
WHERE m.equipment_id = 'EQ001'

ORDER BY event_date DESC;
