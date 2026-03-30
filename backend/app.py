from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import secrets
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, extract
from models import SaleItem, Product
from config import config
from models import (db, User, Product, Supplier, Batch, ProductSupplierMapping, 
                    Sale, SaleItem, ActivityLog, Permission, Department, Employee, 
                    Attendance, LeaveRequest, LeaveBalance, PayrollRecord, JobPosting, 
                    JobApplication, Interview, BarcodeScan)
from auth import (login_required, admin_required, inventory_required, sales_required, 
                  hr_required, log_activity, generate_csrf_token)
from analytics import calculate_metrics, run_all_analytics

# =====================================================
# Initialize Flask app
# =====================================================
app = Flask(__name__, 
            static_folder='../frontend',
            static_url_path='',
            template_folder='../frontend')

env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[env])

CORS(app, supports_credentials=True)
db.init_app(app)

# =====================================================
# Create tables and default data (MERGED)
# =====================================================
with app.app_context():
    db.create_all()
    
    # Create default permissions (MERGED from both versions)
    if Permission.query.count() == 0:
        permissions = [
            # Admin permissions
            ('admin', 'dashboard', True, True, True, True),
            ('admin', 'products', True, True, True, True),
            ('admin', 'suppliers', True, True, True, True),
            ('admin', 'batches', True, True, True, True),
            ('admin', 'sales', True, True, True, True),
            ('admin', 'analytics', True, True, True, True),
            ('admin', 'hr', True, True, True, True),
            
            # Inventory Manager permissions
            ('inventory_manager', 'dashboard', True, False, False, False),
            ('inventory_manager', 'products', True, True, True, True),
            ('inventory_manager', 'suppliers', True, True, True, True),
            ('inventory_manager', 'batches', True, True, True, False),
            
            # Sales Staff permissions
            ('sales_staff', 'dashboard', True, False, False, False),
            ('sales_staff', 'sales', True, True, False, False),
            
            # HR Manager permissions
            ('hr_manager', 'dashboard', True, False, False, False),
            ('hr_manager', 'hr', True, True, True, True),
            ('hr_manager', 'employees', True, True, True, True),
            ('hr_manager', 'attendance', True, True, True, True),
            ('hr_manager', 'leaves', True, True, True, True),
        ]
        
        for role, module, view, create, edit, delete in permissions:
            perm = Permission(
                role=role,
                module=module,
                can_view=view,
                can_create=create,
                can_edit=edit,
                can_delete=delete
            )
            db.session.add(perm)
    
    # Create default users (MERGED from both versions)
    if User.query.count() == 0:
        # Admin
        admin = User(
            username='admin',
            email='admin@erp.com',
            full_name='System Admin',
            role='admin',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        
        # Inventory Manager
        inventory = User(
            username='inventory',
            email='inventory@erp.com',
            full_name='Inventory Manager',
            role='inventory_manager',
            is_active=True
        )
        inventory.set_password('admin123')
        db.session.add(inventory)
        
        # Sales Staff
        sales = User(
            username='sales',
            email='sales@erp.com',
            full_name='Sales Staff',
            role='sales_staff',
            is_active=True
        )
        sales.set_password('admin123')
        db.session.add(sales)
        
        # HR Manager
        hr = User(
            username='hr',
            email='hr@erp.com',
            full_name='HR Manager',
            role='hr_manager',
            is_active=True
        )
        hr.set_password('admin123')
        db.session.add(hr)
        
        db.session.commit()

# =====================================================
# AUTHENTICATION ROUTES
# =====================================================

@app.route('/login')
def login_page():
    """Serve login page"""
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return redirect(user.get_dashboard_url())
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """Handle login request"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        remember = data.get('remember', False)
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 403
        
        session.permanent = remember
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session['full_name'] = user.full_name
        session['csrf_token'] = secrets.token_hex(32)
        
        user.last_login = datetime.utcnow()
        user.last_ip = request.remote_addr
        db.session.commit()
        
        log_activity(user.id, 'login', 'auth', {'ip': request.remote_addr})
        
        return jsonify({
            'success': True,
            'user': user.to_dict(),
            'csrf_token': session['csrf_token'],
            'redirect': user.get_dashboard_url()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/finance/dashboard')
@login_required
def finance_dashboard():
    from sqlalchemy import func

    revenue = db.session.query(
        func.sum(SaleItem.quantity * SaleItem.unit_price)
    ).scalar() or 0

    expense = db.session.query(
        func.sum(SaleItem.quantity * SaleItem.cost_price)
    ).scalar() or 0
    revenue = float(revenue)
    expense = float(expense)
    profit = revenue - expense

    top_products = db.session.query(
        Product.product_name,
        func.count(SaleItem.sale_id).label('total')
    ).join(SaleItem, Product.id == SaleItem.product_id) \
     .group_by(Product.id) \
     .order_by(func.count(SaleItem.sale_id).desc()) \
     .limit(5).all()

    return render_template(
        'finance/dashboard.html',
        revenue=round(revenue, 2),
        expense=round(expense, 2),
        profit=round(profit, 2),
        top_products=top_products
    )

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Handle logout with role-based redirect"""
    try:
        user_role = session.get('role')
        user_id = session.get('user_id')
        
        if user_id:
            log_activity(user_id, 'logout', 'auth')
        
        session.clear()
        
        redirect_url = '/login'
        if user_role == 'admin':
            redirect_url = '/admin/dashboard'
        elif user_role == 'hr_manager':
            redirect_url = '/hr/dashboard'
        elif user_role == 'inventory_manager':
            redirect_url = '/inventory/dashboard'
        elif user_role == 'sales_staff':
            redirect_url = '/sales/dashboard'
        elif user_role == 'employee':
            redirect_url = '/employee/profile'
        
        return jsonify({
            'success': True,
            'redirect_url': redirect_url
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# =====================================================
# ROLE-BASED DASHBOARD ROUTES
# =====================================================

@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return redirect(user.get_dashboard_url())

    return redirect('/login')   # 🔥 FIX
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    return render_template('admin/dashboard.html')

@app.route('/admin/users')
@admin_required
def admin_users():
    """User management page"""
    return render_template('admin/users.html')

@app.route('/inventory/dashboard')
@inventory_required
def inventory_dashboard():
    """Inventory manager dashboard"""
    return render_template('inventory/dashboard.html')

@app.route('/inventory/products')
@inventory_required
def inventory_products():
    """Products management page"""
    return render_template('inventory/products.html')

@app.route('/inventory/suppliers')
@inventory_required
def inventory_suppliers():
    """Suppliers management page"""
    return render_template('inventory/suppliers.html')

@app.route('/sales/dashboard')
@sales_required
def sales_dashboard():
    """Sales dashboard"""
    return render_template('sales/dashboard.html')

@app.route('/sales/pos')
@sales_required
def sales_pos():
    """Point of Sale page"""
    return render_template('sales/pos.html')

# =====================================================
# HR MODULE ROUTES
# =====================================================

@app.route('/hr/dashboard')
@login_required
def hr_dashboard():
    """HR Dashboard"""
    return render_template('hr/dashboard.html')

@app.route('/hr/employees')
@login_required
def hr_employees():
    """Employee Management"""
    return render_template('hr/employees.html')

@app.route('/hr/attendance')
@login_required
def hr_attendance():
    """Attendance Management"""
    return render_template('hr/attendance.html')

@app.route('/hr/leaves')
@login_required
def hr_leaves():
    """Leave Management"""
    return render_template('hr/leaves.html')

@app.route('/hr/payroll')
@login_required
def hr_payroll():
    """Payroll Management"""
    return render_template('hr/payroll.html')

# =====================================================
# EMPLOYEE SELF-SERVICE ROUTES
# =====================================================

@app.route('/employee/profile')
@login_required
def employee_profile():
    """Employee Profile Page"""
    user = User.query.get(session['user_id'])
    if user.role != 'employee':
        return redirect(user.get_dashboard_url())
    return render_template('employee/profile.html')

@app.route('/employee/attendance')
@login_required
def employee_attendance():
    """Employee Attendance Page"""
    user = User.query.get(session['user_id'])
    if user.role != 'employee':
        return redirect(user.get_dashboard_url())
    return render_template('employee/attendance.html')

@app.route('/employee/leaves')
@login_required
def employee_leaves():
    """Employee Leaves Page"""
    user = User.query.get(session['user_id'])
    if user.role != 'employee':
        return redirect(user.get_dashboard_url())
    return render_template('employee/leaves.html')

# =====================================================
# DASHBOARD STATS API
# =====================================================

@app.route('/api/dashboard/stats')
@login_required
def dashboard_stats():
    """Get dashboard statistics based on user role"""
    try:
        role = session['role']
        
        if role == 'admin':
            total_products = Product.query.filter_by(is_active=True).count()
            total_suppliers = Supplier.query.filter_by(is_active=True).count()
            total_users = User.query.filter_by(is_active=True).count()
            total_employees = Employee.query.filter_by(employment_status='active').count()
            
            today_sales = Sale.query.filter(
                func.date(Sale.created_at) == datetime.now().date()
            ).all()
            today_revenue = sum(float(s.grand_total) for s in today_sales)
            
            low_stock = 0
            products = Product.query.filter_by(is_active=True).all()
            for product in products:
                total_stock = sum(b.remaining_quantity for b in product.batches if b.is_active)
                min_level = product.min_stock_level or 0
                if total_stock <= min_level:
                    low_stock += 1
            
            expiring_soon = Batch.query.filter(
                Batch.expiry_date <= datetime.now().date() + timedelta(days=7),
                Batch.expiry_date > datetime.now().date(),
                Batch.remaining_quantity > 0,
                Batch.is_active == True
            ).count()
            
            recent_activities = ActivityLog.query.order_by(
                ActivityLog.created_at.desc()
            ).limit(10).all()
            
            activities = []
            for act in recent_activities:
                user = User.query.get(act.user_id)
                activities.append({
                    'id': act.id,
                    'user': user.full_name if user else 'System',
                    'action': act.action,
                    'module': act.module,
                    'time': act.created_at.isoformat()
                })
            
            return jsonify({
                'total_products': total_products,
                'total_suppliers': total_suppliers,
                'total_users': total_users,
                'total_employees': total_employees,
                'today_revenue': float(today_revenue),
                'today_sales_count': len(today_sales),
                'low_stock_items': low_stock,
                'expiring_soon': expiring_soon,
                'recent_activities': activities
            })
            
        elif role == 'inventory_manager':
            total_products = Product.query.filter_by(is_active=True).count()
            total_suppliers = Supplier.query.filter_by(is_active=True).count()
            
            low_stock = 0
            products = Product.query.filter_by(is_active=True).all()
            for product in products:
                total_stock = sum(b.remaining_quantity for b in product.batches if b.is_active)
                min_level = product.min_stock_level or 0
                if total_stock <= min_level:
                    low_stock += 1
            
            expiring_soon = Batch.query.filter(
                Batch.expiry_date <= datetime.now().date() + timedelta(days=7),
                Batch.expiry_date > datetime.now().date(),
                Batch.remaining_quantity > 0,
                Batch.is_active == True
            ).count()
            
            recent_activities = ActivityLog.query.filter(
                ActivityLog.module.in_(['products', 'suppliers', 'batches'])
            ).order_by(ActivityLog.created_at.desc()).limit(10).all()
            
            activities = []
            for act in recent_activities:
                user = User.query.get(act.user_id)
                activities.append({
                    'id': act.id,
                    'user': user.full_name if user else 'System',
                    'action': act.action,
                    'module': act.module,
                    'time': act.created_at.isoformat()
                })
            
            return jsonify({
                'total_products': total_products,
                'total_suppliers': total_suppliers,
                'low_stock_items': low_stock,
                'expiring_soon': expiring_soon,
                'recent_activities': activities
            })
            
        elif role == 'sales_staff':
            today_sales = Sale.query.filter(
                func.date(Sale.created_at) == datetime.now().date()
            ).all()
            today_revenue = sum(float(s.grand_total) for s in today_sales)
            
            recent_sales = Sale.query.order_by(
                Sale.created_at.desc()
            ).limit(10).all()
            
            sales_data = []
            for sale in recent_sales:
                sales_data.append({
                    'id': sale.id,
                    'invoice': sale.invoice_number,
                    'customer': sale.customer_name or 'Walk-in',
                    'amount': float(sale.grand_total),
                    'time': sale.created_at.isoformat()
                })
            
            return jsonify({
                'today_revenue': float(today_revenue),
                'today_transactions': len(today_sales),
                'recent_sales': sales_data
            })
            
        else:
            return jsonify({'error': 'Invalid role'}), 403
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# ANALYTICS ROUTES
# =====================================================

@app.route('/api/analytics/refresh', methods=['POST'])
@admin_required
def refresh_analytics():
    """Refresh analytics metrics"""
    try:
        calculate_metrics()
        return jsonify({'success': True, 'message': 'Analytics refreshed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/run-all', methods=['POST'])
@admin_required
def run_all_analytics_endpoint():
    """Run all analytics (inventory + HR)"""
    try:
        result = run_all_analytics()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/metrics')
@login_required
def get_analytics_metrics():
    """Get analytics metrics"""
    try:
        from sqlalchemy import text
        
        result = db.session.execute(text("""
            SELECT * FROM recovery_metrics 
            ORDER BY risk_level DESC, days_to_expiry ASC
        """))
        metrics = [dict(row._mapping) for row in result]
        
        result2 = db.session.execute(text("""
            SELECT * FROM alerts 
            WHERE is_read = 0 
            ORDER BY created_at DESC
        """))
        alerts = [dict(row._mapping) for row in result2]
        
        return jsonify({'metrics': metrics, 'alerts': alerts})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# PRODUCT API ROUTES
# =====================================================

@app.route('/api/products', methods=['GET'])
@login_required
def get_products():
    """Get all products with filters and supplier info"""
    try:
        user = User.query.get(session['user_id'])
        if not user.has_permission('products', 'view'):
            return jsonify({'error': 'Permission denied'}), 403
        
        category = request.args.get('category')
        search = request.args.get('search', '')
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 25))
        
        query = Product.query
        
        if category and category != 'all':
            query = query.filter_by(category=category)
        
        if search:
            query = query.filter(
                db.or_(
                    Product.product_name.ilike(f'%{search}%'),
                    Product.barcode.ilike(f'%{search}%'),
                    Product.product_code.ilike(f'%{search}%')
                )
            )
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        paginated = query.order_by(Product.product_name).paginate(page=page, per_page=per_page)
        
        items = []
        for p in paginated.items:
            product_dict = p.to_dict()
            
            # ========== FIX: Get supplier info ==========
            mappings = ProductSupplierMapping.query.filter_by(product_id=p.id).all()
            supplier_names = []
            for mapping in mappings:
                if mapping.supplier:
                    supplier_names.append(mapping.supplier.supplier_name)
            product_dict['suppliers'] = supplier_names
            product_dict['supplier_names'] = ', '.join(supplier_names) if supplier_names else 'None'
            # ============================================
            
            # Get current stock
            total_stock = sum(b.remaining_quantity for b in p.batches if b.is_active)
            product_dict['current_stock'] = total_stock
            
            # Get expiry info
            active_batches = [b for b in p.batches if b.is_active and b.remaining_quantity > 0]
            if active_batches:
                valid_batches = [b for b in active_batches if b.expiry_date]
                if valid_batches:
                    earliest_expiry = min(b.expiry_date for b in valid_batches)
                    product_dict['earliest_expiry'] = earliest_expiry.isoformat() if earliest_expiry else None
                    days_left = (earliest_expiry - datetime.now().date()).days if earliest_expiry else None
                    product_dict['days_to_expiry'] = days_left
                else:
                    product_dict['earliest_expiry'] = None
                    product_dict['days_to_expiry'] = None
            else:
                product_dict['earliest_expiry'] = None
                product_dict['days_to_expiry'] = None
            
            items.append(product_dict)
        
        return jsonify({
            'items': items,
            'total': paginated.total,
            'page': page,
            'pages': paginated.pages,
            'per_page': per_page
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
@app.route('/api/products/<int:product_id>', methods=['DELETE'])
@login_required
def delete_product(product_id):
    """Delete product completely"""
    try:
        user = User.query.get(session['user_id'])
        if not user.has_permission('products', 'delete'):
            return jsonify({'error': 'Permission denied'}), 403
        
        product = Product.query.get_or_404(product_id)
        product_name = product.product_name
        
        # Check if product has any sales records
        sales_items = SaleItem.query.filter_by(product_id=product_id).count()
        
        if sales_items > 0:
            # If product has sales, soft delete
            product.is_active = False
            product.updated_by = session['user_id']
            message = f'Product "{product_name}" deactivated (has sales records)'
            action = 'deactivated'
        else:
            # ========== FIX: Delete related records first ==========
            # 1. Delete product-supplier mappings
            ProductSupplierMapping.query.filter_by(product_id=product_id).delete()
            
            # 2. Delete batches
            Batch.query.filter_by(product_id=product_id).delete()
            
            # 3. Delete the product
            db.session.delete(product)
            message = f'Product "{product_name}" permanently deleted'
            action = 'deleted'
            # ========================================================
        
        db.session.commit()
        
        log_activity(
            session['user_id'], 
            'delete_product', 
            'products', 
            {'product_id': product_id, 'product_name': product_name, 'action': action}
        )
        
        return jsonify({
            'message': message,
            'success': True,
            'product_id': product_id
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
@app.route('/api/products/quick-add', methods=['POST'])
@login_required
def quick_add_product():
    """Quick add product - Fixed for duplicate barcodes and exact matching"""
    try:
        data = request.json
        
        # Validate required fields
        if not data.get('product_name'):
            return jsonify({'error': 'Product name is required'}), 400
        
        # Get values with defaults
        product_name = data['product_name'].strip()
        expiry_date_str = data.get('expiry_date')
        quantity = int(data.get('quantity', 1))
        supplier_input = data.get('supplier_id') or data.get('supplier_name')
        barcode = data.get('barcode', '').strip()
        selling_price = float(data.get('selling_price', 0))
        cost_price = float(data.get('cost_price', 0))
        min_stock = int(data.get('min_stock_level', 10))
        
        print(f"\n{'='*60}")
        print(f"📦 Processing: '{product_name}'")
        print(f"   Barcode provided: '{barcode if barcode else 'None'}'")
        print(f"   Supplier: {supplier_input if supplier_input else 'None'}")
        print(f"   Quantity: {quantity}, Price: {selling_price}, Cost: {cost_price}")
        
        # =====================================================
        # SUPPLIER RESOLUTION LOGIC
        # =====================================================
        supplier_id = None
        supplier_name = None
        
        if supplier_input and str(supplier_input).strip():
            if str(supplier_input).isdigit():
                supplier = Supplier.query.get(int(supplier_input))
                if supplier:
                    supplier_id = supplier.id
                    supplier_name = supplier.supplier_name
                    print(f"   ✅ Found supplier by ID: {supplier_name} (ID: {supplier_id})")
            else:
                supplier = Supplier.query.filter(
                    Supplier.supplier_name.ilike(f"%{supplier_input}%")
                ).first()
                if supplier:
                    supplier_id = supplier.id
                    supplier_name = supplier.supplier_name
                    print(f"   ✅ Found supplier by name: {supplier_name} (ID: {supplier_id})")
        
        # Set default prices if needed
        if selling_price == 0 and cost_price > 0:
            selling_price = cost_price * 1.3
        if cost_price == 0 and selling_price > 0:
            cost_price = selling_price * 0.7
        if selling_price == 0 and cost_price == 0:
            selling_price = 50
            cost_price = 35
        
        # Parse expiry date
        expiry_date = None
        if expiry_date_str:
            try:
                # Handle DD/MM/YYYY or YYYY-MM-DD format
                if '-' in expiry_date_str:
                    expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                elif '/' in expiry_date_str:
                    expiry_date = datetime.strptime(expiry_date_str, '%d/%m/%Y').date()
                print(f"   Expiry date: {expiry_date}")
            except:
                pass
        
        # =====================================================
        # FIND EXISTING PRODUCT - EXACT MATCH ONLY
        # =====================================================
        existing_product = None
        match_reason = None
        
        # LOGIC 1: Try by barcode (ONLY if barcode is provided and NOT 'auto')
        if barcode and barcode != '' and barcode.lower() != 'auto':
            print(f"   🔍 Looking for product with barcode: {barcode}")
            barcode_product = Product.query.filter_by(barcode=barcode).first()
            if barcode_product:
                print(f"   Found product by barcode: '{barcode_product.product_name}'")
                # CRITICAL: Check if barcode belongs to a product with EXACT name match
                if barcode_product.product_name.lower() == product_name.lower():
                    existing_product = barcode_product
                    match_reason = "barcode + exact name"
                    print(f"   ✅ EXACT match by barcode and name")
                else:
                    # Barcode exists but belongs to DIFFERENT product
                    print(f"   ⚠️ WARNING: Barcode '{barcode}' belongs to '{barcode_product.product_name}'")
                    print(f"   ⚠️ This barcode will NOT be used - creating new product with new barcode")
                    # Force barcode to be regenerated
                    barcode = None
        
        # LOGIC 2: Try by EXACT name match (if no barcode match found)
        if not existing_product:
            print(f"   🔍 Looking for exact name match: '{product_name}'")
            
            all_products = Product.query.filter(Product.is_active == True).all()
            
            for prod in all_products:
                if prod.product_name.lower() == product_name.lower():
                    print(f"   Found EXACT name match: '{prod.product_name}'")
                    
                    # Check supplier mapping
                    mappings = ProductSupplierMapping.query.filter_by(product_id=prod.id).all()
                    supplier_ids = [m.supplier_id for m in mappings]
                    
                    supplier_match = False
                    if supplier_id:
                        supplier_match = supplier_id in supplier_ids
                    else:
                        supplier_match = True
                    
                    # Check cost match
                    prod_cost = float(prod.cost_price) if prod.cost_price else 0
                    cost_match = abs(prod_cost - cost_price) < 1.01
                    
                    print(f"      Supplier match: {supplier_match} (DB IDs: {supplier_ids})")
                    print(f"      Cost match: {cost_match} (DB: {prod_cost}, New: {cost_price})")
                    
                    if supplier_match and cost_match:
                        existing_product = prod
                        match_reason = "exact name + supplier + cost"
                        print(f"   ✅ Match found for UPDATE")
                        break
                    else:
                        print(f"   ⚠️ Supplier or cost mismatch - will create NEW product")
                        break
        
        # =====================================================
        # IF PRODUCT EXISTS - INCREASE QUANTITY
        # =====================================================
        if existing_product:
            print(f"\n📈 UPDATING existing product: {existing_product.product_name}")
            print(f"   Match reason: {match_reason}")
            
            existing_batches = Batch.query.filter_by(
                product_id=existing_product.id,
                is_active=True
            ).all()
            
            # Find batch with matching expiry
            matching_batch = None
            if expiry_date:
                for batch in existing_batches:
                    if batch.expiry_date == expiry_date:
                        matching_batch = batch
                        break
            
            # Update min stock - take LOWER value
            min_stock_updated = False
            old_min_stock = existing_product.min_stock_level
            
            if min_stock != existing_product.min_stock_level:
                new_min_stock = min(min_stock, existing_product.min_stock_level)
                existing_product.min_stock_level = new_min_stock
                min_stock_updated = True
                print(f"   Min stock: {old_min_stock} → {new_min_stock}")
            
            # Update prices if different
            if selling_price != float(existing_product.selling_price):
                existing_product.selling_price = selling_price
                print(f"   Selling price updated: {selling_price}")
            if cost_price != float(existing_product.cost_price):
                existing_product.cost_price = cost_price
                print(f"   Cost price updated: {cost_price}")
            
            # Add supplier mapping if needed
            if supplier_id:
                existing_mapping = ProductSupplierMapping.query.filter_by(
                    product_id=existing_product.id,
                    supplier_id=supplier_id
                ).first()
                if not existing_mapping:
                    mapping = ProductSupplierMapping(
                        product_id=existing_product.id,
                        supplier_id=supplier_id,
                        is_preferred=False
                    )
                    db.session.add(mapping)
                    print(f"   Added supplier mapping for ID: {supplier_id}")
            
            # Add to batch
            if matching_batch:
                matching_batch.remaining_quantity += quantity
                matching_batch.quantity += quantity
                db.session.commit()
                print(f"   ✅ Added {quantity} to existing batch (expiry: {expiry_date})")
                
                return jsonify({
                    'success': True,
                    'existing_updated': True,
                    'action': 'updated',
                    'product_name': existing_product.product_name,
                    'quantity_added': quantity,
                    'message': f'Added {quantity} to {existing_product.product_name}'
                }), 200
            else:
                batch_number = f"BATCH-{datetime.now().strftime('%Y%m%d')}-{existing_product.id}-{datetime.now().strftime('%H%M%S')}"
                batch = Batch(
                    batch_number=batch_number,
                    product_id=existing_product.id,
                    expiry_date=expiry_date if expiry_date else datetime.now().date() + timedelta(days=365),
                    received_date=datetime.now().date(),
                    quantity=quantity,
                    remaining_quantity=quantity,
                    purchase_price=cost_price,
                    selling_price=selling_price,
                    created_by=session['user_id']
                )
                db.session.add(batch)
                db.session.commit()
                print(f"   ✅ Created new batch with {quantity} units")
                
                return jsonify({
                    'success': True,
                    'existing_updated': True,
                    'action': 'updated',
                    'product_name': existing_product.product_name,
                    'quantity_added': quantity,
                    'message': f'Added {quantity} to {existing_product.product_name}'
                }), 200
        
        # =====================================================
        # CREATE NEW PRODUCT
        # =====================================================
        print(f"\n🆕 CREATING new product: {product_name}")
        
        # Generate product code
        last_product = Product.query.order_by(Product.id.desc()).first()
        last_id = last_product.id if last_product else 0
        product_code = f"PRD{str(last_id + 1).zfill(5)}"
        
        # Generate barcode (ALWAYS generate new, unique barcode)
        prefix = '890'
        timestamp = datetime.now().strftime('%y%m%d%H%M')
        random_digits = ''.join(random.choices(string.digits, k=4))
        barcode = prefix + timestamp + random_digits
        # Ensure unique barcode
        while Product.query.filter_by(barcode=barcode).first():
            random_digits = ''.join(random.choices(string.digits, k=4))
            barcode = prefix + timestamp + random_digits
        print(f"   Generated new unique barcode: {barcode}")
        
        # Create product
        product = Product(
            product_code=product_code,
            barcode=barcode,
            product_name=product_name,
            selling_price=selling_price,
            cost_price=cost_price,
            min_stock_level=min_stock,
            is_perishable=True if expiry_date else False,
            created_by=session['user_id'],
            updated_by=session['user_id']
        )
        db.session.add(product)
        db.session.flush()
        
        # Create batch
        batch_number = f"BATCH-{datetime.now().strftime('%Y%m%d')}-{product.id}-{datetime.now().strftime('%H%M%S')}"
        batch = Batch(
            batch_number=batch_number,
            product_id=product.id,
            expiry_date=expiry_date if expiry_date else datetime.now().date() + timedelta(days=365),
            received_date=datetime.now().date(),
            quantity=quantity,
            remaining_quantity=quantity,
            purchase_price=cost_price,
            selling_price=selling_price,
            created_by=session['user_id']
        )
        db.session.add(batch)
        
        # Add supplier mapping if found
        if supplier_id:
            mapping = ProductSupplierMapping(
                product_id=product.id,
                supplier_id=supplier_id,
                is_preferred=False,
                supplier_sku=barcode
            )
            db.session.add(mapping)
            print(f"   Added supplier mapping: {supplier_name} (ID: {supplier_id})")
        
        db.session.commit()
        
        print(f"✅ Created new product: {product_name} with barcode: {barcode}")
        
        return jsonify({
            'success': True,
            'existing_updated': False,
            'action': 'created',
            'product_id': product.id,
            'product_name': product.product_name,
            'barcode': barcode,
            'quantity_added': quantity,
            'message': f'Added new product "{product.product_name}" with {quantity} units'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False, 'action': 'failed'}), 500

# =====================================================
# SUPPLIER API ROUTES
# =====================================================
@app.route('/api/suppliers/list', methods=['GET'])
@login_required
def get_suppliers_list():
    """Get simplified list of suppliers for dropdown"""
    try:
        suppliers = Supplier.query.filter_by(is_active=True).all()
        return jsonify([{
            'id': s.id,
            'name': s.supplier_name,
            'code': s.supplier_code
        } for s in suppliers])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/suppliers', methods=['GET'])
@login_required
def get_suppliers():
    """Get all suppliers"""
    try:
        user = User.query.get(session['user_id'])
        if not user.has_permission('suppliers', 'view'):
            return jsonify({'error': 'Permission denied'}), 403
        
        search = request.args.get('search', '')
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        query = Supplier.query
        
        if search:
            query = query.filter(
                db.or_(
                    Supplier.supplier_name.ilike(f'%{search}%'),
                    Supplier.contact_person.ilike(f'%{search}%'),
                    Supplier.email.ilike(f'%{search}%'),
                    Supplier.gst_number.ilike(f'%{search}%')
                )
            )
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        suppliers = query.order_by(Supplier.supplier_name).all()
        
        return jsonify([s.to_dict() for s in suppliers])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/suppliers', methods=['POST'])
@login_required
def create_supplier():
    """Create new supplier"""
    try:
        user = User.query.get(session['user_id'])
        if not user.has_permission('suppliers', 'create'):
            return jsonify({'error': 'Permission denied'}), 403
        
        data = request.json
        
        if not data.get('supplier_name'):
            return jsonify({'error': 'Supplier name is required'}), 400
        
        if not data.get('address_line1') or not data.get('city') or not data.get('state'):
            return jsonify({'error': 'Complete address is required'}), 400
        
        if not data.get('supplier_code'):
            last_supplier = Supplier.query.order_by(Supplier.id.desc()).first()
            last_id = last_supplier.id if last_supplier else 0
            data['supplier_code'] = f"SUP{str(last_id + 1).zfill(5)}"
        
        supplier = Supplier(
            supplier_code=data['supplier_code'],
            supplier_name=data['supplier_name'],
            supplier_type=data.get('supplier_type'),
            contact_person=data.get('contact_person'),
            email=data.get('email'),
            phone=data.get('phone'),
            alternate_phone=data.get('alternate_phone'),
            gst_number=data.get('gst_number'),
            pan_number=data.get('pan_number'),
            address_line1=data['address_line1'],
            address_line2=data.get('address_line2'),
            city=data['city'],
            state=data['state'],
            pincode=data['pincode'],
            country=data.get('country', 'India'),
            payment_terms=data.get('payment_terms'),
            credit_days=data.get('credit_days', 0),
            credit_limit=data.get('credit_limit'),
            is_preferred=data.get('is_preferred', False),
            created_by=session['user_id'],
            updated_by=session['user_id']
        )
        
        db.session.add(supplier)
        db.session.commit()
        
        log_activity(session['user_id'], 'create_supplier', 'suppliers', {'supplier_id': supplier.id})
        
        return jsonify(supplier.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/suppliers/<int:supplier_id>', methods=['PUT'])
@login_required
def update_supplier(supplier_id):
    """Update supplier"""
    try:
        user = User.query.get(session['user_id'])
        if not user.has_permission('suppliers', 'edit'):
            return jsonify({'error': 'Permission denied'}), 403
        
        supplier = Supplier.query.get_or_404(supplier_id)
        data = request.json
        
        updatable_fields = [
            'supplier_name', 'supplier_type', 'contact_person', 'email', 'phone',
            'alternate_phone', 'gst_number', 'pan_number', 'address_line1',
            'address_line2', 'city', 'state', 'pincode', 'country',
            'payment_terms', 'credit_days', 'credit_limit', 'is_preferred', 'is_active'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(supplier, field, data[field])
        
        supplier.updated_by = session['user_id']
        db.session.commit()
        
        log_activity(session['user_id'], 'update_supplier', 'suppliers', {'supplier_id': supplier_id})
        
        return jsonify(supplier.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# =====================================================
# BATCH API ROUTES
# =====================================================

@app.route('/api/batches', methods=['GET'])
@login_required
def get_batches():
    """Get all batches with filters"""
    try:
        user = User.query.get(session['user_id'])
        if not user.has_permission('batches', 'view'):
            return jsonify({'error': 'Permission denied'}), 403
        
        product_id = request.args.get('product_id')
        status = request.args.get('status')
        expiring_soon = request.args.get('expiring_soon', 'false').lower() == 'true'
        
        query = Batch.query.filter_by(is_active=True)
        
        if product_id:
            query = query.filter_by(product_id=product_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if expiring_soon:
            expiry_threshold = datetime.now().date() + timedelta(days=7)
            query = query.filter(Batch.expiry_date <= expiry_threshold)
        
        batches = query.order_by(Batch.expiry_date).all()
        
        return jsonify([b.to_dict() for b in batches])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/batches/receive', methods=['POST'])
@login_required
def receive_batch():
    """Receive new batch"""
    try:
        user = User.query.get(session['user_id'])
        if not user.has_permission('batches', 'create'):
            return jsonify({'error': 'Permission denied'}), 403
        
        data = request.json
        
        product = None
        if data.get('barcode'):
            product = Product.query.filter_by(barcode=data['barcode']).first()
        elif data.get('product_id'):
            product = Product.query.get(data['product_id'])
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        batch = Batch(
            batch_number=data['batch_number'],
            product_id=product.id,
            supplier_id=data.get('supplier_id'),
            manufacturing_date=datetime.strptime(data['manufacturing_date'], '%Y-%m-%d') if data.get('manufacturing_date') else None,
            expiry_date=datetime.strptime(data['expiry_date'], '%Y-%m-%d'),
            received_date=datetime.now().date(),
            quantity=data['quantity'],
            remaining_quantity=data['quantity'],
            purchase_price=data['purchase_price'],
            selling_price=data.get('selling_price', product.selling_price),
            location=data.get('location'),
            created_by=session['user_id']
        )
        
        db.session.add(batch)
        db.session.commit()
        
        log_activity(session['user_id'], 'receive_batch', 'batches', {'batch_id': batch.id, 'product': product.product_name})
        
        return jsonify(batch.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# =====================================================
# SALES API ROUTES
# =====================================================

@app.route('/api/sales', methods=['POST'])
@login_required
def create_sale():
    """Create new sale"""
    try:
        user = User.query.get(session['user_id'])
        if not user.has_permission('sales', 'create'):
            return jsonify({'error': 'Permission denied'}), 403
        
        data = request.json
        
        last_sale = Sale.query.order_by(Sale.id.desc()).first()
        last_id = last_sale.id if last_sale else 0
        invoice_number = f"INV{datetime.now().strftime('%Y%m%d')}{str(last_id + 1).zfill(4)}"
        
        sale = Sale(
            invoice_number=invoice_number,
            customer_name=data.get('customer_name'),
            customer_phone=data.get('customer_phone'),
            customer_email=data.get('customer_email'),
            subtotal=data['subtotal'],
            discount_total=data.get('discount_total', 0),
            tax_total=data.get('tax_total', 0),
            grand_total=data['grand_total'],
            payment_method=data['payment_method'],
            payment_status=data.get('payment_status', 'paid'),
            created_by=session['user_id']
        )
        
        db.session.add(sale)
        db.session.flush()
        
        for item in data['items']:
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item['product_id'],
                batch_id=item.get('batch_id'),
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                discount_percent=item.get('discount_percent', 0),
                discount_amount=item.get('discount_amount', 0),
                total_price=item['total_price']
            )
            db.session.add(sale_item)
            
            if item.get('batch_id'):
                batch = Batch.query.get(item['batch_id'])
                if batch:
                    batch.remaining_quantity -= item['quantity']
        
        db.session.commit()
        
        log_activity(session['user_id'], 'create_sale', 'sales', {'invoice': invoice_number, 'amount': float(data['grand_total'])})
        
        return jsonify(sale.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales/today', methods=['GET'])
@login_required
def get_today_sales():
    """Get today's sales"""
    try:
        user = User.query.get(session['user_id'])
        if not user.has_permission('sales', 'view'):
            return jsonify({'error': 'Permission denied'}), 403
        
        sales = Sale.query.filter(
            func.date(Sale.created_at) == datetime.now().date()
        ).order_by(Sale.created_at.desc()).all()
        
        return jsonify([s.to_dict() for s in sales])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# USER MANAGEMENT API (Admin only)
# =====================================================

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users with pagination and status filter"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        status = request.args.get('status', 'active')
        
        if status == 'active':
            query = User.query.filter_by(is_active=True)
        elif status == 'inactive':
            query = User.query.filter_by(is_active=False)
        else:
            query = User.query
        
        if search:
            query = query.filter(
                db.or_(
                    User.username.ilike(f'%{search}%'),
                    User.full_name.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%')
                )
            )
        
        paginated = query.order_by(User.id).paginate(page=page, per_page=per_page, error_out=False)
        
        users_data = []
        for user in paginated.items:
            users_data.append({
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'email': user.email,
                'role': user.role,
                'department': user.department,
                'phone': user.phone,
                'is_active': user.is_active,
                'last_login': user.last_login.isoformat() if user.last_login else None
            })
        
        return jsonify({
            'items': users_data,
            'total': paginated.total,
            'page': page,
            'pages': paginated.pages,
            'per_page': per_page,
            'status': status
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    """Create new user"""
    try:
        data = request.json
        
        if not data.get('username') or not data.get('email'):
            return jsonify({'error': 'Username and email required'}), 400
        
        if not data.get('password'):
            return jsonify({'error': 'Password required'}), 400
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        user = User(
            username=data['username'],
            email=data['email'],
            full_name=data.get('full_name', ''),
            role=data.get('role', 'sales_staff'),
            department=data.get('department'),
            phone=data.get('phone'),
            is_active=data.get('is_active', True),
            created_by=session['user_id']
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        log_activity(session['user_id'], 'create_user', 'users', {'user_id': user.id})
        
        return jsonify(user.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Update user"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.json
        
        if 'username' in data and data['username'] != user.username:
            existing = User.query.filter_by(username=data['username']).first()
            if existing:
                return jsonify({'error': 'Username already exists'}), 400
            user.username = data['username']
        
        if 'email' in data and data['email'] != user.email:
            existing = User.query.filter_by(email=data['email']).first()
            if existing:
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data['email']
        
        if 'full_name' in data:
            user.full_name = data['full_name']
        
        if 'role' in data:
            user.role = data['role']
        
        if 'department' in data:
            user.department = data['department']
        
        if 'phone' in data:
            user.phone = data['phone']
        
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        if 'password' in data and data['password']:
            user.set_password(data['password'])
        
        db.session.commit()
        
        log_activity(session['user_id'], 'update_user', 'users', {'user_id': user.id})
        
        return jsonify(user.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>/activate', methods=['POST'])
@admin_required
def activate_user(user_id):
    """Reactivate a deactivated user"""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.is_active:
            return jsonify({'error': 'User is already active'}), 400
        
        user.is_active = True
        user.updated_by = session['user_id']
        db.session.commit()
        
        log_activity(session['user_id'], 'activate_user', 'users', {'user_id': user.id})
        
        return jsonify({'message': f'User {user.username} activated successfully', 'user': user.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Soft delete user"""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.id == session['user_id']:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        user.is_active = False
        db.session.commit()
        
        log_activity(session['user_id'], 'delete_user', 'users', {'user_id': user.id})
        
        return jsonify({'message': 'User deactivated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# =====================================================
# HR MODULE API ROUTES
# =====================================================

@app.route('/api/hr/departments', methods=['GET'])
@login_required
def hr_get_departments():
    """Get all departments"""
    try:
        departments = Department.query.all()
        result = []
        for dept in departments:
            result.append({
                'id': dept.id,
                'name': dept.name,
                'code': dept.code,
                'description': dept.description,
                'is_active': dept.is_active
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/employees', methods=['GET'])
@login_required
def hr_get_employees():
    """Get all employees with filters"""
    try:
        department = request.args.get('department')
        status = request.args.get('status')
        search = request.args.get('search', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        query = Employee.query
        
        if department and department != '':
            query = query.filter(Employee.department_id == department)
        
        if status and status != 'all' and status != '':
            query = query.filter(Employee.employment_status == status)
        
        if search:
            query = query.join(User, Employee.user_id == User.id).filter(
                db.or_(
                    User.full_name.ilike(f'%{search}%'),
                    Employee.employee_code.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%')
                )
            )
        
        query = query.order_by(Employee.id.desc())
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        items = [emp.to_dict() for emp in paginated.items]
        
        return jsonify({
            'items': items,
            'total': paginated.total,
            'page': page,
            'pages': paginated.pages,
            'per_page': per_page
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/employees', methods=['POST'])
@hr_required
def hr_create_employee():
    """Create new employee with user account"""
    try:
        data = request.json
        
        if not data.get('username'):
            return jsonify({'error': 'Username is required'}), 400
        
        if not data.get('password') or len(data['password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': f'Username "{data["username"]}" already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        last_emp = Employee.query.order_by(Employee.id.desc()).first()
        last_id = last_emp.id if last_emp else 0
        employee_code = f"EMP{str(last_id + 1).zfill(5)}"
        
        user = User(
            username=data['username'],
            email=data['email'],
            full_name=f"{data['first_name']} {data['last_name']}",
            role=data.get('role', 'employee'),
            is_active=True,
            created_by=session['user_id']
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.flush()
        
        employee = Employee(
            user_id=user.id,
            employee_code=employee_code,
            department_id=data.get('department_id'),
            position=data.get('designation'),
            job_title=data.get('job_title'),
            employment_type=data.get('employee_type', 'permanent'),
            reporting_manager_id=data.get('reporting_manager_id'),
            date_of_birth=datetime.strptime(data['date_of_birth'], '%Y-%m-%d') if data.get('date_of_birth') else None,
            gender=data.get('gender'),
            marital_status=data.get('marital_status'),
            nationality=data.get('nationality', 'Indian'),
            personal_email=data.get('personal_email'),
            personal_phone=data.get('phone'),
            work_email=data['email'],
            work_phone=data.get('work_phone'),
            emergency_contact_name=data.get('emergency_contact_name'),
            emergency_contact_phone=data.get('emergency_contact_phone'),
            emergency_contact_relation=data.get('emergency_contact_relation'),
            address_line1=data.get('address_line1'),
            address_line2=data.get('address_line2'),
            city=data.get('city'),
            state=data.get('state'),
            pincode=data.get('pincode'),
            country=data.get('country', 'India'),
            hire_date=datetime.strptime(data['hire_date'], '%Y-%m-%d'),
            confirmation_date=datetime.strptime(data['confirmation_date'], '%Y-%m-%d') if data.get('confirmation_date') else None,
            employment_status='active',
            basic_salary=data.get('basic_salary'),
            hourly_rate=data.get('hourly_rate'),
            bank_name=data.get('bank_name'),
            bank_account=data.get('bank_account'),
            ifsc_code=data.get('ifsc_code'),
            pan_number=data.get('pan_number'),
            uan_number=data.get('uan_number'),
            esi_number=data.get('esi_number'),
            created_by=session['user_id']
        )
        
        db.session.add(employee)
        db.session.commit()
        
        log_activity(session['user_id'], 'create_employee', 'hr', {'employee_id': employee.id})
        
        return jsonify({
            **employee.to_dict(),
            'username': user.username,
            'role': user.role,
            'message': f'Employee created! Login: {user.username} / Password: {data["password"]}'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/employees/<int:employee_id>', methods=['GET'])
@login_required
def hr_get_employee(employee_id):
    """Get single employee details"""
    try:
        employee = Employee.query.get_or_404(employee_id)
        result = employee.to_dict()
        
        if employee.user:
            result['user_role'] = employee.user.role
            result['role'] = employee.user.role
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/employees/<int:employee_id>', methods=['PUT'])
@hr_required
def hr_update_employee(employee_id):
    """Update employee details"""
    try:
        employee = Employee.query.get_or_404(employee_id)
        data = request.json
        
        updatable_fields = [
            'position', 'job_title', 'employment_type', 'reporting_manager_id',
            'date_of_birth', 'gender', 'marital_status', 'nationality',
            'personal_email', 'personal_phone', 'work_email', 'work_phone',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            'address_line1', 'address_line2', 'city', 'state', 'pincode', 'country',
            'basic_salary', 'hourly_rate', 'bank_name', 'bank_account', 'ifsc_code',
            'pan_number', 'uan_number', 'esi_number', 'employment_status',
            'department_id'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(employee, field, data[field])
        
        if 'designation' in data:
            employee.position = data['designation']
        
        if employee.user:
            if data.get('first_name') and data.get('last_name'):
                employee.user.full_name = f"{data['first_name']} {data['last_name']}"
            
            if data.get('email') and data['email'] != employee.user.email:
                existing_user = User.query.filter_by(email=data['email']).first()
                if existing_user and existing_user.id != employee.user.id:
                    return jsonify({'error': 'Email already exists'}), 400
                employee.user.email = data['email']
            
            new_role = data.get('user_role') or data.get('role')
            if new_role and new_role != employee.user.role:
                employee.user.role = new_role
            
            if data.get('username') and data['username'] != employee.user.username:
                existing_user = User.query.filter_by(username=data['username']).first()
                if existing_user and existing_user.id != employee.user.id:
                    return jsonify({'error': 'Username already exists'}), 400
                employee.user.username = data['username']
        
        if data.get('hire_date') and isinstance(data['hire_date'], str):
            employee.hire_date = datetime.strptime(data['hire_date'], '%Y-%m-%d')
        
        employee.updated_by = session['user_id']
        db.session.commit()
        
        log_activity(session['user_id'], 'update_employee', 'hr', {'employee_id': employee_id})
        return jsonify(employee.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/attendance', methods=['GET'])
@login_required
def hr_get_attendance():
    """Get attendance records"""
    try:
        employee_id = request.args.get('employee_id')
        month = request.args.get('month')
        year = request.args.get('year')
        
        query = Attendance.query
        
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
        if month and year:
            query = query.filter(
                extract('month', Attendance.date) == month,
                extract('year', Attendance.date) == year
            )
        
        records = query.order_by(Attendance.date.desc()).all()
        
        result = []
        for rec in records:
            rec_dict = rec.to_dict()
            if rec.employee:
                rec_dict['employee_code'] = rec.employee.employee_code
                rec_dict['department_name'] = rec.employee.department.name if rec.employee.department else None
            result.append(rec_dict)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/attendance', methods=['POST'])
@hr_required
def hr_mark_attendance():
    """Mark attendance for employee with leave conflict check"""
    try:
        data = request.json
        employee_id = data['employee_id']
        attendance_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        
        conflicting_leave = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.start_date <= attendance_date,
            LeaveRequest.end_date >= attendance_date,
            LeaveRequest.status == 'approved'
        ).first()
        
        leave_warning = None
        if conflicting_leave:
            leave_warning = {
                'has_leave': True,
                'leave_id': conflicting_leave.id,
                'leave_type': conflicting_leave.leave_type,
                'message': f'Employee has APPROVED {conflicting_leave.leave_type.upper()} leave on this date!'
            }
        
        check_in_time = None
        if data.get('check_in_time'):
            check_in_time = datetime.strptime(f"{data['date']} {data['check_in_time']}", '%Y-%m-%d %H:%M')
        
        check_out_time = None
        if data.get('check_out_time'):
            check_out_time = datetime.strptime(f"{data['date']} {data['check_out_time']}", '%Y-%m-%d %H:%M')
        
        work_hours = None
        if check_in_time and check_out_time:
            work_hours = (check_out_time - check_in_time).seconds / 3600
        
        existing = Attendance.query.filter_by(
            employee_id=employee_id,
            date=attendance_date
        ).first()
        
        if existing:
            existing.check_in_time = check_in_time
            existing.check_out_time = check_out_time
            existing.work_hours = work_hours
            existing.status = data['status']
            existing.remarks = data.get('remarks')
        else:
            attendance = Attendance(
                employee_id=employee_id,
                date=attendance_date,
                check_in_time=check_in_time,
                check_out_time=check_out_time,
                work_hours=work_hours,
                status=data['status'],
                remarks=data.get('remarks')
            )
            db.session.add(attendance)
        
        db.session.commit()
        
        log_activity(session['user_id'], 'mark_attendance', 'hr', {'employee_id': employee_id})
        
        response = {'message': 'Attendance marked successfully'}
        if leave_warning:
            response['warning'] = leave_warning
        
        return jsonify(response)
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/leaves', methods=['GET'])
@login_required
def hr_get_leaves():
    """Get leave requests with employee department info"""
    try:
        employee_id = request.args.get('employee_id')
        status = request.args.get('status')
        
        query = LeaveRequest.query
        
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
        if status:
            query = query.filter_by(status=status)
        
        leaves = query.order_by(LeaveRequest.created_at.desc()).all()
        
        result = []
        for leave in leaves:
            leave_dict = leave.to_dict()
            if leave.employee:
                leave_dict['employee_code'] = leave.employee.employee_code
                leave_dict['department_name'] = leave.employee.department.name if leave.employee.department else None
            result.append(leave_dict)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/leaves', methods=['POST'])
@login_required
def hr_create_leave_request():
    """Create leave request"""
    try:
        data = request.json
        employee_id = data.get('employee_id')
        
        if session.get('role') not in ['admin', 'hr_manager']:
            employee = Employee.query.filter_by(user_id=session['user_id']).first()
            if not employee or employee.id != data['employee_id']:
                return jsonify({'error': 'You can only request leave for yourself'}), 403
            employee_id = employee.id
        
        leave = LeaveRequest(
            employee_id=employee_id,
            leave_type=data['leave_type'],
            start_date=datetime.strptime(data['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date(),
            total_days=data['total_days'],
            reason=data.get('reason')
        )
        
        db.session.add(leave)
        db.session.commit()
        
        log_activity(session['user_id'], 'create_leave_request', 'hr', {'leave_id': leave.id})
        return jsonify(leave.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/leaves/<int:leave_id>/approve', methods=['POST'])
@hr_required
def hr_approve_leave(leave_id):
    """Approve or reject leave request"""
    try:
        data = request.json
        leave = LeaveRequest.query.get_or_404(leave_id)
        action = data.get('action')
        
        if action == 'approve':
            leave.status = 'approved'
            leave.approved_by = session['user_id']
            leave.approved_date = datetime.utcnow()
            
            balance = LeaveBalance.query.filter_by(
                employee_id=leave.employee_id,
                year=leave.start_date.year,
                leave_type=leave.leave_type
            ).first()
            
            if balance:
                balance.total_used += leave.total_days
                balance.balance_remaining = balance.total_allocated - balance.total_used
            
        elif action == 'reject':
            leave.status = 'rejected'
            leave.rejection_reason = data.get('reason')
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        db.session.commit()
        
        log_activity(session['user_id'], f'{action}_leave', 'hr', {'leave_id': leave_id})
        return jsonify({'message': f'Leave {action}d successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/leaves/<int:leave_id>/cancel', methods=['POST'])
@hr_required
def hr_cancel_leave(leave_id):
    """Cancel approved leave"""
    try:
        data = request.json
        leave = LeaveRequest.query.get_or_404(leave_id)
        
        if leave.status == 'cancelled':
            return jsonify({'error': 'Leave is already cancelled'}), 400
        
        if leave.status != 'approved':
            return jsonify({'error': f'Only approved leaves can be cancelled. Current status: {leave.status}'}), 400
        
        reason = data.get('reason', 'Employee attended work on leave date')
        
        leave.status = 'cancelled'
        leave.rejection_reason = reason
        
        balance = LeaveBalance.query.filter_by(
            employee_id=leave.employee_id,
            year=leave.start_date.year,
            leave_type=leave.leave_type
        ).first()
        
        if balance:
            balance.total_used = max(0, balance.total_used - leave.total_days)
            balance.balance_remaining = balance.total_allocated - balance.total_used
        
        db.session.commit()
        
        log_activity(session['user_id'], 'cancel_leave', 'hr', {'leave_id': leave_id})
        
        return jsonify({'success': True, 'message': 'Leave cancelled successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/dashboard/stats', methods=['GET'])
@login_required
def hr_dashboard_stats():
    """Get HR dashboard statistics"""
    try:
        total_employees = Employee.query.filter_by(employment_status='active').count()
        today = datetime.now().date()
        today_attendance = Attendance.query.filter(
            Attendance.date == today,
            Attendance.status == 'present'
        ).count()
        pending_leaves = LeaveRequest.query.filter_by(status='pending').count()
        on_leave_today = LeaveRequest.query.filter(
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
            LeaveRequest.status == 'approved'
        ).count()
        
        attendance_rate = (today_attendance / total_employees * 100) if total_employees > 0 else 0
        
        return jsonify({
            'total_employees': total_employees,
            'today_attendance': today_attendance,
            'pending_leaves': pending_leaves,
            'on_leave_today': on_leave_today,
            'attendance_rate': attendance_rate
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# PAYROLL API ROUTES
# =====================================================

@app.route('/api/hr/payroll', methods=['GET'])
@login_required
def hr_get_payroll():
    """Get payroll records"""
    try:
        employee_id = request.args.get('employee_id')
        month = request.args.get('month')
        year = request.args.get('year')
        
        query = PayrollRecord.query
        
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
        if month and year:
            query = query.filter(
                extract('month', PayrollRecord.payroll_month) == month,
                extract('year', PayrollRecord.payroll_month) == year
            )
        
        records = query.order_by(PayrollRecord.payroll_month.desc()).all()
        
        result = []
        for rec in records:
            rec_dict = rec.to_dict()
            if rec.employee:
                rec_dict['employee_name'] = rec.employee.full_name
                rec_dict['employee_code'] = rec.employee.employee_code
                rec_dict['department_name'] = rec.employee.department.name if rec.employee.department else None
            result.append(rec_dict)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/payroll/generate', methods=['POST'])
@hr_required
def hr_generate_payroll():
    """Generate payroll for a month"""
    try:
        data = request.json
        month = data['month']
        year = data['year']
        
        employees = Employee.query.filter_by(employment_status='active').all()
        
        payroll_records = []
        for emp in employees:
            attendance = Attendance.query.filter(
                Attendance.employee_id == emp.id,
                extract('month', Attendance.date) == month,
                extract('year', Attendance.date) == year,
                Attendance.status.in_(['present', 'late', 'half_day'])
            ).all()
            
            present_days = len(attendance)
            total_days = 30
            daily_rate = float(emp.basic_salary or 0) / total_days
            basic_pay = daily_rate * present_days
            allowances = basic_pay * 0.5
            
            overtime_hours = sum(float(a.overtime_hours or 0) for a in attendance)
            overtime_rate = daily_rate / 8 * 1.5
            overtime_pay = overtime_hours * overtime_rate
            
            gross_earnings = basic_pay + allowances + overtime_pay
            pf = min(gross_earnings * 0.12, 1800) if emp.pf_eligible else 0
            esi = gross_earnings * 0.0075 if emp.esi_eligible and gross_earnings <= 21000 else 0
            professional_tax = 200 if gross_earnings > 15000 else 0
            
            total_deductions = pf + esi + professional_tax
            net_payable = gross_earnings - total_deductions
            
            payroll_date = datetime(int(year), int(month), 1).date()
            
            existing = PayrollRecord.query.filter_by(
                employee_id=emp.id,
                payroll_month=payroll_date
            ).first()
            
            if existing:
                existing.basic_salary = basic_pay
                existing.allowances = allowances
                existing.overtime = overtime_pay
                existing.gross_earnings = gross_earnings
                existing.pf_deduction = pf
                existing.esi_deduction = esi
                existing.professional_tax = professional_tax
                existing.total_deductions = total_deductions
                existing.net_payable = net_payable
                existing.present_days = present_days
                existing.absent_days = total_days - present_days
                existing.status = 'draft'
                record = existing
            else:
                record = PayrollRecord(
                    employee_id=emp.id,
                    payroll_month=payroll_date,
                    basic_salary=basic_pay,
                    allowances=allowances,
                    overtime=overtime_pay,
                    gross_earnings=gross_earnings,
                    pf_deduction=pf,
                    esi_deduction=esi,
                    professional_tax=professional_tax,
                    total_deductions=total_deductions,
                    net_payable=net_payable,
                    present_days=present_days,
                    absent_days=total_days - present_days,
                    status='draft'
                )
                db.session.add(record)
            
            payroll_records.append(record)
        
        db.session.commit()
        
        log_activity(session['user_id'], 'generate_payroll', 'hr', {'month': month, 'year': year})
        
        return jsonify({
            'message': f'Payroll generated for {len(payroll_records)} employees',
            'total_cost': sum(float(r.net_payable) for r in payroll_records)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/payroll/<int:payroll_id>/approve', methods=['POST'])
@hr_required
def hr_approve_payroll(payroll_id):
    """Approve or mark as paid payroll record"""
    try:
        payroll = PayrollRecord.query.get_or_404(payroll_id)
        data = request.json
        
        if data.get('mark_paid'):
            payroll.status = 'paid'
            payroll.payment_date = datetime.now().date()
        else:
            payroll.status = 'approved'
            payroll.approved_by = session['user_id']
            payroll.approved_at = datetime.utcnow()
        
        db.session.commit()
        
        log_activity(session['user_id'], f'payroll_{payroll.status}', 'hr', {'payroll_id': payroll_id})
        
        return jsonify({'message': f'Payroll {payroll.status} successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# =====================================================
# EMPLOYEE SELF-SERVICE API ROUTES
# =====================================================

@app.route('/api/employee/profile', methods=['GET'])
@login_required
def employee_get_profile():
    """Get logged-in employee's profile"""
    try:
        user_id = session['user_id']
        employee = Employee.query.filter_by(user_id=user_id).first()
        
        if not employee:
            employee = Employee(
                user_id=user_id,
                employee_code=f"EMP{user_id}",
                hire_date=datetime.now().date(),
                employment_status='active'
            )
            db.session.add(employee)
            db.session.commit()
            return jsonify(employee.to_dict())
        
        return jsonify(employee.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/employee/attendance/recent', methods=['GET'])
@login_required
def employee_recent_attendance():
    """Get recent attendance records for logged-in employee"""
    try:
        user_id = session['user_id']
        employee = Employee.query.filter_by(user_id=user_id).first()
        
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        month = request.args.get('month')
        year = request.args.get('year')
        limit = request.args.get('limit', 100, type=int)
        
        query = Attendance.query.filter_by(employee_id=employee.id)
        
        if month and year:
            query = query.filter(
                extract('month', Attendance.date) == month,
                extract('year', Attendance.date) == year
            )
        
        records = query.order_by(Attendance.date.desc()).limit(limit).all()
        
        return jsonify([rec.to_dict() for rec in records])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/employee/leaves/recent', methods=['GET'])
@login_required
def employee_recent_leaves():
    """Get recent leave requests for logged-in employee"""
    try:
        user_id = session['user_id']
        employee = Employee.query.filter_by(user_id=user_id).first()
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        limit = request.args.get('limit', 10, type=int)
        
        leaves = LeaveRequest.query.filter_by(
            employee_id=employee.id
        ).order_by(LeaveRequest.created_at.desc()).limit(limit).all()
        
        return jsonify([leave.to_dict() for leave in leaves])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/employee/leave/request', methods=['POST'])
@login_required
def employee_request_leave():
    """Create leave request for logged-in employee"""
    try:
        data = request.json
        user_id = session['user_id']
        employee = Employee.query.filter_by(user_id=user_id).first()
        
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        leave = LeaveRequest(
            employee_id=employee.id,
            leave_type=data['leave_type'],
            start_date=datetime.strptime(data['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date(),
            total_days=data['total_days'],
            reason=data.get('reason'),
            status='pending'
        )
        
        db.session.add(leave)
        db.session.commit()
        
        log_activity(session['user_id'], 'request_leave', 'employee', {'leave_id': leave.id})
        
        return jsonify(leave.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# =====================================================
# ANNOUNCEMENTS API
# =====================================================

announcements = []

@app.route('/api/hr/announcements/send', methods=['POST'])
@hr_required
def send_announcement():
    """Send announcement to all employees"""
    try:
        data = request.json
        message = data.get('message')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        announcement = {
            'id': len(announcements) + 1,
            'message': message,
            'created_at': datetime.now().isoformat(),
            'created_by': session['username']
        }
        
        announcements.insert(0, announcement)
        
        while len(announcements) > 20:
            announcements.pop()
        
        log_activity(session['user_id'], 'send_announcement', 'hr', {'message': message[:50]})
        
        return jsonify({'success': True, 'message': 'Announcement sent successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr/announcements/latest', methods=['GET'])
@login_required
def get_latest_announcement():
    """Get latest announcement for employees"""
    try:
        if announcements:
            return jsonify(announcements[0])
        return jsonify({'message': None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# ACTIVITIES API
# =====================================================

@app.route('/api/activities/recent', methods=['GET'])
@login_required
def get_recent_activities():
    """Get recent activities based on user role"""
    try:
        user_role = session.get('role')
        module = request.args.get('module')
        limit = request.args.get('limit', 10, type=int)
        
        query = ActivityLog.query
        
        if module:
            query = query.filter_by(module=module)
        elif user_role == 'inventory_manager':
            query = query.filter(ActivityLog.module.in_(['products', 'suppliers', 'batches']))
        elif user_role == 'sales_staff':
            query = query.filter(ActivityLog.module.in_(['sales']))
        
        activities = query.order_by(ActivityLog.created_at.desc()).limit(limit).all()
        
        result = []
        for act in activities:
            user = User.query.get(act.user_id)
            result.append({
                'id': act.id,
                'user': user.full_name if user else 'System',
                'action': act.action,
                'module': act.module,
                'detail_text': str(act.details) if act.details else '',
                'time': act.created_at.isoformat() if act.created_at else None
            })
        
        return jsonify({'activities': result})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# CATEGORIES API
# =====================================================

@app.route('/api/categories')
@login_required
def get_categories():
    """Get all unique product categories"""
    try:
        categories = db.session.query(Product.category).filter(
            Product.category.isnot(None),
            Product.category != ''
        ).distinct().all()
        
        return jsonify([c[0] for c in categories])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# TEST & UTILITY ROUTES
# =====================================================

@app.route('/api/test', methods=['GET'])
def test():
    """Test route to check if server is running"""
    return jsonify({
        'status': 'ok',
        'message': 'Server is running!',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/debug-products', methods=['GET'])
def debug_products():
    """Debug endpoint to check products"""
    try:
        from sqlalchemy import text
        db_status = db.session.execute(text('SELECT 1')).scalar()
        products = Product.query.all()
        product_count = len(products)
        
        sample_product = None
        if products:
            try:
                sample_product = products[0].to_dict()
            except Exception as e:
                sample_product = {'error': str(e)}
        
        return jsonify({
            'database_connected': bool(db_status),
            'product_count': product_count,
            'sample_product': sample_product
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/employee-mapping', methods=['GET'])
@login_required
def debug_employee_mapping():
    """Debug employee-user mapping"""
    try:
        user_id = session['user_id']
        user = User.query.get(user_id)
        employee = Employee.query.filter_by(user_id=user_id).first()
        
        all_employees = Employee.query.all()
        employee_data = []
        for emp in all_employees:
            employee_data.append({
                'employee_id': emp.id,
                'employee_code': emp.employee_code,
                'user_id': emp.user_id,
                'full_name': emp.full_name,
                'username': emp.user.username if emp.user else None,
                'email': emp.user.email if emp.user else None
            })
        
        return jsonify({
            'current_user': {
                'user_id': user_id,
                'username': user.username,
                'role': user.role,
                'full_name': user.full_name
            },
            'current_employee': employee.to_dict() if employee else None,
            'all_employees': employee_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# ERROR HANDLERS
# =====================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# =====================================================
# MAIN ENTRY POINT
# =====================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)