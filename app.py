from flask import Flask, render_template
import os

app = Flask(__name__)

@app.route('/')
def index():
    # Данные пользователя (заглушка)
    user_data = {
        "username": "TelegramUser",
        "avatar": "https://via.placeholder.com/150",
        "fragments": 100
    }
    return render_template('index.html', user_data=user_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Используем порт из переменной окружения
    app.run(host='0.0.0.0', port=port)  # Слушаем на всех интерфейсах