from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

# =====================================================
# USER MODEL
# =====================================================
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum('admin', 'hr_manager', 'inventory_manager', 'sales_staff', 'employee'), nullable=False)

    department = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    profile_image = db.Column(db.String(500))
    
    theme_preference = db.Column(db.String(20), default='light')
    default_dashboard = db.Column(db.String(50))
    
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    last_ip = db.Column(db.String(45))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    creator = db.relationship('User', remote_side=[id], backref='created_users')
    products_created = db.relationship('Product', foreign_keys='Product.created_by', backref='creator')
    products_updated = db.relationship('Product', foreign_keys='Product.updated_by', backref='updater')
    suppliers_created = db.relationship('Supplier', foreign_keys='Supplier.created_by', backref='creator')
    suppliers_updated = db.relationship('Supplier', foreign_keys='Supplier.updated_by', backref='updater')
    sales_made = db.relationship('Sale', backref='cashier')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, module, action='view'):
        """Check if user has permission for a module action"""
        if self.role == 'admin':
            return True
        
        perm = Permission.query.filter_by(role=self.role, module=module).first()
        if not perm:
            return False
        
        if action == 'view':
            return perm.can_view
        elif action == 'create':
            return perm.can_create
        elif action == 'edit':
            return perm.can_edit
        elif action == 'delete':
            return perm.can_delete
        elif action == 'approve':
            return perm.can_approve
        
        return False
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'department': self.department,
            'phone': self.phone,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'theme_preference': self.theme_preference,
            'default_dashboard': self.get_dashboard_url()
        }
    
    def get_dashboard_url(self):
        """Get default dashboard URL based on role"""
        if self.role == 'admin':
            return '/admin/dashboard'
        elif self.role == 'hr_manager':
            return '/hr/dashboard'
        elif self.role == 'inventory_manager':
            return '/inventory/dashboard'
        elif self.role == 'sales_staff':
            return '/sales/dashboard'
        elif self.role == 'employee':
            return '/employee/profile'
        return '/login'


# =====================================================
# PERMISSION MODEL
# =====================================================
class Permission(db.Model):
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.Enum('admin', 'hr_manager', 'inventory_manager', 'sales_staff'), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    can_view = db.Column(db.Boolean, default=True)
    can_create = db.Column(db.Boolean, default=False)
    can_edit = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    can_approve = db.Column(db.Boolean, default=False)
    
    __table_args__ = (db.UniqueConstraint('role', 'module', name='unique_role_module'),)


# =====================================================
# PRODUCT MODEL
# =====================================================
class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), unique=True, nullable=False)
    barcode = db.Column(db.String(100), unique=True)
    product_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    sub_category = db.Column(db.String(100))
    brand = db.Column(db.String(100))
    
    cost_price = db.Column(db.Numeric(10,2), nullable=False)
    selling_price = db.Column(db.Numeric(10,2), nullable=False)
    mrp = db.Column(db.Numeric(10,2))
    gst_rate = db.Column(db.Numeric(5,2), default=0)
    
    unit_type = db.Column(db.Enum('piece', 'kg', 'gram', 'liter', 'ml', 'box', 'packet', 'dozen'), default='piece')
    min_stock_level = db.Column(db.Integer, default=10)
    max_stock_level = db.Column(db.Integer, default=1000)
    reorder_level = db.Column(db.Integer, default=50)
    
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer)
    requires_refrigeration = db.Column(db.Boolean, default=False)
    
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    batches = db.relationship('Batch', backref='product', lazy=True, cascade='all, delete-orphan')
    supplier_mappings = db.relationship('ProductSupplierMapping', backref='product', lazy=True)
    
    def get_total_stock(self):
        return sum(b.remaining_quantity for b in self.batches if b.is_active) if self.batches else 0
    
    def get_expiring_count(self):
        if not self.batches:
            return 0
        return sum(1 for b in self.batches if b.status == 'expiring_soon' and b.is_active)
    
    def to_dict(self):
        return {
            "id": self.id,
            "product_code": self.product_code,
            "barcode": self.barcode,
            "product_name": self.product_name,
            "description": self.description,
            "category": self.category,
            "sub_category": self.sub_category,
            "brand": self.brand,
            "cost_price": float(self.cost_price or 0),
            "selling_price": float(self.selling_price or 0),
            "mrp": float(self.mrp or 0),
            "gst_rate": float(self.gst_rate or 0),
            "unit_type": self.unit_type,
            "min_stock_level": self.min_stock_level or 0,
            "max_stock_level": self.max_stock_level or 0,
            "reorder_level": self.reorder_level or 0,
            "is_perishable": self.is_perishable,
            "shelf_life_days": self.shelf_life_days,
            "requires_refrigeration": self.requires_refrigeration,
            "is_active": self.is_active
        }


# =====================================================
# SUPPLIER MODEL
# =====================================================
class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_code = db.Column(db.String(50), unique=True, nullable=False)
    supplier_name = db.Column(db.String(200), nullable=False)
    supplier_type = db.Column(db.Enum('manufacturer', 'distributor', 'wholesaler', 'retailer', 'importer'))
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    alternate_phone = db.Column(db.String(20))
    website = db.Column(db.String(200))
    
    gst_number = db.Column(db.String(20), unique=True)
    pan_number = db.Column(db.String(20), unique=True)
    
    address_line1 = db.Column(db.Text, nullable=False)
    address_line2 = db.Column(db.Text)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    country = db.Column(db.String(100), default='India')
    
    bank_name = db.Column(db.String(200))
    account_number = db.Column(db.String(50))
    ifsc_code = db.Column(db.String(20))
    account_holder_name = db.Column(db.String(200))
    
    payment_terms = db.Column(db.String(50))
    credit_days = db.Column(db.Integer, default=0)
    credit_limit = db.Column(db.Numeric(10,2))
    
    reliability_rating = db.Column(db.Integer, default=3)
    quality_rating = db.Column(db.Integer, default=3)
    delivery_rating = db.Column(db.Integer, default=3)
    overall_rating = db.Column(db.Numeric(3,2), default=3.0)
    
    is_active = db.Column(db.Boolean, default=True)
    is_preferred = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    batches = db.relationship('Batch', backref='supplier', lazy=True)
    product_mappings = db.relationship('ProductSupplierMapping', backref='supplier', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'supplier_code': self.supplier_code,
            'supplier_name': self.supplier_name,
            'supplier_type': self.supplier_type,
            'contact_person': self.contact_person,
            'email': self.email,
            'phone': self.phone,
            'gst_number': self.gst_number,
            'pan_number': self.pan_number,
            'address': f"{self.address_line1}, {self.city}, {self.state} - {self.pincode}",
            'address_line1': self.address_line1,
            'address_line2': self.address_line2,
            'city': self.city,
            'state': self.state,
            'pincode': self.pincode,
            'country': self.country,
            'payment_terms': self.payment_terms,
            'credit_days': self.credit_days,
            'credit_limit': float(self.credit_limit) if self.credit_limit else None,
            'overall_rating': float(self.overall_rating) if self.overall_rating else 3.0,
            'is_active': self.is_active,
            'is_preferred': self.is_preferred,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# =====================================================
# BATCH MODEL
# =====================================================
class Batch(db.Model):
    __tablename__ = 'batches'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_number = db.Column(db.String(100), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    
    manufacturing_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date, nullable=False)
    received_date = db.Column(db.Date, nullable=False)
    
    quantity = db.Column(db.Integer, nullable=False)
    remaining_quantity = db.Column(db.Integer, nullable=False)
    damaged_quantity = db.Column(db.Integer, default=0)
    returned_quantity = db.Column(db.Integer, default=0)
    
    purchase_price = db.Column(db.Numeric(10,2), nullable=False)
    selling_price = db.Column(db.Numeric(10,2))
    mrp_at_receipt = db.Column(db.Numeric(10,2))
    
    location = db.Column(db.String(50))
    rack_number = db.Column(db.String(20))
    shelf_number = db.Column(db.String(20))
    bin_number = db.Column(db.String(20))
    
    quality_check_passed = db.Column(db.Boolean, default=True)
    quality_check_date = db.Column(db.Date)
    quality_notes = db.Column(db.Text)
    
    status = db.Column(db.Enum('in_stock', 'low_stock', 'expiring_soon', 'expired', 'sold_out', 'quarantined'), default='in_stock')
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def to_dict(self):
        days_until_expiry = (self.expiry_date - datetime.now().date()).days if self.expiry_date else None
        return {
            'id': self.id,
            'batch_number': self.batch_number,
            'product_id': self.product_id,
            'product_name': self.product.product_name if self.product else None,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier.supplier_name if self.supplier else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'received_date': self.received_date.isoformat() if self.received_date else None,
            'quantity': self.quantity,
            'remaining_quantity': self.remaining_quantity,
            'damaged_quantity': self.damaged_quantity,
            'returned_quantity': self.returned_quantity,
            'purchase_price': float(self.purchase_price) if self.purchase_price else 0,
            'selling_price': float(self.selling_price) if self.selling_price else None,
            'mrp_at_receipt': float(self.mrp_at_receipt) if self.mrp_at_receipt else None,
            'location': self.location,
            'rack_number': self.rack_number,
            'shelf_number': self.shelf_number,
            'bin_number': self.bin_number,
            'quality_check_passed': self.quality_check_passed,
            'quality_check_date': self.quality_check_date.isoformat() if self.quality_check_date else None,
            'quality_notes': self.quality_notes,
            'status': self.status,
            'days_until_expiry': days_until_expiry,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# =====================================================
# PRODUCT SUPPLIER MAPPING
# =====================================================
class ProductSupplierMapping(db.Model):
    __tablename__ = 'product_supplier_mapping'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    
    supplier_sku = db.Column(db.String(100))
    supplier_price = db.Column(db.Numeric(10,2))
    is_preferred = db.Column(db.Boolean, default=False)
    is_primary = db.Column(db.Boolean, default=False)
    lead_time_days = db.Column(db.Integer)
    minimum_order_quantity = db.Column(db.Integer, default=1)
    maximum_order_quantity = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('product_id', 'supplier_id', name='unique_product_supplier'),)


# =====================================================
# SALE MODEL
# =====================================================
class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_name = db.Column(db.String(200))
    customer_phone = db.Column(db.String(20))
    customer_email = db.Column(db.String(100))
    customer_gst = db.Column(db.String(20))
    
    subtotal = db.Column(db.Numeric(10,2), nullable=False)
    discount_total = db.Column(db.Numeric(10,2), default=0)
    tax_total = db.Column(db.Numeric(10,2), default=0)
    grand_total = db.Column(db.Numeric(10,2), nullable=False)
    
    payment_method = db.Column(db.Enum('cash', 'card', 'upi', 'credit', 'bank_transfer'), nullable=False)
    payment_status = db.Column(db.Enum('paid', 'pending', 'partial', 'refunded'), default='paid')
    payment_reference = db.Column(db.String(100))
    
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'subtotal': float(self.subtotal),
            'discount_total': float(self.discount_total),
            'tax_total': float(self.tax_total),
            'grand_total': float(self.grand_total),
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'cashier': self.cashier.full_name if self.cashier else None,
            'items': [item.to_dict() for item in self.items],
            'item_count': len(self.items)
        }


# =====================================================
# SALE ITEM MODEL
# =====================================================
class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'))
    cost_price = db.Column(db.Float, nullable=True)  # ← FROM FRIEND (for profit tracking)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10,2), nullable=False)
    discount_percent = db.Column(db.Numeric(5,2), default=0)
    discount_amount = db.Column(db.Numeric(10,2), default=0)
    tax_amount = db.Column(db.Numeric(10,2), default=0)
    total_price = db.Column(db.Numeric(10,2), nullable=False)
    
    # Relationships
    product = db.relationship('Product')
    batch = db.relationship('Batch')
    
    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.product_name if self.product else None,
            'batch_number': self.batch.batch_number if self.batch else None,
            'cost_price': self.cost_price,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price),
            'discount_percent': float(self.discount_percent),
            'discount_amount': float(self.discount_amount),
            'tax_amount': float(self.tax_amount),
            'total_price': float(self.total_price)
        }

# =====================================================
# ACTIVITY LOG MODEL
# =====================================================
class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50))
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='activities')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user': self.user.full_name if self.user else 'System',
            'action': self.action,
            'module': self.module,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'ip_address': self.ip_address
        }


# =====================================================
# BARCODE SCAN LOG
# =====================================================
class BarcodeScan(db.Model):
    __tablename__ = 'barcode_scans'
    
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(100), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'))
    scan_type = db.Column(db.Enum('receiving', 'selling', 'inventory', 'return', 'damage'), nullable=False)
    scan_time = db.Column(db.DateTime, default=datetime.utcnow)
    scanned_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    device_info = db.Column(db.String(255))
    is_successful = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.String(255))
    
    # Relationships
    product = db.relationship('Product')
    batch = db.relationship('Batch')
    scanner = db.relationship('User', foreign_keys=[scanned_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'barcode': self.barcode,
            'product_name': self.product.product_name if self.product else None,
            'scan_type': self.scan_type,
            'scan_time': self.scan_time.isoformat() if self.scan_time else None,
            'scanned_by': self.scanner.full_name if self.scanner else None,
            'is_successful': self.is_successful
        }


# =====================================================
# HR MODULE MODELS
# =====================================================

class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True)
    description = db.Column(db.Text)
    parent_dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    parent = db.relationship('Department', remote_side=[id], backref='sub_departments')
    employees = db.relationship('Employee', backref='department', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'parent_dept_id': self.parent_dept_id,
            'is_active': self.is_active
        }


class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    employee_code = db.Column(db.String(50), unique=True, nullable=False)
    
    # Professional Information
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    position = db.Column(db.String(100))
    job_title = db.Column(db.String(100))
    # MERGED: Includes all options from both versions
    employment_type = db.Column(db.Enum('full_time', 'part_time', 'contract', 'intern', 'trainee', 'Permanent'), 
                                default='full_time')
    reporting_manager_id = db.Column(db.Integer, db.ForeignKey('employees.id'))
    
    # Personal Information
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.Enum('male', 'female', 'other'))
    marital_status = db.Column(db.Enum('single', 'married', 'divorced', 'widowed'))
    nationality = db.Column(db.String(50), default='Indian')
    
    # Contact
    personal_email = db.Column(db.String(100))
    personal_phone = db.Column(db.String(20))
    work_email = db.Column(db.String(100))
    work_phone = db.Column(db.String(20))
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_phone = db.Column(db.String(20))
    emergency_contact_relation = db.Column(db.String(50))
    
    # Address
    address_line1 = db.Column(db.Text)
    address_line2 = db.Column(db.Text)
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    pincode = db.Column(db.String(10))
    country = db.Column(db.String(50), default='India')
    
    # Employment Dates
    hire_date = db.Column(db.Date, nullable=False)
    confirmation_date = db.Column(db.Date)
    termination_date = db.Column(db.Date)
    employment_status = db.Column(db.Enum('active', 'on_leave', 'suspended', 'terminated'), default='active')
    
    # Compensation
    basic_salary = db.Column(db.Numeric(10,2))
    hourly_rate = db.Column(db.Numeric(10,2))
    pf_eligible = db.Column(db.Boolean, default=True)
    esi_eligible = db.Column(db.Boolean, default=True)
    
    # Bank Details
    bank_name = db.Column(db.String(100))
    bank_account = db.Column(db.String(50))
    ifsc_code = db.Column(db.String(20))
    pan_number = db.Column(db.String(20))
    uan_number = db.Column(db.String(20))
    esi_number = db.Column(db.String(20))
    
    # Documents
    profile_photo = db.Column(db.String(500))
    resume_url = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='employee_profile')
    reporting_manager = db.relationship('Employee', remote_side=[id], backref='subordinates')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_employees')
    updater = db.relationship('User', foreign_keys=[updated_by], backref='updated_employees')
    
    @property
    def full_name(self):
        if self.user:
            return self.user.full_name
        return ''
    
    @property
    def email(self):
        if self.user:
            return self.user.email
        return self.work_email or self.personal_email
    
    @property
    def designation(self):
        return self.position
    
    def to_dict(self):
        user = User.query.get(self.user_id) if self.user_id else None
        
        full_name = user.full_name if user else ''
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        return {
            'id': self.id,
            'user_id': self.user_id,
            'employee_code': self.employee_code,
            'full_name': full_name,
            'first_name': first_name,
            'last_name': last_name,
            'username': user.username if user else '',
            'email': user.email if user else '',
            'user_role': user.role if user else '',
            'role': user.role if user else '',
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'position': self.position,
            'designation': self.position,
            'job_title': self.job_title,
            'employment_type': self.employment_type,
            'reporting_manager_id': self.reporting_manager_id,
            'reporting_manager_name': self.reporting_manager.full_name if self.reporting_manager else None,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'gender': self.gender,
            'marital_status': self.marital_status,
            'nationality': self.nationality,
            'personal_email': self.personal_email,
            'personal_phone': self.personal_phone,
            'work_email': self.work_email,
            'work_phone': self.work_phone,
            'phone': self.personal_phone,
            'emergency_contact_name': self.emergency_contact_name,
            'emergency_contact_phone': self.emergency_contact_phone,
            'emergency_contact_relation': self.emergency_contact_relation,
            'address_line1': self.address_line1,
            'address_line2': self.address_line2,
            'city': self.city,
            'state': self.state,
            'pincode': self.pincode,
            'country': self.country,
            'hire_date': self.hire_date.isoformat() if self.hire_date else None,
            'confirmation_date': self.confirmation_date.isoformat() if self.confirmation_date else None,
            'termination_date': self.termination_date.isoformat() if self.termination_date else None,
            'employment_status': self.employment_status,
            'basic_salary': float(self.basic_salary) if self.basic_salary else 0,
            'hourly_rate': float(self.hourly_rate) if self.hourly_rate else 0,
            'bank_name': self.bank_name,
            'bank_account': self.bank_account,
            'ifsc_code': self.ifsc_code,
            'pan_number': self.pan_number,
            'uan_number': self.uan_number,
            'esi_number': self.esi_number,
            'profile_photo': self.profile_photo
        }
class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    check_in_time = db.Column(db.DateTime)
    check_out_time = db.Column(db.DateTime)
    check_in_location = db.Column(db.String(200))
    check_out_location = db.Column(db.String(200))
    work_hours = db.Column(db.Numeric(5,2))
    overtime_hours = db.Column(db.Numeric(5,2), default=0)
    status = db.Column(db.Enum('present', 'absent', 'late', 'half_day', 'holiday', 'week_off'))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='attendance_records')
    
    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else None,
            'department_name': self.employee.department.name if self.employee and self.employee.department else None,
            'date': self.date.isoformat() if self.date else None,
            'check_in_time': self.check_in_time.isoformat() if self.check_in_time else None,
            'check_out_time': self.check_out_time.isoformat() if self.check_out_time else None,
            'work_hours': float(self.work_hours) if self.work_hours else 0,
            'overtime_hours': float(self.overtime_hours) if self.overtime_hours else 0,
            'status': self.status,
            'remarks': self.remarks
        }


class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    leave_type = db.Column(db.Enum('annual', 'sick', 'casual', 'unpaid', 'maternity', 'paternity'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_days = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.Enum('pending', 'approved', 'rejected', 'cancelled'), default='pending')
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_date = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='leave_requests')
    approver = db.relationship('User', foreign_keys=[approved_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else None,
            'employee_code': self.employee.employee_code if self.employee else None,
            'department_name': self.employee.department.name if self.employee and self.employee.department else None,
            'leave_type': self.leave_type,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'total_days': self.total_days,
            'reason': self.reason,
            'status': self.status,
            'approved_by': self.approved_by,
            'approved_by_name': self.approver.full_name if self.approver else None,
            'approved_date': self.approved_date.isoformat() if self.approved_date else None,
            'rejection_reason': self.rejection_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class LeaveBalance(db.Model):
    __tablename__ = 'leave_balances'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    leave_type = db.Column(db.Enum('annual', 'sick', 'casual', 'unpaid', 'maternity'), nullable=False)
    total_allocated = db.Column(db.Integer, default=0)
    total_used = db.Column(db.Integer, default=0)
    balance_remaining = db.Column(db.Integer, default=0)
    year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='leave_balances')
    
    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.full_name if self.employee else None,
            'leave_type': self.leave_type,
            'total_allocated': self.total_allocated,
            'total_used': self.total_used,
            'balance_remaining': self.balance_remaining,
            'year': self.year
        }


class PayrollRecord(db.Model):
    __tablename__ = 'payroll_records'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    payroll_month = db.Column(db.Date, nullable=False)
    basic_salary = db.Column(db.Numeric(12,2))
    allowances = db.Column(db.Numeric(12,2), default=0)
    overtime = db.Column(db.Numeric(12,2), default=0)
    bonuses = db.Column(db.Numeric(12,2), default=0)
    gross_earnings = db.Column(db.Numeric(12,2))
    
    pf_deduction = db.Column(db.Numeric(12,2), default=0)
    esi_deduction = db.Column(db.Numeric(12,2), default=0)
    professional_tax = db.Column(db.Numeric(12,2), default=0)
    tds = db.Column(db.Numeric(12,2), default=0)
    other_deductions = db.Column(db.Numeric(12,2), default=0)
    total_deductions = db.Column(db.Numeric(12,2))
    
    net_payable = db.Column(db.Numeric(12,2))
    
    attendance_days = db.Column(db.Integer)
    present_days = db.Column(db.Integer)
    absent_days = db.Column(db.Integer)
    leave_days = db.Column(db.Integer)
    
    payment_method = db.Column(db.Enum('bank', 'cash', 'cheque'), default='bank')
    bank_account = db.Column(db.String(50))
    transaction_id = db.Column(db.String(100))
    payment_date = db.Column(db.Date)
    
    status = db.Column(db.Enum('draft', 'approved', 'paid', 'cancelled'), default='draft')
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='payroll_records')
    approver = db.relationship('User', foreign_keys=[approved_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'payroll_month': self.payroll_month.isoformat() if self.payroll_month else None,
            'basic_salary': float(self.basic_salary) if self.basic_salary else 0,
            'allowances': float(self.allowances) if self.allowances else 0,
            'overtime': float(self.overtime) if self.overtime else 0,
            'bonuses': float(self.bonuses) if self.bonuses else 0,
            'gross_earnings': float(self.gross_earnings) if self.gross_earnings else 0,
            'pf_deduction': float(self.pf_deduction) if self.pf_deduction else 0,
            'esi_deduction': float(self.esi_deduction) if self.esi_deduction else 0,
            'professional_tax': float(self.professional_tax) if self.professional_tax else 0,
            'tds': float(self.tds) if self.tds else 0,
            'other_deductions': float(self.other_deductions) if self.other_deductions else 0,
            'total_deductions': float(self.total_deductions) if self.total_deductions else 0,
            'net_payable': float(self.net_payable) if self.net_payable else 0,
            'attendance_days': self.attendance_days,
            'present_days': self.present_days,
            'absent_days': self.absent_days,
            'leave_days': self.leave_days,
            'payment_method': self.payment_method,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'status': self.status,
            'notes': self.notes
        }


# =====================================================
# RECRUITMENT MODELS (Optional)
# =====================================================

class JobPosting(db.Model):
    __tablename__ = 'job_postings'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    location = db.Column(db.String(100))
    employment_type = db.Column(db.String(50))
    experience_required = db.Column(db.Integer)
    salary_range_min = db.Column(db.Numeric(10,2))
    salary_range_max = db.Column(db.Numeric(10,2))
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)
    responsibilities = db.Column(db.Text)
    benefits = db.Column(db.Text)
    status = db.Column(db.Enum('draft', 'published', 'closed', 'cancelled'), default='draft')
    published_date = db.Column(db.DateTime)
    closing_date = db.Column(db.Date)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    department = db.relationship('Department', backref='job_postings')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'location': self.location,
            'employment_type': self.employment_type,
            'experience_required': self.experience_required,
            'salary_range_min': float(self.salary_range_min) if self.salary_range_min else 0,
            'salary_range_max': float(self.salary_range_max) if self.salary_range_max else 0,
            'description': self.description,
            'requirements': self.requirements,
            'responsibilities': self.responsibilities,
            'benefits': self.benefits,
            'status': self.status,
            'published_date': self.published_date.isoformat() if self.published_date else None,
            'closing_date': self.closing_date.isoformat() if self.closing_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class JobApplication(db.Model):
    __tablename__ = 'job_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'))
    candidate_name = db.Column(db.String(100), nullable=False)
    candidate_email = db.Column(db.String(100), nullable=False)
    candidate_phone = db.Column(db.String(20))
    resume_url = db.Column(db.String(500))
    cover_letter = db.Column(db.Text)
    current_company = db.Column(db.String(100))
    current_salary = db.Column(db.Numeric(10,2))
    expected_salary = db.Column(db.Numeric(10,2))
    notice_period = db.Column(db.Integer)
    source = db.Column(db.String(50))
    status = db.Column(db.Enum('applied', 'screening', 'interview', 'offered', 'hired', 'rejected'), default='applied')
    current_stage = db.Column(db.String(50))
    rating = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    screening_date = db.Column(db.DateTime)
    interview_date = db.Column(db.DateTime)
    offer_date = db.Column(db.DateTime)
    hired_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    job_posting = db.relationship('JobPosting', backref='applications')
    
    def to_dict(self):
        return {
            'id': self.id,
            'job_posting_id': self.job_posting_id,
            'job_title': self.job_posting.title if self.job_posting else None,
            'candidate_name': self.candidate_name,
            'candidate_email': self.candidate_email,
            'candidate_phone': self.candidate_phone,
            'resume_url': self.resume_url,
            'cover_letter': self.cover_letter,
            'current_company': self.current_company,
            'current_salary': float(self.current_salary) if self.current_salary else 0,
            'expected_salary': float(self.expected_salary) if self.expected_salary else 0,
            'notice_period': self.notice_period,
            'source': self.source,
            'status': self.status,
            'current_stage': self.current_stage,
            'rating': self.rating,
            'feedback': self.feedback,
            'applied_date': self.applied_date.isoformat() if self.applied_date else None,
            'screening_date': self.screening_date.isoformat() if self.screening_date else None,
            'interview_date': self.interview_date.isoformat() if self.interview_date else None,
            'offer_date': self.offer_date.isoformat() if self.offer_date else None,
            'hired_date': self.hired_date.isoformat() if self.hired_date else None
        }


class Interview(db.Model):
    __tablename__ = 'interviews'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('job_applications.id'))
    interviewer_id = db.Column(db.Integer, db.ForeignKey('employees.id'))
    interview_type = db.Column(db.Enum('phone', 'video', 'onsite', 'technical', 'hr'))
    interview_date = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer)
    location = db.Column(db.String(200))
    meeting_link = db.Column(db.String(500))
    feedback = db.Column(db.Text)
    rating = db.Column(db.Integer)
    result = db.Column(db.Enum('pending', 'passed', 'failed'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    application = db.relationship('JobApplication', backref='interviews')
    interviewer = db.relationship('Employee', foreign_keys=[interviewer_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'candidate_name': self.application.candidate_name if self.application else None,
            'interviewer_id': self.interviewer_id,
            'interviewer_name': self.interviewer.full_name if self.interviewer else None,
            'interview_type': self.interview_type,
            'interview_date': self.interview_date.isoformat() if self.interview_date else None,
            'duration': self.duration,
            'location': self.location,
            'meeting_link': self.meeting_link,
            'feedback': self.feedback,
            'rating': self.rating,
            'result': self.result,
            'notes': self.notes
        }
