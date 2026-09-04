# 🤖 RoboLab: Robotics Laboratory Equipment, Component Booking and Maintenance Management System

> **DBMS Semester Project (Project 29)**  
> Built with **MySQL**, **Python Flask**, and a modern **Dark-Tech Web UI** (HTML5, Vanilla CSS, JavaScript).

---

## 📋 Table of Contents
1. [Project Overview](#-project-overview)
2. [Database Architecture & 3NF Schema](#-database-architecture--3nf-schema)
3. [Key Features & Workflows](#-key-features--workflows)
4. [Technology Stack](#-technology-stack)
5. [Installation & Setup Guide](#-installation--setup-guide)
6. [SQL Viva & Review Cheat Sheet](#-sql-viva--review-cheat-sheet)
7. [Project Directory Structure](#-project-directory-structure)

---

## 🚀 Project Overview

The **Robotics Laboratory Equipment, Component Booking and Maintenance Management System (RoboLab)** is an academic and laboratory operations platform designed to eliminate manual tracking of high-value robotic equipment, prototyping components, sensors, microcontrollers, and actuators.

The system solves critical lab management challenges:
* **Who currently has a component?** Immediate visibility of student borrowers, issuing date, and return due date.
* **Which project is using it?** Direct linkage between allocated components and student academic projects.
* **What equipment is available?** Real-time booking slots for 6-DOF Robotic Arms, 3D Printers, CNCs, and Mobile Robots.
* **Equipment Historical Timeline:** Complete audit trail for any piece of equipment showing bookings, breakdown incidents, vendor servicing, and calibration certifications.
* **Low Stock Alerts:** Automatic warnings when sensor or controller inventory drops below minimum thresholds.

---

## 🗄️ Database Architecture & 3NF Schema

The database consists of **18 relational tables** designed in **Third Normal Form (3NF)** with explicit foreign keys, primary keys, integrity constraints (`NOT NULL`, `UNIQUE`, `CHECK`, `DEFAULT`), SQL Views, and Triggers.

### Relational Schema Summary:

1. `ROLES`: System user roles (`Admin`, `Lab Technician`, `Faculty`, `Student`).
2. `USERS`: Lab staff, faculty mentors, and students with department and roll numbers.
3. `LABORATORIES`: Physical laboratory rooms and location codes (e.g. Central Robotics Lab, Rapid Prototyping Lab).
4. `EQUIPMENT_CATEGORIES`: Manipulators, Additive Manufacturing, Autonomous Mobile Robots, Test & Measurement, CNC.
5. `EQUIPMENT`: High-value equipment with unique IDs (`EQ001`), serial numbers, purchase dates, warranty dates, and statuses.
6. `COMPONENT_CATEGORIES`: Microcontrollers, Sensors, Motors, Drivers, Consumables.
7. `COMPONENTS`: Inventory with unique IDs (`C001`), total stock, available quantity, minimum stock thresholds, unit costs, and bin locations.
8. `PROJECTS`: Academic robotics projects guided by faculty.
9. `PROJECT_MEMBERS`: Many-to-many relationship mapping students to robotics projects.
10. `BOOKINGS`: Time slot reservations for heavy equipment with faculty approval status (`PENDING`, `APPROVED`, `IN_USE`, `RETURNED`).
11. `EQUIPMENT_ALLOCATION`: Component issuance mapping `Student -> Project -> Component -> Quantity -> Timeline`.
12. `USAGE_LOGS`: Session time logs and operational metrics.
13. `RETURNS`: Quality and condition verification (`Good`, `Damaged`, `Burnt/Faulty`) upon component returns.
14. `BREAKDOWNS`: Incident reports detailing equipment failures and severity.
15. `MAINTENANCE_JOBS`: Service jobs assigned to vendors or in-house technicians with cost tracking.
16. `VENDORS`: Service partners and suppliers.
17. `CALIBRATIONS`: Scheduled metrology calibration compliance for test instruments.
18. `NOTIFICATIONS`: System alerts for low stock, booking approvals, and overdue returns.

---

## 🛠️ Key Features & Workflows

```text
               STUDENT WORKFLOW
                      │
        Select Project & Search Item
                      │
               Create Booking
                      │
        Faculty / Technician Approves
                      │
           Component Stock Deducted
                      │
               Return & Verify
                      │
        Stock Restored / Breakdown Logged
```

### 1. Equipment Historical Timeline (EQ001 Robotic Arm)
Visiting `/equipment/EQ001` provides a comprehensive chronological timeline of all bookings, student projects, breakdown reports, and vendor maintenance jobs.

### 2. Student-Project Component Allocations
Tracks which student (`Sufiyan Khan`) has which items (`Arduino Uno x1`, `Ultrasonic Sensor x2`, `Servo Motor x2`) for a specific project (`Autonomous Line Following Robot`).

### 3. Interactive DBMS Viva Reports Explorer
A built-in `/reports` page allows evaluators and students to execute complex SQL queries and view both the **raw SQL statement** and the live query output.

---

## 💻 Technology Stack

* **Frontend:** HTML5, Modern CSS3 (Dark-Tech Glassmorphism, Google Fonts `Outfit`, `Inter`, `JetBrains Mono`), Vanilla JavaScript.
* **Backend:** Python Flask with parameter-sanitized SQL query executors.
* **Database:** MySQL 8.x / MariaDB (includes automatic SQLite fallback for instant zero-config testing).
* **Database Driver:** `mysql-connector-python`.

---

## ⚙️ Installation & Setup Guide

### 1. Clone or Open the Project
Open the folder in your terminal:
```bash
cd c:\Users\sumiy\OneDrive\Desktop\academic_codes\SQL_PBL
```

### 2. Set Up Python Virtual Environment
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. (Option A) Configure MySQL Database (Recommended for Review)
1. Open MySQL Command Line or MySQL Workbench.
2. Import the schema and seed scripts:
```sql
SOURCE database/schema.sql;
SOURCE database/seed.sql;
```
3. Update your `.env` or `config.py` with your MySQL credentials:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=robotics_lab
```

### 4. (Option B) Instant Local Mode (Zero-Config)
If MySQL is not currently running on your machine, the application automatically initializes and loads the complete dataset in local database mode without requiring any manual setup!

### 5. Launch the Web Application
```bash
python app.py
```
Open your browser and navigate to:
👉 **`http://127.0.0.1:5000`**

---

## 🔍 SQL Viva & Review Cheat Sheet

Here are sample queries included in `database/queries.sql` and the `/reports` explorer:

### Query 1: Find Active Component Allocations (4-Table JOIN)
```sql
SELECT 
    u.full_name AS student_name,
    u.roll_number,
    p.project_name,
    c.component_name,
    ea.quantity,
    ea.issue_date,
    ea.expected_return_date
FROM EQUIPMENT_ALLOCATION ea
JOIN USERS u ON ea.user_id = u.user_id
JOIN COMPONENTS c ON ea.component_id = c.component_id
JOIN PROJECTS p ON ea.project_id = p.project_id
WHERE ea.status = 'Issued';
```

### Query 2: Low Stock Warning (Conditional Selection)
```sql
SELECT 
    c.component_name,
    c.total_quantity,
    c.available_quantity,
    c.minimum_stock,
    (c.minimum_stock - c.available_quantity) AS shortage_count
FROM COMPONENTS c
WHERE c.available_quantity <= c.minimum_stock;
```

### Query 3: Equipment Utilization & Total Bookings (GROUP BY & Aggregation)
```sql
SELECT 
    e.equipment_name,
    ec.category_name,
    COUNT(b.booking_id) AS total_bookings
FROM EQUIPMENT e
JOIN EQUIPMENT_CATEGORIES ec ON e.category_id = ec.category_id
LEFT JOIN BOOKINGS b ON e.equipment_id = b.equipment_id
GROUP BY e.equipment_id, e.equipment_name, ec.category_name
ORDER BY total_bookings DESC;
```

---

## 📁 Project Directory Structure

```
SQL_PBL/
├── app.py                      # Flask backend controller & REST routing
├── config.py                   # Configuration for MySQL & database connections
├── db.py                       # Connection manager, query executor & fallback
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation & viva guide
├── database/
│   ├── schema.sql              # MySQL DDL with 18 tables, constraints, views & triggers
│   ├── seed.sql                # Seed dataset with realistic robotics components
│   └── queries.sql             # Viva review queries (JOINs, Aggregates, Subqueries)
├── static/
│   ├── css/
│   │   └── style.css           # Dark-tech glassmorphic styling & responsive layout
│   └── js/
│       └── main.js             # Modal interactions and dynamic UI logic
└── templates/
    ├── layout.html             # Base layout with sidebar navigation
    ├── dashboard.html          # KPI dashboard & activity feeds
    ├── equipment.html          # Equipment catalog & registration
    ├── equipment_detail.html   # Equipment specs & chronological history timeline
    ├── components.html         # Component stock levels, restock & issue
    ├── bookings.html           # Slot booking & approval workflow
    ├── allocations.html        # Student -> Project -> Component tracking
    ├── projects.html           # Robotics academic projects & team members
    ├── maintenance.html        # Breakdowns & maintenance jobs
    ├── calibrations.html       # Metrology & calibration compliance
    ├── vendors.html            # Service partners & vendors
    └── reports.html            # Interactive SQL query playground for reviews
```
