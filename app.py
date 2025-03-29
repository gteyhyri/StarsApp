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
                    total_nft NUMERIC DEFAULT 0,
                    referral_count INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Добавляем столбец, если он не существует
            cursor.execute('''
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                  WHERE table_name='users' AND column_name='referral_count') THEN
                        ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0;
                    END IF;
                END $$;
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
        cursor.execute('SELECT best_time, total_nft, referral_count FROM users WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        
        if result:
            return jsonify({
                'best_time': result[0] if result[0] is not None else 0,
                'total_nft': float(result[1]) if result[1] is not None else 0,
                'referral_count': result[2] if result[2] is not None else 0
            })
        else:
            return jsonify({
                'best_time': 0,
                'total_nft': 0,
                'referral_count': 0
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
        referrer_id = int(data.get('referrer_id', 0))
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            # Проверяем существование пользователя
            cursor.execute('SELECT best_time, total_nft, referral_count FROM users WHERE user_id = %s', (user_id,))
            result = cursor.fetchone()
            
            best_time = game_time
            total_nft = nft_collected
            referral_count = 0
            
            if result:
                current_best = result[0] if result[0] is not None else 0
                current_nft = float(result[1]) if result[1] is not None else 0
                referral_count = result[2] if result[2] is not None else 0
                
                # Обновляем лучший результат (меньшее время лучше)
                best_time = game_time if (current_best == 0 or game_time < current_best) else current_best
                
                # Суммируем NFT
                total_nft = current_nft + nft_collected
                
                cursor.execute(''' 
                    UPDATE users 
                    SET best_time = %s, 
                        total_nft = %s, 
                        username = %s,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                ''', (best_time, total_nft, username, user_id))
            else:
                # Создаем нового пользователя
                cursor.execute(''' 
                    INSERT INTO users (user_id, username, best_time, total_nft, referral_count)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id, username, best_time, total_nft, referral_count))
            
            # Если есть реферер, начисляем ему бонус
            if referrer_id > 0 and referrer_id != user_id:  # Проверяем, чтобы пользователь не был сам себе реферером
                cursor.execute('SELECT 1 FROM users WHERE user_id = %s', (referrer_id,))
                if cursor.fetchone():
                    # Начисляем 0.5 NFT за каждого реферала
                    cursor.execute('''
                        UPDATE users 
                        SET total_nft = total_nft + 0.5,
                            referral_count = referral_count + 1,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE user_id = %s
                        RETURNING total_nft, referral_count
                    ''', (referrer_id,))
                    referrer_data = cursor.fetchone()
                    print(f"Начислено 0.5 NFT рефереру {referrer_id}. Теперь у него: {referrer_data[0]} NFT и {referrer_data[1]} рефералов")
            
            db.commit()
            
            return jsonify({
                'status': 'success',
                'best_time': best_time,
                'total_nft': float(total_nft),
                'referral_count': referral_count
            })
            
        except Exception as e:
            db.rollback()
            return jsonify({'error': f'Database error: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# Инициализация базы данных при старте
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)