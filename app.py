from flask import Flask, request, jsonify, g, render_template
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)
DATABASE = 'game_data.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            try:
                cursor.execute('''
                    CREATE TABLE users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        best_time INTEGER DEFAULT 0,
                        total_nft INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                db.commit()
                print("Database table created successfully")
            except Exception as e:
                print(f"Error creating database table: {e}")
                db.rollback()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Инициализация базы данных при запуске
if not os.path.exists(DATABASE):
    print("Creating new database...")
    init_db()
else:
    print("Database already exists, initializing...")
    init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_user_data', methods=['GET'])
def get_user_data():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id format'}), 400
    
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT best_time, total_nft FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            return jsonify({
                'best_time': result['best_time'] if result['best_time'] is not None else 0,
                'total_nft': result['total_nft'] if result['total_nft'] is not None else 0
            })
        else:
            return jsonify({
                'best_time': 0,
                'total_nft': 0
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save_game_result', methods=['POST'])
def save_game_result():
    data = request.json
    
    try:
        user_id = int(data.get('user_id', 0))
        if user_id == 0:
            return jsonify({'error': 'user_id is required'}), 400
        
        username = data.get('username', 'unknown')
        game_time = int(data.get('game_time', 0))
        nft_collected = int(data.get('nft_collected', 0))
        
        db = get_db()
        cursor = db.cursor()
        
        # Получаем текущие значения
        cursor.execute('SELECT best_time, total_nft FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            current_best = result['best_time'] if result['best_time'] is not None else 0
            current_nft = result['total_nft'] if result['total_nft'] is not None else 0
            
            # Обновляем лучший результат (меньшее время)
            best_time = min(current_best, game_time) if current_best > 0 else game_time
            
            # Суммируем NFT
            total_nft = current_nft + nft_collected
            
            cursor.execute(''' 
                UPDATE users 
                SET best_time = ?, 
                    total_nft = ?, 
                    username = ?,
                    last_updated = ?
                WHERE user_id = ?
            ''', (best_time, total_nft, username, datetime.now(), user_id))
            
        else:
            # Для нового пользователя
            best_time = game_time
            total_nft = nft_collected
            cursor.execute(''' 
                INSERT INTO users (user_id, username, best_time, total_nft, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, best_time, total_nft, datetime.now()))
        
        db.commit()
        
        return jsonify({
            'status': 'success',
            'best_time': best_time,
            'total_nft': total_nft
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)