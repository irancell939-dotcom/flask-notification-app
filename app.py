from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, abort, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Notification, Comment, Vehicle, Violation
from config import Config
from datetime import datetime
import jdatetime
import os
import csv
import io

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, instance_relative_config=False)
app.config.from_object(Config)
app.instance_path = os.path.join(BASE_DIR, 'instance')

try:
    os.makedirs(app.instance_path, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create instance folder: {e}")

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
            
            vehicle = Vehicle(
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
            db.session.commit()
            flash('خودرو با موفقیت اضافه شد', 'success')
            return redirect(url_for('vehicles'))
        except Exception as e:
            flash('خطا در ثبت اطلاعات خودرو', 'error')
            
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
            
            db.session.commit()
            flash('اطلاعات خودرو با موفقیت ویرایش شد', 'success')
            return redirect(url_for('vehicle_detail', id=vehicle.id))
        except Exception as e:
            flash('خطا در ویرایش اطلاعات خودرو', 'error')
            
    return render_template('edit_vehicle.html', vehicle=vehicle)

@app.route('/delete_vehicle/<int:id>')
@login_required
def delete_vehicle(id):
    if not current_user.is_admin:
        flash('فقط مدیر می‌تواند خودرو حذف کند', 'error')
        return redirect(url_for('vehicles'))
    
    vehicle = Vehicle.query.get_or_404(id)
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
    
    # BOM برای نمایش صحیح فارسی در اکسل
    output.write('\ufeff')
    
    fieldnames = [
        'plate_1', 'plate_2', 'plate_3', 'plate_4',
        'vehicle_type', 'color', 'driver_name', 'position',
        'student_id', 'major', 'phone', 'parking',
        'validity_date', 'description', 'entrance_gate',
        'referrer', 'archive_location'
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for v in vehicles:
        writer.writerow({
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
            # خواندن محتوا - پشتیبانی از UTF-8 با BOM
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
                    # بررسی فیلدهای اجباری
                    missing = [f for f in required_fields if not row.get(f, '').strip()]
                    if missing:
                        errors.append(f"ردیف {row_num}: فیلدهای اجباری خالی است: {', '.join(missing)}")
                        continue
                    
                    # تبدیل تاریخ شمسی به میلادی
                    validity_date = jdatetime.datetime.strptime(
                        row['validity_date'].strip(), '%Y/%m/%d'
                    ).togregorian().date()
                    
                    vehicle = Vehicle(
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
                for err in errors[:10]:  # نمایش حداکثر ۱ خطا
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
            # اطمینان از غیر دائمی بودن session - با بستن مرورگر پاک می‌شود
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
        db.create_all()  # فقط جداول را می‌سازد، کاربر پیش‌فرض ایجاد نمی‌کند
    app.run(debug=True, host='0.0.0.0', port=5000)
