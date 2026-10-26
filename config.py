import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this'
    # استفاده از دیتابیس Supabase اگر در Render باشد، در غیر این صورت SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(BASE_DIR, 'notifications.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
