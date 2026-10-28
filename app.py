from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, abort, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Notification, Comment, Vehicle, Violation
from config import Config
from datetime import datetime, timedelta
import jdatetime
import os
import csv
import io
from werkzeug.utils import secure_filename
from PIL import Image

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, instance_relative_config=False)
app.config.from_object(Config)
app.instance_path = os.path.join(BASE_DIR, 'instance')

# ایجاد پوشه‌های لازم
try:
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create folders: {e}")

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_now():
    return {'datetime': datetime}

@app.context_processor
def inject_db_size():
    """محاسبه حجم دیتابیس برای نمایش به مدیر"""
    db_size = None
    if current_user.is_authenticated and current_user.is_admin:
        try:
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if 'sqlite' in db_uri:
                db_path = db_uri.replace('sqlite:///', '')
                if db_path.startswith('/'):
                    db_path = db_path[1:]
                if os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    if size_bytes < 1024:
                        db_size = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        db_size = f"{size_bytes / 1024:.2f} KB"
                    elif size_bytes < 1024 * 1024 * 1024:
                        db_size = f"{size_bytes / (1024 * 1024):.2f} MB"
                    else:
                        db_size = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
            elif 'postgresql' in db_uri or 'postgres' in db_uri:
                from sqlalchemy import text
                with db.engine.connect() as conn:
                    result = conn.execute(text("SELECT pg_database_size(current_database())"))
                    size_bytes = result.scalar()
                    if size_bytes < 1024:
                        db_size = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        db_size = f"{size_bytes / 1024:.2f} KB"
                    elif size_bytes < 1024 * 1024 * 1024:
                        db_size = f"{size_bytes / (1024 * 1024):.2f} MB"
                    else:
                        db_size = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
        except Exception as e:
            db_size = "خطا"
    return {'db_size': db_size}

def allowed_file(filename):
    """بررسی فرمت مجاز فایل"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def compress_image(file, max_size_kb=25):
    """
    فشرده‌سازی خودکار عکس تا رسیدن به کمترین حد قابل نمایش (پیش‌فرض 25 کیلوبایت)
    """
    try:
        # ۱. باز کردن عکس
        img = Image.open(file)
        
        # ۲. تبدیل به RGB (حذف کانال شفافیت برای کاهش حجم)
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        
        # ۳. کوچک کردن ابعاد (حداکثر ۳۰۰ پیکسل برای هر طرف)
        max_dimension = 300
        if img.width > max_dimension or img.height > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        
        output = io.BytesIO()
        quality = 50  # شروع با کیفیت متوسط
        
        # ۴. حلقه فشرده‌سازی تا رسیدن به حجم هدف
        while quality > 20:  # کیفیت را پایین‌تر از ۲۰ نبر چون تصویر خراب می‌شود
            output.seek(0)
            output.truncate()
            
            # ذخیره به فرمت JPEG با بهینه‌سازی
            img.save(output, format='JPEG', quality=quality, optimize=True)
            
            size_kb = output.tell() / 1024
            
            if size_kb <= max_size_kb:
                break
            
            quality -= 10  # کاهش پله‌ای کیفیت
        
        # ۵. اگر هنوز حجم بالا بود، ابعاد را باز هم کوچک‌تر کن
        if size_kb > max_size_kb:
            scale = 0.7
            while size_kb > max_size_kb and scale > 0.4:
                new_size = (int(img.width * scale), int(img.height * scale))
                img_resized = img.resize(new_size, Image.Resampling.LANCZOS)
                
                output.seek(0)
                output.truncate()
                img_resized.save(output, format='JPEG', quality=30, optimize=True)
                
                size_kb = output.tell() / 1024
                scale -= 0.1
        
        output.seek(0)
        return output
        
    except Exception as e:
        print(f"خطا در فشرده‌سازی عکس: {e}")
        return None

def save_vehicle_photo(file, national_id):
    """ذخیره عکس خودرو با فشرده‌سازی حداکثری"""
    if file and allowed_file(file.filename):
        # فراخوانی تابع فشرده‌سازی با هدف ۵ کیلوبایت
        compressed_image = compress_image(file, max_size_kb=25)
        
        if compressed_image:
            filename = f"{national_id}.jpg"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            with open(filepath, 'wb') as f:
                f.write(compressed_image.read())
            
            return f"uploads/vehicles/{filename}"
        else:
            # اگر خطا داد، عکس اصلی را با فرمت jpg ذخیره کن
            filename = f"{national_id}.jpg"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.seek(0)
            # تبدیل ساده در صورت شکست فشرده‌سازی
            img = Image.open(file).convert('RGB')
            img.save(filepath, format='JPEG', quality=50, optimize=True)
            return f"uploads/vehicles/{filename}"
    return None

@app.route('/uploads/vehicles/<filename>')
def uploaded_file(filename):
    """سرویس‌دهی فایل‌های آپلود شده"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ========== اطلاعیه‌ها ==========
@app.route('/')
@login_required
def index():
    notifications = Notification.query.filter(
        Notification.is_archived == False,
        Notification.is_approved == True
    ).order_by(Notification.created_at.desc()).all()
    active_notifications = [n for n in notifications if not n.is_expired()]
    return render_template('index.html', notifications=active_notifications)

@app.route('/pending')
@login_required
def pending_notifications():
    if not current_user.is_admin:
        flash('شما دسترسی ندارید', 'error')
        return redirect(url_for('index'))
    pending = Notification.query.filter(
        Notification.is_approved == False,
        Notification.is_archived == False
    ).order_by(Notification.created_at.desc()).all()
    return render_template('pending.html', notifications=pending)

@app.route('/approve/<int:item_id>')
@login_required
def approve_item(item_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    notification = Notification.query.get_or_404(item_id)
    notification.is_approved = True
    db.session.commit()
    flash('اطلاعیه تایید و منتشر شد', 'success')
    return redirect(url_for('pending_notifications'))

@app.route('/archive')
@login_required
def archive():
    notifications = Notification.query.filter(
        (Notification.is_archived == True) |
        (Notification.expiry_date < datetime.now().date())
    ).order_by(Notification.created_at.desc()).all()
    return render_template('archive.html', notifications=notifications)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_item():
    if not current_user.is_admin and not current_user.can_add_notification:
        flash('شما دسترسی به درج اطلاعیه جدید ندارید', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        expiry_date_str = request.form.get('expiry_date')
        is_important = 'is_important' in request.form
        
        if not all([title, description, expiry_date_str]):
            flash('لطفاً تمام فیلدها را پر کنید', 'error')
            return redirect(url_for('add_item'))
        
        try:
            expiry_date = jdatetime.datetime.strptime(expiry_date_str, '%Y/%m/%d').togregorian().date()
            is_approved = current_user.is_admin
            notification = Notification(
                title=title, description=description, expiry_date=expiry_date,
                created_by=current_user.id, is_important=is_important,
                is_approved=is_approved
            )
            db.session.add(notification)
            db.session.commit()
            if current_user.is_admin:
                flash('اطلاعیه با موفقیت منتشر شد', 'success')
            else:
                flash('اطلاعیه ثبت شد و پس از تایید مدیر نمایش داده می‌شود', 'info')
            return redirect(url_for('index'))
        except Exception as e:
            flash('خطا در ثبت اطلاعیه', 'error')
            
    return render_template('add_item.html')

@app.route('/view/<int:item_id>')
@login_required
def view_item(item_id):
    notification = Notification.query.get_or_404(item_id)
    return render_template('view_item.html', notification=notification)

@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند اطلاعیه را ویرایش کند', 'error')
        return redirect(url_for('index'))
    
    notification = Notification.query.get_or_404(item_id)
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        expiry_date_str = request.form.get('expiry_date')
        is_important = 'is_important' in request.form
        
        if not all([title, description, expiry_date_str]):
            flash('لطفاً تمام فیلدها را پر کنید', 'error')
            return redirect(url_for('edit_item', item_id=item_id))
        
        try:
            notification.title = title
            notification.description = description
            notification.expiry_date = jdatetime.datetime.strptime(expiry_date_str, '%Y/%m/%d').togregorian().date()
            notification.is_important = is_important
            db.session.commit()
            flash('اطلاعیه با موفقیت ویرایش شد', 'success')
            ref = request.referrer or ''
            if 'pending' in ref:
                return redirect(url_for('pending_notifications'))
            return redirect(url_for('index'))
        except Exception as e:
            flash('خطا در ویرایش اطلاعیه', 'error')
            
    return render_template('edit_item.html', notification=notification)

@app.route('/delete/<int:item_id>')
@login_required
def delete_item(item_id):
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند اطلاعیه را حذف کند', 'error')
        return redirect(url_for('index'))
    
    notification = Notification.query.get_or_404(item_id)
    db.session.delete(notification)
    db.session.commit()
    flash('اطلاعیه حذف شد', 'success')
    return redirect(url_for('index'))

@app.route('/toggle_important/<int:item_id>')
@login_required
def toggle_important(item_id):
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند اهمیت اطلاعیه را تغییر دهد', 'error')
        return redirect(url_for('index'))
    
    notification = Notification.query.get_or_404(item_id)
    notification.is_important = not notification.is_important
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/archive_item/<int:item_id>')
@login_required
def archive_item(item_id):
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند اطلاعیه را بایگانی کند', 'error')
        return redirect(url_for('index'))
    
    notification = Notification.query.get_or_404(item_id)
    notification.is_archived = True
    db.session.commit()
    flash('اطلاعیه بایگانی شد', 'success')
    return redirect(url_for('index'))

# ========== کامنت‌ها ==========
@app.route('/comment/add/<int:item_id>', methods=['POST'])
@login_required
def add_comment(item_id):
    text = request.form.get('text')
    if text:
        comment = Comment(notification_id=item_id, user_id=current_user.id, text=text)
        db.session.add(comment)
        db.session.commit()
        flash('نظر شما با موفقیت ثبت شد', 'success')
    return redirect(url_for('view_item', item_id=item_id))

@app.route('/comment/delete/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if current_user.is_admin or comment.user_id == current_user.id:
        db.session.delete(comment)
        db.session.commit()
        flash('نظر حذف شد', 'success')
    return redirect(url_for('view_item', item_id=comment.notification_id))

# ========== خودروها ==========
@app.route('/vehicles')
@login_required
def vehicles():
    plate_1 = request.args.get('plate_1', '').strip()
    plate_2 = request.args.get('plate_2', '').strip()
    plate_3 = request.args.get('plate_3', '').strip()
    plate_4 = request.args.get('plate_4', '').strip()
    driver_search = request.args.get('driver', '').strip()
    filter_type = request.args.get('filter', '').strip()
    
    all_vehicles = Vehicle.query.order_by(Vehicle.created_at.desc()).all()
    
    # محاسبه آمار کلی
    total = len(all_vehicles)
    active_count = len([v for v in all_vehicles if not v.is_expired()])
    expired_count = len([v for v in all_vehicles if v.is_expired()])
    violation_count = len([v for v in all_vehicles if v.violations_count > 0])
    
    # اعمال فیلتر مدیر
    if filter_type and current_user.is_admin:
        if filter_type == 'active':
            filtered = [v for v in all_vehicles if not v.is_expired()]
        elif filter_type == 'expired':
            filtered = [v for v in all_vehicles if v.is_expired()]
        elif filter_type == 'violation':
            filtered = [v for v in all_vehicles if v.violations_count > 0]
        else:
            filtered = all_vehicles
    else:
        filtered = all_vehicles
        filter_type = ''
    
    # اعمال فیلتر جستجو
    if plate_1:
        filtered = [v for v in filtered if plate_1 in v.plate_1]
    if plate_2:
        filtered = [v for v in filtered if plate_2 in v.plate_2]
    if plate_3:
        filtered = [v for v in filtered if plate_3 in v.plate_3]
    if plate_4:
        filtered = [v for v in filtered if plate_4 in v.plate_4]
    if driver_search:
        filtered = [v for v in filtered if driver_search.lower() in v.driver_name.lower()]
    
    return render_template('vehicle_list.html',
                           vehicles=filtered,
                           total_vehicles=total,
                           active_count=active_count,
                           expired_count=expired_count,
                           violation_count=violation_count,
                           active_filter=filter_type,
                           plate_1=plate_1, plate_2=plate_2,
                           plate_3=plate_3, plate_4=plate_4,
                           driver_search=driver_search)

@app.route('/live_search_driver')
@login_required
def live_search_driver():
    query = request.args.get('q', '').strip()
    if not query:
        vehicles = Vehicle.query.order_by(Vehicle.created_at.desc()).all()
    else:
        vehicles = Vehicle.query.filter(
            Vehicle.driver_name.ilike(f'%{query}%')
        ).order_by(Vehicle.created_at.desc()).all()
    
    html = render_template('vehicle_cards_partial.html', vehicles=vehicles)
    return jsonify({'html': html})

@app.route('/vehicle/<int:id>')
@login_required
def vehicle_detail(id):
    vehicle = Vehicle.query.get_or_404(id)
    return render_template('vehicle_detail.html', vehicle=vehicle)

@app.route('/add_vehicle', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند خودرو اضافه کند', 'error')
        return redirect(url_for('vehicles'))
    
    if request.method == 'POST':
        try:
            validity_date = jdatetime.datetime.strptime(
                request.form.get('validity_date'), '%Y/%m/%d'
            ).togregorian().date()
            
            national_id = request.form.get('national_id', '').strip()
            
            if national_id and Vehicle.query.filter_by(national_id=national_id).first():
                flash('این شماره ملی قبلاً ثبت شده است', 'error')
                return redirect(url_for('add_vehicle'))
            
            vehicle = Vehicle(
                national_id=national_id or None,
                dormitory_status=request.form.get('dormitory_status', '').strip() or None,
                plate_1=request.form.get('plate_1'),
                plate_2=request.form.get('plate_2'),
                plate_3=request.form.get('plate_3'),
                plate_4=request.form.get('plate_4'),
                vehicle_type=request.form.get('vehicle_type'),
                color=request.form.get('color'),
                driver_name=request.form.get('driver_name'),
                position=request.form.get('position'),
                student_id=request.form.get('student_id'),
                major=request.form.get('major'),
                phone=request.form.get('phone'),
                parking=request.form.get('parking'),
                validity_date=validity_date,
                description=request.form.get('description'),
                entrance_gate=request.form.get('entrance_gate'),
                referrer=request.form.get('referrer'),
                archive_location=request.form.get('archive_location')
            )
            db.session.add(vehicle)
            db.session.flush()
            
            # آپلود و فشرده‌سازی عکس
            photo = request.files.get('photo')
            if photo and photo.filename and national_id:
                photo_path = save_vehicle_photo(photo, national_id)
                if photo_path:
                    vehicle.photo_path = photo_path
            
            db.session.commit()
            flash('خودرو با موفقیت اضافه شد', 'success')
            return redirect(url_for('vehicles'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطا در ثبت اطلاعات خودرو: {str(e)}', 'error')
            
    return render_template('add_vehicle.html')

@app.route('/edit_vehicle/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_vehicle(id):
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند خودرو را ویرایش کند', 'error')
        return redirect(url_for('vehicles'))
    
    vehicle = Vehicle.query.get_or_404(id)
    if request.method == 'POST':
        try:
            validity_date = jdatetime.datetime.strptime(
                request.form.get('validity_date'), '%Y/%m/%d'
            ).togregorian().date()
            
            new_national_id = request.form.get('national_id', '').strip()
            
            if new_national_id:
                existing = Vehicle.query.filter_by(national_id=new_national_id).first()
                if existing and existing.id != vehicle.id:
                    flash('این شماره ملی قبلاً برای خودروی دیگری ثبت شده است', 'error')
                    return redirect(url_for('edit_vehicle', id=vehicle.id))
            
            vehicle.national_id = new_national_id or None
            vehicle.dormitory_status = request.form.get('dormitory_status', '').strip() or None
            vehicle.plate_1 = request.form.get('plate_1')
            vehicle.plate_2 = request.form.get('plate_2')
            vehicle.plate_3 = request.form.get('plate_3')
            vehicle.plate_4 = request.form.get('plate_4')
            vehicle.vehicle_type = request.form.get('vehicle_type')
            vehicle.color = request.form.get('color')
            vehicle.driver_name = request.form.get('driver_name')
            vehicle.position = request.form.get('position')
            vehicle.student_id = request.form.get('student_id')
            vehicle.major = request.form.get('major')
            vehicle.phone = request.form.get('phone')
            vehicle.parking = request.form.get('parking')
            vehicle.validity_date = validity_date
            vehicle.description = request.form.get('description')
            vehicle.entrance_gate = request.form.get('entrance_gate')
            vehicle.referrer = request.form.get('referrer')
            vehicle.archive_location = request.form.get('archive_location')
            
            # آپلود عکس جدید
            photo = request.files.get('photo')
            if photo and photo.filename:
                # حذف عکس قبلی
                if vehicle.photo_path:
                    old_path = os.path.join(BASE_DIR, vehicle.photo_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # ذخیره عکس جدید
                national_id = vehicle.national_id or str(vehicle.id)
                photo_path = save_vehicle_photo(photo, national_id)
                if photo_path:
                    vehicle.photo_path = photo_path
            
            db.session.commit()
            flash('اطلاعات خودرو با موفقیت ویرایش شد', 'success')
            return redirect(url_for('vehicle_detail', id=vehicle.id))
        except Exception as e:
            db.session.rollback()
            flash(f'خطا در ویرایش اطلاعات خودرو: {str(e)}', 'error')
            
    return render_template('edit_vehicle.html', vehicle=vehicle)

@app.route('/delete_vehicle/<int:id>')
@login_required
def delete_vehicle(id):
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند خودرو حذف کند', 'error')
        return redirect(url_for('vehicles'))
    
    vehicle = Vehicle.query.get_or_404(id)
    
    # حذف عکس خودرو
    if vehicle.photo_path:
        photo_full_path = os.path.join(BASE_DIR, vehicle.photo_path)
        if os.path.exists(photo_full_path):
            os.remove(photo_full_path)
    
    db.session.delete(vehicle)
    db.session.commit()
    flash('خودرو حذف شد', 'success')
    return redirect(url_for('vehicles'))

# ========== Import/Export خودرو با اکسل ==========
@app.route('/vehicles/export_excel')
@login_required
def export_vehicles_excel():
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند فایل اکسل دریافت کند', 'error')
        return redirect(url_for('vehicles'))
    
    vehicles = Vehicle.query.order_by(Vehicle.created_at.desc()).all()
    output = io.StringIO()
    output.write('\ufeff')
    
    fieldnames = [
        'national_id', 'plate_1', 'plate_2', 'plate_3', 'plate_4',
        'vehicle_type', 'color', 'driver_name', 'position',
        'student_id', 'major', 'phone', 'parking',
        'validity_date', 'dormitory_status', 'description', 'entrance_gate',
        'referrer', 'archive_location'
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for v in vehicles:
        writer.writerow({
            'national_id': v.national_id or '',
            'plate_1': v.plate_1,
            'plate_2': v.plate_2,
            'plate_3': v.plate_3,
            'plate_4': v.plate_4,
            'vehicle_type': v.vehicle_type,
            'color': v.color,
            'driver_name': v.driver_name,
            'position': v.position or '',
            'student_id': v.student_id or '',
            'major': v.major or '',
            'phone': v.phone,
            'parking': v.parking or '',
            'validity_date': v.get_shamsi_validity(),
            'dormitory_status': v.dormitory_status or '',
            'description': v.description or '',
            'entrance_gate': v.entrance_gate or '',
            'referrer': v.referrer or '',
            'archive_location': v.archive_location or ''
        })
    
    filename = f"vehicles_template_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@app.route('/vehicles/import_excel', methods=['GET', 'POST'])
@login_required
def import_vehicles_excel():
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند فایل اکسل بارگذاری کند', 'error')
        return redirect(url_for('vehicles'))
    
    if request.method == 'POST':
        file = request.files.get('excel_file')
        if not file or file.filename == '':
            flash('لطفاً یک فایل انتخاب کنید', 'error')
            return redirect(url_for('import_vehicles_excel'))
        
        if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
            flash('فقط فایل‌های CSV یا Excel مجاز هستند', 'error')
            return redirect(url_for('import_vehicles_excel'))
        
        try:
            content = file.stream.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content))
            
            added = 0
            errors = []
            row_num = 1
            
            required_fields = ['plate_1', 'plate_2', 'plate_3', 'plate_4', 
                             'vehicle_type', 'color', 'driver_name', 'phone', 'validity_date']
            
            for row in reader:
                row_num += 1
                try:
                    missing = [f for f in required_fields if not row.get(f, '').strip()]
                    if missing:
                        errors.append(f"ردیف {row_num}: فیلدهای اجباری خالی است: {', '.join(missing)}")
                        continue
                    
                    validity_date = jdatetime.datetime.strptime(
                        row['validity_date'].strip(), '%Y/%m/%d'
                    ).togregorian().date()
                    
                    national_id = row.get('national_id', '').strip() or None
                    
                    if national_id and Vehicle.query.filter_by(national_id=national_id).first():
                        errors.append(f"ردیف {row_num}: شماره ملی {national_id} تکراری است")
                        continue
                    
                    vehicle = Vehicle(
                        national_id=national_id,
                        dormitory_status=row.get('dormitory_status', '').strip() or None,
                        plate_1=row['plate_1'].strip(),
                        plate_2=row['plate_2'].strip(),
                        plate_3=row['plate_3'].strip(),
                        plate_4=row['plate_4'].strip(),
                        vehicle_type=row['vehicle_type'].strip(),
                        color=row['color'].strip(),
                        driver_name=row['driver_name'].strip(),
                        position=row.get('position', '').strip() or None,
                        student_id=row.get('student_id', '').strip() or None,
                        major=row.get('major', '').strip() or None,
                        phone=row['phone'].strip(),
                        parking=row.get('parking', '').strip() or None,
                        validity_date=validity_date,
                        description=row.get('description', '').strip() or None,
                        entrance_gate=row.get('entrance_gate', '').strip() or None,
                        referrer=row.get('referrer', '').strip() or None,
                        archive_location=row.get('archive_location', '').strip() or None
                    )
                    db.session.add(vehicle)
                    added += 1
                except ValueError as e:
                    errors.append(f"ردیف {row_num}: تاریخ نامعتبر (فرمت صحیح: 1403/01/15)")
                except Exception as e:
                    errors.append(f"ردیف {row_num}: خطا - {str(e)}")
            
            if added > 0:
                db.session.commit()
                flash(f'{added} خودرو با موفقیت اضافه شد', 'success')
            
            if errors:
                for err in errors[:10]:
                    flash(err, 'error')
                if len(errors) > 10:
                    flash(f'... و {len(errors) - 10} خطای دیگر', 'error')
            
            if added == 0 and errors:
                return redirect(url_for('import_vehicles_excel'))
            
            return redirect(url_for('vehicles'))
            
        except UnicodeDecodeError:
            flash('فایل باید با فرمت UTF-8 ذخیره شده باشد. در اکسل: Save As → CSV UTF-8', 'error')
            return redirect(url_for('import_vehicles_excel'))
        except Exception as e:
            flash(f'خطا در خواندن فایل: {str(e)}', 'error')
            return redirect(url_for('import_vehicles_excel'))
    
    return render_template('import_vehicles.html')

# ========== تخلفات ==========
@app.route('/violation/add/<int:vehicle_id>', methods=['POST'])
@login_required
def add_violation(vehicle_id):
    description = request.form.get('description', '').strip()
    if not description:
        flash('لطفاً شرح تخلف را وارد کنید', 'error')
        return redirect(url_for('vehicle_detail', id=vehicle_id))
    
    violation = Violation(
        vehicle_id=vehicle_id,
        user_id=current_user.id,
        description=description
    )
    db.session.add(violation)
    db.session.commit()
    flash('تخلف با موفقیت ثبت شد', 'success')
    return redirect(url_for('vehicle_detail', id=vehicle_id))

@app.route('/violation/delete/<int:violation_id>')
@login_required
def delete_violation(violation_id):
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند تخلف را حذف کند', 'error')
        return redirect(url_for('index'))
    
    violation = Violation.query.get_or_404(violation_id)
    vehicle_id = violation.vehicle_id
    db.session.delete(violation)
    db.session.commit()
    flash('تخلف حذف شد', 'success')
    return redirect(url_for('vehicle_detail', id=vehicle_id))

# ========== احراز هویت ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            session.permanent = False
            return redirect(url_for('index'))
        flash('نام کاربری یا رمز عبور اشتباه است', 'error')
        
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ========== مدیریت کاربران ==========
@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if not current_user.is_admin:
        flash('شما دسترسی ندارید', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            username = request.form.get('username')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            password = request.form.get('password')
            is_admin = 'is_admin' in request.form
            can_add = 'can_add_notification' in request.form
            
            if User.query.filter_by(username=username).first():
                flash('این نام کاربری قبلاً وجود دارد', 'error')
            else:
                user = User(
                    username=username, first_name=first_name, last_name=last_name,
                    is_admin=is_admin, can_add_notification=can_add
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash('کاربر جدید اضافه شد', 'success')
                
        elif action == 'update':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                user.first_name = request.form.get('first_name')
                user.last_name = request.form.get('last_name')
                user.is_admin = 'is_admin' in request.form
                user.can_add_notification = 'can_add_notification' in request.form
                new_password = request.form.get('new_password')
                if new_password:
                    user.set_password(new_password)
                db.session.commit()
                flash('اطلاعات کاربر بروزرسانی شد', 'success')
                
        elif action == 'delete':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user and user.id != current_user.id:
                db.session.delete(user)
                db.session.commit()
                flash('کاربر حذف شد', 'success')
            else:
                flash('نمی‌توانید کاربر فعلی را حذف کنید', 'error')
                
    users = User.query.all()
    return render_template('manage_users.html', users=users)

# ========== راه‌اندازی ==========
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
