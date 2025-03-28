from flask import Flask, request, jsonify, g, render_template
from flask_cors import CORS
import psycopg2
from psycopg2 import sql
from datetime import datetime
import os
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# Получаем URL базы данных из переменной окружения
DATABASE_URL = "postgresql://botstars_user:8mnDmL6NV0YbMTlyuukGwjtUiHE17ip2@dpg-cvj7si9r0fns73ed6ibg-a.oregon-postgres.render.com/botstars"

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        # Парсим URL для подключения
        result = urlparse(DATABASE_URL)
        username = result.username
        password = result.password
        database = result.path[1:]
        hostname = result.hostname
        port = result.port
        
        db = g._database = psycopg2.connect(
            dbname=database,
            user=username,
            password=password,
            host=hostname,
            port=port
        )
    return db

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    best_time INTEGER DEFAULT 0,
                    total_nft INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            db.commit()
            print("✅ Database table initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            db.rollback()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

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
        cursor.execute('SELECT best_time, total_nft FROM users WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        
        if result:
            return jsonify({
                'best_time': result[0] if result[0] is not None else 0,
                'total_nft': result[1] if result[1] is not None else 0
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
    try:
        data = request.json
        user_id = int(data.get('user_id', 0))
        if user_id == 0:
            return jsonify({'error': 'user_id is required'}), 400
        
        username = data.get('username', 'unknown')
        game_time = int(data.get('game_time', 0))
        nft_collected = int(data.get('nft_collected', 0))
        
        db = get_db()
        cursor = db.cursor()
        
        # Проверяем существование пользователя
        cursor.execute('SELECT best_time, total_nft FROM users WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        
        if result:
            current_best = result[0] if result[0] is not None else 0
            current_nft = result[1] if result[1] is not None else 0
            
            # Обновляем лучший результат (меньшее время)
            best_time = min(current_best, game_time) if current_best > 0 else game_time
            
            # Суммируем NFT
            total_nft = current_nft + nft_collected
            
            cursor.execute(''' 
                UPDATE users 
                SET best_time = %s, 
                    total_nft = %s, 
                    username = %s,
                    last_updated = %s
                WHERE user_id = %s
            ''', (best_time, total_nft, username, datetime.now(), user_id))
        else:
            # Создаем нового пользователя
            best_time = game_time
            total_nft = nft_collected
            cursor.execute(''' 
                INSERT INTO users (user_id, username, best_time, total_nft, last_updated)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, username, best_time, total_nft, datetime.now()))
        
        db.commit()
        
        return jsonify({
            'status': 'success',
            'best_time': best_time,
            'total_nft': total_nft
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Инициализация базы данных при старте
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)