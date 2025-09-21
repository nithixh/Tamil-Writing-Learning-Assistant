# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_bcrypt import Bcrypt
import sqlite3
import os
import cv2
import numpy as np
import base64
import io
from PIL import Image
import json
from datetime import datetime

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
        last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (lesson_id) REFERENCES lessons (id),
        UNIQUE(user_id, lesson_id)
    )
    ''')
    
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
        
        # Uyir-Mei Eluthukal (க – ஹ)
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

# Helper function for database operations
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Authentication middleware
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
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
            
            # Create empty progress records for all lessons
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
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
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
    cursor = conn.cursor()
    
    # Get user progress
    cursor.execute('''
    SELECT 
        COUNT(*) as total_lessons,
        SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_lessons,
        AVG(CASE WHEN completed = 1 THEN last_accuracy END) as avg_accuracy
    FROM progress 
    WHERE user_id = ?
    ''', (session['user_id'],))
    
    progress = cursor.fetchone()
    conn.close()
    
    total_lessons = progress['total_lessons'] or 0
    completed_lessons = progress['completed_lessons'] or 0
    avg_accuracy = round((progress['avg_accuracy'] or 0) * 100, 1)
    
    return render_template('dashboard.html', 
                         username=session['username'],
                         total_lessons=total_lessons,
                         completed_lessons=completed_lessons,
                         avg_accuracy=avg_accuracy)

@app.route('/lessons')
@login_required
def lessons():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all lessons with user progress
    cursor.execute('''
    SELECT l.*, p.attempts, p.successful_attempts, p.last_accuracy, p.completed
    FROM lessons l
    LEFT JOIN progress p ON l.id = p.lesson_id AND p.user_id = ?
    ORDER BY l.order_index
    ''', (session['user_id'],))
    
    lessons_data = cursor.fetchall()
    
    # Calculate unlock status
    lessons_with_status = []
    for lesson in lessons_data:
        lesson_dict = dict(lesson)
        
        # Check if previous lessons are completed enough to unlock this one
        if lesson['order_index'] == 0:
            lesson_dict['unlocked'] = True
        else:
            # Check unlock threshold
            cursor.execute('''
            SELECT AVG(last_accuracy) as prev_avg_accuracy
            FROM progress p
            JOIN lessons l ON p.lesson_id = l.id
            WHERE p.user_id = ? AND l.order_index < ?
            ''', (session['user_id'], lesson['order_index']))
            
            prev_avg = cursor.fetchone()['prev_avg_accuracy'] or 0
            lesson_dict['unlocked'] = prev_avg * 100 >= lesson['unlock_threshold']
        
        lessons_with_status.append(lesson_dict)
    
    conn.close()
    
    return render_template('lessons.html', lessons=lessons_with_status)

@app.route('/lesson/<int:lesson_id>')
@login_required
def lesson_detail(lesson_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get lesson details
    cursor.execute('''
    SELECT l.*, p.attempts, p.successful_attempts, p.last_accuracy, p.completed
    FROM lessons l
    LEFT JOIN progress p ON l.id = p.lesson_id AND p.user_id = ?
    WHERE l.id = ?
    ''', (session['user_id'], lesson_id))
    
    lesson = cursor.fetchone()
    
    if not lesson:
        conn.close()
        return "Lesson not found", 404
    
    # Check if lesson is unlocked
    if lesson['order_index'] > 0:
        cursor.execute('''
        SELECT AVG(last_accuracy) as prev_avg_accuracy
        FROM progress p
        JOIN lessons l ON p.lesson_id = l.id
        WHERE p.user_id = ? AND l.order_index < ?
        ''', (session['user_id'], lesson['order_index']))
        
        prev_avg = cursor.fetchone()['prev_avg_accuracy'] or 0
        if prev_avg * 100 < lesson['unlock_threshold']:
            conn.close()
            return "Lesson is locked. Complete previous lessons first.", 403
    
    if lesson['content_type'] == 'translation':
        content = json.loads(lesson['content'])
    else:
        content = lesson['content']
    # Find the next lesson (by order_index)
        cursor.execute('''
        SELECT id FROM lessons
        WHERE order_index > ?
        ORDER BY order_index ASC
        LIMIT 1
        ''', (lesson['order_index'],))

        next_lesson_row = cursor.fetchone()
        next_lesson_id = next_lesson_row['id'] if next_lesson_row else None

    conn.close()
    
    return render_template('lesson.html', lesson=dict(lesson), content=content, next_lesson_id=next_lesson_id)


@app.route('/api/submit_attempt/<int:lesson_id>', methods=['POST'])
@login_required
def submit_attempt(lesson_id):
    try:
        # Get the image data from the request
        data = request.get_json()
        image_data = data['image'].split(',')[1]  # Remove the data:image/png;base64 part
        
        # Decode the base64 image
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to OpenCV format
        opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # For now, we'll use a simple comparison approach
        # In a real implementation, you would use a trained model or more sophisticated algorithm
        
        # Get the expected content for this lesson
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT content, content_type FROM lessons WHERE id = ?", (lesson_id,))
        lesson = cursor.fetchone()
        
        expected_content = lesson['content']
        if lesson['content_type'] == 'translation':
            expected_content = json.loads(lesson['content'])['ta']
        
        # Simple evaluation (placeholder for actual ML model)
        # This is a very basic implementation - in production, use a proper Tamil OCR or handwriting recognition model
        is_correct, accuracy = evaluate_drawing(opencv_image, expected_content)
        
        # Update user progress
        cursor.execute('''
        UPDATE progress 
        SET attempts = attempts + 1,
            successful_attempts = successful_attempts + ?,
            last_accuracy = ?,
            last_attempt = CURRENT_TIMESTAMP,
            completed = CASE WHEN ? >= 0.8 THEN 1 ELSE completed END
        WHERE user_id = ? AND lesson_id = ?
        ''', (1 if is_correct else 0, accuracy, accuracy, session['user_id'], lesson_id))
        
        conn.commit()
        conn.close()
        
        feedback = "சரி! நீங்கள் சரியாக எழுதியுள்ளீர்கள்." if is_correct else "மீண்டும் முயற்சிக்கவும். உங்கள் எழுத்து சற்று வித்தியாசமாக உள்ளது."
        
        return jsonify({
            'success': True,
            'correct': is_correct,
            'accuracy': round(accuracy * 100, 1),
            'feedback': feedback
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def evaluate_drawing(image, expected_text):
    """
    Placeholder function for evaluating Tamil handwriting.
    In a real implementation, this would use a proper Tamil OCR or handwriting recognition model.
    
    For this demo, we'll return a random accuracy score with a bias toward correctness
    based on the complexity of the expected text.
    """
    # Simple placeholder - in a real app, use a Tamil OCR library or ML model
    import random
    
    # More complex text gets lower accuracy on average
    complexity_factor = min(1.0, 0.8 - (len(expected_text) * 0.05))
    
    # Generate a "random" accuracy that's biased toward being correct for simple text
    accuracy = max(0.3, min(1.0, random.normalvariate(complexity_factor, 0.2)))
    
    # Consider it correct if accuracy is above 70%
    is_correct = accuracy >= 0.7
    
    return is_correct, accuracy

if __name__ == '__main__':
    app.run(debug=True)
