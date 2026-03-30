# analytics.py - Profit Recovery Analytics Module
# Complete version with inventory expiry tracking and HR analytics

from datetime import datetime, timedelta
from sqlalchemy import text, func
from models import db, Product, Batch, Sale, Employee, Attendance, LeaveRequest, PayrollRecord

# =====================================================
# INVENTORY ANALYTICS FUNCTIONS
# =====================================================

def calculate_metrics():
    """
    Calculate profit recovery metrics for expiring products
    This function is called by the Flask app
    """
    try:
        # Get all batches with remaining stock
        query = """
            SELECT 
                b.id AS batch_id,
                b.product_id,
                p.product_name,
                p.product_code,
                b.remaining_quantity AS quantity,
                b.expiry_date,
                p.cost_price,
                p.selling_price,
                b.purchase_price,
                b.batch_number
            FROM batches b
            INNER JOIN products p ON b.product_id = p.id
            WHERE b.remaining_quantity > 0
            AND b.is_active = 1
            ORDER BY b.expiry_date ASC
        """
        
        result = db.session.execute(text(query))
        data = result.fetchall()
        
        today = datetime.now().date()
        
        # Clear old metrics
        db.session.execute(text("DELETE FROM recovery_metrics"))
        db.session.execute(text("DELETE FROM alerts WHERE is_read = 0"))
        
        metrics_count = 0
        high_risk_count = 0
        
        for row in data:
            batch = dict(row._mapping)
            
            # Calculate days until expiry
            expiry_date = batch['expiry_date']
            if expiry_date:
                days = (expiry_date - today).days
            else:
                days = 365
            
            # Risk Classification based on days to expiry
            if days <= 2:
                risk = "HIGH"
                discount = 0.30
                high_risk_count += 1
            elif days <= 5:
                risk = "MEDIUM"
                discount = 0.15
            elif days <= 10:
                risk = "MEDIUM"
                discount = 0.10
            else:
                risk = "LOW"
                discount = 0.0
            
            # Safe type conversions
            quantity = int(batch['quantity'] or 0)
            cost_price = float(batch['cost_price'] or 0)
            selling_price = float(batch['selling_price'] or 0)
            
            # Calculate metrics
            potential_loss = quantity * cost_price
            recoverable = quantity * (selling_price * (1 - discount))
            discount_amount = quantity * selling_price * discount
            efficiency = (recoverable / potential_loss * 100) if potential_loss > 0 else 0
            
            # Insert into recovery_metrics
            insert_query = """
                INSERT INTO recovery_metrics 
                (batch_id, product_id, product_name, product_code, quantity, expiry_date, 
                 days_to_expiry, risk_level, suggested_discount, 
                 potential_loss, recoverable_amount, recovery_efficiency, discount_amount,
                 batch_number)
                VALUES 
                (:batch_id, :product_id, :product_name, :product_code, :quantity, :expiry_date,
                 :days_to_expiry, :risk_level, :suggested_discount,
                 :potential_loss, :recoverable_amount, :recovery_efficiency, :discount_amount,
                 :batch_number)
                ON DUPLICATE KEY UPDATE
                    quantity = VALUES(quantity),
                    expiry_date = VALUES(expiry_date),
                    days_to_expiry = VALUES(days_to_expiry),
                    risk_level = VALUES(risk_level),
                    suggested_discount = VALUES(suggested_discount),
                    potential_loss = VALUES(potential_loss),
                    recoverable_amount = VALUES(recoverable_amount),
                    recovery_efficiency = VALUES(recovery_efficiency),
                    discount_amount = VALUES(discount_amount)
            """
            
            db.session.execute(text(insert_query), {
                'batch_id': batch['batch_id'],
                'product_id': batch['product_id'],
                'product_name': batch['product_name'],
                'product_code': batch.get('product_code', ''),
                'quantity': quantity,
                'expiry_date': expiry_date,
                'days_to_expiry': days,
                'risk_level': risk,
                'suggested_discount': discount * 100,
                'potential_loss': potential_loss,
                'recoverable_amount': recoverable,
                'recovery_efficiency': efficiency,
                'discount_amount': discount_amount,
                'batch_number': batch.get('batch_number', '')
            })
            
            metrics_count += 1
            
            # Create alerts for HIGH risk products
            if risk == "HIGH":
                if days < 0:
                    message = f"{batch['product_name']} has EXPIRED! Immediate action required."
                elif days == 0:
                    message = f"{batch['product_name']} expires TODAY! Urgent sale needed."
                else:
                    message = f"{batch['product_name']} expires in {days} days! Apply {int(discount*100)}% discount."
                
                alert_query = """
                    INSERT INTO alerts (product_id, message, risk_level, product_name, batch_id)
                    VALUES (:product_id, :message, :risk_level, :product_name, :batch_id)
                """
                db.session.execute(text(alert_query), {
                    'product_id': batch['product_id'],
                    'message': message,
                    'risk_level': risk,
                    'product_name': batch['product_name'],
                    'batch_id': batch['batch_id']
                })
        
        db.session.commit()
        
        print(f"[{datetime.now()}] Analytics metrics calculated: {metrics_count} products, {high_risk_count} high risk")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error calculating analytics: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_summary_metrics():
    """
    Get summary metrics for inventory dashboard
    """
    try:
        # Check if recovery_metrics table exists
        try:
            result = db.session.execute(text("SELECT SUM(potential_loss) as total FROM recovery_metrics"))
            total_loss = result.fetchone()[0] or 0
        except:
            total_loss = 0
        
        try:
            result = db.session.execute(text("SELECT SUM(recoverable_amount) as total FROM recovery_metrics"))
            total_recoverable = result.fetchone()[0] or 0
        except:
            total_recoverable = 0
        
        try:
            result = db.session.execute(text("SELECT COUNT(*) as count FROM recovery_metrics WHERE risk_level = 'HIGH'"))
            high_risk = result.fetchone()[0] or 0
        except:
            high_risk = 0
        
        try:
            result = db.session.execute(text("SELECT COUNT(*) as count FROM recovery_metrics WHERE risk_level = 'MEDIUM'"))
            medium_risk = result.fetchone()[0] or 0
        except:
            medium_risk = 0
        
        try:
            result = db.session.execute(text("SELECT COUNT(*) as count FROM recovery_metrics WHERE risk_level = 'LOW'"))
            low_risk = result.fetchone()[0] or 0
        except:
            low_risk = 0
        
        total_products = high_risk + medium_risk + low_risk
        
        return {
            'total_potential_loss': float(total_loss),
            'total_recoverable': float(total_recoverable),
            'high_risk_count': high_risk,
            'medium_risk_count': medium_risk,
            'low_risk_count': low_risk,
            'total_products_at_risk': total_products,
            'recovery_rate': (total_recoverable / total_loss * 100) if total_loss > 0 else 0
        }
        
    except Exception as e:
        print(f"Error getting summary metrics: {e}")
        return {
            'total_potential_loss': 0,
            'total_recoverable': 0,
            'high_risk_count': 0,
            'medium_risk_count': 0,
            'low_risk_count': 0,
            'total_products_at_risk': 0,
            'recovery_rate': 0
        }


def get_expiring_products(days_threshold=7):
    """
    Get products expiring within specified days
    """
    try:
        today = datetime.now().date()
        expiry_limit = today + timedelta(days=days_threshold)
        
        query = """
            SELECT 
                p.id,
                p.product_name,
                p.product_code,
                p.barcode,
                p.selling_price,
                p.cost_price,
                SUM(b.remaining_quantity) as total_stock,
                MIN(b.expiry_date) as earliest_expiry,
                COUNT(b.id) as batch_count
            FROM products p
            INNER JOIN batches b ON p.id = b.product_id
            WHERE b.expiry_date <= :expiry_limit
            AND b.expiry_date > :today
            AND b.remaining_quantity > 0
            AND b.is_active = 1
            GROUP BY p.id, p.product_name, p.product_code, p.barcode, p.selling_price, p.cost_price
            ORDER BY earliest_expiry ASC
        """
        
        result = db.session.execute(text(query), {
            'expiry_limit': expiry_limit,
            'today': today
        })
        
        products = []
        for row in result:
            products.append(dict(row._mapping))
        
        return products
        
    except Exception as e:
        print(f"Error getting expiring products: {e}")
        return []


def get_low_stock_products():
    """
    Get products with low stock (below min_stock_level)
    """
    try:
        query = """
            SELECT 
                p.id,
                p.product_name,
                p.product_code,
                p.barcode,
                p.min_stock_level,
                p.selling_price,
                COALESCE(SUM(b.remaining_quantity), 0) as current_stock
            FROM products p
            LEFT JOIN batches b ON p.id = b.product_id AND b.is_active = 1
            WHERE p.is_active = 1
            GROUP BY p.id, p.product_name, p.product_code, p.barcode, p.min_stock_level, p.selling_price
            HAVING current_stock <= p.min_stock_level
            ORDER BY (current_stock / p.min_stock_level) ASC
        """
        
        result = db.session.execute(text(query))
        
        products = []
        for row in result:
            products.append(dict(row._mapping))
        
        return products
        
    except Exception as e:
        print(f"Error getting low stock products: {e}")
        return []


def get_dashboard_alerts(limit=10):
    """
    Get active alerts for dashboard
    """
    try:
        query = """
            SELECT * FROM alerts 
            WHERE is_read = 0 
            ORDER BY created_at DESC
            LIMIT :limit
        """
        
        result = db.session.execute(text(query), {'limit': limit})
        alerts = [dict(row._mapping) for row in result]
        
        return alerts
        
    except Exception as e:
        print(f"Error getting alerts: {e}")
        return []


# =====================================================
# HR ANALYTICS FUNCTIONS
# =====================================================

def get_hr_dashboard_metrics():
    """
    Get HR dashboard metrics
    """
    try:
        # Total employees
        total_employees = Employee.query.filter_by(employment_status='active').count()
        
        # Today's attendance
        today = datetime.now().date()
        today_attendance = Attendance.query.filter(
            Attendance.date == today,
            Attendance.status == 'present'
        ).count()
        
        # Pending leaves
        pending_leaves = LeaveRequest.query.filter_by(status='pending').count()
        
        # On leave today
        on_leave_today = LeaveRequest.query.filter(
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
            LeaveRequest.status == 'approved'
        ).count()
        
        # Attendance rate
        attendance_rate = (today_attendance / total_employees * 100) if total_employees > 0 else 0
        
        return {
            'total_employees': total_employees,
            'today_attendance': today_attendance,
            'pending_leaves': pending_leaves,
            'on_leave_today': on_leave_today,
            'attendance_rate': attendance_rate
        }
        
    except Exception as e:
        print(f"Error getting HR metrics: {e}")
        return {
            'total_employees': 0,
            'today_attendance': 0,
            'pending_leaves': 0,
            'on_leave_today': 0,
            'attendance_rate': 0
        }


def get_employee_attendance_summary(employee_id, year=None, month=None):
    """
    Get attendance summary for a specific employee
    """
    try:
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month
        
        query = Attendance.query.filter(
            Attendance.employee_id == employee_id,
            extract('year', Attendance.date) == year,
            extract('month', Attendance.date) == month
        )
        
        records = query.all()
        
        present = sum(1 for r in records if r.status == 'present')
        absent = sum(1 for r in records if r.status == 'absent')
        late = sum(1 for r in records if r.status == 'late')
        half_day = sum(1 for r in records if r.status == 'half_day')
        
        total = len(records)
        attendance_rate = (present / total * 100) if total > 0 else 0
        
        return {
            'present': present,
            'absent': absent,
            'late': late,
            'half_day': half_day,
            'total_days': total,
            'attendance_rate': attendance_rate
        }
        
    except Exception as e:
        print(f"Error getting employee attendance summary: {e}")
        return {
            'present': 0,
            'absent': 0,
            'late': 0,
            'half_day': 0,
            'total_days': 0,
            'attendance_rate': 0
        }


def get_leave_balance_summary(employee_id):
    """
    Get leave balance summary for an employee
    """
    try:
        current_year = datetime.now().year
        
        balances = LeaveBalance.query.filter_by(
            employee_id=employee_id,
            year=current_year
        ).all()
        
        result = {}
        for balance in balances:
            result[balance.leave_type] = {
                'total_allocated': balance.total_allocated,
                'total_used': balance.total_used,
                'balance_remaining': balance.balance_remaining
            }
        
        return result
        
    except Exception as e:
        print(f"Error getting leave balance: {e}")
        return {}


def get_payroll_summary(month=None, year=None):
    """
    Get payroll summary for a specific month
    """
    try:
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month
        
        payroll_month = datetime(int(year), int(month), 1).date()
        
        records = PayrollRecord.query.filter(
            extract('month', PayrollRecord.payroll_month) == month,
            extract('year', PayrollRecord.payroll_month) == year
        ).all()
        
        total_employees = len(records)
        total_payroll = sum(float(r.net_payable) for r in records)
        avg_salary = total_payroll / total_employees if total_employees > 0 else 0
        
        return {
            'total_employees': total_employees,
            'total_payroll': total_payroll,
            'avg_salary': avg_salary,
            'records': [r.to_dict() for r in records]
        }
        
    except Exception as e:
        print(f"Error getting payroll summary: {e}")
        return {
            'total_employees': 0,
            'total_payroll': 0,
            'avg_salary': 0,
            'records': []
        }


# =====================================================
# COMPREHENSIVE ANALYTICS RUNNER
# =====================================================

def run_all_analytics():
    """
    Run all analytics (inventory + HR)
    """
    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] Running ALL analytics...")
    print(f"{'='*60}")
    
    # Run inventory analytics
    print("\n📦 INVENTORY ANALYTICS:")
    inventory_success = calculate_metrics()
    
    if inventory_success:
        inv_summary = get_summary_metrics()
        expiring = get_expiring_products(7)
        low_stock = get_low_stock_products()
        alerts = get_dashboard_alerts(5)
        
        print(f"  - Products at risk: {inv_summary['total_products_at_risk']}")
        print(f"  - High risk: {inv_summary['high_risk_count']}")
        print(f"  - Medium risk: {inv_summary['medium_risk_count']}")
        print(f"  - Low risk: {inv_summary['low_risk_count']}")
        print(f"  - Potential loss: ₹{inv_summary['total_potential_loss']:,.2f}")
        print(f"  - Recoverable: ₹{inv_summary['total_recoverable']:,.2f}")
        print(f"  - Recovery rate: {inv_summary['recovery_rate']:.1f}%")
        print(f"  - Expiring in 7 days: {len(expiring)} products")
        print(f"  - Low stock: {len(low_stock)} products")
        print(f"  - Active alerts: {len(alerts)}")
    
    # Run HR analytics
    print("\n👥 HR ANALYTICS:")
    hr_metrics = get_hr_dashboard_metrics()
    
    print(f"  - Total employees: {hr_metrics['total_employees']}")
    print(f"  - Today's attendance: {hr_metrics['today_attendance']}")
    print(f"  - Attendance rate: {hr_metrics['attendance_rate']:.1f}%")
    print(f"  - Pending leaves: {hr_metrics['pending_leaves']}")
    print(f"  - On leave today: {hr_metrics['on_leave_today']}")
    
    print(f"\n{'='*60}")
    print("✅ Analytics run completed")
    print(f"{'='*60}\n")
    
    return {
        'inventory_success': inventory_success,
        'inventory_summary': inv_summary if inventory_success else None,
        'hr_metrics': hr_metrics
    }


def run_analytics_auto():
    """
    Run analytics automatically (can be called by scheduler)
    - Alias for run_all_analytics for backward compatibility
    """
    return run_all_analytics()


# For testing directly
if __name__ == '__main__':
    from app import app, db
    with app.app_context():
        run_all_analytics()