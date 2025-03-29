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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_visits (
                    visit_id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    referrer_id BIGINT,
                    visit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, referrer_id)
                )
            ''')
            
            db.commit()
            print("✅ Database tables initialized successfully")
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
        referrer_id = int(data.get('referrer_id', 0)) if data.get('referrer_id') not in [None, 'null', 'undefined'] else 0
        
        print(f"🔹 New game result - User: {user_id}, Referrer: {referrer_id}, Time: {game_time}, NFT: {nft_collected}")
        
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
                
                best_time = game_time if (current_best == 0 or game_time < current_best) else current_best
                total_nft = current_nft + nft_collected
                
                cursor.execute(''' 
                    UPDATE users 
                    SET best_time = %s, 
                        total_nft = %s, 
                        username = %s,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                ''', (best_time, total_nft, username, user_id))
                print(f"🔄 Updated user {user_id} with time {best_time} and NFT {total_nft}")
            else:
                cursor.execute(''' 
                    INSERT INTO users (user_id, username, best_time, total_nft, referral_count)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id, username, best_time, total_nft, referral_count))
                print(f"🆕 Created new user {user_id} with time {best_time} and NFT {total_nft}")
            
            # Обработка реферала
            if referrer_id > 0 and referrer_id != user_id:
                print(f"🔍 Checking referral from {user_id} to {referrer_id}")
                
                # Проверяем, что это первый визит реферала
                cursor.execute('''
                    SELECT visit_time FROM user_visits 
                    WHERE user_id = %s AND referrer_id = %s
                ''', (user_id, referrer_id))
                existing_visit = cursor.fetchone()
                
                if not existing_visit:
                    print(f"🎉 New referral detected: {user_id} referred by {referrer_id}")
                    
                    try:
                        # Записываем визит
                        cursor.execute('''
                            INSERT INTO user_visits (user_id, referrer_id, visit_time)
                            VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ''', (user_id, referrer_id))
                        
                        # Начисляем бонус рефереру
                        cursor.execute('''
                            UPDATE users 
                            SET total_nft = total_nft + 0.5,
                                referral_count = referral_count + 1
                            WHERE user_id = %s
                            RETURNING total_nft, referral_count
                        ''', (referrer_id,))
                        
                        referrer_data = cursor.fetchone()
                        if referrer_data:
                            print(f"💰 Added 0.5 NFT to referrer {referrer_id}. Now has: {referrer_data[0]} NFT and {referrer_data[1]} referrals")
                        else:
                            print(f"⚠️ Referrer {referrer_id} not found in database")
                            
                    except Exception as e:
                        print(f"❌ Error processing referral: {str(e)}")
                        db.rollback()
                        return jsonify({'error': f'Referral processing error: {str(e)}'}), 500
                else:
                    print(f"⏩ Already processed referral from {user_id} to {referrer_id} at {existing_visit[0]}")
            else:
                print(f"⏩ No valid referral (referrer_id: {referrer_id}, user_id: {user_id})")
            
            db.commit()
            
            return jsonify({
                'status': 'success',
                'best_time': best_time,
                'total_nft': float(total_nft),
                'referral_count': referral_count
            })
            
        except Exception as e:
            db.rollback()
            print(f"❌ Database error: {str(e)}")
            return jsonify({'error': f'Database error: {str(e)}'}), 500
            
    except Exception as e:
        print(f"❌ General error: {str(e)}")
        return jsonify({'error': str(e)}), 500
# Инициализация базы данных при старте
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)