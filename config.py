import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # کلید امنیتی (حتماً در Render یک مقدار تصادفی و طولانی برای آن تنظیم کنید)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this-in-production'
    
    # دریافت آدرس دیتابیس از محیط (Render)
    db_url = os.environ.get('DATABASE_URL')
    
    if db_url:
        # رفع مشکل رایج Neon/Render: تبدیل postgres:// به postgresql:// برای سازگاری با SQLAlchemy
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
            
    # اگر DATABASE_URL وجود نداشت (حالت لوکال)، از SQLite استفاده کن
    SQLALCHEMY_DATABASE_URI = db_url or 'sqlite:///' + os.path.join(BASE_DIR, 'notifications.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # تنظیمات حیاتی برای جلوگیری از قطع شدن اتصال در دیتابیس‌های Serverless مثل Neon
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # بررسی سلامت اتصال قبل از استفاده
        "pool_recycle": 300,     # بازسازی اتصال هر 5 دقیقه
    }
