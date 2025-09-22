# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_bcrypt import Bcrypt
import sqlite3
import os
import cv2
import numpy as np
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import json
from datetime import datetime
import cv2.ximgproc as ximgproc
import requests

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production
bcrypt = Bcrypt(app)

# Database initialization
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create lessons table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_type TEXT NOT NULL,
        title TEXT NOT NULL,
        content_type TEXT NOT NULL,  -- 'letter', 'word', 'sentence', 'translation'
        content TEXT NOT NULL,  -- The actual Tamil content
        order_index INTEGER NOT NULL,
        unlock_threshold INTEGER DEFAULT 0  -- Percentage needed to unlock
    )
    ''')
    
    # Create progress table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        lesson_id INTEGER NOT NULL,
        attempts INTEGER DEFAULT 0,
        successful_attempts INTEGER DEFAULT 0,
        last_accuracy REAL DEFAULT 0,
        highest_accuracy REAL DEFAULT 0,
        last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (lesson_id) REFERENCES lessons (id),
        UNIQUE(user_id, lesson_id)
    )
    ''')
    
    # Safely add the new column if it doesn't exist for current users
    try:
        cursor.execute('ALTER TABLE progress ADD COLUMN highest_accuracy REAL DEFAULT 0')
    except sqlite3.OperationalError:
        pass # Column already exists, do nothing
    
    # Insert default lessons if they don't exist
    cursor.execute("SELECT COUNT(*) FROM lessons")
    if cursor.fetchone()[0] == 0:
        # Uyir Eluthukal (அ – ஔ)
        uyir_letters = ['அ', 'ஆ', 'இ', 'ஈ', 'உ', 'ஊ', 'எ', 'ஏ', 'ஐ', 'ஒ', 'ஓ', 'ஔ']
        for i, letter in enumerate(uyir_letters):
            cursor.execute(
                "INSERT INTO lessons (lesson_type, title, content_type, content, order_index) VALUES (?, ?, ?, ?, ?)",
                ('uyir', f'உயிர் எழுத்து {i+1}', 'letter', letter, i)
            )
        
        # Mei Eluthukal (க் – ன்)
        mei_letters = ['க்', 'ங்', 'ச்', 'ஞ்', 'ட்', 'ண்', 'த்', 'ந்', 'ப்', 'ம்', 'ய்', 'ர்', 'ல்', 'வ்', 'ழ்', 'ள்', 'ற்', 'ன்']
        for i, letter in enumerate(mei_letters):
            cursor.execute(
                "INSERT INTO lessons (lesson_type, title, content_type, content, order_index) VALUES (?, ?, ?, ?, ?)",
                ('mei', f'மெய் எழுத்து {i+1}', 'letter', letter, i + len(uyir_letters))
            )
        
        # Uyir-Mei Eluthukal (க – ன)
        uyirmei_letters = ['க', 'ங', 'ச', 'ஞ', 'ட', 'ண', 'த', 'ந', 'ப', 'ம', 'ய', 'ர', 'ல', 'வ', 'ழ', 'ள', 'ற', 'ன']
        for i, letter in enumerate(uyirmei_letters):
            cursor.execute(
                "INSERT INTO lessons (lesson_type, title, content_type, content, order_index) VALUES (?, ?, ?, ?, ?)",
                ('uyirmei', f'உயிர்மெய் எழுத்து {i+1}', 'letter', letter, i + len(uyir_letters) + len(mei_letters))
            )
        
        # Simple words
        simple_words = ['அம்மா', 'அப்பா', 'தண்ணீர்', 'பள்ளி', 'புத்தகம்', 'வீடு', 'தோட்டம்', 'பூ', 'மரம்', 'பழம்']
        for i, word in enumerate(simple_words):
            cursor.execute(
                "INSERT INTO lessons (lesson_type, title, content_type, content, order_index, unlock_threshold) VALUES (?, ?, ?, ?, ?, ?)",
                ('words', f'எளிய சொல் {i+1}', 'word', word, i + len(uyir_letters) + len(mei_letters) + len(uyirmei_letters), 60)
            )
        
        # Short sentences
        sentences = [
            'அம்மா வீட்டில் உள்ளார்.',
            'நான் பள்ளிக்கு செல்கிறேன்.',
            'அவன் புத்தகம் வாசிக்கிறான்.',
            'நீர் குடிக்கவும்.',
            'பூவை பார்த்தேன்.'
        ]
        for i, sentence in enumerate(sentences):
            cursor.execute(
                "INSERT INTO lessons (lesson_type, title, content_type, content, order_index, unlock_threshold) VALUES (?, ?, ?, ?, ?, ?)",
                ('sentences', f'சிறு வாக்கியம் {i+1}', 'sentence', sentence, i + len(uyir_letters) + len(mei_letters) + len(uyirmei_letters) + len(simple_words), 70)
            )
        
        # English to Tamil translations
        translations = [
            {'en': 'mother', 'ta': 'அம்மா'},
            {'en': 'water', 'ta': 'தண்ணீர்'},
            {'en': 'book', 'ta': 'புத்தகம்'},
            {'en': 'school', 'ta': 'பள்ளி'},
            {'en': 'flower', 'ta': 'பூ'}
        ]
        for i, trans in enumerate(translations):
            cursor.execute(
                "INSERT INTO lessons (lesson_type, title, content_type, content, order_index, unlock_threshold) VALUES (?, ?, ?, ?, ?, ?)",
                ('translations', f'மொழிபெயர்ப்பு {i+1}', 'translation', json.dumps(trans), i + len(uyir_letters) + len(mei_letters) + len(uyirmei_letters) + len(simple_words) + len(sentences), 80)
            )
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/tts')
def tts():
    text = request.args.get('text', '')
    if not text:
        return "No text provided", 400
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={text}&tl=ta&client=tw-ob"
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    return send_file(BytesIO(r.content), mimetype='audio/mpeg')

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if not username or not email or not password:
            return render_template('signup.html', error='All fields are required')
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, hashed_password)
            )
            conn.commit()
            
            cursor.execute("SELECT id FROM lessons")
            lessons = cursor.fetchall()
            user_id = cursor.lastrowid
            
            for lesson in lessons:
                cursor.execute(
                    "INSERT INTO progress (user_id, lesson_id) VALUES (?, ?)",
                    (user_id, lesson['id'])
                )
            conn.commit()
            
            session['user_id'] = user_id
            session['username'] = username
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError:
            return render_template('signup.html', error='Username or email already exists')
        finally:
            conn.close()
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        
        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    progress = conn.execute('''
        SELECT 
            COUNT(*) as total_lessons,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_lessons,
            AVG(CASE WHEN completed = 1 THEN highest_accuracy END) as avg_accuracy
            FROM progress 
            WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()

    # Get difficult lessons
    difficult_lessons = conn.execute('''
        SELECT l.id, l.title, l.content, p.highest_accuracy
        FROM lessons l
        JOIN progress p ON l.id = p.lesson_id
        WHERE p.user_id = ? AND p.attempts > 0 AND p.completed = 0
        ORDER BY p.highest_accuracy ASC
        LIMIT 3
        ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                            username=session.get('username'),
                            total_lessons=progress['total_lessons'] or 0,
                            completed_lessons=progress['completed_lessons'] or 0,
                            avg_accuracy=round((progress['avg_accuracy'] or 0) * 100, 1),
                            difficult_lessons=difficult_lessons)

@app.route('/lessons')
@login_required
def lessons():
    conn = get_db_connection()
    lessons_data_rows = conn.execute('''
        SELECT l.*, p.attempts, p.successful_attempts, p.last_accuracy, p.highest_accuracy, p.completed
        FROM lessons l
        LEFT JOIN progress p ON l.id = p.lesson_id AND p.user_id = ?
        ORDER BY l.order_index
    ''', (session['user_id'],)).fetchall()
    
    lessons_data = [dict(row) for row in lessons_data_rows]

    # Calculate unlock status
    # This logic now depends on highest_accuracy
    for i, lesson in enumerate(lessons_data):
        if lesson['unlock_threshold'] == 0:
            lesson['unlocked'] = True
        else:
            # Check if all previous lessons are completed with sufficient accuracy
            unlocked = True
            for prev_lesson in lessons_data[:i]:
                # A lesson must be completed to count towards unlocking the next one
                if not prev_lesson['completed']:
                    unlocked = False
                    break
            lesson['unlocked'] = unlocked
    
    conn.close()
    return render_template('lessons.html', lessons=lessons_data)

@app.route('/lesson/<int:lesson_id>')
@login_required
def lesson_detail(lesson_id):
    conn = get_db_connection()
    lesson = conn.execute('''
        SELECT l.*, p.attempts, p.successful_attempts, p.last_accuracy, p.highest_accuracy, p.completed
        FROM lessons l
        LEFT JOIN progress p ON l.id = p.lesson_id AND p.user_id = ?
        WHERE l.id = ?
    ''', (session['user_id'], lesson_id)).fetchone()
    
    if not lesson:
        conn.close()
        return "Lesson not found", 404
    
    # Simplified unlock check for direct access
    if lesson['order_index'] > 0:
        prev_lesson_progress = conn.execute('''
            SELECT p.completed FROM progress p
            JOIN lessons l ON p.lesson_id = l.id
            WHERE p.user_id = ? AND l.order_index < ?
            ORDER BY l.order_index DESC
        ''', (session['user_id'], lesson['order_index'])).fetchall()
        
        is_locked = any(not p['completed'] for p in prev_lesson_progress)
        if is_locked and lesson['unlock_threshold'] > 0:
            return "Lesson is locked. Complete previous lessons first.", 403

    if lesson['content_type'] == 'translation':
        content = json.loads(lesson['content'])
    else:
        content = lesson['content']
    
    next_lesson_row = conn.execute('''
        SELECT id FROM lessons
        WHERE order_index > ?
        ORDER BY order_index ASC
        LIMIT 1
    ''', (lesson['order_index'],)).fetchone()
    next_lesson_id = next_lesson_row['id'] if next_lesson_row else None
    
    conn.close()
    return render_template('lesson.html', lesson=lesson, content=content, next_lesson_id=next_lesson_id)

@app.route('/api/submit_attempt/<int:lesson_id>', methods=['POST'])
@login_required
def submit_attempt(lesson_id):
    conn = None
    try:
        data = request.get_json()
        image_data = data['image'].split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        user_image = Image.open(BytesIO(image_bytes))
        
        conn = get_db_connection()
        lesson = conn.execute("SELECT content, content_type FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        
        if not lesson:
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404
            
        expected_content = lesson['content']
        if lesson['content_type'] == 'translation':
            expected_content = json.loads(lesson['content'])['ta']
        
        is_correct, accuracy = evaluate_drawing(user_image, expected_content)
        
        accuracy_val = float(accuracy) / 100.0
        
        conn.execute('''
            UPDATE progress 
            SET attempts = attempts + 1,
                successful_attempts = successful_attempts + ?,
                last_accuracy = ?,
                highest_accuracy = MAX(highest_accuracy, ?),
                last_attempt = CURRENT_TIMESTAMP,
                completed = CASE WHEN completed = 1 THEN 1 ELSE ? END
            WHERE user_id = ? AND lesson_id = ?
        ''', (1 if is_correct else 0, accuracy_val, accuracy_val, 1 if is_correct else 0, session['user_id'], lesson_id))
        
        conn.commit()
        
        feedback = "சரி! நீங்கள் சரியாக எழுதியுள்ளீர்கள்." if is_correct else "மீண்டும் முயற்சிக்கவும். உங்கள் எழுத்து சற்று வித்தியாசமாக உள்ளது."
        
        return jsonify({
            'success': True,
            'correct': bool(is_correct),
            'accuracy': float(accuracy),
            'feedback': feedback
        })
    
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f"A server error occurred: {str(e)}"
        }), 500
    finally:
        if conn:
            conn.close()

def evaluate_drawing(user_image, expected_text, font_path="static/fonts/NotoSansTamil-Regular.ttf", size=(600, 300)):
    """
    Evaluates a user's drawing using a two-way check for a more robust and fair score.
    1. Precision: Measures how close the user's strokes are to the template path.
    2. Completeness: Measures if the user has drawn all parts of the template path.
    """
    # --- 1. Preprocess the User's Drawing ---
    user_img_np = np.array(user_image)
    if user_img_np.shape[2] < 4: return False, 0.0
    alpha_channel = user_img_np[:, :, 3]
    _, user_bin = cv2.threshold(alpha_channel, 10, 255, cv2.THRESH_BINARY)
    coords = cv2.findNonZero(user_bin)
    if coords is None: return False, 0.0
    x, y, w, h = cv2.boundingRect(coords)
    user_bin_cropped = user_bin[y:y+h, x:x+w]
    target_size = 256
    square_canvas = np.zeros((target_size, target_size), dtype=np.uint8)
    scale = 0.9 * target_size / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized_drawing = cv2.resize(user_bin_cropped, (new_w, new_h), interpolation=cv2.INTER_AREA)
    paste_x = (target_size - new_w) // 2
    paste_y = (target_size - new_h) // 2
    square_canvas[paste_y:paste_y+new_h, paste_x:paste_x+new_w] = resized_drawing
    user_drawing_final = square_canvas
    
    # --- 2. Create the Template and its Skeleton ---
    template_img = Image.new("L", (target_size, target_size), 0)
    draw = ImageDraw.Draw(template_img)
    try:
        font_size = int(target_size * 1.2)
        font = ImageFont.truetype(font_path, font_size)
        while font.getbbox(expected_text)[2] > target_size * 0.9 or font.getbbox(expected_text)[3] > target_size * 0.9:
            font_size -= 2
            font = ImageFont.truetype(font_path, font_size)
    except IOError: font = ImageFont.load_default()
    text_bbox = draw.textbbox((0, 0), expected_text, font=font)
    text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    pos = ((target_size - text_width) // 2, (target_size - text_height) // 2 - text_bbox[1])
    draw.text(pos, expected_text, fill=255, font=font)
    template_bin = np.array(template_img)
    template_skeleton = ximgproc.thinning(template_bin)

    # --- 3. Two-Way Distance Calculation ---
    template_dist_map = cv2.distanceTransform(cv2.bitwise_not(template_skeleton), cv2.DIST_L2, 3)
    user_pixels = cv2.findNonZero(user_drawing_final)
    if user_pixels is None: return False, 0.0
    
    total_precision_dist = sum(template_dist_map[y, x] for p in user_pixels for x, y in p)
    avg_precision_dist = total_precision_dist / len(user_pixels)

    user_dist_map = cv2.distanceTransform(cv2.bitwise_not(user_drawing_final), cv2.DIST_L2, 3)
    template_pixels = cv2.findNonZero(template_skeleton)
    if template_pixels is None: return False, 0.0
    
    total_completeness_dist = sum(user_dist_map[y, x] for p in template_pixels for x, y in p)
    avg_completeness_dist = total_completeness_dist / len(template_pixels)
    
    # --- 4. Combined Scoring ---
    max_dist = 0.10 * target_size

    precision_penalty = min(avg_precision_dist / max_dist, 1.0)
    completeness_penalty = min(avg_completeness_dist / max_dist, 1.0)

    precision_score = 1.0 - precision_penalty
    completeness_score = 1.0 - completeness_penalty

    final_score = np.sqrt(precision_score * completeness_score)
    
    accuracy_percent = round(final_score * 100, 1)
    is_correct = accuracy_percent >= 50.0

    return is_correct, accuracy_percent

if __name__ == '__main__':
    app.run(debug=True)
