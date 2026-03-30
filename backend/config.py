import os
from datetime import timedelta

class Config:
    # =====================================================
    # DATABASE CONFIGURATION
    # =====================================================
    # MySQL Database - UNIFIED configuration for all modules
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'Srija2005')  # ← Use your actual password
    MYSQL_DB = os.environ.get('MYSQL_DB', 'profit_recovery_erp_unified')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    
    # SQLAlchemy Database URI
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,  # Check connection before using
    }
    
    # =====================================================
    # SECURITY CONFIGURATION
    # =====================================================
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-super-secret-key-change-in-production-2024')
    
    # Session Configuration
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY', SECRET_KEY)
    
    # =====================================================
    # FILE UPLOAD CONFIGURATION
    # =====================================================
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default
    
    # Allowed file extensions for uploads
    ALLOWED_EXTENSIONS = {
        'image': {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'},
        'document': {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv'},
        'resume': {'pdf', 'doc', 'docx'}
    }
    
    # =====================================================
    # EMAIL CONFIGURATION (for notifications)
    # =====================================================
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@profitrecovery.com')
    
    # =====================================================
    # LOGGING CONFIGURATION
    # =====================================================
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/erp.log')
    LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', 10 * 1024 * 1024))  # 10MB
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', 5))
    
    # =====================================================
    # CACHE CONFIGURATION (optional)
    # =====================================================
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'simple')
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', 300))  # 5 minutes
    
    # =====================================================
    # API CONFIGURATION
    # =====================================================
    API_RATE_LIMIT = os.environ.get('API_RATE_LIMIT', '100 per minute')
    API_CORS_ORIGINS = os.environ.get('API_CORS_ORIGINS', '*').split(',')
    
    # =====================================================
    # HR MODULE CONFIGURATION
    # =====================================================
    # Leave Policies
    DEFAULT_ANNUAL_LEAVE = int(os.environ.get('DEFAULT_ANNUAL_LEAVE', 12))
    DEFAULT_SICK_LEAVE = int(os.environ.get('DEFAULT_SICK_LEAVE', 10))
    DEFAULT_CASUAL_LEAVE = int(os.environ.get('DEFAULT_CASUAL_LEAVE', 8))
    
    # Attendance Configuration
    DEFAULT_WORK_HOURS = float(os.environ.get('DEFAULT_WORK_HOURS', 9.0))
    LATE_THRESHOLD_MINUTES = int(os.environ.get('LATE_THRESHOLD_MINUTES', 15))
    HALF_DAY_THRESHOLD_HOURS = float(os.environ.get('HALF_DAY_THRESHOLD_HOURS', 4.0))
    
    # Payroll Configuration
    PF_PERCENTAGE = float(os.environ.get('PF_PERCENTAGE', 12.0))
    PF_MAX_LIMIT = float(os.environ.get('PF_MAX_LIMIT', 1800.0))
    ESI_PERCENTAGE = float(os.environ.get('ESI_PERCENTAGE', 0.75))
    ESI_MAX_SALARY = float(os.environ.get('ESI_MAX_SALARY', 21000.0))
    PROFESSIONAL_TAX_THRESHOLD = float(os.environ.get('PROFESSIONAL_TAX_THRESHOLD', 15000.0))
    PROFESSIONAL_TAX_AMOUNT = float(os.environ.get('PROFESSIONAL_TAX_AMOUNT', 200.0))
    
    # =====================================================
    # INVENTORY MODULE CONFIGURATION
    # =====================================================
    # Stock Alerts
    LOW_STOCK_ALERT_DAYS = int(os.environ.get('LOW_STOCK_ALERT_DAYS', 7))
    EXPIRY_ALERT_DAYS = int(os.environ.get('EXPIRY_ALERT_DAYS', 30))
    
    # Barcode Configuration
    BARCODE_PREFIX = os.environ.get('BARCODE_PREFIX', '890')
    BARCODE_DEFAULT_LENGTH = int(os.environ.get('BARCODE_DEFAULT_LENGTH', 13))
    
    # Batch Configuration
    DEFAULT_BATCH_EXPIRY_DAYS = int(os.environ.get('DEFAULT_BATCH_EXPIRY_DAYS', 365))
    
    # =====================================================
    # SALES MODULE CONFIGURATION
    # =====================================================
    INVOICE_PREFIX = os.environ.get('INVOICE_PREFIX', 'INV')
    DEFAULT_DISCOUNT_PERCENT = float(os.environ.get('DEFAULT_DISCOUNT_PERCENT', 0))
    DEFAULT_TAX_PERCENT = float(os.environ.get('DEFAULT_TAX_PERCENT', 18))
    
    # =====================================================
    # REPORTING CONFIGURATION
    # =====================================================
    REPORT_PAGE_SIZE = int(os.environ.get('REPORT_PAGE_SIZE', 50))
    REPORT_EXPORT_FORMATS = ['pdf', 'excel', 'csv']
    
    # =====================================================
    # FRONTEND CONFIGURATION
    # =====================================================
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0  # Disable caching for development
    
    # =====================================================
    # DEVELOPMENT/PRODUCTION SPECIFIC
    # =====================================================
    DEBUG = False
    TESTING = False
    
    @staticmethod
    def init_app(app):
        """Initialize app with configuration"""
        # Create upload folder if it doesn't exist
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)
        
        # Create logs folder if it doesn't exist
        log_dir = os.path.dirname(Config.LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Configure logging
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not app.debug:
            file_handler = RotatingFileHandler(
                Config.LOG_FILE, 
                maxBytes=Config.LOG_MAX_BYTES, 
                backupCount=Config.LOG_BACKUP_COUNT
            )
            file_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            app.logger.addHandler(file_handler)
            app.logger.setLevel(getattr(logging, Config.LOG_LEVEL))
            app.logger.info('ERP System started')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # Development database (use separate DB for dev)
    MYSQL_DB = os.environ.get('MYSQL_DB_DEV', 'profit_recovery_erp_dev')
    
    # Development settings
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0
    
    # Allow insecure settings in development
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False  # Disable CSRF for development
    
    # Development logging
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    
    # Use in-memory database for testing
    MYSQL_DB = os.environ.get('MYSQL_DB_TEST', 'profit_recovery_erp_test')
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Testing logging
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Production security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    WTF_CSRF_ENABLED = True
    
    # Production logging
    LOG_LEVEL = 'WARNING'
    
    # Production database should use environment variables
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')  # Must be set in production
    MYSQL_DB = os.environ.get('MYSQL_DB', 'profit_recovery_erp')
    
    # Secret key must be set in environment
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    @staticmethod
    def init_app(app):
        """Production-specific initialization"""
        Config.init_app(app)
        
        # Ensure secret key is set in production
        if not app.config['SECRET_KEY']:
            raise ValueError("SECRET_KEY must be set in production environment")
        
        # Log to syslog in production
        import logging
        from logging.handlers import SysLogHandler
        
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)


class StagingConfig(ProductionConfig):
    """Staging configuration (between development and production)"""
    DEBUG = True
    TESTING = False
    
    # Staging security (half-secure)
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = True
    
    # Staging logging
    LOG_LEVEL = 'INFO'
    
    MYSQL_DB = os.environ.get('MYSQL_DB_STAGING', 'profit_recovery_erp_staging')


class DockerConfig(ProductionConfig):
    """Docker container configuration"""
    # Docker-specific settings
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'db')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'erp_user')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'erp_password')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'profit_recovery_erp')
    
    # Docker logging
    LOG_LEVEL = 'INFO'
    
    # Docker file paths
    UPLOAD_FOLDER = '/app/uploads'
    LOG_FILE = '/app/logs/erp.log'


# =====================================================
# CONFIGURATION DICTIONARY
# =====================================================

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'staging': StagingConfig,
    'docker': DockerConfig,
    'default': DevelopmentConfig
}


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def get_config():
    """Get current configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, DevelopmentConfig)


def is_development():
    """Check if running in development mode"""
    return os.environ.get('FLASK_ENV', 'development') == 'development'


def is_production():
    """Check if running in production mode"""
    return os.environ.get('FLASK_ENV', 'development') == 'production'


def get_db_uri():
    """Get database URI from configuration"""
    cfg = get_config()
    return cfg.SQLALCHEMY_DATABASE_URI


def validate_config():
    """Validate configuration settings"""
    errors = []
    warnings = []
    
    # Check required settings in production
    if is_production():
        if not os.environ.get('SECRET_KEY'):
            errors.append("SECRET_KEY environment variable is required in production")
        
        if not os.environ.get('MYSQL_PASSWORD'):
            errors.append("MYSQL_PASSWORD environment variable is required in production")
    
    # Check database connection settings
    cfg = get_config()
    if not cfg.MYSQL_HOST:
        warnings.append("MYSQL_HOST not set, using default 'localhost'")
    
    if not cfg.MYSQL_USER:
        warnings.append("MYSQL_USER not set, using default 'root'")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


# For testing directly
if __name__ == '__main__':
    print("Configuration Validation:")
    validation = validate_config()
    print(f"Valid: {validation['valid']}")
    if validation['errors']:
        print("Errors:")
        for error in validation['errors']:
            print(f"  - {error}")
    if validation['warnings']:
        print("Warnings:")
        for warning in validation['warnings']:
            print(f"  - {warning}")
    
    print("\nCurrent Configuration:")
    cfg = get_config()
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"Database: {cfg.MYSQL_DB} on {cfg.MYSQL_HOST}:{cfg.MYSQL_PORT}")
    print(f"Debug Mode: {cfg.DEBUG}")
    print(f"Log Level: {cfg.LOG_LEVEL}")