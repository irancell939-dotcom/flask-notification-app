from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import jdatetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    can_add_notification = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.username

    def get_iso_created(self):
        if self.created_at:
            return self.created_at.isoformat() + 'Z'
        return ''


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    is_archived = db.Column(db.Boolean, default=False)
    is_important = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    comments = db.relationship('Comment', backref='notification', lazy=True, cascade="all, delete-orphan")

    def is_expired(self):
        today = jdatetime.date.today()
        expiry = jdatetime.date.fromgregorian(date=self.expiry_date)
        return today > expiry

    def get_shamsi_expiry(self):
        return jdatetime.date.fromgregorian(date=self.expiry_date).strftime('%Y/%m/%d')

    def get_iso_created(self):
        if self.created_at:
            return self.created_at.isoformat() + 'Z'
        return ''


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey('notification.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', backref='comments')

    def get_iso_created(self):
        if self.created_at:
            return self.created_at.isoformat() + 'Z'
        return ''


class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # فیلدهای جدید
    national_id = db.Column(db.String(10), unique=True, nullable=True)
    dormitory_status = db.Column(db.String(50), nullable=True)
    photo_path = db.Column(db.String(200), nullable=True)
    
    plate_1 = db.Column(db.String(2), nullable=False)
    plate_2 = db.Column(db.String(1), nullable=False)
    plate_3 = db.Column(db.String(3), nullable=False)
    plate_4 = db.Column(db.String(2), nullable=False)
    vehicle_type = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    driver_name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100), nullable=True)
    student_id = db.Column(db.String(50), nullable=True)
    major = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    parking = db.Column(db.String(50), nullable=True)
    validity_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    entrance_gate = db.Column(db.String(100), nullable=True)
    referrer = db.Column(db.String(100), nullable=True)
    archive_location = db.Column(db.String(100), nullable=True)

    violations = db.relationship('Violation', backref='vehicle', lazy=True, cascade="all, delete-orphan")

    def get_shamsi_validity(self):
        return jdatetime.date.fromgregorian(date=self.validity_date).strftime('%Y/%m/%d')

    def get_iso_created(self):
        if self.created_at:
            return self.created_at.isoformat() + 'Z'
        return ''

    def is_expired(self):
        today = jdatetime.date.today()
        validity = jdatetime.date.fromgregorian(date=self.validity_date)
        return today > validity

    @property
    def full_plate(self):
        return f"{self.plate_1} {self.plate_2} {self.plate_3} - {self.plate_4}"

    @property
    def violations_count(self):
        return len(self.violations)


class Violation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reporter = db.relationship('User', backref='violations_reported')

    def get_iso_created(self):
        if self.created_at:
            return self.created_at.isoformat() + 'Z'
        return ''
