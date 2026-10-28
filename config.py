import os

# مسیر پایه پروژه
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'flask-notification-secret-key-2026'
    
    # مسیر دیتابیس (پشتیبانی همزمان از Neon و SQLite لوکال)
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'notifications.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # تنظیمات حیاتی برای جلوگیری از قطع اتصال در دیتابیس‌های Serverless مثل Neon
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    
    # ========== تنظیمات آپلود فایل ==========
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'vehicles')
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # حداکثر حجم آپلود ۲ مگابایت
