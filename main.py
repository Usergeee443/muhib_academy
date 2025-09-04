import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import pymysql
from config import Config
import requests
from datetime import datetime
import json

app = Flask(__name__)
app.config.from_object(Config)

# File upload configuration
UPLOAD_FOLDER = 'static/images/courses'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Til ma'lumotlarini yuklash
def load_translations():
    translations = {}
    languages = ['uz', 'ru', 'en']
    
    for lang in languages:
        try:
            with open(f'translations/{lang}.json', 'r', encoding='utf-8') as f:
                translations[lang] = json.load(f)
        except FileNotFoundError:
            # Agar fayl topilmasa, standart qiymatlar
            translations[lang] = {}
    
    return translations

def get_current_language():
    return session.get('language', 'uz')

def get_translation(key, lang=None):
    if lang is None:
        lang = get_current_language()
    translations = load_translations()
    return translations.get(lang, {}).get(key, key)

# Template funksiyasini global qilish
@app.context_processor
def utility_processor():
    return dict(get_translation=get_translation, current_lang=get_current_language)

def get_db_connection():
    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            charset='utf8mb4'
        )
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE {Config.DB_NAME}")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title_uz VARCHAR(255) NOT NULL,
                title_ru VARCHAR(255),
                title_en VARCHAR(255),
                description_uz TEXT NOT NULL,
                description_ru TEXT,
                description_en TEXT,
                duration_uz VARCHAR(100) NOT NULL,
                duration_ru VARCHAR(100),
                duration_en VARCHAR(100),
                price_uz VARCHAR(100) NOT NULL,
                price_ru VARCHAR(100),
                price_en VARCHAR(100),
                start_date_uz VARCHAR(100) NOT NULL,
                start_date_ru VARCHAR(100),
                start_date_en VARCHAR(100),
                features_uz TEXT,
                features_ru TEXT,
                features_en TEXT,
                image_path VARCHAR(255),
                color VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        admin_password = generate_password_hash('admin123')
        cursor.execute('INSERT IGNORE INTO admins (username, password_hash) VALUES (%s, %s)', ('admin', admin_password))

        # Database migration - image_path ustunini qo'shish
        try:
            cursor.execute("ALTER TABLE courses ADD COLUMN image_path VARCHAR(255) AFTER features_en")
            print("image_path ustuni qo'shildi!")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("image_path ustuni allaqachon mavjud!")
            else:
                print(f"Migration xatoligi: {e}")

        cursor.execute('SELECT COUNT(*) FROM courses')
        courses_count = cursor.fetchone()[0]
        if courses_count == 0:
            default_courses = [
                ('Qur\'on o\'qish', 'Чтение Корана', 'Quran Reading', 
                 'Qur\'on o\'qishni 0 dan boshlab o\'rganing', 'Изучите чтение Корана с нуля', 'Learn Quran reading from scratch',
                 '6 oy', '6 месяцев', '6 months',
                 '500,000 so\'m', '500,000 сум', '500,000 UZS',
                 '15 Yanvar', '15 Январь', '15 January',
                 'Tajvid qoidalari, Nozil tarixi, Xat turlari', 'Правила таджвида, История ниспослания, Виды письма', 'Tajweed rules, Revelation history, Writing styles',
                 'static/images/courses/quran.jpg', 'from-islamic-green to-islamic-blue'),
                
                ('Arab tili', 'Арабский язык', 'Arabic Language',
                 'Arab tilini amaliy va nazariy jihatdan o\'rganing', 'Изучите арабский язык практично и теоретично', 'Learn Arabic language practically and theoretically',
                 '8 oy', '8 месяцев', '8 months',
                 '600,000 so\'m', '600,000 сум', '600,000 UZS',
                 '20 Yanvar', '20 Январь', '20 January',
                 'Grammatika, Nutq, Yozish, O\'qish', 'Грамматика, Речь, Письмо, Чтение', 'Grammar, Speaking, Writing, Reading',
                 'static/images/courses/arabic.jpg', 'from-islamic-gold to-orange-500'),
                
                ('Islom asoslari', 'Основы ислама', 'Islamic Fundamentals',
                 'Islom dinining asoslari va tarixi', 'Основы и история исламской религии', 'Fundamentals and history of Islamic religion',
                 '4 oy', '4 месяца', '4 months',
                 '400,000 so\'m', '400,000 сум', '400,000 UZS',
                 '25 Yanvar', '25 Январь', '25 January',
                 'Aqida, Ibadat, Axloq, Tarix', 'Акида, Ибадат, Ахляк, История', 'Aqeedah, Worship, Ethics, History',
                 'static/images/courses/islamic.jpg', 'from-islamic-purple to-purple-600')
            ]
            
            for course in default_courses:
                cursor.execute('''
                    INSERT INTO courses
                    (title_uz, title_ru, title_en, description_uz, description_ru, description_en,
                     duration_uz, duration_ru, duration_en, price_uz, price_ru, price_en,
                     start_date_uz, start_date_ru, start_date_en, features_uz, features_ru, features_en, image_path, color)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', course)
            print("Standart kurslar qo'shildi!")
        else:
            print("Kurslar allaqachon mavjud!")
        connection.commit()
        cursor.close()
        connection.close()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database initialization error: {e}")

def send_telegram_message(message):
    try:
        if Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHAT_ID:
            url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": Config.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data)
            return response.status_code == 200
    except Exception as e:
        print(f"Telegram message error: {e}")
    return False

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/set_language/<language>')
def set_language(language):
    if language in ['uz', 'ru', 'en']:
        session['language'] = language
    return redirect(request.referrer or url_for('home'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/enroll')
def enroll():
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database bilan bog\'lanishda xatolik yuz berdi', 'error')
            return render_template('enroll.html', courses=[])
        
        cursor = conn.cursor()
        cursor.execute('SELECT id, title_uz, title_ru, title_en, description_uz, description_ru, description_en, image_path FROM courses ORDER BY created_at DESC')
        courses = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('enroll.html', courses=courses)
    except Exception as e:
        print(f"Error in enroll: {e}")
        flash('Ma\'lumotlarni yuklashda xatolik yuz berdi', 'error')
        return render_template('enroll.html', courses=[])

@app.route('/enroll', methods=['POST'])
def enroll_post():
    try:
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        course_id = request.form.get('course_id')
        preferred_time = request.form.get('preferred_time')
        message = request.form.get('message')
        
        # Get course details
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('SELECT title_uz FROM courses WHERE id = %s', (course_id,))
            course = cursor.fetchone()
            cursor.close()
            conn.close()
            
            course_name = course['title_uz'] if course else 'Noma\'lum kurs'
        else:
            course_name = 'Noma\'lum kurs'
        
        # Send to Telegram
        telegram_message = f"""
🎓 <b>Yangi ro'yxatdan o'tish!</b>

👤 <b>Ism:</b> {full_name}
📱 <b>Telefon:</b> {phone}
📧 <b>Email:</b> {email}
📚 <b>Kurs:</b> {course_name}
⏰ <b>Vaqt:</b> {preferred_time}
💬 <b>Xabar:</b> {message}

📅 <b>Sana:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}
        """
        
        send_telegram_message(telegram_message)
        
        flash('Arizangiz muvaffaqiyatli yuborildi! Tez orada siz bilan bog\'lanamiz.', 'success')
        return redirect(url_for('enroll'))
        
    except Exception as e:
        print(f"Enrollment error: {e}")
        flash('Arizani yuborishda xatolik yuz berdi. Iltimos, qaytadan urinib ko\'ring.', 'error')
        return redirect(url_for('enroll'))

@app.route('/online-courses')
def online_courses():
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database bilan bog\'lanishda xatolik yuz berdi', 'error')
            return render_template('online_courses.html', courses=[])
        
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM courses ORDER BY created_at DESC')
        courses = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('online_courses.html', courses=courses)
    except Exception as e:
        print(f"Error in online_courses: {e}")
        flash('Kurslarni yuklashda xatolik yuz berdi', 'error')
        return render_template('online_courses.html', courses=[])

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database bilan bog\'lanishda xatolik yuz berdi', 'error')
            return redirect(url_for('online_courses'))
        
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM courses WHERE id = %s', (course_id,))
        course = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not course:
            flash('Kurs topilmadi', 'error')
            return redirect(url_for('online_courses'))
        
        return render_template('course_detail.html', course=course)
    except Exception as e:
        print(f"Error in course_detail: {e}")
        flash('Kurs ma\'lumotlarini yuklashda xatolik yuz berdi', 'error')
        return redirect(url_for('online_courses'))

@app.route('/admin')
def admin():
    if 'admin_logged_in' in session:
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/login.html')

@app.route('/admin/login', methods=['POST'])
def admin_login_post():
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if conn is None:
            flash('Database bilan bog\'lanishda xatolik yuz berdi', 'error')
            return redirect(url_for('admin'))
        
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM admins WHERE username = %s', (username,))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Muvaffaqiyatli kirildi!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Noto\'g\'ri login yoki parol!', 'error')
            return redirect(url_for('admin'))
            
    except Exception as e:
        print(f"Admin login error: {e}")
        flash('Kirishda xatolik yuz berdi', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('Tizimdan chiqildi', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database bilan bog\'lanishda xatolik yuz berdi', 'error')
            return render_template('admin/dashboard.html', courses=[])
        
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM courses ORDER BY created_at DESC')
        courses = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('admin/dashboard.html', courses=courses)
    except Exception as e:
        print(f"Error in admin_dashboard: {e}")
        flash('Kurslarni yuklashda xatolik yuz berdi', 'error')
        return render_template('admin/dashboard.html', courses=[])

@app.route('/admin/course/add', methods=['GET', 'POST'])
@admin_required
def admin_add_course():
    if request.method == 'POST':
        try:
            # Get form data
            title_uz = request.form.get('title_uz')
            title_ru = request.form.get('title_ru')
            title_en = request.form.get('title_en')
            description_uz = request.form.get('description_uz')
            description_ru = request.form.get('description_ru')
            description_en = request.form.get('description_en')
            duration_uz = request.form.get('duration_uz')
            duration_ru = request.form.get('duration_ru')
            duration_en = request.form.get('duration_en')
            price_uz = request.form.get('price_uz')
            price_ru = request.form.get('price_ru')
            price_en = request.form.get('price_en')
            start_date_uz = request.form.get('start_date_uz')
            start_date_ru = request.form.get('start_date_ru')
            start_date_en = request.form.get('start_date_en')
            features_uz = request.form.get('features_uz')
            features_ru = request.form.get('features_ru')
            features_en = request.form.get('features_en')
            color = request.form.get('color')
            
            # Handle image upload
            image_path = None
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Add timestamp to avoid conflicts
                    name, ext = os.path.splitext(filename)
                    filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    image_path = f"static/images/courses/{filename}"
            
            conn = get_db_connection()
            if conn is None:
                flash('Database bilan bog\'lanishda xatolik yuz berdi', 'error')
                return redirect(url_for('admin_add_course'))
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO courses
                (title_uz, title_ru, title_en, description_uz, description_ru, description_en,
                 duration_uz, duration_ru, duration_en, price_uz, price_ru, price_en,
                 start_date_uz, start_date_ru, start_date_en, features_uz, features_ru, features_en, image_path, color)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (title_uz, title_ru, title_en, description_uz, description_ru, description_en,
                  duration_uz, duration_ru, duration_en, price_uz, price_ru, price_en,
                  start_date_uz, start_date_ru, start_date_en, features_uz, features_ru, features_en, image_path, color))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash('Kurs muvaffaqiyatli qo\'shildi!', 'success')
            return redirect(url_for('admin_dashboard'))
            
        except Exception as e:
            print(f"Add course error: {e}")
            flash('Kurs qo\'shishda xatolik yuz berdi', 'error')
            return redirect(url_for('admin_add_course'))
    
    return render_template('admin/add_course.html')

@app.route('/admin/course/edit/<int:course_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_course(course_id):
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database bilan bog\'lanishda xatolik yuz berdi', 'error')
            return redirect(url_for('admin_dashboard'))
        
        if request.method == 'POST':
            # Get form data
            title_uz = request.form.get('title_uz')
            title_ru = request.form.get('title_ru')
            title_en = request.form.get('title_en')
            description_uz = request.form.get('description_uz')
            description_ru = request.form.get('description_ru')
            description_en = request.form.get('description_en')
            duration_uz = request.form.get('duration_uz')
            duration_ru = request.form.get('duration_ru')
            duration_en = request.form.get('duration_en')
            price_uz = request.form.get('price_uz')
            price_ru = request.form.get('price_ru')
            price_en = request.form.get('price_en')
            start_date_uz = request.form.get('start_date_uz')
            start_date_ru = request.form.get('start_date_ru')
            start_date_en = request.form.get('start_date_en')
            features_uz = request.form.get('features_uz')
            features_ru = request.form.get('features_ru')
            features_en = request.form.get('features_en')
            color = request.form.get('color')
            
            # Handle image upload
            image_path = None
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Add timestamp to avoid conflicts
                    name, ext = os.path.splitext(filename)
                    filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    image_path = f"static/images/courses/{filename}"
            
            cursor = conn.cursor()
            if image_path:
                cursor.execute('''
                    UPDATE courses SET
                    title_uz = %s, title_ru = %s, title_en = %s,
                    description_uz = %s, description_ru = %s, description_en = %s,
                    duration_uz = %s, duration_ru = %s, duration_en = %s,
                    price_uz = %s, price_ru = %s, price_en = %s,
                    start_date_uz = %s, start_date_ru = %s, start_date_en = %s,
                    features_uz = %s, features_ru = %s, features_en = %s,
                    image_path = %s, color = %s
                    WHERE id = %s
                ''', (title_uz, title_ru, title_en, description_uz, description_ru, description_en,
                      duration_uz, duration_ru, duration_en, price_uz, price_ru, price_en,
                      start_date_uz, start_date_ru, start_date_en, features_uz, features_ru, features_en,
                      image_path, color, course_id))
            else:
                cursor.execute('''
                    UPDATE courses SET
                    title_uz = %s, title_ru = %s, title_en = %s,
                    description_uz = %s, description_ru = %s, description_en = %s,
                    duration_uz = %s, duration_ru = %s, duration_en = %s,
                    price_uz = %s, price_ru = %s, price_en = %s,
                    start_date_uz = %s, start_date_ru = %s, start_date_en = %s,
                    features_uz = %s, features_ru = %s, features_en = %s,
                    color = %s
                    WHERE id = %s
                ''', (title_uz, title_ru, title_en, description_uz, description_ru, description_en,
                      duration_uz, duration_ru, duration_en, price_uz, price_ru, price_en,
                      start_date_uz, start_date_ru, start_date_en, features_uz, features_ru, features_en,
                      color, course_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash('Kurs muvaffaqiyatli yangilandi!', 'success')
            return redirect(url_for('admin_dashboard'))
        
        # GET request - show edit form
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM courses WHERE id = %s', (course_id,))
        course = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not course:
            flash('Kurs topilmadi', 'error')
            return redirect(url_for('admin_dashboard'))
        
        return render_template('admin/edit_course.html', course=course)
        
    except Exception as e:
        print(f"Edit course error: {e}")
        flash('Kursni tahrirlashda xatolik yuz berdi', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/course/delete/<int:course_id>')
@admin_required
def admin_delete_course(course_id):
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database bilan bog\'lanishda xatolik yuz berdi', 'error')
            return redirect(url_for('admin_dashboard'))
        
        cursor = conn.cursor()
        cursor.execute('DELETE FROM courses WHERE id = %s', (course_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Kurs muvaffaqiyatli o\'chirildi!', 'success')
        return redirect(url_for('admin_dashboard'))
        
    except Exception as e:
        print(f"Delete course error: {e}")
        flash('Kursni o\'chirishda xatolik yuz berdi', 'error')
        return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)