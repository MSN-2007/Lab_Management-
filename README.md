# 🤖 RoboLab: Robotics Laboratory Equipment, Component Booking and Maintenance Management System

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Flask: 3.0+](https://img.shields.io/badge/Flask-3.0+-black.svg)](https://palletsprojects.com/p/flask/)
[![Offline Ready](https://img.shields.io/badge/Offline-100%25%20Ready-success.svg)](README.md)

> An open-source, academic and laboratory operations platform designed to eliminate manual tracking of robotics equipment, hardware prototyping components, sensors, microcontrollers, and actuators.

---

## 📋 Table of Contents
1. [Project Overview](#-project-overview)
2. [Key Features](#-key-features)
3. [Technology Stack](#-technology-stack)
4. [Quick Start & Setup](#-quick-start--setup)
5. [Database Architecture & 3NF Schema](#-database-architecture--3nf-schema)
6. [SQL Viva & Reports Explorer](#-sql-viva--reports-explorer)
7. [Contributing](#-contributing)
8. [License](#-license)

---

## 🚀 Project Overview

The **RoboLab** system provides a complete digital workflow for academic makerspaces, university robotics labs, and research institutions:
* **Component Allocation:** Immediate tracking of student borrowers, project linkages, issue dates, and return due dates.
* **Slot Reservations:** Time slot booking for shared high-value equipment (6-DOF Robotic Arms, 3D Printers, CNCs, Mobile Robots).
* **Equipment Historical Timeline:** Complete audit trail showing bookings, breakdown incidents, vendor servicing, and calibration records.
* **Low Stock Alerts:** Automatic warnings when inventory drops below predefined minimum thresholds.
* **100% Offline Ready:** Bundled with local fonts and FontAwesome icon assets—no internet connection required to run.

---

## 🛠️ Key Features

* 📱 **Clean Minimalist Dark UI:** Slate/charcoal theme designed for high usability and clarity.
* ⚡ **Dual Database Engine:** Runs with **MySQL** in production and auto-falls back to **SQLite** for zero-config testing.
* 👥 **Role-Based Portals:** Personalized interfaces for **Students**, **Faculty Mentors**, **Lab Technicians**, and **Admins**.
* 📊 **Interactive SQL Viva Explorer:** Live SQL queries with display of raw queries and execution results.
* 🔌 **100% Offline Compatible:** Zero external CDN dependencies.

---

## 💻 Technology Stack

* **Frontend:** HTML5, Modern Vanilla CSS (Clean Minimalist Dark Theme), Vanilla JavaScript, Local FontAwesome 6.5.
* **Backend:** Python Flask.
* **Database Support:** MySQL 8.x / SQLite 3 (Embedded).
* **Configuration:** `python-dotenv` with `.env` support.

---

## ⚙️ Quick Start & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/SQL_PBL.git
cd SQL_PBL
```

### 2. Set Up Virtual Environment (Optional but Recommended)
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the example configuration file:
```bash
cp .env.example .env
```
*(By default, RoboLab runs immediately out-of-the-box using the embedded SQLite database if MySQL is not running).*

### 5. Start the Application
```bash
python app.py
# Or on Windows using Python launcher:
py app.py
```

Open your browser at:
👉 **`http://127.0.0.1:5000`**

---

## 🗄️ Database Architecture & 3NF Schema

The database consists of **18 relational tables** designed in **Third Normal Form (3NF)**:

1. `ROLES`: System roles (`Admin`, `Lab Technician`, `Faculty`, `Student`).
2. `USERS`: Lab staff, mentors, and students with department and roll numbers.
3. `LABORATORIES`: Physical laboratory locations and room codes.
4. `EQUIPMENT_CATEGORIES`: Manipulators, Additive Manufacturing, AMRs, Test Instruments.
5. `EQUIPMENT`: High-value equipment with unique IDs, serial numbers, and statuses.
6. `COMPONENT_CATEGORIES`: Microcontrollers, Sensors, Motors, Drivers.
7. `COMPONENTS`: Inventory with stock levels, thresholds, unit costs, and storage bins.
8. `PROJECTS`: Academic robotics projects guided by faculty.
9. `PROJECT_MEMBERS`: Mapping students to robotics projects.
10. `BOOKINGS`: Equipment slot reservations with approvals.
11. `EQUIPMENT_ALLOCATION`: Component issuance mapping (`Student -> Project -> Component`).
12. `USAGE_LOGS`: Session time logs and operational metrics.
13. `RETURNS`: Quality verification (`Good`, `Damaged`, `Burnt`) upon component returns.
14. `BREAKDOWNS`: Incident reports detailing equipment failures and severity.
15. `MAINTENANCE_JOBS`: Service jobs assigned to vendors or in-house technicians.
16. `VENDORS`: Service partners and suppliers.
17. `CALIBRATIONS`: Scheduled metrology calibration compliance.
18. `NOTIFICATIONS`: System alerts for low stock and overdue returns.

---

## 🤝 Contributing

Contributions are welcome! Please check out [CONTRIBUTING.md](CONTRIBUTING.md) for branch workflows and guidelines.

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.
