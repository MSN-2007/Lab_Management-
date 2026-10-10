import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from config import Config
from db import query_db, execute_db, is_using_sqlite, is_demo_loaded, load_demo_showcase_data, reset_to_clean_slate

app = Flask(__name__)
app.config.from_object(Config)

def get_current_user():
    """Returns the currently logged-in user record or default user."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    user = query_db("""
        SELECT u.*, r.role_name
        FROM USERS u
        JOIN ROLES r ON u.role_id = r.role_id
        WHERE u.user_id = %s
    """, [user_id], one=True)
    return user

@app.context_processor
def inject_global_metrics():
    """Injects system status, user role, and notification counters across all templates."""
    try:
        user = get_current_user()
        unread_notifs = query_db("SELECT COUNT(*) AS cnt FROM NOTIFICATIONS WHERE is_read = 0", one=True)
        pending_bookings = query_db("SELECT COUNT(*) AS cnt FROM BOOKINGS WHERE status = 'PENDING'", one=True)
        low_stock_count = query_db("SELECT COUNT(*) AS cnt FROM COMPONENTS WHERE available_quantity <= minimum_stock", one=True)
        engine_mode = "SQLite (Local Auto-Sync)" if is_using_sqlite() else "MySQL (Production)"
        demo_active = is_demo_loaded()
        
        # Fetch list of quick-switch users for the topbar
        all_demo_users = query_db("""
            SELECT u.user_id, u.full_name, u.email, u.roll_number, r.role_name
            FROM USERS u
            JOIN ROLES r ON u.role_id = r.role_id
            ORDER BY u.user_id ASC
            LIMIT 10
        """)
        
        return {
            'current_user': user,
            'demo_users': all_demo_users or [],
            'unread_notifications_count': unread_notifs['cnt'] if unread_notifs else 0,
            'pending_bookings_count': pending_bookings['cnt'] if pending_bookings else 0,
            'low_stock_alerts_count': low_stock_count['cnt'] if low_stock_count else 0,
            'database_engine': engine_mode,
            'is_demo_mode': demo_active
        }
    except Exception:
        return {
            'current_user': None,
            'demo_users': [],
            'unread_notifications_count': 0,
            'pending_bookings_count': 0,
            'low_stock_alerts_count': 0,
            'database_engine': 'Database Initializing',
            'is_demo_mode': False
        }

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Auto-fallback to first available user
            first_user = query_db("SELECT u.user_id, r.role_name, u.full_name FROM USERS u JOIN ROLES r ON u.role_id = r.role_id ORDER BY u.user_id ASC LIMIT 1", one=True)
            if first_user:
                session['user_id'] = first_user['user_id']
                session['role_name'] = first_user['role_name']
                session['full_name'] = first_user['full_name']
            else:
                session['user_id'] = 1
                session['role_name'] = 'Admin'
        return f(*args, **kwargs)
    return decorated_function

# ------------------------------------------------------------------------------
# AUTHENTICATION, REGISTRATION & DEMO CONTROL
# ------------------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        user = query_db("""
            SELECT u.*, r.role_name
            FROM USERS u
            JOIN ROLES r ON u.role_id = r.role_id
            WHERE LOWER(u.email) = %s OR LOWER(u.roll_number) = %s
        """, [email, email], one=True)
        
        if user:
            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            session['role_name'] = user['role_name']
            session['role_id'] = user['role_id']
            flash(f"Welcome back, {user['full_name']} ({user['role_name']})!", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or roll/staff number. If this is a new profile, please Register first or click 'Run Live Demo Showcase'.", 'danger')

    # Demo personas for quick 1-click login
    demo_roles = query_db("""
        SELECT u.user_id, u.full_name, u.email, u.roll_number, u.department, r.role_name, r.description
        FROM USERS u
        JOIN ROLES r ON u.role_id = r.role_id
        WHERE u.user_id IN (1, 2, 3, 5)
        ORDER BY u.user_id ASC
    """)
    demo_active = is_demo_loaded()
    return render_template('login.html', demo_roles=demo_roles or [], is_demo_mode=demo_active)

@app.route('/register', methods=['GET', 'POST'])
def register():
    roles = query_db("SELECT * FROM ROLES ORDER BY role_id ASC") or []
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        role_id = int(request.form.get('role_id', 4))
        roll_number = request.form.get('roll_number', '').strip() or None
        department = request.form.get('department', 'Robotics & Automation').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', 'default123').strip()
        
        if not full_name or not email:
            flash("Full name and email address are required.", "danger")
            return render_template('register.html', roles=roles)
            
        existing = query_db("SELECT * FROM USERS WHERE LOWER(email) = %s OR (roll_number IS NOT NULL AND roll_number = %s)", [email, roll_number], one=True)
        if existing:
            flash("An account with this email address or roll/staff ID already exists. Please log in.", "warning")
            return redirect(url_for('login'))
            
        try:
            new_user_id = execute_db("""
                INSERT INTO USERS (role_id, full_name, email, password_hash, roll_number, phone, department)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, [role_id, full_name, email, password, roll_number, phone, department])
            
            user = query_db("""
                SELECT u.*, r.role_name
                FROM USERS u
                JOIN ROLES r ON u.role_id = r.role_id
                WHERE u.user_id = %s
            """, [new_user_id], one=True)
            
            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            session['role_name'] = user['role_name']
            session['role_id'] = user['role_id']
            
            flash(f"Profile created successfully! Welcome to RoboLab, {user['full_name']} ({user['role_name']}).", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Error registering account: {str(e)}", "danger")
            return render_template('register.html', roles=roles)
            
    return render_template('register.html', roles=roles)

@app.route('/launch-demo')
def launch_demo():
    if not is_demo_loaded():
        load_demo_showcase_data()
    user = query_db("SELECT u.*, r.role_name FROM USERS u JOIN ROLES r ON u.role_id = r.role_id WHERE u.user_id = 1", one=True)
    if user:
        session['user_id'] = user['user_id']
        session['full_name'] = user['full_name']
        session['role_name'] = user['role_name']
        session['role_id'] = user['role_id']
        flash(f"✨ Launched Live Demo Showcase as {user['full_name']} ({user['role_name']}) with preloaded robotics equipment, components, and bookings!", "success")
    return redirect(url_for('dashboard'))

@app.route('/demo-login/<int:user_id>')
def demo_login(user_id):
    if not is_demo_loaded():
        load_demo_showcase_data()
    user = query_db("SELECT u.*, r.role_name FROM USERS u JOIN ROLES r ON u.role_id = r.role_id WHERE u.user_id = %s", [user_id], one=True)
    if user:
        session['user_id'] = user['user_id']
        session['full_name'] = user['full_name']
        session['role_name'] = user['role_name']
        session['role_id'] = user['role_id']
        flash(f"✨ Switched active persona to: {user['full_name']} ({user['role_name']})", "success")
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/database/load-demo', methods=['GET', 'POST'])
def db_load_demo():
    load_demo_showcase_data()
    user = query_db("SELECT u.*, r.role_name FROM USERS u JOIN ROLES r ON u.role_id = r.role_id WHERE u.user_id = 1", one=True)
    if user:
        session['user_id'] = user['user_id']
        session['role_name'] = user['role_name']
        session['full_name'] = user['full_name']
    flash("✨ Live Demo Showcase data loaded! All sample equipment, components, allocations, and bookings are ready to explore.", "success")
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/database/reset-clean', methods=['GET', 'POST'])
def db_reset_clean():
    reset_to_clean_slate()
    user = query_db("SELECT u.*, r.role_name FROM USERS u JOIN ROLES r ON u.role_id = r.role_id WHERE u.user_id = 1", one=True)
    if user:
        session['user_id'] = user['user_id']
        session['role_name'] = user['role_name']
        session['full_name'] = user['full_name']
    flash("🧹 Database reset to Clean Slate. All sample equipment, components, and bookings cleared. Ready for your own custom laboratories and profiles!", "info")
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", 'info')
    return redirect(url_for('login'))

@app.route('/switch-role/<int:user_id>')
def switch_role(user_id):
    user = query_db("""
        SELECT u.*, r.role_name
        FROM USERS u
        JOIN ROLES r ON u.role_id = r.role_id
        WHERE u.user_id = %s
    """, [user_id], one=True)
    if user:
        session['user_id'] = user['user_id']
        session['full_name'] = user['full_name']
        session['role_name'] = user['role_name']
        session['role_id'] = user['role_id']
        flash(f"Switched active persona to: {user['full_name']} ({user['role_name']})", 'success')
    return redirect(request.referrer or url_for('dashboard'))

# ------------------------------------------------------------------------------
# 0. USER ACCOUNTS MANAGEMENT & PROFILE
# ------------------------------------------------------------------------------
@app.route('/users')
@login_required
def users_list():
    user = get_current_user()
    if user and user['role_name'] != 'Admin':
        flash("Access restricted. User Accounts management is restricted to Administrators.", 'danger')
        return redirect(url_for('dashboard'))

    role_filter = request.args.get('role', '')
    search_query = request.args.get('q', '').strip()
    
    sql = """
        SELECT u.*, r.role_name,
               (SELECT COUNT(*) FROM BOOKINGS b WHERE b.user_id = u.user_id) AS total_bookings,
               (SELECT COUNT(*) FROM EQUIPMENT_ALLOCATION ea WHERE ea.user_id = u.user_id AND ea.status = 'Issued') AS active_loans,
               (SELECT COUNT(*) FROM PROJECT_MEMBERS pm WHERE pm.user_id = u.user_id) AS project_count
        FROM USERS u
        JOIN ROLES r ON u.role_id = r.role_id
        WHERE 1=1
    """
    params = []
    if role_filter:
        sql += " AND r.role_name = %s"
        params.append(role_filter)
    if search_query:
        sql += " AND (u.full_name LIKE %s OR u.email LIKE %s OR u.roll_number LIKE %s OR u.department LIKE %s)"
        term = f"%{search_query}%"
        params.extend([term, term, term, term])
        
    sql += " ORDER BY u.role_id ASC, u.user_id ASC"
    users = query_db(sql, params)
    roles = query_db("SELECT * FROM ROLES ORDER BY role_id ASC") or []
    
    return render_template('users.html', users=users, roles=roles, selected_role=role_filter, search=search_query)

@app.route('/users/add', methods=['POST'])
@login_required
def users_add():
    user = get_current_user()
    if user and user['role_name'] != 'Admin':
        flash("Unauthorized. Only Administrators can create accounts.", 'danger')
        return redirect(url_for('dashboard'))

    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    role_id = int(request.form.get('role_id', 4))
    roll_number = request.form.get('roll_number', '').strip() or None
    department = request.form.get('department', 'Robotics & Automation').strip()
    phone = request.form.get('phone', '').strip()
    
    if not full_name or not email:
        flash("Full Name and Email are required.", "danger")
        return redirect(url_for('users_list'))
        
    try:
        execute_db("""
            INSERT INTO USERS (role_id, full_name, email, roll_number, phone, department)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, [role_id, full_name, email, roll_number, phone, department])
        flash(f"New account for '{full_name}' assigned successfully!", "success")
    except Exception as e:
        flash(f"Error creating account: {str(e)}", "danger")
        
    return redirect(url_for('users_list'))

@app.route('/users/edit/<int:user_id>', methods=['POST'])
@login_required
def users_edit(user_id):
    user = get_current_user()
    if user and user['role_name'] != 'Admin':
        flash("Unauthorized. Only Administrators can edit accounts.", 'danger')
        return redirect(url_for('dashboard'))

    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    role_id = int(request.form.get('role_id', 4))
    roll_number = request.form.get('roll_number', '').strip() or None
    department = request.form.get('department', '').strip()
    phone = request.form.get('phone', '').strip()
    
    try:
        execute_db("""
            UPDATE USERS
            SET full_name = %s, email = %s, role_id = %s, roll_number = %s, department = %s, phone = %s
            WHERE user_id = %s
        """, [full_name, email, role_id, roll_number, department, phone, user_id])
        flash(f"Account for '{full_name}' updated successfully.", "success")
    except Exception as e:
        flash(f"Error updating account: {str(e)}", "danger")
        
    return redirect(url_for('users_list'))

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
def users_delete(user_id):
    user = get_current_user()
    if user and user['role_name'] != 'Admin':
        flash("Unauthorized. Only Administrators can delete accounts.", 'danger')
        return redirect(url_for('dashboard'))

    curr = session.get('user_id')
    if curr == user_id:
        flash("You cannot delete your own currently active account.", "warning")
        return redirect(url_for('users_list'))
        
    try:
        execute_db("DELETE FROM USERS WHERE user_id = %s", [user_id])
        flash(f"Account #{user_id} deleted successfully.", "info")
    except Exception as e:
        flash(f"Error deleting user (they may have active bookings or loans): {str(e)}", "danger")
        
    return redirect(url_for('users_list'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        full_name = request.form.get('full_name', user['full_name']).strip()
        phone = request.form.get('phone', user['phone']).strip()
        department = request.form.get('department', user['department']).strip()
        roll_number = request.form.get('roll_number', user['roll_number']).strip()
        
        try:
            execute_db("""
                UPDATE USERS
                SET full_name = %s, phone = %s, department = %s, roll_number = %s
                WHERE user_id = %s
            """, [full_name, phone, department, roll_number, user['user_id']])
            session['full_name'] = full_name
            flash("Profile updated successfully!", "success")
            return redirect(url_for('profile'))
        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "danger")
            
    # User activity statistics
    bookings_res = query_db("SELECT COUNT(*) AS cnt FROM BOOKINGS WHERE user_id = %s", [user['user_id']], one=True)
    allocations_res = query_db("SELECT COUNT(*) AS cnt FROM EQUIPMENT_ALLOCATION WHERE user_id = %s AND status = 'Issued'", [user['user_id']], one=True)
    projects_res = query_db("SELECT COUNT(*) AS cnt FROM PROJECT_MEMBERS WHERE user_id = %s", [user['user_id']], one=True)
    
    bookings_count = bookings_res['cnt'] if bookings_res else 0
    allocations_count = allocations_res['cnt'] if allocations_res else 0
    projects_count = projects_res['cnt'] if projects_res else 0
    
    return render_template('profile.html', user=user, bookings_count=bookings_count, allocations_count=allocations_count, projects_count=projects_count)

# ------------------------------------------------------------------------------
# 1. DASHBOARD & ROLE-TAILORED OVERVIEW
# ------------------------------------------------------------------------------
@app.route('/')
@login_required
def dashboard():
    user = get_current_user()
    role = user['role_name'] if user else 'Admin'
    user_id = user['user_id'] if user else 1
    
    # Global Metrics
    total_eq = query_db("SELECT COUNT(*) AS cnt FROM EQUIPMENT", one=True)['cnt']
    avail_eq = query_db("SELECT COUNT(*) AS cnt FROM EQUIPMENT WHERE status = 'Available'", one=True)['cnt']
    in_use_eq = query_db("SELECT COUNT(*) AS cnt FROM EQUIPMENT WHERE status = 'In Use'", one=True)['cnt']
    maint_eq = query_db("SELECT COUNT(*) AS cnt FROM EQUIPMENT WHERE status = 'Maintenance'", one=True)['cnt']
    
    total_comp = query_db("SELECT COUNT(*) AS cnt, SUM(total_quantity) AS total_items, SUM(available_quantity) AS avail_items FROM COMPONENTS", one=True)
    active_allocations = query_db("SELECT COUNT(*) AS cnt FROM EQUIPMENT_ALLOCATION WHERE status = 'Issued'", one=True)['cnt']
    active_projects = query_db("SELECT COUNT(*) AS cnt FROM PROJECTS WHERE status = 'Active'", one=True)['cnt']
    
    # Personal Activity Data for Student & Faculty
    my_allocations = []
    my_bookings = []
    my_projects = []
    if role in ['Student', 'Faculty']:
        my_allocations = query_db("""
            SELECT ea.*, c.component_name, c.storage_bin, COALESCE(p.project_name, 'Independent Lab Activity') AS project_name
            FROM EQUIPMENT_ALLOCATION ea
            JOIN COMPONENTS c ON ea.component_id = c.component_id
            LEFT JOIN PROJECTS p ON ea.project_id = p.project_id
            WHERE ea.user_id = %s
            ORDER BY ea.allocation_id DESC
        """, [user_id])
        
        my_bookings = query_db("""
            SELECT b.*, e.equipment_name, e.location, p.project_name
            FROM BOOKINGS b
            JOIN EQUIPMENT e ON b.equipment_id = e.equipment_id
            LEFT JOIN PROJECTS p ON b.project_id = p.project_id
            WHERE b.user_id = %s
            ORDER BY b.booking_id DESC
        """, [user_id])
        
        if role == 'Faculty':
            my_projects = query_db("""
                SELECT p.*, 'Faculty Guide' AS role_in_project, u.full_name AS guide_name
                FROM PROJECTS p
                LEFT JOIN USERS u ON p.guide_faculty_id = u.user_id
                WHERE p.guide_faculty_id = %s
                ORDER BY p.project_id DESC
            """, [user_id])
        else:
            my_projects = query_db("""
                SELECT p.*, pm.role_in_project, u.full_name AS guide_name
                FROM PROJECTS p
                JOIN PROJECT_MEMBERS pm ON p.project_id = pm.project_id
                LEFT JOIN USERS u ON p.guide_faculty_id = u.user_id
                WHERE pm.user_id = %s
                ORDER BY p.project_id DESC
            """, [user_id])

    # Recent Activity Feed for Staff / Admin / Tech / Faculty
    recent_allocations = query_db("""
        SELECT ea.allocation_id, u.full_name AS student_name, c.component_name, ea.quantity, p.project_name, ea.issue_date, ea.status
        FROM EQUIPMENT_ALLOCATION ea
        JOIN USERS u ON ea.user_id = u.user_id
        JOIN COMPONENTS c ON ea.component_id = c.component_id
        JOIN PROJECTS p ON ea.project_id = p.project_id
        ORDER BY ea.allocation_id DESC LIMIT 4
    """)
    
    recent_bookings = query_db("""
        SELECT b.booking_id, e.equipment_name, u.full_name AS student_name, b.booking_date, b.start_time, b.end_time, b.status
        FROM BOOKINGS b
        JOIN EQUIPMENT e ON b.equipment_id = e.equipment_id
        JOIN USERS u ON b.user_id = u.user_id
        ORDER BY b.booking_id DESC LIMIT 4
    """)
    
    recent_maintenance = query_db("""
        SELECT m.job_id, e.equipment_name, m.problem_description, m.start_date, m.status, v.vendor_name
        FROM MAINTENANCE_JOBS m
        JOIN EQUIPMENT e ON m.equipment_id = e.equipment_id
        LEFT JOIN VENDORS v ON m.vendor_id = v.vendor_id
        ORDER BY m.job_id DESC LIMIT 4
    """)

    low_stock_items = query_db("""
        SELECT component_id, component_name, available_quantity, minimum_stock, total_quantity
        FROM COMPONENTS
        WHERE available_quantity <= minimum_stock
        ORDER BY (minimum_stock - available_quantity) DESC LIMIT 5
    """)
    
    return render_template('dashboard.html',
                           role=role,
                           total_eq=total_eq,
                           avail_eq=avail_eq,
                           in_use_eq=in_use_eq,
                           maint_eq=maint_eq,
                           total_comp=total_comp['cnt'] or 0,
                           avail_comp_units=total_comp['avail_items'] or 0,
                           active_allocations=active_allocations,
                           active_projects=active_projects,
                           my_allocations=my_allocations,
                           my_bookings=my_bookings,
                           my_projects=my_projects,
                           recent_allocations=recent_allocations,
                           recent_bookings=recent_bookings,
                           recent_maintenance=recent_maintenance,
                           low_stock_items=low_stock_items)

# ------------------------------------------------------------------------------
# 2. EQUIPMENT CATALOG & HISTORY TIMELINE
# ------------------------------------------------------------------------------
@app.route('/equipment')
@login_required
def equipment_list():
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    search_query = request.args.get('q', '').strip()
    
    sql = """
        SELECT e.*, ec.category_name, l.lab_name
        FROM EQUIPMENT e
        JOIN EQUIPMENT_CATEGORIES ec ON e.category_id = ec.category_id
        JOIN LABORATORIES l ON e.laboratory_id = l.lab_id
        WHERE 1=1
    """
    params = []
    if status_filter:
        sql += " AND e.status = %s"
        params.append(status_filter)
    if category_filter:
        sql += " AND e.category_id = %s"
        params.append(category_filter)
    if search_query:
        sql += " AND (e.equipment_name LIKE %s OR e.equipment_id LIKE %s OR e.location LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
        
    sql += " ORDER BY e.equipment_id ASC"
    
    equipment = query_db(sql, params)
    categories = query_db("SELECT * FROM EQUIPMENT_CATEGORIES ORDER BY category_name ASC")
    labs = query_db("SELECT * FROM LABORATORIES ORDER BY lab_name ASC")
    
    return render_template('equipment.html', equipment=equipment, categories=categories, labs=labs,
                           selected_status=status_filter, selected_cat=category_filter, search=search_query)

@app.route('/equipment/<equipment_id>')
@login_required
def equipment_detail(equipment_id):
    eq = query_db("""
        SELECT e.*, ec.category_name, l.lab_name, l.location_code
        FROM EQUIPMENT e
        JOIN EQUIPMENT_CATEGORIES ec ON e.category_id = ec.category_id
        JOIN LABORATORIES l ON e.laboratory_id = l.lab_id
        WHERE e.equipment_id = %s
    """, [equipment_id], one=True)
    
    if not eq:
        flash(f"Equipment '{equipment_id}' not found.", 'danger')
        return redirect(url_for('equipment_list'))
    
    bookings = query_db("""
        SELECT b.booking_date AS event_date, 'Booking' AS event_type, b.status AS event_status,
               CONCAT('Booked by ', u.full_name, ' (', u.roll_number, ') for ', COALESCE(p.project_name, 'General Research'), ' [Slot: ', b.start_time, ' - ', b.end_time, ']') AS details,
               b.purpose AS notes
        FROM BOOKINGS b
        JOIN USERS u ON b.user_id = u.user_id
        LEFT JOIN PROJECTS p ON b.project_id = p.project_id
        WHERE b.equipment_id = %s
    """, [equipment_id])
    
    breakdowns = query_db("""
        SELECT brk.reported_date AS event_date, 'Breakdown' AS event_type, brk.status AS event_status,
               CONCAT('Reported by ', u.full_name, ' - Severity: ', brk.severity) AS details,
               brk.problem_description AS notes
        FROM BREAKDOWNS brk
        JOIN USERS u ON brk.reported_by = u.user_id
        WHERE brk.equipment_id = %s
    """, [equipment_id])
    
    user = get_current_user()
    if user and user['role_name'] in ['Admin', 'Lab Technician']:
        maint_cost_expr = "CONCAT('Vendor: ', COALESCE(v.vendor_name, 'In-House'), ' | Cost: Rs.', m.cost)"
    else:
        maint_cost_expr = "CONCAT('Vendor: ', COALESCE(v.vendor_name, 'In-House'))"

    maintenance = query_db(f"""
        SELECT m.start_date AS event_date, 'Maintenance' AS event_type, m.status AS event_status,
               {maint_cost_expr} AS details,
               CONCAT('Action: ', COALESCE(m.action_taken, m.problem_description)) AS notes
        FROM MAINTENANCE_JOBS m
        LEFT JOIN VENDORS v ON m.vendor_id = v.vendor_id
        WHERE m.equipment_id = %s
    """, [equipment_id])
    
    calibrations = query_db("""
        SELECT cal.last_calibration_date AS event_date, 'Calibration' AS event_type, cal.status AS event_status,
               CONCAT('Certified by: ', cal.certified_by, ' | Next Due: ', cal.next_due_date) AS details,
               cal.remarks AS notes
        FROM CALIBRATIONS cal
        WHERE cal.equipment_id = %s
    """, [equipment_id])
    
    timeline = bookings + breakdowns + maintenance + calibrations
    timeline.sort(key=lambda x: str(x['event_date']), reverse=True)
    
    return render_template('equipment_detail.html', eq=eq, timeline=timeline)

@app.route('/equipment/add', methods=['POST'])
@login_required
def equipment_add():
    user = get_current_user()
    if user and user['role_name'] == 'Student':
        flash("Unauthorized: Students cannot register new equipment.", 'danger')
        return redirect(url_for('equipment_list'))

    eq_id = request.form.get('equipment_id', '').strip()
    name = request.form.get('equipment_name', '').strip()
    cat_id = request.form.get('category_id')
    lab_id = request.form.get('laboratory_id')
    serial = request.form.get('serial_number', '').strip()
    purchase_date = request.form.get('purchase_date')
    warranty_end = request.form.get('warranty_end') or None
    location = request.form.get('location', '').strip()
    desc = request.form.get('description', '').strip()
    
    try:
        execute_db("""
            INSERT INTO EQUIPMENT (equipment_id, equipment_name, category_id, laboratory_id, serial_number, purchase_date, warranty_end, status, location, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s)
        """, [eq_id, name, cat_id, lab_id, serial, purchase_date, warranty_end, location, desc])
        flash(f"Equipment '{name}' ({eq_id}) registered successfully!", 'success')
    except Exception as e:
        flash(f"Error registering equipment: {str(e)}", 'danger')
        
    return redirect(url_for('equipment_list'))

@app.route('/equipment/<equipment_id>/status', methods=['POST'])
@login_required
def equipment_update_status(equipment_id):
    new_status = request.form.get('status')
    try:
        execute_db("UPDATE EQUIPMENT SET status = %s WHERE equipment_id = %s", [new_status, equipment_id])
        flash(f"Status for {equipment_id} updated to '{new_status}'.", 'success')
    except Exception as e:
        flash(f"Failed to update status: {str(e)}", 'danger')
    return redirect(url_for('equipment_detail', equipment_id=equipment_id))

# ------------------------------------------------------------------------------
# 3. COMPONENTS & STOCK MANAGEMENT
# ------------------------------------------------------------------------------
@app.route('/components')
@login_required
def components_list():
    cat_filter = request.args.get('category', '')
    low_stock_only = request.args.get('low_stock', '')
    search = request.args.get('q', '').strip()
    
    sql = """
        SELECT c.*, cc.category_name,
               (c.total_quantity - c.available_quantity) AS issued_quantity
        FROM COMPONENTS c
        JOIN COMPONENT_CATEGORIES cc ON c.category_id = cc.category_id
        WHERE 1=1
    """
    params = []
    if cat_filter:
        sql += " AND c.category_id = %s"
        params.append(cat_filter)
    if low_stock_only == '1':
        sql += " AND c.available_quantity <= c.minimum_stock"
    if search:
        sql += " AND (c.component_name LIKE %s OR c.component_id LIKE %s OR c.storage_bin LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        
    sql += " ORDER BY c.component_id ASC"
    
    components = query_db(sql, params)
    categories = query_db("SELECT * FROM COMPONENT_CATEGORIES ORDER BY category_name ASC")
    projects = query_db("SELECT project_id, project_name FROM PROJECTS WHERE status = 'Active' ORDER BY project_name ASC")
    
    return render_template('components.html', components=components, categories=categories, projects=projects,
                           selected_cat=cat_filter, low_stock=low_stock_only, search=search)

@app.route('/components/add', methods=['POST'])
@login_required
def component_add():
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized. Only Admin and Lab Technicians can add new components.", 'danger')
        return redirect(url_for('components_list'))

    c_id = request.form.get('component_id', '').strip()
    name = request.form.get('component_name', '').strip()
    cat_id = request.form.get('category_id')
    total_qty = int(request.form.get('total_quantity', 0))
    min_stock = int(request.form.get('minimum_stock', 5))
    unit_cost = float(request.form.get('unit_cost', 0.0))
    bin_loc = request.form.get('storage_bin', '').strip()
    specs = request.form.get('specifications', '').strip()
    
    try:
        execute_db("""
            INSERT INTO COMPONENTS (component_id, component_name, category_id, total_quantity, available_quantity, minimum_stock, unit_cost, storage_bin, specifications)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [c_id, name, cat_id, total_qty, total_qty, min_stock, unit_cost, bin_loc, specs])
        flash(f"Component '{name}' ({c_id}) added to inventory!", 'success')
    except Exception as e:
        flash(f"Error adding component: {str(e)}", 'danger')
        
    return redirect(url_for('components_list'))

@app.route('/components/restock', methods=['POST'])
@login_required
def component_restock():
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized. Only Admin and Lab Technicians can restock components.", 'danger')
        return redirect(url_for('components_list'))

    c_id = request.form.get('component_id')
    add_qty = int(request.form.get('additional_quantity', 0))
    if add_qty <= 0:
        flash("Restock quantity must be positive.", 'warning')
        return redirect(url_for('components_list'))
        
    try:
        execute_db("""
            UPDATE COMPONENTS
            SET total_quantity = total_quantity + %s, available_quantity = available_quantity + %s
            WHERE component_id = %s
        """, [add_qty, add_qty, c_id])
        flash(f"Restocked {add_qty} units to component {c_id}.", 'success')
    except Exception as e:
        flash(f"Restock error: {str(e)}", 'danger')
        
    return redirect(url_for('components_list'))

@app.route('/components/request', methods=['POST'])
@login_required
def component_request():
    user = get_current_user()
    user_id = user['user_id'] if user else 1

    data = request.get_json(silent=True)
    if data:
        items = data.get('items', [])
        proj_id = data.get('project_id') or None
        exp_return = data.get('expected_return_date')
        remarks = data.get('remarks', '').strip()
    else:
        c_id = request.form.get('component_id')
        qty = int(request.form.get('quantity', 1))
        items = [{'component_id': c_id, 'quantity': qty}] if c_id else []
        proj_id = request.form.get('project_id') or None
        exp_return = request.form.get('expected_return_date')
        remarks = request.form.get('remarks', '').strip()

    if not items:
        if request.is_json:
            return jsonify({'success': False, 'message': 'No components selected.'}), 400
        flash("No components selected for request.", 'warning')
        return redirect(url_for('components_list'))

    import datetime
    today_str = datetime.date.today().isoformat()
    if not exp_return:
        exp_return = (datetime.date.today() + datetime.timedelta(days=14)).isoformat()

    success_count = 0
    for item in items:
        c_id = item.get('component_id')
        qty = int(item.get('quantity', 1))
        if not c_id or qty <= 0:
            continue

        comp = query_db("SELECT component_name, available_quantity FROM COMPONENTS WHERE component_id = %s", [c_id], one=True)
        if not comp:
            continue

        execute_db("""
            INSERT INTO EQUIPMENT_ALLOCATION (component_id, user_id, project_id, quantity, issue_date, expected_return_date, status, remarks)
            VALUES (%s, %s, %s, %s, %s, %s, 'Requested', %s)
        """, [c_id, user_id, proj_id, qty, today_str, exp_return, remarks or f"Requested {qty}x {comp['component_name']}"])
        success_count += 1

    if request.is_json:
        return jsonify({'success': True, 'count': success_count, 'message': f'Requested {success_count} component(s) successfully!'})

    flash(f"Submitted component request for {success_count} item(s)! Awaiting Admin / Technician approval.", 'success')
    return redirect(url_for('allocations_list'))

# ------------------------------------------------------------------------------
# 4. BOOKINGS & APPROVALS (Equipment Slots)
# ------------------------------------------------------------------------------
def normalize_time_str(t_str):
    if not t_str:
        return '00:00:00'
    t_str = str(t_str).strip()
    parts = t_str.split(':')
    try:
        if len(parts) == 2:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"
        elif len(parts) >= 3:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
    except (ValueError, TypeError):
        pass
    return t_str

@app.route('/bookings')
@login_required
def bookings_list():
    status_filter = request.args.get('status', '')
    user = get_current_user()
    
    sql = """
        SELECT b.*, e.equipment_name, e.location, u.full_name AS student_name, u.roll_number,
               r.role_name AS user_role,
               p.project_name, approver.full_name AS approver_name
        FROM BOOKINGS b
        JOIN EQUIPMENT e ON b.equipment_id = e.equipment_id
        JOIN USERS u ON b.user_id = u.user_id
        JOIN ROLES r ON u.role_id = r.role_id
        LEFT JOIN PROJECTS p ON b.project_id = p.project_id
        LEFT JOIN USERS approver ON b.approved_by = approver.user_id
        WHERE 1=1
    """
    params = []
    
    # If logged in as Student, only show their bookings
    if user and user['role_name'] == 'Student':
        sql += " AND b.user_id = %s"
        params.append(user['user_id'])
        
    if status_filter:
        sql += " AND b.status = %s"
        params.append(status_filter)
        
    # Faculty requests are prioritized over Student requests, with Pending items at top
    sql += """ ORDER BY 
        CASE WHEN b.status = 'PENDING' THEN 1 ELSE 2 END ASC,
        CASE WHEN r.role_name = 'Faculty' THEN 1 WHEN r.role_name = 'Student' THEN 2 ELSE 3 END ASC,
        b.booking_date DESC, b.start_time DESC, b.booking_id DESC"""
    
    bookings = query_db(sql, params)
    
    # Analyze slot conflicts across bookings to display competition and exclusivity in UI
    all_active_bookings = query_db("""
        SELECT b.booking_id, b.equipment_id, b.booking_date, b.start_time, b.end_time, b.status, u.full_name AS student_name
        FROM BOOKINGS b
        JOIN USERS u ON b.user_id = u.user_id
        WHERE b.status IN ('PENDING', 'APPROVED', 'IN_USE')
    """)
    for b in bookings:
        competing = []
        approved_conflict = None
        b_start = normalize_time_str(b['start_time'])
        b_end = normalize_time_str(b['end_time'])
        for other in all_active_bookings:
            if other['booking_id'] != b['booking_id'] and other['equipment_id'] == b['equipment_id'] and str(other['booking_date']) == str(b['booking_date']):
                o_start = normalize_time_str(other['start_time'])
                o_end = normalize_time_str(other['end_time'])
                # Overlap condition: other.start < b.end and other.end > b.start
                if o_start < b_end and o_end > b_start:
                    if other['status'] in ('APPROVED', 'IN_USE'):
                        approved_conflict = other
                    elif other['status'] == 'PENDING':
                        competing.append(other)
        b['competing_requests'] = competing
        b['approved_conflict'] = approved_conflict

    equipment = query_db("SELECT equipment_id, equipment_name, status FROM EQUIPMENT ORDER BY equipment_name ASC")
    bookable_users = query_db("""
        SELECT u.user_id, u.full_name, u.roll_number, r.role_name
        FROM USERS u
        JOIN ROLES r ON u.role_id = r.role_id
        WHERE r.role_name IN ('Faculty', 'Student')
        ORDER BY CASE r.role_name WHEN 'Faculty' THEN 1 ELSE 2 END, u.full_name ASC
    """)
    projects = query_db("SELECT project_id, project_name FROM PROJECTS WHERE status = 'Active' ORDER BY project_name ASC")
    
    return render_template('bookings.html', bookings=bookings, equipment=equipment,
                           bookable_users=bookable_users, projects=projects, selected_status=status_filter)

@app.route('/bookings/create', methods=['POST'])
@login_required
def booking_create():
    user = get_current_user()
    eq_id = request.form.get('equipment_id')
    if user and user['role_name'] in ['Student', 'Faculty']:
        user_id = user['user_id']
    else:
        user_id = request.form.get('user_id') or (user['user_id'] if user else 1)
    proj_id = request.form.get('project_id') or None
    b_date = request.form.get('booking_date')
    start_t = normalize_time_str(request.form.get('start_time'))
    end_t = normalize_time_str(request.form.get('end_time'))
    purpose = request.form.get('purpose', '').strip()
    
    if end_t <= start_t:
        flash("Invalid time slot: Slot end time must be after start time.", "danger")
        return redirect(url_for('bookings_list'))
        
    eq = query_db("SELECT equipment_name FROM EQUIPMENT WHERE equipment_id = %s", [eq_id], one=True)
    eq_name = eq['equipment_name'] if eq else eq_id

    # Check if this slot is already APPROVED or currently IN_USE by another user
    conflict_approved = query_db("""
        SELECT b.*, u.full_name
        FROM BOOKINGS b
        JOIN USERS u ON b.user_id = u.user_id
        WHERE b.equipment_id = %s
          AND b.booking_date = %s
          AND b.status IN ('APPROVED', 'IN_USE')
          AND (b.start_time < %s AND b.end_time > %s)
    """, [eq_id, b_date, end_t, start_t], one=True)
    
    if conflict_approved:
        flash(f"Slot conflict: {eq_name} is already approved and reserved for {conflict_approved['full_name']} on {b_date} ({conflict_approved['start_time']} - {conflict_approved['end_time']}). Only one user can use equipment at a time. Please pick another slot.", 'danger')
        return redirect(url_for('bookings_list'))
        
    # Check if there are other pending requests for this slot
    pending_conflicts = query_db("""
        SELECT COUNT(*) AS cnt
        FROM BOOKINGS
        WHERE equipment_id = %s
          AND booking_date = %s
          AND status = 'PENDING'
          AND (start_time < %s AND end_time > %s)
    """, [eq_id, b_date, end_t, start_t], one=True)
    competing_cnt = pending_conflicts['cnt'] if pending_conflicts else 0

    try:
        execute_db("""
            INSERT INTO BOOKINGS (equipment_id, user_id, project_id, booking_date, start_time, end_time, purpose, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING')
        """, [eq_id, user_id, proj_id, b_date, start_t, end_t, purpose])
        
        if competing_cnt > 0:
            flash(f"Booking requested for {eq_name}! Notice: {competing_cnt} other user(s) have also requested an overlapping slot. Admin or Lab Technician will review and approve only one requester.", 'warning')
        else:
            flash(f"Equipment booking requested successfully for {eq_name}! Awaiting Admin / Technician approval.", 'success')
    except Exception as e:
        flash(f"Error creating booking: {str(e)}", 'danger')
        
    return redirect(url_for('bookings_list'))

@app.route('/bookings/<int:booking_id>/status', methods=['POST'])
@login_required
def booking_update_status(booking_id):
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized. Only Admin and Lab Technicians have authority to approve or manage booking requests.", 'danger')
        return redirect(url_for('bookings_list'))

    action = request.form.get('action') # APPROVE, REJECT, START_USE, COMPLETE
    approver_id = user['user_id'] if user else 1
    
    b = query_db("SELECT * FROM BOOKINGS WHERE booking_id = %s", [booking_id], one=True)
    if not b:
        flash("Booking not found.", 'danger')
        return redirect(url_for('bookings_list'))
        
    b_start = normalize_time_str(b['start_time'])
    b_end = normalize_time_str(b['end_time'])

    try:
        if action == 'APPROVE':
            # Mutual Exclusion Check 1: Ensure no overlapping booking is ALREADY approved or in use
            conflicting_approved = query_db("""
                SELECT b.*, u.full_name, e.equipment_name
                FROM BOOKINGS b
                JOIN USERS u ON b.user_id = u.user_id
                JOIN EQUIPMENT e ON b.equipment_id = e.equipment_id
                WHERE b.equipment_id = %s
                  AND b.booking_date = %s
                  AND b.booking_id != %s
                  AND b.status IN ('APPROVED', 'IN_USE')
                  AND (b.start_time < %s AND b.end_time > %s)
            """, [b['equipment_id'], b['booking_date'], booking_id, b_end, b_start], one=True)
            
            if conflicting_approved:
                flash(f"Cannot approve Booking #{booking_id}: Equipment '{conflicting_approved['equipment_name']}' is ALREADY approved for {conflicting_approved['full_name']} ({conflicting_approved['start_time']} - {conflicting_approved['end_time']}) under Booking #{conflicting_approved['booking_id']}. Only one user can use this machine at a time.", 'danger')
                return redirect(url_for('bookings_list'))
                
            # Mutual Exclusion Check 2: Find all competing PENDING requests for this slot
            conflicting_pending = query_db("""
                SELECT b.booking_id, u.full_name
                FROM BOOKINGS b
                JOIN USERS u ON b.user_id = u.user_id
                WHERE b.equipment_id = %s
                  AND b.booking_date = %s
                  AND b.booking_id != %s
                  AND b.status = 'PENDING'
                  AND (b.start_time < %s AND b.end_time > %s)
            """, [b['equipment_id'], b['booking_date'], booking_id, b_end, b_start])

            # Approve this booking
            execute_db("UPDATE BOOKINGS SET status = 'APPROVED', approved_by = %s WHERE booking_id = %s", [approver_id, booking_id])
            
            # Automatically decline competing pending requests for this slot
            if conflicting_pending:
                for cp in conflicting_pending:
                    execute_db("""
                        UPDATE BOOKINGS 
                        SET status = 'REJECTED', 
                            approved_by = %s,
                            purpose = purpose || %s
                        WHERE booking_id = %s
                    """, [approver_id, f" [Auto-declined: Slot allocated to Booking #{booking_id}]", cp['booking_id']])
                
                competing_names = ', '.join([f"#{cp['booking_id']} ({cp['full_name']})" for cp in conflicting_pending])
                flash(f"Booking #{booking_id} APPROVED! Notice: Competing overlapping request(s) [{competing_names}] were automatically declined so only one user can access the equipment.", 'success')
            else:
                flash(f"Booking #{booking_id} has been APPROVED.", 'success')
        elif action == 'REJECT':
            execute_db("UPDATE BOOKINGS SET status = 'REJECTED', approved_by = %s WHERE booking_id = %s", [approver_id, booking_id])
            flash(f"Booking #{booking_id} REJECTED.", 'info')
        elif action == 'START_USE':
            execute_db("UPDATE BOOKINGS SET status = 'IN_USE' WHERE booking_id = %s", [booking_id])
            execute_db("UPDATE EQUIPMENT SET status = 'In Use' WHERE equipment_id = %s", [b['equipment_id']])
            execute_db("""
                INSERT INTO USAGE_LOGS (equipment_id, user_id, project_id, start_timestamp, log_notes)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s)
            """, [b['equipment_id'], b['user_id'], b['project_id'], f"Usage session started for booking #{booking_id}"])
            flash(f"Session started for {b['equipment_id']}. Equipment marked In Use.", 'success')
        elif action == 'COMPLETE':
            execute_db("UPDATE BOOKINGS SET status = 'RETURNED' WHERE booking_id = %s", [booking_id])
            execute_db("UPDATE EQUIPMENT SET status = 'Available' WHERE equipment_id = %s", [b['equipment_id']])
            flash(f"Booking #{booking_id} completed. Equipment marked Available.", 'success')
    except Exception as e:
        flash(f"Status update error: {str(e)}", 'danger')
        
    return redirect(url_for('bookings_list'))

# ------------------------------------------------------------------------------
# 5. ALLOCATIONS (Student -> Project -> Component Tracking)
# ------------------------------------------------------------------------------
@app.route('/allocations')
@login_required
def allocations_list():
    status_filter = request.args.get('status', '')
    user = get_current_user()
    
    sql = """
        SELECT ea.*, c.component_name, c.storage_bin, u.full_name AS student_name, u.roll_number,
               COALESCE(p.project_name, 'Independent Lab Activity') AS project_name,
               r.role_name AS user_role
        FROM EQUIPMENT_ALLOCATION ea
        JOIN COMPONENTS c ON ea.component_id = c.component_id
        JOIN USERS u ON ea.user_id = u.user_id
        JOIN ROLES r ON u.role_id = r.role_id
        LEFT JOIN PROJECTS p ON ea.project_id = p.project_id
        WHERE 1=1
    """
    params = []
    if user and user['role_name'] == 'Student':
        sql += " AND ea.user_id = %s"
        params.append(user['user_id'])
    elif user and user['role_name'] == 'Faculty':
        sql += " AND (ea.user_id = %s OR p.guide_faculty_id = %s)"
        params.append(user['user_id'])
        params.append(user['user_id'])

    if status_filter:
        sql += " AND ea.status = %s"
        params.append(status_filter)
        
    sql += """ ORDER BY 
        CASE WHEN ea.status = 'Requested' THEN 1 WHEN ea.status = 'Issued' THEN 2 ELSE 3 END ASC,
        CASE WHEN r.role_name = 'Faculty' THEN 1 WHEN r.role_name = 'Student' THEN 2 ELSE 3 END ASC,
        ea.allocation_id DESC"""
    
    allocations = query_db(sql, params)
    components = query_db("SELECT component_id, component_name, available_quantity FROM COMPONENTS WHERE available_quantity > 0 ORDER BY component_name ASC")
    recipients = query_db("""
        SELECT u.user_id, u.full_name, u.roll_number, r.role_name
        FROM USERS u
        JOIN ROLES r ON u.role_id = r.role_id
        WHERE r.role_name IN ('Faculty', 'Student')
        ORDER BY CASE r.role_name WHEN 'Faculty' THEN 1 ELSE 2 END, u.full_name ASC
    """)
    projects = query_db("SELECT project_id, project_name FROM PROJECTS WHERE status = 'Active' ORDER BY project_name ASC")
    
    return render_template('allocations.html', allocations=allocations, components=components,
                           students=recipients, recipients=recipients, projects=projects, selected_status=status_filter)

@app.route('/allocations/issue', methods=['POST'])
@login_required
def allocation_issue():
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized. Only Admin and Lab Technicians have authority to issue components.", 'danger')
        return redirect(url_for('allocations_list'))

    c_id = request.form.get('component_id')
    user_id = request.form.get('user_id')
    proj_id = request.form.get('project_id') or None
    qty = int(request.form.get('quantity', 1))
    issue_date = request.form.get('issue_date')
    exp_return = request.form.get('expected_return_date')
    remarks = request.form.get('remarks', '').strip()
    
    comp = query_db("SELECT available_quantity, component_name FROM COMPONENTS WHERE component_id = %s", [c_id], one=True)
    if not comp or comp['available_quantity'] < qty:
        flash(f"Insufficient stock! Requested: {qty}, Available: {comp['available_quantity'] if comp else 0}", 'danger')
        return redirect(url_for('allocations_list'))
        
    try:
        execute_db("""
            INSERT INTO EQUIPMENT_ALLOCATION (component_id, user_id, project_id, quantity, issue_date, expected_return_date, status, remarks)
            VALUES (%s, %s, %s, %s, %s, %s, 'Issued', %s)
        """, [c_id, user_id, proj_id, qty, issue_date, exp_return, remarks])
        
        execute_db("UPDATE COMPONENTS SET available_quantity = available_quantity - %s WHERE component_id = %s", [qty, c_id])
        flash(f"Allocated {qty}x {comp['component_name']} successfully!", 'success')
    except Exception as e:
        flash(f"Allocation error: {str(e)}", 'danger')
        
    return redirect(url_for('allocations_list'))

@app.route('/allocations/<int:allocation_id>/approve', methods=['POST'])
@login_required
def allocation_approve(allocation_id):
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized. Only Admin and Lab Technicians can approve component requests.", 'danger')
        return redirect(url_for('allocations_list'))
        
    alloc = query_db("SELECT * FROM EQUIPMENT_ALLOCATION WHERE allocation_id = %s", [allocation_id], one=True)
    if not alloc:
        flash("Allocation record not found.", 'danger')
        return redirect(url_for('allocations_list'))
        
    comp = query_db("SELECT available_quantity, component_name FROM COMPONENTS WHERE component_id = %s", [alloc['component_id']], one=True)
    if not comp or comp['available_quantity'] < alloc['quantity']:
        flash(f"Cannot approve: Insufficient stock for {comp['component_name'] if comp else 'component'}! Available: {comp['available_quantity'] if comp else 0}, Requested: {alloc['quantity']}", 'danger')
        return redirect(url_for('allocations_list'))
        
    import datetime
    today_str = datetime.date.today().isoformat()
    try:
        execute_db("""
            UPDATE EQUIPMENT_ALLOCATION
            SET status = 'Issued', issue_date = %s
            WHERE allocation_id = %s
        """, [today_str, allocation_id])
        execute_db("UPDATE COMPONENTS SET available_quantity = available_quantity - %s WHERE component_id = %s", [alloc['quantity'], alloc['component_id']])
        flash(f"Request #{allocation_id} APPROVED and {alloc['quantity']}x {comp['component_name']} issued successfully!", 'success')
    except Exception as e:
        flash(f"Error approving request: {str(e)}", 'danger')
        
    return redirect(url_for('allocations_list'))

@app.route('/allocations/<int:allocation_id>/reject', methods=['POST'])
@login_required
def allocation_reject(allocation_id):
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized. Only Admin and Lab Technicians can reject component requests.", 'danger')
        return redirect(url_for('allocations_list'))
        
    reason = request.form.get('reason', 'Request declined by lab staff.').strip()
    try:
        execute_db("""
            UPDATE EQUIPMENT_ALLOCATION
            SET status = 'Rejected', remarks = remarks || %s
            WHERE allocation_id = %s
        """, [f" [Rejected: {reason}]", allocation_id])
        flash(f"Request #{allocation_id} REJECTED.", 'info')
    except Exception as e:
        flash(f"Error rejecting request: {str(e)}", 'danger')
        
    return redirect(url_for('allocations_list'))

@app.route('/allocations/<int:allocation_id>/return', methods=['POST'])
@login_required
def allocation_return(allocation_id):
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized. Only Admin and Lab Technicians can process returns.", 'danger')
        return redirect(url_for('allocations_list'))

    ret_date = request.form.get('return_date')
    ret_qty = int(request.form.get('returned_quantity', 1))
    condition = request.form.get('condition_status', 'Good')
    verifier_id = user['user_id'] if user else 2
    notes = request.form.get('penalty_or_notes', '').strip()
    
    alloc = query_db("SELECT * FROM EQUIPMENT_ALLOCATION WHERE allocation_id = %s", [allocation_id], one=True)
    if not alloc:
        flash("Allocation record not found.", 'danger')
        return redirect(url_for('allocations_list'))
        
    try:
        execute_db("""
            INSERT INTO RETURNS (allocation_id, return_date, returned_quantity, condition_status, verified_by, penalty_or_notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, [allocation_id, ret_date, ret_qty, condition, verifier_id, notes])
        
        execute_db("""
            UPDATE EQUIPMENT_ALLOCATION
            SET status = 'Returned', actual_return_date = %s
            WHERE allocation_id = %s
        """, [ret_date, allocation_id])
        
        if condition in ['Good', 'Damaged']:
            execute_db("UPDATE COMPONENTS SET available_quantity = available_quantity + %s WHERE component_id = %s", [ret_qty, alloc['component_id']])
            
        flash(f"Return verified and logged. Component stock updated.", 'success')
    except Exception as e:
        flash(f"Return error: {str(e)}", 'danger')
        
    return redirect(url_for('allocations_list'))

# ------------------------------------------------------------------------------
# 6. PROJECTS & STUDENT TEAMS
# ------------------------------------------------------------------------------
@app.route('/projects')
@login_required
def projects_list():
    projects = query_db("""
        SELECT p.*, u.full_name AS guide_name,
               COUNT(DISTINCT pm.user_id) AS member_count,
               COUNT(DISTINCT ea.allocation_id) AS items_allocated
        FROM PROJECTS p
        LEFT JOIN USERS u ON p.guide_faculty_id = u.user_id
        LEFT JOIN PROJECT_MEMBERS pm ON p.project_id = pm.project_id
        LEFT JOIN EQUIPMENT_ALLOCATION ea ON p.project_id = ea.project_id AND ea.status = 'Issued'
        GROUP BY p.project_id
        ORDER BY p.project_id ASC
    """)
    
    members_map = {}
    for p in projects:
        members_map[p['project_id']] = query_db("""
            SELECT pm.role_in_project, u.full_name, u.roll_number, u.email
            FROM PROJECT_MEMBERS pm
            JOIN USERS u ON pm.user_id = u.user_id
            WHERE pm.project_id = %s
        """, [p['project_id']])
        
    faculty = query_db("SELECT user_id, full_name FROM USERS WHERE role_id IN (1, 3) ORDER BY full_name ASC")
    
    return render_template('projects.html', projects=projects, members_map=members_map, faculty=faculty)

@app.route('/projects/create', methods=['POST'])
@login_required
def project_create():
    name = request.form.get('project_name', '').strip()
    guide_id = request.form.get('guide_faculty_id')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date') or None
    desc = request.form.get('description', '').strip()
    
    try:
        execute_db("""
            INSERT INTO PROJECTS (project_name, guide_faculty_id, start_date, end_date, status, description)
            VALUES (%s, %s, %s, %s, 'Active', %s)
        """, [name, guide_id, start_date, end_date, desc])
        flash(f"Project '{name}' registered successfully!", 'success')
    except Exception as e:
        flash(f"Project registration error: {str(e)}", 'danger')
        
    return redirect(url_for('projects_list'))

# ------------------------------------------------------------------------------
# 7. MAINTENANCE, BREAKDOWNS & VENDORS
# ------------------------------------------------------------------------------
@app.route('/maintenance')
@login_required
def maintenance_list():
    jobs = query_db("""
        SELECT m.*, e.equipment_name, v.vendor_name, v.phone AS vendor_phone
        FROM MAINTENANCE_JOBS m
        JOIN EQUIPMENT e ON m.equipment_id = e.equipment_id
        LEFT JOIN VENDORS v ON m.vendor_id = v.vendor_id
        ORDER BY m.job_id DESC
    """)
    
    breakdowns = query_db("""
        SELECT b.*, e.equipment_name, u.full_name AS reporter_name
        FROM BREAKDOWNS b
        JOIN EQUIPMENT e ON b.equipment_id = e.equipment_id
        JOIN USERS u ON b.reported_by = u.user_id
        ORDER BY b.breakdown_id DESC
    """)
    
    equipment = query_db("SELECT equipment_id, equipment_name FROM EQUIPMENT ORDER BY equipment_name ASC")
    vendors = query_db("SELECT vendor_id, vendor_name, service_type FROM VENDORS ORDER BY vendor_name ASC")
    users = query_db("SELECT user_id, full_name FROM USERS ORDER BY full_name ASC")
    
    return render_template('maintenance.html', jobs=jobs, breakdowns=breakdowns,
                           equipment=equipment, vendors=vendors, users=users)

@app.route('/breakdowns/report', methods=['POST'])
@login_required
def breakdown_report():
    user = get_current_user()
    eq_id = request.form.get('equipment_id')
    rep_by = request.form.get('reported_by') or (user['user_id'] if user else 5)
    rep_date = request.form.get('reported_date')
    problem = request.form.get('problem_description', '').strip()
    severity = request.form.get('severity', 'Medium')
    
    try:
        execute_db("""
            INSERT INTO BREAKDOWNS (equipment_id, reported_by, reported_date, problem_description, severity, status)
            VALUES (%s, %s, %s, %s, %s, 'Reported')
        """, [eq_id, rep_by, rep_date, problem, severity])
        
        if severity in ['High', 'Critical']:
            execute_db("UPDATE EQUIPMENT SET status = 'Maintenance' WHERE equipment_id = %s", [eq_id])
            
        flash(f"Breakdown reported for {eq_id}. Equipment status updated.", 'warning')
    except Exception as e:
        flash(f"Breakdown error: {str(e)}", 'danger')
        
    return redirect(url_for('maintenance_list'))

@app.route('/maintenance/create', methods=['POST'])
@login_required
def maintenance_create():
    eq_id = request.form.get('equipment_id')
    brk_id = request.form.get('breakdown_id') or None
    vendor_id = request.form.get('vendor_id') or None
    start_date = request.form.get('start_date')
    cost = float(request.form.get('cost', 0.0))
    problem = request.form.get('problem_description', '').strip()
    
    try:
        execute_db("""
            INSERT INTO MAINTENANCE_JOBS (equipment_id, breakdown_id, vendor_id, start_date, cost, problem_description, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'In Progress')
        """, [eq_id, brk_id, vendor_id, start_date, cost, problem])
        execute_db("UPDATE EQUIPMENT SET status = 'Maintenance' WHERE equipment_id = %s", [eq_id])
        if brk_id:
            execute_db("UPDATE BREAKDOWNS SET status = 'In Maintenance' WHERE breakdown_id = %s", [brk_id])
        flash("Maintenance job launched successfully.", 'success')
    except Exception as e:
        flash(f"Error starting maintenance: {str(e)}", 'danger')
        
    return redirect(url_for('maintenance_list'))

@app.route('/maintenance/<int:job_id>/complete', methods=['POST'])
@login_required
def maintenance_complete(job_id):
    comp_date = request.form.get('completion_date')
    action = request.form.get('action_taken', '').strip()
    cost = float(request.form.get('cost', 0.0))
    
    job = query_db("SELECT * FROM MAINTENANCE_JOBS WHERE job_id = %s", [job_id], one=True)
    if not job:
        flash("Maintenance job not found.", 'danger')
        return redirect(url_for('maintenance_list'))
        
    try:
        execute_db("""
            UPDATE MAINTENANCE_JOBS
            SET status = 'Completed', completion_date = %s, action_taken = %s, cost = %s
            WHERE job_id = %s
        """, [comp_date, action, cost, job_id])
        execute_db("UPDATE EQUIPMENT SET status = 'Available' WHERE equipment_id = %s", [job['equipment_id']])
        if job['breakdown_id']:
            execute_db("UPDATE BREAKDOWNS SET status = 'Resolved' WHERE breakdown_id = %s", [job['breakdown_id']])
        flash(f"Maintenance Job #{job_id} resolved! {job['equipment_id']} is now Available.", 'success')
    except Exception as e:
        flash(f"Error completing maintenance: {str(e)}", 'danger')
        
    return redirect(url_for('maintenance_list'))

# ------------------------------------------------------------------------------
# 8. CALIBRATIONS & VENDORS
# ------------------------------------------------------------------------------
@app.route('/calibrations')
@login_required
def calibrations_list():
    calibrations = query_db("""
        SELECT cal.*, e.equipment_name, e.location
        FROM CALIBRATIONS cal
        JOIN EQUIPMENT e ON cal.equipment_id = e.equipment_id
        ORDER BY cal.next_due_date ASC
    """)
    equipment = query_db("SELECT equipment_id, equipment_name FROM EQUIPMENT ORDER BY equipment_name ASC")
    return render_template('calibrations.html', calibrations=calibrations, equipment=equipment)

@app.route('/vendors')
@login_required
def vendors_list():
    vendors = query_db("""
        SELECT v.*, COUNT(m.job_id) AS service_jobs_count, COALESCE(SUM(m.cost), 0) AS total_billed
        FROM VENDORS v
        LEFT JOIN MAINTENANCE_JOBS m ON v.vendor_id = m.vendor_id
        GROUP BY v.vendor_id
        ORDER BY v.vendor_name ASC
    """)
    return render_template('vendors.html', vendors=vendors)

# ------------------------------------------------------------------------------
# 9. INTERACTIVE DBMS SQL REPORTS PLAYGROUND (Viva Ready)
# ------------------------------------------------------------------------------
REPORT_QUERIES = {
    'available_equipment': {
        'title': 'Equipment Availability Report',
        'desc': 'Lists all equipment currently available for booking in the laboratory.',
        'sql': """
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
"""
    },
    'active_allocations': {
        'title': 'Current Component Allocations to Students',
        'desc': 'Detailed 4-table join showing which student borrowed what component for which project.',
        'sql': """
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
"""
    },
    'low_stock': {
        'title': 'Low Stock & Inventory Shortage Report',
        'desc': 'Identifies components whose available quantity has fallen below the safety minimum stock threshold.',
        'sql': """
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
"""
    },
    'maintenance_history': {
        'title': 'Equipment Maintenance & Repair Logs',
        'desc': 'Comprehensive maintenance log with cost breakdowns and vendor linkages.',
        'sql': """
SELECT 
    e.equipment_id,
    e.equipment_name,
    m.problem_description,
    m.action_taken,
    m.start_date,
    m.completion_date,
    m.cost,
    m.status AS maintenance_status,
    COALESCE(v.vendor_name, 'In-House') AS service_vendor
FROM MAINTENANCE_JOBS m
JOIN EQUIPMENT e ON m.equipment_id = e.equipment_id
LEFT JOIN VENDORS v ON m.vendor_id = v.vendor_id
ORDER BY m.start_date DESC;
"""
    },
    'equipment_utilization': {
        'title': 'Equipment Booking Frequency & Utilization',
        'desc': 'Demonstrates GROUP BY, COUNT, and Conditional Aggregation to calculate total bookings per equipment.',
        'sql': """
SELECT 
    e.equipment_id,
    e.equipment_name,
    ec.category_name,
    COUNT(b.booking_id) AS total_times_booked,
    SUM(CASE WHEN b.status IN ('APPROVED', 'RETURNED', 'IN_USE') THEN 1 ELSE 0 END) AS successful_bookings
FROM EQUIPMENT e
JOIN EQUIPMENT_CATEGORIES ec ON e.category_id = ec.category_id
LEFT JOIN BOOKINGS b ON e.equipment_id = b.equipment_id
GROUP BY e.equipment_id, e.equipment_name, ec.category_name
ORDER BY total_times_booked DESC;
"""
    },
    'project_costs': {
        'title': 'Total Component Value Issued per Project',
        'desc': 'Uses GROUP BY and HAVING to calculate the total INR cost value of components issued to academic projects.',
        'sql': """
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
ORDER BY total_allocated_value_inr DESC;
"""
    },
    'breakdown_frequency': {
        'title': 'Frequent Equipment Breakdowns by Severity',
        'desc': 'Shows aggregate breakdown counts and highest severity incidents per equipment.',
        'sql': """
SELECT 
    e.equipment_id,
    e.equipment_name,
    COUNT(brk.breakdown_id) AS total_breakdowns,
    MAX(brk.reported_date) AS last_breakdown_date
FROM EQUIPMENT e
JOIN BREAKDOWNS brk ON e.equipment_id = brk.equipment_id
GROUP BY e.equipment_id, e.equipment_name
ORDER BY total_breakdowns DESC;
"""
    },
    'calibration_due': {
        'title': 'Calibration Schedules & Due Date Audit',
        'desc': 'Audit of metrology calibrations for test and measurement lab equipment.',
        'sql': """
SELECT 
    cal.calibration_id,
    e.equipment_id,
    e.equipment_name,
    cal.last_calibration_date,
    cal.next_due_date,
    cal.certified_by,
    cal.status
FROM CALIBRATIONS cal
JOIN EQUIPMENT e ON cal.equipment_id = e.equipment_id
ORDER BY cal.next_due_date ASC;
"""
    }
}

@app.route('/reports')
@login_required
def reports_view():
    selected_key = request.args.get('report', 'available_equipment')
    if selected_key not in REPORT_QUERIES:
        selected_key = 'available_equipment'
        
    report_info = REPORT_QUERIES[selected_key]
    results = query_db(report_info['sql'])
    columns = list(results[0].keys()) if results else []
    
    return render_template('reports.html',
                           reports_catalog=REPORT_QUERIES,
                           selected_key=selected_key,
                           report_info=report_info,
                           columns=columns,
                           results=results)

# ------------------------------------------------------------------------------
# 11. REQUISITIONS & MODULE PROCUREMENT (Things to Order & Buy Links)
# ------------------------------------------------------------------------------
@app.route('/procurement')
@login_required
def procurement_list():
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Access restricted. Procurement & Orders is only available to Admin and Lab Technicians.", 'danger')
        return redirect(url_for('dashboard'))

    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    search = request.args.get('q', '').strip()

    sql = """
        SELECT r.*, u.full_name AS requester_name, c.available_quantity, c.minimum_stock, c.storage_bin
        FROM REQUISITIONS r
        LEFT JOIN USERS u ON r.requested_by = u.user_id
        LEFT JOIN COMPONENTS c ON r.component_id = c.component_id
        WHERE 1=1
    """
    params = []
    if status_filter:
        sql += " AND r.status = %s"
        params.append(status_filter)
    if priority_filter:
        sql += " AND r.priority = %s"
        params.append(priority_filter)
    if search:
        sql += " AND (r.item_name LIKE %s OR r.category_name LIKE %s OR r.vendor_name_1 LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term])

    sql += " ORDER BY CASE r.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, r.requisition_id DESC"

    requisitions = query_db(sql, params)

    all_components = query_db("SELECT component_id, component_name, available_quantity, minimum_stock, unit_cost FROM COMPONENTS ORDER BY component_name ASC")
    low_stock_items = query_db("SELECT * FROM COMPONENTS WHERE available_quantity <= minimum_stock ORDER BY available_quantity ASC")

    total_orders = len(requisitions)
    pending_count = sum(1 for r in requisitions if r['status'] == 'Pending Order')
    in_transit_count = sum(1 for r in requisitions if r['status'] in ['Ordered', 'In Transit'])
    total_est_cost = sum((r['required_quantity'] or 0) * float(r['estimated_unit_cost'] or 0) for r in requisitions if r['status'] != 'Cancelled')

    return render_template('procurement.html',
                           requisitions=requisitions,
                           all_components=all_components,
                           low_stock_items=low_stock_items,
                           selected_status=status_filter,
                           selected_priority=priority_filter,
                           search=search,
                           total_orders=total_orders,
                           pending_count=pending_count,
                           in_transit_count=in_transit_count,
                           total_est_cost=total_est_cost)

@app.route('/procurement/add', methods=['POST'])
@login_required
def procurement_add():
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized. Only Admin and Lab Technicians can create procurement orders.", 'danger')
        return redirect(url_for('dashboard'))

    comp_id = request.form.get('component_id', '').strip() or None
    item_name = request.form.get('item_name', '').strip()
    category_name = request.form.get('category_name', 'Microcontrollers & Sensors').strip()
    required_qty = int(request.form.get('required_quantity', 1))
    est_cost = float(request.form.get('estimated_unit_cost', 0.0))
    priority = request.form.get('priority', 'Medium')
    
    vendor_1 = request.form.get('vendor_name_1', 'Robu.in').strip()
    link_1 = request.form.get('buy_link_1', '').strip()
    vendor_2 = request.form.get('vendor_name_2', 'ElectronicsComp').strip()
    link_2 = request.form.get('buy_link_2', '').strip()
    vendor_3 = request.form.get('vendor_name_3', 'Amazon India').strip()
    link_3 = request.form.get('buy_link_3', '').strip()
    notes = request.form.get('notes', '').strip()
    requester_id = user['user_id'] if user else 1

    if not item_name:
        flash("Item/Module name is required.", 'danger')
        return redirect(url_for('procurement_list'))

    try:
        execute_db("""
            INSERT INTO REQUISITIONS (component_id, item_name, category_name, required_quantity, estimated_unit_cost, priority, status, vendor_name_1, buy_link_1, vendor_name_2, buy_link_2, vendor_name_3, buy_link_3, notes, requested_by)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending Order', %s, %s, %s, %s, %s, %s, %s, %s)
        """, [comp_id, item_name, category_name, required_qty, est_cost, priority, vendor_1, link_1, vendor_2, link_2, vendor_3, link_3, notes, requester_id])
        flash(f"Order request for '{item_name}' (Qty: {required_qty}) submitted successfully!", 'success')
    except Exception as e:
        flash(f"Error creating order request: {str(e)}", 'danger')

    return redirect(url_for('procurement_list'))

@app.route('/procurement/quick-add/<component_id>', methods=['POST'])
@login_required
def procurement_quick_add(component_id):
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized. Only Admin and Lab Technicians can create reorder requests.", 'danger')
        return redirect(url_for('components_list'))

    comp = query_db("SELECT * FROM COMPONENTS WHERE component_id = %s", [component_id], one=True)
    if not comp:
        flash("Component not found.", 'danger')
        return redirect(url_for('procurement_list'))

    reorder_qty = max(comp['minimum_stock'] * 2 - comp['available_quantity'], 5)
    item_name = comp['component_name']
    
    import urllib.parse
    encoded_query = urllib.parse.quote_plus(item_name)
    link_robu = f"https://robu.in/?s={encoded_query}&post_type=product"
    link_ecomp = f"https://www.electronicscomp.com/index.php?route=product/search&search={encoded_query}"
    link_amazon = f"https://www.amazon.in/s?k={encoded_query}"

    try:
        execute_db("""
            INSERT INTO REQUISITIONS (component_id, item_name, category_name, required_quantity, estimated_unit_cost, priority, status, vendor_name_1, buy_link_1, vendor_name_2, buy_link_2, vendor_name_3, buy_link_3, notes, requested_by)
            VALUES (%s, %s, %s, %s, %s, 'High', 'Pending Order', 'Robu.in', %s, 'ElectronicsComp', %s, 'Amazon India', %s, %s, %s)
        """, [component_id, item_name, 'Electronics Restock', reorder_qty, comp['unit_cost'], link_robu, link_ecomp, link_amazon, f"Auto-generated restock requisition for low stock ({comp['available_quantity']} units remaining).", user['user_id'] if user else 1])
        flash(f"Quick re-order request generated for '{item_name}' with 3 buy links!", 'success')
    except Exception as e:
        flash(f"Error creating quick order: {str(e)}", 'danger')

    return redirect(url_for('procurement_list'))

@app.route('/procurement/status/<int:requisition_id>', methods=['POST'])
@login_required
def procurement_update_status(requisition_id):
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized.", 'danger')
        return redirect(url_for('dashboard'))

    new_status = request.form.get('status')
    r = query_db("SELECT * FROM REQUISITIONS WHERE requisition_id = %s", [requisition_id], one=True)
    if not r:
        flash("Requisition item not found.", 'danger')
        return redirect(url_for('procurement_list'))

    try:
        execute_db("UPDATE REQUISITIONS SET status = %s WHERE requisition_id = %s", [new_status, requisition_id])
        
        if new_status == 'Received' and r['component_id']:
            execute_db("""
                UPDATE COMPONENTS 
                SET total_quantity = total_quantity + %s,
                    available_quantity = available_quantity + %s
                WHERE component_id = %s
            """, [r['required_quantity'], r['required_quantity'], r['component_id']])
            flash(f"Order #{requisition_id} marked as Received! Added {r['required_quantity']} units to component stock ({r['component_id']}).", 'success')
        else:
            flash(f"Requisition #{requisition_id} status updated to '{new_status}'.", 'success')
    except Exception as e:
        flash(f"Error updating status: {str(e)}", 'danger')

    return redirect(url_for('procurement_list'))

@app.route('/procurement/delete/<int:requisition_id>', methods=['POST'])
@login_required
def procurement_delete(requisition_id):
    user = get_current_user()
    if user and user['role_name'] not in ['Admin', 'Lab Technician']:
        flash("Unauthorized.", 'danger')
        return redirect(url_for('dashboard'))

    try:
        execute_db("DELETE FROM REQUISITIONS WHERE requisition_id = %s", [requisition_id])
        flash(f"Order item #{requisition_id} deleted.", 'info')
    except Exception as e:
        flash(f"Error deleting requisition: {str(e)}", 'danger')

    return redirect(url_for('procurement_list'))

if __name__ == '__main__':
    print("=" * 60)
    print("RoboLab: Robotics Lab Management System Started")
    print("Server running at: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, port=5000)
