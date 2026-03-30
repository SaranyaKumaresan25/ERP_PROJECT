from functools import wraps
from flask import session, jsonify, request
from models import User, ActivityLog
from datetime import datetime
import secrets

# =====================================================
# AUTHENTICATION DECORATORS
# =====================================================

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Authentication required', 'login_required': True}), 401
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


def inventory_required(f):
    """Decorator to require inventory manager or admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        role = session.get('role')
        if role not in ['admin', 'inventory_manager']:
            return jsonify({'error': 'Inventory manager access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


def sales_required(f):
    """Decorator to require sales staff or admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        role = session.get('role')
        if role not in ['admin', 'sales_staff']:
            return jsonify({'error': 'Sales staff access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


def hr_required(f):
    """Decorator to require HR or admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        role = session.get('role')
        if role not in ['admin', 'hr_manager']:
            return jsonify({'error': 'HR access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


def employee_required(f):
    """Decorator to require employee role (self-service access)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        role = session.get('role')
        if role not in ['admin', 'hr_manager', 'employee']:
            return jsonify({'error': 'Employee access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


def any_role_required(allowed_roles):
    """Decorator to require any of the specified roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            role = session.get('role')
            if role not in allowed_roles:
                return jsonify({'error': f'Access requires one of: {", ".join(allowed_roles)}'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def log_activity(user_id, action, module=None, details=None):
    """Log user activity"""
    try:
        from app import db
        log = ActivityLog(
            user_id=user_id,
            action=action,
            module=module,
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")
        db.session.rollback()


def generate_csrf_token():
    """Generate CSRF token"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def get_dashboard_url_for_role(role):
    """Get dashboard URL based on user role"""
    role_urls = {
        'admin': '/admin/dashboard',
        'hr_manager': '/hr/dashboard',
        'inventory_manager': '/inventory/dashboard',
        'sales_staff': '/sales/dashboard',
        'employee': '/employee/profile'
    }
    return role_urls.get(role, '/login')


def get_employee_by_user_id(user_id):
    """Get employee record associated with user"""
    try:
        from models import Employee
        return Employee.query.filter_by(user_id=user_id).first()
    except Exception as e:
        print(f"Error getting employee: {e}")
        return None


def get_user_permissions(user_role):
    """Get permissions for a given user role"""
    try:
        from models import Permission
        permissions = Permission.query.filter_by(role=user_role).all()
        return {
            'role': user_role,
            'modules': {
                perm.module: {
                    'view': perm.can_view,
                    'create': perm.can_create,
                    'edit': perm.can_edit,
                    'delete': perm.can_delete,
                    'approve': perm.can_approve
                } for perm in permissions
            }
        }
    except Exception as e:
        print(f"Error getting permissions: {e}")
        return {'role': user_role, 'modules': {}}


def check_user_permission(user_id, module, action='view'):
    """Check if a user has permission for a specific module action"""
    try:
        from models import User
        user = User.query.get(user_id)
        if not user:
            return False
        return user.has_permission(module, action)
    except Exception as e:
        print(f"Error checking permission: {e}")
        return False


# =====================================================
# SESSION MANAGEMENT
# =====================================================

def get_current_user():
    """Get the current logged-in user from session"""
    try:
        from models import User
        user_id = session.get('user_id')
        if user_id:
            return User.query.get(user_id)
        return None
    except Exception as e:
        print(f"Error getting current user: {e}")
        return None


def get_current_user_role():
    """Get the role of the current logged-in user"""
    return session.get('role')


def is_authenticated():
    """Check if user is authenticated"""
    return 'user_id' in session


def is_role(role):
    """Check if current user has a specific role"""
    return session.get('role') == role


def is_any_role(roles):
    """Check if current user has any of the specified roles"""
    return session.get('role') in roles


# =====================================================
# AUDIT & SECURITY
# =====================================================

def log_security_event(user_id, event_type, details=None):
    """Log security-related events (failed logins, etc.)"""
    try:
        from app import db
        from models import ActivityLog
        log = ActivityLog(
            user_id=user_id,
            action=f"security_{event_type}",
            module="security",
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging security event: {e}")


def validate_csrf_token(token):
    """Validate CSRF token"""
    stored_token = session.get('csrf_token')
    if not stored_token or not token:
        return False
    return secrets.compare_digest(stored_token, token)


def get_client_ip():
    """Get client IP address from request"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr


# =====================================================
# DASHBOARD REDIRECTION
# =====================================================

def redirect_to_dashboard():
    """Redirect user to their appropriate dashboard based on role"""
    role = session.get('role')
    return get_dashboard_url_for_role(role)


def get_role_based_redirect(user_role):
    """Get redirect URL based on user role"""
    return get_dashboard_url_for_role(user_role)


# =====================================================
# PERMISSION CHECKING DECORATORS
# =====================================================

def permission_required(module, action='view'):
    """Decorator to check if user has permission for a module action"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            user_id = session['user_id']
            if check_user_permission(user_id, module, action):
                return f(*args, **kwargs)
            
            return jsonify({'error': f'Permission denied for {module}:{action}'}), 403
        return decorated_function
    return decorator


def module_access_required(module):
    """Decorator to require view permission for a module"""
    return permission_required(module, 'view')


def module_create_required(module):
    """Decorator to require create permission for a module"""
    return permission_required(module, 'create')


def module_edit_required(module):
    """Decorator to require edit permission for a module"""
    return permission_required(module, 'edit')


def module_delete_required(module):
    """Decorator to require delete permission for a module"""
    return permission_required(module, 'delete')


# =====================================================
# USER STATUS HELPERS
# =====================================================

def is_user_active(user_id):
    """Check if a user is active"""
    try:
        from models import User
        user = User.query.get(user_id)
        return user and user.is_active
    except Exception:
        return False


def get_user_full_name(user_id):
    """Get user's full name by ID"""
    try:
        from models import User
        user = User.query.get(user_id)
        return user.full_name if user else 'Unknown'
    except Exception:
        return 'Unknown'


# =====================================================
# SESSION UTILITIES
# =====================================================

def update_session_user(user):
    """Update session with user data"""
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    session['full_name'] = user.full_name
    session['csrf_token'] = secrets.token_hex(32)


def clear_session():
    """Clear all session data"""
    session.clear()


def get_session_data():
    """Get current session data (safe version)"""
    return {
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'role': session.get('role'),
        'full_name': session.get('full_name'),
        'authenticated': 'user_id' in session
    }


# =====================================================
# INITIALIZATION
# =====================================================

def init_auth(app):
    """Initialize authentication for the app"""
    # Set session cookie security settings
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Generate initial CSRF token
    @app.before_request
    def before_request():
        if 'user_id' in session and 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)