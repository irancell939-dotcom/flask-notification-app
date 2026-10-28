import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this-in-production'
    
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = db_url or 'sqlite:///' + os.path.join(BASE_DIR, 'notifications.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    
    # ========== تنظیمات Session برای Logout خودکار ==========
    # Session غیر دائمی - با بستن مرورگر پاک می‌شود
    SESSION_PERMANENT = False
    
    # اگر کاربر تا ۳۰ دقیقه فعالیتی نداشت، خودکار خارج می‌شود
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    
    # امنیت کوکی‌ها
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = True  # در Render (HTTPS) حتماً True باشد
