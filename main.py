from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_from_directory
import mysql.connector
import os
import requests
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import uuid
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

# Upload konfiguratsiyasi
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_COURSES = 15

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Upload papkasini yaratish
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# MySQL konfiguratsiyasi
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

# Admin hisobini yaratish va jadvallarni yaratish
def create_admin_account():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Admin jadvali mavjudligini tekshirish
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INT PRIMARY KEY AUTO_INCREMENT,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Kategoriyalar jadvalini yaratish
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kategoriyalar (
                id INT PRIMARY KEY AUTO_INCREMENT,
                nom VARCHAR(100) UNIQUE NOT NULL,
                yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Default kategoriyalarni qo'shish
        cursor.execute("SELECT COUNT(*) FROM kategoriyalar")
        cat_count = cursor.fetchone()[0]
        
        if cat_count == 0:
            cursor.execute("INSERT INTO kategoriyalar (nom) VALUES ('Online')")
            cursor.execute("INSERT INTO kategoriyalar (nom) VALUES ('Offline')")
            cursor.execute("INSERT INTO kategoriyalar (nom) VALUES ('Hybrid')")
            cursor.execute("INSERT INTO kategoriyalar (nom) VALUES ('Intensiv')")
            print("Default kategoriyalar yaratildi: Online, Offline, Hybrid, Intensiv")
        
        # Kurslar jadvalini yangilash (kategoriya qo'shish)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kurslar (
                id INT PRIMARY KEY AUTO_INCREMENT,
                nom VARCHAR(255) NOT NULL,
                tafsif TEXT,
                davomiyligi VARCHAR(100),
                darslar_soni INT,
                narx DECIMAL(10,2),
                rasm_url VARCHAR(500),
                kategoriya_id INT,
                active TINYINT DEFAULT 1,
                yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                yangilangan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (kategoriya_id) REFERENCES kategoriyalar(id)
            )
        """)
        
        # Agar kategoriya_id ustuni mavjud bo'lmasa, qo'shish
        try:
            cursor.execute("ALTER TABLE kurslar ADD COLUMN kategoriya_id INT")
            cursor.execute("ALTER TABLE kurslar ADD FOREIGN KEY (kategoriya_id) REFERENCES kategoriyalar(id)")
            # Barcha mavjud kurslarni Online kategoriyasiga o'rnatish
            cursor.execute("UPDATE kurslar SET kategoriya_id = 1 WHERE kategoriya_id IS NULL")
        except:
            pass  # Ustun allaqachon mavjud
        
        # Admin mavjudligini tekshirish
        cursor.execute("SELECT COUNT(*) FROM admins")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Default admin yaratish
            admin_username = "admin"
            admin_password = "admin123"  # Buni o'zgartiring!
            password_hash = generate_password_hash(admin_password)
            
            cursor.execute(
                "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
                (admin_username, password_hash)
            )
            conn.commit()
            print(f"Admin yaratildi: {admin_username} / {admin_password}")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Admin yaratishda xato: {e}")

# Kategoriyalarni tekshirish va qo'shish funksiyasi
def check_and_create_categories():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Kategoriyalar sonini tekshirish
        cursor.execute("SELECT COUNT(*) FROM kategoriyalar")
        cat_count = cursor.fetchone()[0]
        
        if cat_count == 0:
            # Default kategoriyalarni qo'shish
            default_categories = ['Online', 'Offline', 'Hybrid', 'Intensiv']
            for category in default_categories:
                cursor.execute("INSERT INTO kategoriyalar (nom) VALUES (%s)", (category,))
            
            conn.commit()
            print(f"Kategoriyalar yaratildi: {', '.join(default_categories)}")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Kategoriyalarni tekshirishda xato: {e}")

# Fayl uzatmasini tekshirish
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Admin login tekshirish decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Telegram bot orqali xabar yuborish
def send_telegram_message(message):
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        return None
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, data=data)
        return response.json()
    except Exception as e:
        print(f"Telegram xabar yuborishda xato: {e}")
        return None

# Main routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/courses')
def get_courses():
    try:
        kategoriya = request.args.get('kategoriya')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT k.id, k.nom, k.davomiyligi, k.darslar_soni, k.narx, k.rasm_url, 
                   kat.nom as kategoriya
            FROM kurslar k
            LEFT JOIN kategoriyalar kat ON k.kategoriya_id = kat.id
            WHERE k.active = 1
        """
        params = []
        
        if kategoriya and kategoriya != 'all':
            query += " AND kat.nom = %s"
            params.append(kategoriya)
        
        query += " ORDER BY k.yaratilgan_sana DESC"
        
        cursor.execute(query, params)
        courses = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify(courses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/kategoriyalar')
def get_kategoriyalar():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM kategoriyalar ORDER BY nom")
        kategoriyalar = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify(kategoriyalar)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT k.*, kat.nom as kategoriya
            FROM kurslar k
            LEFT JOIN kategoriyalar kat ON k.kategoriya_id = kat.id
            WHERE k.id = %s AND k.active = 1
        """, (course_id,))
        
        course = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if course:
            return render_template('course_detail.html', course=course)
        else:
            flash('Kurs topilmadi', 'error')
            return redirect(url_for('index'))
    except Exception as e:
        flash('Xato yuz berdi', 'error')
        return redirect(url_for('index'))

@app.route('/api/register', methods=['POST'])
def register_course():
    try:
        data = request.json
        
        # Ma'lumotlarni tekshirish
        required_fields = ['ism', 'telefon', 'kurs_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} majburiy maydon'}), 400
        
        # Kurs ma'lumotlarini olish
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT k.nom, kat.nom as kategoriya
            FROM kurslar k
            LEFT JOIN kategoriyalar kat ON k.kategoriya_id = kat.id
            WHERE k.id = %s AND k.active = 1
        """, (data['kurs_id'],))
        course = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not course:
            return jsonify({'error': 'Kurs topilmadi'}), 404
        
        # Telegram orqali xabar yuborish
        message = f"""
🎓 <b>Yangi kursga yozilish!</b>

👤 <b>Ism:</b> {data['ism']}
📞 <b>Telefon:</b> {data['telefon']}
📚 <b>Kurs:</b> {course['nom']}
📍 <b>Kategoriya:</b> {course['kategoriya']}
📅 <b>Sana:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}
        """
        
        send_telegram_message(message)
        return jsonify({'success': True, 'message': 'Muvaffaqiyatli ro\'yxatdan o\'tdingiz!'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Admin routes
@app.route('/admin')
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

@app.route('/admin/login', methods=['POST'])
def admin_login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        flash('Username va parol kiritish majburiy', 'error')
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
        admin = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            flash('Muvaffaqiyatli kirildi!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Noto\'g\'ri username yoki parol', 'error')
            return redirect(url_for('admin_login'))
    
    except Exception as e:
        flash('Login qilishda xato yuz berdi', 'error')
        return redirect(url_for('admin_login'))

@app.route('/admin/logout')
@admin_required
def admin_logout():
    session.clear()
    flash('Tizimdan chiqildi', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    try:
        # Kategoriyalarni tekshirish
        check_and_create_categories()
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Kurslar sonini hisoblash
        cursor.execute("SELECT COUNT(*) as total FROM kurslar WHERE active = 1")
        total_courses = cursor.fetchone()['total']
        
        # Barcha kurslarni olish
        cursor.execute("""
            SELECT k.*, kat.nom as kategoriya
            FROM kurslar k
            LEFT JOIN kategoriyalar kat ON k.kategoriya_id = kat.id
            WHERE k.active = 1 
            ORDER BY k.yaratilgan_sana DESC
        """)
        courses = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('admin_dashboard.html', 
                             courses=courses, 
                             total_courses=total_courses,
                             max_courses=MAX_COURSES)
    
    except Exception as e:
        flash('Ma\'lumotlarni yuklashda xato', 'error')
        return render_template('admin_dashboard.html', courses=[], total_courses=0, max_courses=MAX_COURSES)

@app.route('/admin/course/add', methods=['GET', 'POST'])
@admin_required
def admin_add_course():
    if request.method == 'GET':
        # Kurslar sonini tekshirish
        try:
            # Kategoriyalarni tekshirish
            check_and_create_categories()
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) FROM kurslar WHERE active = 1")
            count = cursor.fetchone()['COUNT(*)']
            
            # Kategoriyalarni olish
            cursor.execute("SELECT * FROM kategoriyalar ORDER BY nom")
            kategoriyalar = cursor.fetchall()
            
            # Debug uchun kategoriyalarni chop etish
            print(f"Kategoriyalar soni: {len(kategoriyalar)}")
            for kat in kategoriyalar:
                print(f"Kategoriya: {kat}")
            
            cursor.close()
            conn.close()
            
            if count >= MAX_COURSES:
                flash(f'Maksimal {MAX_COURSES} ta kurs yaratish mumkin!', 'error')
                return redirect(url_for('admin_dashboard'))
                
            return render_template('admin_add_course.html', kategoriyalar=kategoriyalar)
        except Exception as e:
            flash('Xato yuz berdi', 'error')
            return redirect(url_for('admin_dashboard'))
    
    try:
        # Kurslar sonini tekshirish
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) FROM kurslar WHERE active = 1")
        count = cursor.fetchone()['COUNT(*)']
        
        if count >= MAX_COURSES:
            cursor.close()
            conn.close()
            flash(f'Maksimal {MAX_COURSES} ta kurs yaratish mumkin!', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Admin parolini tekshirish
        admin_password = request.form.get('admin_password')
        if not admin_password:
            flash('Admin paroli majburiy!', 'error')
            return redirect(url_for('admin_add_course'))
        
        # Joriy adminning parolini tekshirish
        cursor.execute("SELECT password_hash FROM admins WHERE id = %s", (session['admin_id'],))
        admin = cursor.fetchone()
        
        if not admin or not check_password_hash(admin['password_hash'], admin_password):
            cursor.close()
            conn.close()
            flash('Noto\'g\'ri admin paroli!', 'error')
            return redirect(url_for('admin_add_course'))
        
        # Form ma'lumotlarini olish
        nom = request.form.get('nom')
        tafsif = request.form.get('tafsif')
        davomiyligi = request.form.get('davomiyligi')
        darslar_soni = request.form.get('darslar_soni')
        narx = request.form.get('narx')
        kategoriya_id = request.form.get('kategoriya_id')
        
        # Majburiy maydonlarni tekshirish
        if not all([nom, tafsif, davomiyligi, darslar_soni, narx, kategoriya_id]):
            flash('Barcha majburiy maydonlarni to\'ldirish kerak!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_add_course'))
        
        # Kategoriya mavjudligini tekshirish
        cursor.execute("SELECT id FROM kategoriyalar WHERE id = %s", (kategoriya_id,))
        if not cursor.fetchone():
            flash('Noto\'g\'ri kategoriya tanlandi!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_add_course'))
        
        # Rasm yuklash
        rasm_url = ''
        if 'rasm' in request.files:
            file = request.files['rasm']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Unique filename yaratish
                file_ext = filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                rasm_url = f'/static/uploads/{unique_filename}'
        
        # Ma'lumotlar bazasiga qo'shish
        cursor.execute("""
            INSERT INTO kurslar (nom, tafsif, davomiyligi, darslar_soni, narx, rasm_url, kategoriya_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (nom, tafsif, davomiyligi, int(darslar_soni), float(narx), rasm_url, int(kategoriya_id)))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Kurs muvaffaqiyatli qo\'shildi!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    except ValueError as e:
        flash('Noto\'g\'ri ma\'lumot kiritildi! Raqamlarni to\'g\'ri kiriting.', 'error')
        return redirect(url_for('admin_add_course'))
    except Exception as e:
        flash('Kurs qo\'shishda xato yuz berdi!', 'error')
        return redirect(url_for('admin_add_course'))

@app.route('/admin/course/edit/<int:course_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_course(course_id):
    if request.method == 'GET':
        try:
            # Kategoriyalarni tekshirish
            check_and_create_categories()
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM kurslar WHERE id = %s AND active = 1", (course_id,))
            course = cursor.fetchone()
            
            cursor.execute("SELECT * FROM kategoriyalar ORDER BY nom")
            kategoriyalar = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            if not course:
                flash('Kurs topilmadi', 'error')
                return redirect(url_for('admin_dashboard'))
            
            return render_template('admin_edit_course.html', course=course, kategoriyalar=kategoriyalar)
        except Exception as e:
            flash('Kurs ma\'lumotlarini yuklashda xato', 'error')
            return redirect(url_for('admin_dashboard'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Admin parolini tekshirish
        admin_password = request.form.get('admin_password')
        if not admin_password:
            flash('Admin paroli majburiy!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_edit_course', course_id=course_id))
        
        # Joriy adminning parolini tekshirish
        cursor.execute("SELECT password_hash FROM admins WHERE id = %s", (session['admin_id'],))
        admin = cursor.fetchone()
        
        if not admin or not check_password_hash(admin['password_hash'], admin_password):
            cursor.close()
            conn.close()
            flash('Noto\'g\'ri admin paroli!', 'error')
            return redirect(url_for('admin_edit_course', course_id=course_id))
        
        # Form ma'lumotlarini olish
        nom = request.form.get('nom')
        tafsif = request.form.get('tafsif')
        davomiyligi = request.form.get('davomiyligi')
        darslar_soni = request.form.get('darslar_soni')
        narx = request.form.get('narx')
        kategoriya_id = request.form.get('kategoriya_id')
        
        # Majburiy maydonlarni tekshirish
        if not all([nom, tafsif, davomiyligi, darslar_soni, narx, kategoriya_id]):
            flash('Barcha majburiy maydonlarni to\'ldirish kerak!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_edit_course', course_id=course_id))
        
        # Kategoriya mavjudliginix tekshirish
        cursor.execute("SELECT id FROM kategoriyalar WHERE id = %s", (kategoriya_id,))
        if not cursor.fetchone():
            flash('Noto\'g\'ri kategoriya tanlandi!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_edit_course', course_id=course_id))
        
        # Kurs mavjudligini tekshirish
        cursor.execute("SELECT rasm_url FROM kurslar WHERE id = %s AND active = 1", (course_id,))
        old_course = cursor.fetchone()
        
        if not old_course:
            flash('Kurs topilmadi', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_dashboard'))
        
        rasm_url = old_course['rasm_url']
        
        # Yangi rasm yuklash
        if 'rasm' in request.files:
            file = request.files['rasm']
            if file and file.filename != '' and allowed_file(file.filename):
                # Eski rasmni o'chirish
                if rasm_url and rasm_url.startswith('/static/uploads/'):
                    old_file_path = rasm_url[1:]  # '/' ni olib tashlash
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                
                # Yangi rasmni saqlash
                filename = secure_filename(file.filename)
                file_ext = filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                rasm_url = f'/static/uploads/{unique_filename}'
        
        # Ma'lumotlarni yangilash
        cursor.execute("""
            UPDATE kurslar 
            SET nom = %s, tafsif = %s, davomiyligi = %s, darslar_soni = %s, narx = %s, rasm_url = %s,
                kategoriya_id = %s, yangilangan_sana = CURRENT_TIMESTAMP
            WHERE id = %s AND active = 1
        """, (nom, tafsif, davomiyligi, int(darslar_soni), float(narx), rasm_url, int(kategoriya_id), course_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Kurs muvaffaqiyatli yangilandi!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    except ValueError as e:
        flash('Noto\'g\'ri ma\'lumot kiritildi! Raqamlarni to\'g\'ri kiriting.', 'error')
        return redirect(url_for('admin_edit_course', course_id=course_id))
    except Exception as e:
        flash('Kurs yangilashda xato yuz berdi!', 'error')
        return redirect(url_for('admin_edit_course', course_id=course_id))
        
@app.route('/admin/course/delete/<int:course_id>', methods=['POST'])
@admin_required
def admin_delete_course(course_id):
    try:
        # JSON ma'lumotlarini olish
        data = request.get_json()
        admin_password = data.get('admin_password') if data else None
        
        if not admin_password:
            return jsonify({'error': 'Admin paroli majburiy!', 'success': False}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Admin parolini tekshirish
        cursor.execute("SELECT password_hash FROM admins WHERE id = %s", (session['admin_id'],))
        admin = cursor.fetchone()
        
        if not admin or not check_password_hash(admin['password_hash'], admin_password):
            cursor.close()
            conn.close()
            return jsonify({'error': 'Noto\'g\'ri admin paroli!', 'success': False}), 401
        
        # Kurs ma'lumotlarini olish
        cursor.execute("SELECT rasm_url FROM kurslar WHERE id = %s AND active = 1", (course_id,))
        course = cursor.fetchone()
        
        if not course:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Kurs topilmadi!', 'success': False}), 404
        
        # Rasmni o'chirish
        if course['rasm_url'] and course['rasm_url'].startswith('/static/uploads/'):
            file_path = course['rasm_url'][1:]  # '/' ni olib tashlash
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass  # Fayl o'chirilmasa ham davom etamiz
        
        # Kursni o'chirish (soft delete)
        cursor.execute("UPDATE kurslar SET active = 0 WHERE id = %s", (course_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Kurs muvaffaqiyatli o\'chirildi!'})
    
    except Exception as e:
        return jsonify({'error': 'Kurs o\'chirishda xato yuz berdi!', 'success': False}), 500

# Eski GET method bilan delete ham qoldiramiz (backward compatibility uchun)
@app.route('/admin/course/delete/<int:course_id>')
@admin_required
def admin_delete_course_get(course_id):
    # Bu method endi faqat dashboard'ga redirect qiladi
    flash('Kurs o\'chirish uchun parol talab qilinadi', 'error')
    return redirect(url_for('admin_dashboard'))

# Static files serve (development uchun)
@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    create_admin_account()
    app.run(debug=True)