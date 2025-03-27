from flask import Flask, request, jsonify, g, render_template
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)
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

# Проверка и инициализация базы данных при запуске
if not os.path.exists(DATABASE):
    print("Creating new database...")
    init_db()
else:
    print("Database already exists")

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
    
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id format'}), 400
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT best_time, total_nft FROM users WHERE user_id = ?', (user_id,))
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

@app.route('/save_game_result', methods=['POST'])
def save_game_result():
    data = request.json
    
    # Валидация user_id
    try:
        user_id = int(data.get('user_id', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid user_id'}), 400
    
    if user_id == 0:
        return jsonify({'error': 'user_id is required'}), 400
    
    username = data.get('username', 'unknown')
    game_time = data.get('game_time', 0)
    nft_collected = data.get('nft_collected', 0)
    
    # Проверка типов данных
    try:
        game_time = int(game_time)
        nft_collected = int(nft_collected)
        print(f"Received game_time: {game_time}, nft_collected: {nft_collected}")
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid game_time or nft_collected format'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Получаем текущие значения
        cursor.execute('SELECT best_time, total_nft FROM users WHERE user_id = ?', (user_id,))
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
                SET best_time = ?, 
                    total_nft = ?, 
                    username = ?
                WHERE user_id = ?
            ''', (best_time, total_nft, username, user_id))
            
        else:
            # Для нового пользователя устанавливаем текущие значения
            best_time = game_time
            total_nft = nft_collected
            cursor.execute(''' 
                INSERT INTO users (user_id, username, best_time, total_nft)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, best_time, total_nft))
        
        db.commit()
        
        print(f"Saved game data - user_id: {user_id}, best_time: {best_time}, total_nft: {total_nft}")
        
        return jsonify({
            'status': 'success',
            'best_time': best_time,
            'total_nft': total_nft
        })
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Убедимся, что база данных существует
    if not os.path.exists(DATABASE):
        init_db()
    
    app.run(host='0.0.0.0', port=5000, debug=True)