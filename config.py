import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'flask-notification-secret-key-2026'
    
    # پشتیبانی از Neon (PostgreSQL) و SQLite
    db_url = os.environ.get('DATABASE_URL')
    
    if db_url:
        # تبدیل postgres:// به postgresql:// برای سازگاری با SQLAlchemy
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        # حالت لوکال: SQLite
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'notifications.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # تنظیمات حیاتی برای Neon (جلوگیری از قطع اتصال)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    
    # محدودیت آپلود فایل (2 مگابایت برای آپلود اولیه)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    
    # مسیر پوشه آپلود عکس‌ها
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'vehicles')
    
    # تنظیمات Session
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = True
