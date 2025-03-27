from flask import Flask, request, jsonify, g, render_template
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'game_data.db'

# Функции для работы с базой данных
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                best_time INTEGER DEFAULT 0,
                total_nft INTEGER DEFAULT 0
            )
        ''')
        db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Главная страница
@app.route('/')
def index():
    return render_template('index.html')

# API endpoints
@app.route('/get_user_data', methods=['GET'])
def get_user_data():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT best_time, total_nft FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result:
        return jsonify({
            'best_time': result[0],
            'total_nft': result[1]
        })
    else:
        return jsonify({
            'best_time': 0,
            'total_nft': 0
        })

@app.route('/save_game_result', methods=['POST'])
def save_game_result():
    data = request.json
    user_id = data.get('user_id')
    username = data.get('username')
    game_time = data.get('game_time')
    nft_collected = data.get('nft_collected')
    
    if not all([user_id, game_time is not None, nft_collected is not None]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Проверяем, есть ли пользователь в базе
    cursor.execute('SELECT best_time, total_nft FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result:
        # Используем МИНИМАЛЬНОЕ время для best_time
        best_time = min(result[0], game_time) if result[0] > 0 else game_time
        total_nft = result[1] + nft_collected
        cursor.execute('''
            UPDATE users 
            SET best_time = ?, total_nft = ?, username = ?
            WHERE user_id = ?
        ''', (best_time, total_nft, username, user_id))
    else:
        best_time = game_time
        total_nft = nft_collected
        cursor.execute('''
            INSERT INTO users (user_id, username, best_time, total_nft)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, best_time, total_nft))
    
    db.commit()
    return jsonify({
        'best_time': best_time,
        'total_nft': total_nft
    })

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    app.run(host='0.0.0.0', port=5000)