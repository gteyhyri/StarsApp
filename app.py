from flask import Flask, request, jsonify, g
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

# Конфигурация базы данных
DATABASE = 'space_star.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Создаем таблицу пользователей, если ее нет
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            best_time INTEGER DEFAULT 0,
            max_speed REAL DEFAULT 0,
            last_played TEXT
        )
        ''')
        
        # Создаем таблицу NFT, если ее нет
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS nfts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            color TEXT,
            count INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            UNIQUE(user_id, color)
        )
        ''')
        
        db.commit()

@app.route('/get_user_data', methods=['POST'])
def get_user_data():
    data = request.json
    user_id = data.get('userId')
    username = data.get('username')
    
    db = get_db()
    cursor = db.cursor()
    
    # Проверяем, есть ли пользователь в базе
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        # Если пользователя нет, создаем новую запись
        cursor.execute('''
        INSERT INTO users (user_id, username, last_played) 
        VALUES (?, ?, ?)
        ''', (user_id, username, datetime.now().isoformat()))
        db.commit()
    
    # Получаем данные пользователя
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    # Получаем NFT пользователя
    cursor.execute('SELECT color, count FROM nfts WHERE user_id = ?', (user_id,))
    nfts = cursor.fetchall()
    
    # Формируем словарь NFT
    nft_dict = {nft['color']: nft['count'] for nft in nfts}
    
    return jsonify({
        'success': True,
        'data': {
            'userId': user['user_id'],
            'username': user['username'],
            'bestTime': user['best_time'],
            'maxSpeed': user['max_speed'],
            'nfts': nft_dict
        }
    })

@app.route('/save_game_results', methods=['POST'])
def save_game_results():
    data = request.json
    user_id = data.get('userId')
    game_time = data.get('gameTime', 0)
    max_speed = data.get('maxSpeed', 0)
    nfts = data.get('nfts', {})
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Обновляем рекорды пользователя
        cursor.execute('''
        UPDATE users 
        SET 
            best_time = MAX(best_time, ?),
            max_speed = MAX(max_speed, ?),
            last_played = ?
        WHERE user_id = ?
        ''', (game_time, max_speed, datetime.now().isoformat(), user_id))
        
        # Обновляем или добавляем NFT
        for color, count in nfts.items():
            cursor.execute('''
            INSERT INTO nfts (user_id, color, count)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, color) DO UPDATE SET
                count = count + excluded.count
            ''', (user_id, color, count))
        
        db.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Инициализируем базу данных при первом запуске
    if not os.path.exists(DATABASE):
        init_db()
    
    app.run(debug=True)