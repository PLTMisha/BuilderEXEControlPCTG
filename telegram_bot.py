import os
import sys
import time
import json
import uuid
import zipfile
import tempfile
import shutil
import threading
import logging
import subprocess
import requests
import zipfile
from pathlib import Path
from datetime import datetime
import secrets
import string
import os
import sys
import tempfile
import shutil
import subprocess
import logging


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler


GENERATOR_BOT_TOKEN = "8229458291:AAEwZx3C0o1qq4vYTHFzCreGpFVtytEFo_E"  
ADMIN_CHAT_ID = 5450404463  


USERS_DATA_FILE = "users_data.json"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("generator_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)


users_data = {}

def load_users_data():
    """Загружает данные пользователей"""
    global users_data
    try:
        if os.path.exists(USERS_DATA_FILE):
            with open(USERS_DATA_FILE, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
            logging.info(f"Загружены данные {len(users_data)} пользователей")
    except Exception as e:
        logging.error(f"Ошибка загрузки данных пользователей: {e}")
        users_data = {}

def save_users_data():
    """Сохраняет данные пользователей"""
    try:
        with open(USERS_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"Ошибка сохранения данных пользователей: {e}")
        return False

def generate_password(length=12):
    """Генерирует случайный пароль"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def get_user_data(user_id):
    """Получает данные пользователя"""
    return users_data.get(str(user_id), {})

def set_user_data(user_id, data):
    """Сохраняет данные пользователя"""
    users_data[str(user_id)] = data
    save_users_data()

def start_handler(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    logging.info(f"Пользователь {username} ({user_id}) запустил бота")
    
    
    keyboard = [
        [KeyboardButton("📋 Функции программы")],
        [KeyboardButton("🔑 Ввести токен бота")],
        [KeyboardButton("💬 Поддержка")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = """
🤖 Добро пожаловать в генератор PC Controller!

Этот бот создаст для вас персональную программу для удаленного управления компьютером через Telegram.

📋 Нажмите "Функции программы", чтобы узнать все возможности
🔑 Введите токен вашего Telegram-бота для начала работы

⚠️ Важно: Вам понадобится создать своего бота через @BotFather
    """
    
    update.message.reply_text(welcome_text, reply_markup=reply_markup)

def functions_handler(update: Update, context: CallbackContext):
    """Показывает функции программы"""
    functions_text = """
📋 ВОЗМОЖНОСТИ PC CONTROLLER

🖥️ СИСТЕМА:
• Перезагрузка и выключение компьютера
• Блокировка системы
• Смена обоев рабочего стола
• Управление яркостью и громкостью
• Очистка корзины

📂 ФАЙЛЫ:
• Просмотр содержимого папок
• Загрузка файлов на компьютер
• Удаление файлов и папок
• Поиск файлов

📡 СЕТЬ:
• Сканирование локальной сети
• Ping хостов
• Тест скорости интернета

📸 МЕДИА:
• Скриншоты экрана
• Запись экрана
• Фото и видео с веб-камеры
• Автоматические скриншоты
• Live-трансляция экрана с управлением

⌨️ ВВОД:
• Ввод текста в активное окно
• Виртуальная клавиатура
• Горячие клавиши

🔊 ЗВУК:
• Управление громкостью
• Воспроизведение/пауза
• Переключение треков

⚙️ МОНИТОРИНГ:
• Информация о системе
• Графики загрузки CPU/RAM
• Мониторинг температуры
• Лог активных окон

🖥️ ПРОГРАММЫ:
• Запуск установленных программ
• Добавление новых программ
• Управление списком программ

🌐 УДАЛЕННЫЙ ДОСТУП:
• Веб-панель управления
• Поддержка ngrok для доступа из интернета
• Защита паролем
    """
    
    keyboard = [
        [KeyboardButton("🔑 Ввести токен бота")],
        [KeyboardButton("🏠 Главное меню")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    update.message.reply_text(functions_text, reply_markup=reply_markup)

def token_input_handler(update: Update, context: CallbackContext):
    """Обработчик ввода токена"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['status'] = 'waiting_token'
    set_user_data(user_id, user_data)
    
    keyboard = [[KeyboardButton("🏠 Главное меню")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    token_text = """
🔑 ВВОД ТОКЕНА БОТА

Пожалуйста, отправьте токен вашего Telegram-бота.

📝 Как получить токен:
1. Напишите @BotFather в Telegram
2. Отправьте команду /newbot
3. Выберите имя и username для бота
4. Скопируйте полученный токен

⚠️ Токен имеет вид: 1234567890:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

Отправьте токен следующим сообщением:
    """
    
    update.message.reply_text(token_text, reply_markup=reply_markup)

def validate_token(token):
    """Проверяет корректность токена"""
    try:
        
        parts = token.split(':')
        if len(parts) != 2:
            return False
        
        bot_id = parts[0]
        bot_hash = parts[1]
        
        
        if not bot_id.isdigit():
            return False
        
        
        if len(bot_hash) < 20:
            return False
            
        
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('ok', False)
        
        return False
        
    except Exception as e:
        logging.error(f"Ошибка валидации токена: {e}")
        return False

def create_personalized_code(token, user_id):
    """Создает персонализированный код программы"""
    try:
        
        with open('pc_controller_template.py', 'r', encoding='utf-8') as f:
            original_code = f.read()
        
        
        personalized_code = original_code.replace(
            'TOKEN = "8282388858:AAHYEEW3ebFolN1lyTCmVyps1v5z5DyTbVk"',
            f'TOKEN = "{token}"'
        ).replace(
            'OWNER_CHAT_ID = 5450404463',
            f'OWNER_CHAT_ID = {user_id}'
        )
        
        return personalized_code
    except Exception as e:
        logging.error(f"Ошибка создания персонализированного кода: {e}")
        return None

def create_zip_package(user_id, token):
    """Создает ZIP-пакет с программой"""
    try:
        
        temp_dir = tempfile.mkdtemp(prefix=f"pc_controller_{user_id}_")
        
        
        personalized_code = create_personalized_code(token, user_id)
        if not personalized_code:
            return None, None
        
        
        main_file = os.path.join(temp_dir, 'main.py')
        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(personalized_code)
        
        
        html_source = 'live_control.html'
        if os.path.exists(html_source):
            shutil.copy2(html_source, temp_dir)
        else:
            
            create_html_file(temp_dir)
        
        
        programs_file = os.path.join(temp_dir, 'user_programs.json')
        with open(programs_file, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        
        
        requirements_file = os.path.join(temp_dir, 'requirements.txt')
        create_requirements_file(requirements_file)
        
        
        readme_file = os.path.join(temp_dir, 'README.txt')
        create_readme_file(readme_file)
        
        
        password = generate_password()
        
        
        zip_path = os.path.join(temp_dir, f'PCController_{user_id}.zip')
        create_password_protected_zip(temp_dir, zip_path, password)
        
        return zip_path, password
        
    except Exception as e:
        logging.error(f"Ошибка создания ZIP-пакета: {e}")
        return None, None

def create_html_file(temp_dir):
    """Создает HTML файл для live control"""
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>PC Control Panel</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: linear-gradient(135deg, 
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .controls { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .control-group { background: 
        .control-group h3 { color: 
        button { padding: 12px 20px; margin: 5px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.3s ease; }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
        .mouse-btn { background: linear-gradient(45deg, 
        .kbd-btn { background: linear-gradient(45deg, 
        
        .status { padding: 15px; background: linear-gradient(45deg, 
        input[type="text"] { width: 200px; padding: 8px 12px; border: 2px solid 
        input[type="text"]:focus { border-color: 
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.4/socket.io.js"></script>
</head>
<body>
    <div class="container">
        <h1 style="text-align: center; color: 
        <div class="status" id="status">🔄 Подключение к серверу...</div>
        
        <div class="controls">
            <div class="control-group">
                <h3>🖱️ Управление мышью</h3>
                <button class="mouse-btn" onclick="mouseAction('left')">👆 Левый клик</button>
                <button class="mouse-btn" onclick="mouseAction('right')">👇 Правый клик</button>
                <button class="mouse-btn" onclick="mouseAction('double')">⚡ Двойной клик</button>
                <br>
                <div style="text-align: center; margin-top: 10px;">
                    <button class="mouse-btn" onclick="mouseAction('up')" style="display: block; margin: 5px auto;">⬆️</button>
                    <div>
                        <button class="mouse-btn" onclick="mouseAction('left_move')" style="display: inline-block;">⬅️</button>
                        <button class="mouse-btn" onclick="mouseAction('right_move')" style="display: inline-block;">➡️</button>
                    </div>
                    <button class="mouse-btn" onclick="mouseAction('down')" style="display: block; margin: 5px auto;">⬇️</button>
                </div>
            </div>
            
            <div class="control-group">
                <h3>⌨️ Клавиатура</h3>
                <div style="margin-bottom: 15px;">
                    <input type="text" id="textInput" placeholder="Введите текст для ввода...">
                    <button class="kbd-btn" onclick="typeText()">📝 Ввести</button>
                </div>
                <button class="kbd-btn" onclick="keyAction('enter')">⏎ Enter</button>
                <button class="kbd-btn" onclick="keyAction('esc')">⎋ Escape</button>
                <button class="kbd-btn" onclick="keyAction('tab')">⇥ Tab</button>
                <button class="kbd-btn" onclick="keyAction('space')">␣ Пробел</button>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 20px;">
            <h3>🖥️ Экран компьютера</h3>
            <img id="screen" src="/stream?pw={{ pw }}" alt="Desktop Stream" onload="this.style.opacity=1" style="opacity:0; transition: opacity 0.3s;">
        </div>
    </div>

    <script>
        const socket = io();
        const status = document.getElementById('status');
        
        socket.on('connect', function() {
            status.innerHTML = '✅ Подключен к серверу';
            status.style.background = 'linear-gradient(45deg, 
        });
        
        socket.on('disconnect', function() {
            status.innerHTML = '❌ Соединение потеряно';
            status.style.background = 'linear-gradient(45deg, 
        });
        
        function mouseAction(action) {
            fetch('/api/mouse?pw={{ pw }}', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'action=' + action
            }).catch(console.error);
        }
        
        function keyAction(action) {
            fetch('/api/keyboard?pw={{ pw }}', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'action=' + action
            }).catch(console.error);
        }
        
        function typeText() {
            const text = document.getElementById('textInput').value;
            if (text.trim()) {
                fetch('/api/keyboard?pw={{ pw }}', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: 'action=type&text=' + encodeURIComponent(text)
                }).catch(console.error);
                document.getElementById('textInput').value = '';
            }
        }
        
        // Обновление скриншота с оптимизацией
        let updateInterval = 200; // начальная частота обновления
        function updateScreen() {
            const img = document.getElementById('screen');
            const newSrc = '/stream?pw={{ pw }}&t=' + Date.now();
            img.src = newSrc;
        }
        
        setInterval(updateScreen, updateInterval);
        
        // Обработка нажатий клавиш на странице
        document.addEventListener('keydown', function(e) {
            if (e.target.tagName !== 'INPUT') {
                e.preventDefault();
                let key = e.key;
                if (key === ' ') key = 'space';
                if (key === 'Enter') key = 'enter';
                if (key === 'Escape') key = 'esc';
                keyAction(key);
            }
        });
        
        // Управление мышью по клику на изображение
        document.getElementById('screen').addEventListener('click', function(e) {
            const rect = this.getBoundingClientRect();
            const x = Math.round((e.clientX - rect.left) / rect.width * 100);
            const y = Math.round((e.clientY - rect.top) / rect.height * 100);
            
            fetch('/api/mouse?pw={{ pw }}', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: `action=click&x=${x}&y=${y}`
            }).catch(console.error);
        });
    </script>
</body>
</html>'''
    
    html_file = os.path.join(temp_dir, 'live_control.html')
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logging.info("HTML файл создан")

def create_requirements_file(file_path):
    """Создает файл requirements.txt"""
    requirements = '''pyautogui==0.9.54
opencv-python==4.8.1.78
numpy==1.24.3
mss==9.0.1
Pillow==10.0.1
psutil==5.9.6
python-telegram-bot==13.15
requests==2.31.0
pyngrok==7.0.0
Flask==2.3.3
Flask-SocketIO==5.3.6
watchdog==3.0.0
pywin32==306
speedtest-cli==2.1.3
scipy==1.11.4
sounddevice==0.4.6
pyperclip==1.8.2
aiortc==1.6.0
av==10.0.0
PyInstaller==6.2.0
pyzmq==25.1.1
websocket-client==1.6.4
python-dateutil==2.8.2'''
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(requirements)
    logging.info("Requirements файл создан")

def create_readme_file(file_path):
    """Создает файл с инструкцией"""
    readme_content = """
🤖 PC CONTROLLER - ИНСТРУКЦИЯ ПО УСТАНОВКЕ

📋 СОДЕРЖИМОЕ АРХИВА:
• main.py - основная программа
• live_control.html - веб-интерфейс для управления
• user_programs.json - файл пользовательских программ
• requirements.txt - список зависимостей
• README.txt - данная инструкция

🔧 УСТАНОВКА:

1️⃣ УСТАНОВКА PYTHON:
   • Скачайте Python 3.8+ с https://python.org
   • При установке обязательно отметьте "Add to PATH"

2️⃣ УСТАНОВКА ЗАВИСИМОСТЕЙ:
   • Откройте командную строку (Win+R, cmd)
   • Перейдите в папку с файлами: cd "путь_к_папке"
   • Выполните: pip install -r requirements.txt

3️⃣ ЗАПУСК ПРОГРАММЫ:
   • Запустите: python main.py
   • Или просто двойной клик по main.py

🚀 ПЕРВЫЙ ЗАПУСК:
   • При первом запуске программа создаст все необходимые файлы
   • Отправьте команду /start своему боту в Telegram
   • Используйте команды для управления компьютером

🔐 БЕЗОПАСНОСТЬ:
   • Программа работает только с вашим Telegram ID
   • Все веб-интерфейсы защищены паролем
   • При подозрительной активности бот заблокирует доступ

⚙️ ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ:
   • Для доступа из интернета установите ngrok
   • Для автозапуска добавьте в автозагрузку Windows
   • Настройки программ находятся в user_programs.json

🆘 РЕШЕНИЕ ПРОБЛЕМ:
   • При ошибках установки: pip install --upgrade pip
   • Проблемы с pywin32: pip install --force-reinstall pywin32
   • Антивирус блокирует: добавьте папку в исключения

📞 ПОДДЕРЖКА:
   Если у вас возникли проблемы, обратитесь к администратору бота.

✅ ГОТОВО! Ваш PC Controller настроен и готов к использованию!
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    logging.info("README файл создан")

def create_password_protected_zip(source_dir, zip_path, password):
    """Создает защищенный паролем ZIP архив"""
    try:
        import pyminizip
        
        
        files_to_zip = []
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file != os.path.basename(zip_path):  
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, source_dir)
                    files_to_zip.append((file_path, arc_name))
        
        
        pyminizip.compress_multiple(
            [f[0] for f in files_to_zip],  
            [f[1] for f in files_to_zip],  
            zip_path,                      
            password,                      
            5                             
        )
        
        return True
        
    except ImportError:
        
        logging.warning("pyminizip не установлен, создается обычный ZIP без пароля")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    if file != os.path.basename(zip_path):
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, source_dir)
                        zipf.write(file_path, arc_name)
        
        return False
    
    except Exception as e:
        logging.error(f"Ошибка создания ZIP: {e}")
        return False

def build_exe_for_user(user_id, token, temp_dir):
    """Собирает EXE файл для пользователя с детальным логированием"""
    try:
        logging.info(f"Начинаю сборку EXE для пользователя {user_id}")
        
        
        try:
            import PyInstaller
            logging.info(f"PyInstaller найден: версия {PyInstaller.__version__}")
        except ImportError:
            logging.error("PyInstaller не установлен!")
            return None
        
        
        spec_content = f'''

import os
import sys

block_cipher = None


pathex = [r'{temp_dir}']


datas = [
    (r'{temp_dir}/live_control.html', '.'),
    (r'{temp_dir}/user_programs.json', '.'),
]


hiddenimports = [
    'pkg_resources.py2_warn',
    'telegram',
    'telegram.ext',
    'telegram.ext.updater',
    'telegram.ext.commandhandler',
    'telegram.ext.messagehandler',
    'telegram.ext.callbackqueryhandler',
    'pyautogui',
    'cv2',
    'numpy',
    'PIL',
    'PIL.Image',
    'PIL.ImageGrab',
    'mss',
    'psutil',
    'requests',
    'json',
    'base64',
    'threading',
    'subprocess',
    'os',
    'sys',
    'time',
    'io',
    'tempfile',
    'pathlib',
    'logging',
    'socket',
    'urllib.request',
    'urllib.parse',
]


if sys.platform.startswith('win'):
    hiddenimports.extend([
        'win32gui',
        'win32con',
        'win32api',
        'win32process',
        'winsound',
    ])


excludes = [
    'tkinter',
    'matplotlib',
    'IPython',
    'jupyter',
    'notebook',
    'scipy.spatial.cKDTree',
    'scipy.sparse.csgraph._validation',
]

a = Analysis(
    [r'{temp_dir}/main.py'],
    pathex=pathex,
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PCController_{user_id}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PCController_{user_id}',
)
'''
        
        spec_path = os.path.join(temp_dir, 'pc_controller.spec')
        with open(spec_path, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        logging.info(f"Spec файл создан: {spec_path}")
        
        
        requirements_content = '''pyautogui==0.9.54
opencv-python==4.8.1.78
numpy==1.24.3
mss==9.0.1
Pillow==10.0.1
psutil==5.9.6
python-telegram-bot==13.15
requests==2.31.0
PyInstaller==6.2.0'''
        
        req_path = os.path.join(temp_dir, 'requirements.txt')
        with open(req_path, 'w') as f:
            f.write(requirements_content)
        
        
        old_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            logging.info("Запускаю PyInstaller...")
            
            
            cmd = [
                sys.executable, '-m', 'PyInstaller',
                '--clean',
                '--noconfirm',
                '--log-level=DEBUG',  
                'pc_controller.spec'
            ]
            
            logging.info(f"Команда: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1200,  
                cwd=temp_dir
            )
            
            logging.info(f"PyInstaller return code: {result.returncode}")
            
            if result.stdout:
                logging.info(f"PyInstaller stdout:\n{result.stdout[-2000:]}")  
            
            if result.stderr:
                logging.error(f"PyInstaller stderr:\n{result.stderr[-2000:]}")
            
            if result.returncode == 0:
                
                possible_paths = [
                    os.path.join(temp_dir, 'dist', f'PCController_{user_id}', f'PCController_{user_id}.exe'),
                    os.path.join(temp_dir, 'dist', f'PCController_{user_id}.exe'),
                    os.path.join(temp_dir, 'dist', 'PCController', 'PCController.exe')
                ]
                
                for exe_path in possible_paths:
                    if os.path.exists(exe_path):
                        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
                        logging.info(f"EXE найден: {exe_path}, размер: {size_mb:.1f} MB")
                        return exe_path
                
                
                dist_dir = os.path.join(temp_dir, 'dist')
                if os.path.exists(dist_dir):
                    for root, dirs, files in os.walk(dist_dir):
                        for file in files:
                            if file.endswith('.exe'):
                                exe_path = os.path.join(root, file)
                                logging.info(f"Найден EXE файл: {exe_path}")
                                return exe_path
                
                logging.error("EXE файл не найден после успешной сборки")
                logging.info(f"Содержимое dist: {os.listdir(dist_dir) if os.path.exists(dist_dir) else 'dist не найден'}")
                return None
                
            else:
                logging.error(f"PyInstaller завершился с ошибкой {result.returncode}")
                return None
                
        finally:
            os.chdir(old_cwd)
            
    except subprocess.TimeoutExpired:
        logging.error("Таймаут при сборке EXE")
        return None
    except Exception as e:
        logging.error(f"Ошибка при сборке EXE: {str(e)}")
        logging.exception("Полная трассировка ошибки:")
        return None

def test_exe_build():
    """Тестовая функция для проверки сборки EXE"""
    import tempfile
    import shutil
    
    logging.basicConfig(level=logging.INFO)
    
    
    temp_dir = tempfile.mkdtemp(prefix="exe_test_")
    
    try:
        
        test_code = '''
import sys
import os

def main():
    print("Hello from EXE!")
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
'''
        
        main_path = os.path.join(temp_dir, 'main.py')
        with open(main_path, 'w') as f:
            f.write(test_code)
        
        
        with open(os.path.join(temp_dir, 'live_control.html'), 'w') as f:
            f.write('<html><body>Test</body></html>')
        
        with open(os.path.join(temp_dir, 'user_programs.json'), 'w') as f:
            f.write('{}')
        
        
        exe_path = build_exe_for_user("test", "test_token", temp_dir)
        
        if exe_path:
            print(f"✅ Тест успешен! EXE создан: {exe_path}")
            return True
        else:
            print("❌ Тест провален!")
            return False
            
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def diagnose_system():
    """Диагностирует систему на готовность к сборке EXE"""
    issues = []
    
    try:
        import PyInstaller
        print(f"✅ PyInstaller: {PyInstaller.__version__}")
    except ImportError:
        issues.append("❌ PyInstaller не установлен")
    
    try:
        import telegram
        print(f"✅ python-telegram-bot: {telegram.__version__}")
    except ImportError:
        issues.append("❌ python-telegram-bot не установлен")
    
    
    import psutil
    memory_gb = psutil.virtual_memory().available / (1024**3)
    if memory_gb < 2:
        issues.append(f"⚠️ Мало свободной памяти: {memory_gb:.1f} GB")
    else:
        print(f"✅ Свободной памяти: {memory_gb:.1f} GB")
    
    
    if diagnose_f_drive():
        print("✅ Диск F: готов для сборки")
    else:
        issues.append("❌ Диск F: не готов для сборки")
    
    if issues:
        print("\n🔧 Найдены проблемы:")
        for issue in issues:
            print(issue)
        return False
    else:
        print("\n✅ Система готова к сборке EXE на диске F:")
        return True
def setup_f_drive_build():
    """Настраивает использование диска F: для сборки"""
    
    
    f_build_dir = "F:/PCController_Build"
    f_temp_dir = "F:/temp"
    
    
    os.makedirs(f_build_dir, exist_ok=True)
    os.makedirs(f_temp_dir, exist_ok=True)
    
    
    os.environ['PYINSTALLER_CONFIG_DIR'] = f_build_dir
    os.environ['TMPDIR'] = f_temp_dir  
    os.environ['TEMP'] = f_temp_dir    
    os.environ['TMP'] = f_temp_dir     
    
    logging.info(f"Настроена сборка на диске F:")
    logging.info(f"Рабочая папка: {f_build_dir}")
    logging.info(f"Временная папка: {f_temp_dir}")
    
    return f_build_dir, f_temp_dir

def create_f_temp_dir(prefix="pc_controller_"):
    """Создает временную папку на диске F:"""
    f_temp_base = "F:/temp"
    os.makedirs(f_temp_base, exist_ok=True)
    
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    temp_dir = os.path.join(f_temp_base, f"{prefix}{unique_id}")
    os.makedirs(temp_dir, exist_ok=True)
    
    return temp_dir

def build_exe_for_user_f_drive_nuitka(user_id, token, use_f_drive=True):
    """Собирает EXE файл с использованием Nuitka на диске F:"""
    try:
        logging.info(f"Начинаю сборку EXE с Nuitka для пользователя {user_id}")
        
        
        try:
            result = subprocess.run([sys.executable, '-c', 'import nuitka; print(nuitka.__version__)'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logging.info(f"Nuitka версия: {result.stdout.strip()}")
            else:
                logging.info("Nuitka не найден, устанавливаю...")
                subprocess.run([sys.executable, '-m', 'pip', 'install', 'nuitka'], 
                             check=True, capture_output=True, timeout=180)
                logging.info("Nuitka установлен успешно")
        except Exception as e:
            logging.error(f"Ошибка с Nuitka: {e}")
            return None
        
        
        if use_f_drive:
            f_build_dir, f_temp_dir = setup_f_drive_build()
            temp_dir = create_f_temp_dir(f"nuitka_build_{user_id}_")
        else:
            temp_dir = tempfile.mkdtemp(prefix=f"nuitka_{user_id}_")
            f_temp_dir = tempfile.gettempdir()
        
        logging.info(f"Временная папка: {temp_dir}")
        
        
        personalized_code = create_personalized_code(token, user_id)
        if not personalized_code:
            return None
        
        main_file = os.path.join(temp_dir, 'main.py')
        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(personalized_code)
        
        
        create_html_file(temp_dir)
        
        programs_file = os.path.join(temp_dir, 'user_programs.json')
        with open(programs_file, 'w', encoding='utf-8') as f:
            import json
            json.dump({}, f, ensure_ascii=False, indent=2)
        
        
        output_dir = os.path.join(temp_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        cmd = [
            sys.executable, '-m', 'nuitka',
            '--standalone',  
            '--assume-yes-for-downloads',
            '--output-dir=' + output_dir,
            '--windows-console-mode=attach',
            
            
            '--include-module=telegram',
            '--include-module=pyautogui',
            '--include-module=cv2',
            '--include-module=numpy',
            '--include-module=PIL',
            '--include-module=psutil',
            '--include-module=requests',
            
            
            '--include-data-files=' + os.path.join(temp_dir, 'live_control.html') + '=live_control.html',
            '--include-data-files=' + os.path.join(temp_dir, 'user_programs.json') + '=user_programs.json',
            
            main_file
        ]
        
        logging.info("Запускаю Nuitka (упрощенную версию)...")
        logging.info(f"Рабочая папка: {temp_dir}")
        
        
        full_cmd = ' '.join(cmd)
        logging.info(f"Полная команда Nuitka: {full_cmd}")
        
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  
            cwd=temp_dir,
            env=os.environ.copy()
        )
        
        logging.info(f"Nuitka return code: {result.returncode}")
        
        
        if result.stdout:
            logging.info(f"Nuitka STDOUT:\n{result.stdout}")
        
        if result.stderr:
            logging.error(f"Nuitka STDERR:\n{result.stderr}")
        
        if result.returncode == 0:
            
            main_name = os.path.splitext(os.path.basename(main_file))[0]
            exe_folder = os.path.join(output_dir, main_name + '.dist')
            exe_path = os.path.join(exe_folder, main_name + '.exe')
            
            if os.path.exists(exe_path):
                size_mb = os.path.getsize(exe_path) / (1024 * 1024)
                logging.info(f"EXE создан: {exe_path}, размер: {size_mb:.1f} MB")
                
                
                zip_path = os.path.join(temp_dir, f'PCController_{user_id}_nuitka.zip')
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(exe_folder):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_name = os.path.relpath(file_path, exe_folder)
                            zipf.write(file_path, arc_name)
                
                logging.info(f"Создан ZIP с Nuitka сборкой: {zip_path}")
                return zip_path  
            else:
                
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        if file.endswith('.exe'):
                            found_exe = os.path.join(root, file)
                            logging.info(f"Найден EXE: {found_exe}")
                            return found_exe
                
                logging.error("EXE файл не найден после успешной сборки Nuitka")
                
                if os.path.exists(output_dir):
                    logging.info(f"Содержимое {output_dir}:")
                    for item in os.listdir(output_dir):
                        item_path = os.path.join(output_dir, item)
                        if os.path.isdir(item_path):
                            logging.info(f"  Папка: {item}")
                            for sub_item in os.listdir(item_path):
                                logging.info(f"    {sub_item}")
                        else:
                            logging.info(f"  Файл: {item}")
                return None
        else:
            logging.error(f"Nuitka завершился с ошибкой {result.returncode}")
            
            
            logging.info("Пробуем минимальную команду Nuitka...")
            simple_cmd = [
                sys.executable, '-m', 'nuitka',
                '--standalone',
                '--assume-yes-for-downloads',
                '--output-dir=' + output_dir,
                main_file
            ]
            
            simple_result = subprocess.run(
                simple_cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=temp_dir
            )
            
            if simple_result.returncode == 0:
                logging.info("Минимальная команда сработала!")
                
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        if file.endswith('.exe'):
                            return os.path.join(root, file)
            else:
                logging.error(f"Минимальная команда тоже не сработала: {simple_result.stderr}")
            
            return None
            
    except subprocess.TimeoutExpired:
        logging.error("Таймаут при сборке EXE с Nuitka")
        return None
    except Exception as e:
        logging.error(f"Общая ошибка при сборке EXE с Nuitka: {str(e)}")
        return None
    
def test_nuitka_simple():
    """Простой тест Nuitka с минимальным кодом"""
    try:
        temp_dir = tempfile.mkdtemp(prefix="nuitka_test_")
        
        
        test_code = '''
import sys
print("Hello from Nuitka!")
input("Press Enter...")
'''
        
        test_file = os.path.join(temp_dir, 'test.py')
        with open(test_file, 'w') as f:
            f.write(test_code)
        
        
        cmd = [
            sys.executable, '-m', 'nuitka',
            '--standalone',
            '--assume-yes-for-downloads',
            test_file
        ]
        
        print(f"Тестирую Nuitka в папке: {temp_dir}")
        print(f"Команда: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, cwd=temp_dir, timeout=300)
        
        if result.returncode == 0:
            print("✅ Nuitka работает!")
            return True
        else:
            print(f"❌ Nuitka не работает, код: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка теста Nuitka: {e}")
        return False
    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

def diagnose_nuitka_issues():
    """Диагностирует проблемы с Nuitka и предлагает решения"""
    issues = []
    solutions = []
    
    print("=== Диагностика Nuitka ===")
    
    
    python_version = sys.version_info
    print(f"Python версия: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 7):
        issues.append("Старая версия Python")
        solutions.append("Обновите Python до версии 3.7+")
    
    
    try:
        result = subprocess.run([sys.executable, '-c', 'import nuitka; print(nuitka.__version__)'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Nuitka установлен: версия {result.stdout.strip()}")
        else:
            issues.append("Nuitka не установлен правильно")
            solutions.append("Переустановите: pip uninstall nuitka && pip install nuitka")
    except Exception as e:
        issues.append(f"Ошибка импорта Nuitka: {e}")
        solutions.append("Установите Nuitka: pip install nuitka")
    
    
    try:
        
        result = subprocess.run(['where', 'cl'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ MSVC компилятор найден")
        else:
            
            result = subprocess.run(['where', 'gcc'], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ GCC компилятор найден")
            else:
                issues.append("C++ компилятор не найден")
                solutions.append("Установите Visual Studio Build Tools или MinGW-w64")
    except Exception:
        issues.append("Не удалось проверить компилятор")
        solutions.append("Установите Visual Studio Build Tools")
    
    
    import psutil
    disk_usage = psutil.disk_usage('C:/')
    free_gb = disk_usage.free / (1024**3)
    
    if free_gb < 3:
        issues.append(f"Мало места на диске C: ({free_gb:.1f} GB)")
        solutions.append("Освободите место на диске (нужно минимум 3 GB)")
    
    
    import ctypes
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            issues.append("Нет прав администратора")
            solutions.append("Запустите скрипт от имени администратора")
        else:
            print("✅ Права администратора есть")
    except:
        print("⚠️ Не удалось проверить права администратора")
    
    
    if issues:
        print("\n❌ Найдены проблемы:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        
        print("\n🔧 Рекомендуемые решения:")
        for i, solution in enumerate(solutions, 1):
            print(f"  {i}. {solution}")
        
        return False
    else:
        print("\n✅ Nuitka готов к работе!")
        return True
    
def fix_nuitka_install():
    """Пытается исправить установку Nuitka"""
    try:
        print("Переустановка Nuitka...")
        
        
        subprocess.run([sys.executable, '-m', 'pip', 'uninstall', 'nuitka', '-y'], 
                      capture_output=True)
        
        
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], 
                      check=True, capture_output=True)
        
        
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'nuitka'], 
                      check=True, capture_output=True)
        
        print("✅ Nuitka переустановлен")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка переустановки: {e}")
        return False


def fallback_to_pyinstaller_optimized(user_id, token, temp_dir):
    """Оптимизированная версия PyInstaller если Nuitka не работает"""
    try:
        logging.info("Используем оптимизированный PyInstaller как fallback")
        
        
        spec_content = f'''

import sys
import os

block_cipher = None

a = Analysis(
    ['{temp_dir}/main.py'],
    pathex=['{temp_dir}'],
    binaries=[],
    datas=[
        ('{temp_dir}/live_control.html', '.'),
        ('{temp_dir}/user_programs.json', '.'),
    ],
    hiddenimports=[
        'telegram', 'telegram.ext',
        'pyautogui', 'cv2', 'numpy',
        'PIL', 'mss', 'psutil', 'requests'
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PCController_{user_id}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
)
'''
        
        spec_path = os.path.join(temp_dir, 'minimal.spec')
        with open(spec_path, 'w') as f:
            f.write(spec_content)
        
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--clean', '--noconfirm',
            spec_path
        ]
        
        result = subprocess.run(cmd, cwd=temp_dir, timeout=300)
        
        if result.returncode == 0:
            exe_path = os.path.join(temp_dir, 'dist', f'PCController_{user_id}.exe')
            if os.path.exists(exe_path):
                return exe_path
        
        return None
        
    except Exception as e:
        logging.error(f"Fallback PyInstaller ошибка: {e}")
        return None

def check_and_install_nuitka():
    """Проверяет и устанавливает Nuitka если нужно"""
    try:
        result = subprocess.run([sys.executable, '-c', 'import nuitka'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            logging.info("Nuitka уже установлен")
            return True
    except:
        pass
    
    try:
        logging.info("Устанавливаю Nuitka...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'nuitka'], 
                     check=True, capture_output=True, timeout=120)
        logging.info("Nuitka установлен успешно")
        return True
    except Exception as e:
        logging.error(f"Не удалось установить Nuitka: {e}")
        return False

def cleanup_f_drive():
    """Очищает временные файлы на диске F:"""
    try:
        f_temp_dir = "F:/temp"
        if os.path.exists(f_temp_dir):
            
            import time
            current_time = time.time()
            
            for item in os.listdir(f_temp_dir):
                item_path = os.path.join(f_temp_dir, item)
                if os.path.isdir(item_path):
                    
                    created_time = os.path.getctime(item_path)
                    age_hours = (current_time - created_time) / 3600
                    
                    if age_hours > 24:  
                        try:
                            shutil.rmtree(item_path)
                            logging.info(f"Удалена старая папка: {item_path}")
                        except:
                            pass
    except Exception as e:
        logging.error(f"Ошибка очистки F: диска: {e}")

def diagnose_f_drive():
    """Диагностирует диск F: для сборки"""
    try:
        
        if not os.path.exists("F:/"):
            print("❌ Диск F: недоступен")
            return False
        
        
        f_stats = shutil.disk_usage("F:/")
        f_free_gb = f_stats.free / (1024**3)
        f_total_gb = f_stats.total / (1024**3)
        
        print(f"✅ Диск F: доступен")
        print(f"✅ Свободно: {f_free_gb:.1f} GB из {f_total_gb:.1f} GB")
        
        if f_free_gb < 3:
            print(f"⚠️  Мало места на F: ({f_free_gb:.1f} GB < 3 GB)")
            return False
        
        
        test_dir = "F:/test_build_access"
        try:
            os.makedirs(test_dir, exist_ok=True)
            os.rmdir(test_dir)
            print("✅ Есть права на создание папок")
        except Exception as e:
            print(f"❌ Нет прав на создание папок: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка проверки F: диска: {e}")
        return False

def upload_to_fileio(file_path):
    """Загружает файл на file.io"""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post('https://file.io', files=files, timeout=60)
            
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('link')
        
        return None
        
    except Exception as e:
        logging.error(f"Ошибка загрузки на file.io: {e}")
        return None

def message_handler(update: Update, context: CallbackContext):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    text = update.message.text
    
    user_data = get_user_data(user_id)
    status = user_data.get('status', '')
    
    if text == "🏠 Главное меню":
        start_handler(update, context)
        return
    
    if text == "📋 Функции программы":
        functions_handler(update, context)
        return
    
    if text == "🔑 Ввести токен бота":
        token_input_handler(update, context)
        return
    
    if text == "💬 Поддержка":
        support_text = """
💬 ПОДДЕРЖКА

📧 Контакты для связи:
• Telegram: @nocock
• Email: support@example.com

🔧 Частые вопросы:
• Как создать бота? - обратитесь к @BotFather
• Программа не запускается? - проверьте установку Python
• Антивирус блокирует? - добавьте в исключения

⏰ Время ответа: обычно в течение 24 часов
        """
        update.message.reply_text(support_text)
        return
    
    
    if status == 'waiting_token':
        token = text.strip()
        
        update.message.reply_text("⏳ Проверяю токен...")
        
        if validate_token(token):
            user_data['token'] = token
            user_data['status'] = 'token_validated'
            set_user_data(user_id, user_data)
            
            
            keyboard = [
                [InlineKeyboardButton("📦 ZIP архив", callback_data="get_zip")],
                [InlineKeyboardButton("⚙️ EXE файл", callback_data="get_exe")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            success_text = f"""
✅ Токен принят!

🤖 Информация о боте:
• Токен: {token[:10]}...
• Ваш ID: {user_id}

Выберите формат получения программы:

📦 ZIP архив - исходные файлы Python
⚙️ EXE файл - готовая к запуску программа

Оба варианта будут защищены уникальным паролем.
            """
            
            update.message.reply_text(success_text, reply_markup=reply_markup)
            
        else:
            keyboard = [[KeyboardButton("🔑 Попробовать еще раз")], [KeyboardButton("🏠 Главное меню")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            error_text = """
❌ Неверный токен!

Токен должен иметь вид:
1234567890:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

🔧 Проверьте:
• Скопирован ли токен полностью
• Нет ли лишних пробелов
• Активен ли бот (напишите ему /start)

Попробуйте еще раз:
            """
            
            update.message.reply_text(error_text, reply_markup=reply_markup)
    
    else:
        
        keyboard = [
            [KeyboardButton("📋 Функции программы")],
            [KeyboardButton("🔑 Ввести токен бота")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        update.message.reply_text(
            "❓ Не понимаю эту команду. Используйте кнопки меню:",
            reply_markup=reply_markup
        )

def send_exe_file(context, user_id, exe_path, query):
   """Универсальная функция отправки EXE файла"""
   try:
       file_size_mb = os.path.getsize(exe_path) / (1024 * 1024)
       
       
       if file_size_mb < 50:
           query.edit_message_text("📤 Отправляю файл через Telegram...")
           
           try:
               with open(exe_path, 'rb') as f:
                   context.bot.send_document(
                       chat_id=user_id,
                       document=f,
                       filename=f'PCController_{user_id}.exe',
                       caption=f"""
⚙️ Ваш PC Controller готов!

📏 Размер: {file_size_mb:.1f} MB
📋 Запускайте от имени администратора
🔒 Файл содержит ваши персональные настройки
                       """,
                       timeout=300
                   )
               
               return True
               
           except Exception as e:
               logging.error(f"Ошибка отправки через Telegram: {e}")
               
               pass
       
       
       query.edit_message_text("📤 Загружаю на file.io...")
       download_link = upload_to_fileio(exe_path)
       
       if download_link:
           success_message = f"""
⚙️ Ваш EXE файл готов!

🔗 Ссылка для скачивания:
{download_link}

📏 Размер: {file_size_mb:.1f} MB
⚠️ Файл удалится после первого скачивания!
📋 Запускайте от имени администратора
🔒 Файл содержит ваши персональные настройки
           """
           
           context.bot.send_message(
               chat_id=user_id,
               text=success_message
           )
           
           return True
       else:
           query.edit_message_text("""
❌ Не удалось загрузить файл.

🔄 Попробуйте:
1. Запросить ZIP архив
2. Попробовать позже
3. Обратиться в поддержку
           """)
           
           return False
           
   except Exception as e:
       logging.error(f"Ошибка отправки EXE файла: {e}")
       query.edit_message_text(f"❌ Ошибка отправки файла: {str(e)[:100]}")
       return False

def button_callback(update: Update, context: CallbackContext):
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "main_menu":
        
        query.edit_message_text("🏠 Главное меню")
        start_handler(query, context)
        return
    
    user_data = get_user_data(user_id)
    token = user_data.get('token')
    
    if not token:
        query.edit_message_text("❌ Сначала введите токен бота!")
        return
    
    if data == "get_zip":
        query.edit_message_text("📦 Создание ZIP архива...")
        
        
        zip_path, password = create_zip_package(user_id, token)
        
        if zip_path and os.path.exists(zip_path):
            try:
                
                with open(zip_path, 'rb') as f:
                    context.bot.send_document(
                        chat_id=user_id,
                        document=f,
                        filename=f'PCController_{user_id}.zip',
                        caption=f"""
📦 Ваш PC Controller готов!

🔐 Пароль архива: `{password}`
📁 Содержимое: main.py, HTML, JSON, requirements.txt

📋 Инструкция по установке включена в архив.
                        """,
                        parse_mode='Markdown'
                    )
                
                
                user_data['last_generation'] = datetime.now().isoformat()
                user_data['generation_count'] = user_data.get('generation_count', 0) + 1
                set_user_data(user_id, user_data)
                
                
                try:
                    context.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=f"✅ ZIP сгенерирован для @{query.from_user.username} (ID: {user_id})"
                    )
                except:
                    pass
                
            except Exception as e:
                logging.error(f"Ошибка отправки ZIP: {e}")
                query.edit_message_text("❌ Ошибка при отправке файла. Попробуйте еще раз.")
                
            finally:
                
                try:
                    temp_dir = os.path.dirname(zip_path)
                    shutil.rmtree(temp_dir)
                except:
                    pass
        else:
            query.edit_message_text("❌ Ошибка создания архива. Попробуйте позже.")
        
    elif data == "get_exe":
        query.edit_message_text("🔧 Проверяю Nuitka...")
        
        
        if not diagnose_nuitka_issues():
            if not fix_nuitka_install():
                query.edit_message_text("❌ Nuitka недоступен. Попробуйте ZIP архив или обратитесь в поддержку.")
                return
        
        query.edit_message_text("⚙️ Создание EXE с Nuitka... (3-5 минут)")
        
        try:
            exe_path = build_exe_for_user_f_drive_nuitka(user_id, token, use_f_drive=True)
            
            if exe_path and os.path.exists(exe_path):
                size_mb = os.path.getsize(exe_path) / (1024 * 1024)
                logging.info(f"Файл создан: {exe_path}, размер: {size_mb:.1f} MB")
                
                if send_exe_file(context, user_id, exe_path, query):
                    user_data['last_generation'] = datetime.now().isoformat()
                    user_data['generation_count'] = user_data.get('generation_count', 0) + 1
                    set_user_data(user_id, user_data)
            else:
                
                query.edit_message_text("⚙️ Nuitka не сработал, пробую PyInstaller...")
                fallback_exe = fallback_to_pyinstaller_optimized(user_id, token, temp_dir)
                
                if fallback_exe:
                    send_exe_file(context, user_id, fallback_exe, query)
                else:
                    query.edit_message_text("❌ Ошибка сборки EXE. Попробуйте ZIP архив.")
                    
        except Exception as e:
            logging.error(f"Ошибка создания EXE: {e}")
            query.edit_message_text(f"❌ Ошибка: попробуйте ZIP архив")
        
        finally:
            cleanup_f_drive()

def error_handler(update: Update, context: CallbackContext):
    """Обработчик ошибок"""
    logging.error(f"Ошибка: {context.error}")

def admin_stats(update: Update, context: CallbackContext):
    """Статистика для админа"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    
    total_users = len(users_data)
    active_users = len([u for u in users_data.values() if u.get('token')])
    total_generations = sum(u.get('generation_count', 0) for u in users_data.values())
    
    stats_text = f"""
📊 СТАТИСТИКА БОТА

👥 Пользователи: {total_users}
✅ С токенами: {active_users}
⚙️ Всего генераций: {total_generations}

📈 Последние пользователи:
    """
    
    
    recent_users = sorted(
        users_data.items(),
        key=lambda x: x[1].get('last_generation', ''),
        reverse=True
    )[:5]
    
    for user_id, data in recent_users:
        if 'last_generation' in data:
            stats_text += f"\n• {user_id}: {data.get('generation_count', 0)} генераций"
    
    update.message.reply_text(stats_text)

def main():

    
    """Основная функция"""
    if not GENERATOR_BOT_TOKEN or GENERATOR_BOT_TOKEN == "YOUR_GENERATOR_BOT_TOKEN":
        print("❌ Установите GENERATOR_BOT_TOKEN в коде!")
        return
    
    if ADMIN_CHAT_ID == 123456789:
        print("❌ Установите ADMIN_CHAT_ID в коде!")
        return
    
    
    if not os.path.exists('pc_controller_template.py'):
        print("❌ Не найден файл pc_controller_template.py!")
        print("Переименуйте ваш main.py в pc_controller_template.py")
        return
    
    print("🤖 Запуск бота-генератора...")

    if check_and_install_nuitka():
        print("Nuitka готов к использованию - быстрая сборка EXE")
    else:
        print("Nuitka недоступен - будет использован резервный метод")

    if diagnose_nuitka_issues():
        print("Все чики пуки")
    else:
        fix_nuitka_install()

    cleanup_f_drive()

    
    load_users_data()
    
    
    updater = Updater(GENERATOR_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    
    dp.add_handler(CommandHandler("start", start_handler))
    dp.add_handler(CommandHandler("stats", admin_stats))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_error_handler(error_handler)
    
    
    updater.start_polling()
    print("✅ Бот-генератор запущен!")
    print(f"📊 Загружено {len(users_data)} пользователей")
    
    try:
        updater.idle()
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
        updater.stop()


if __name__ == "__main__":
    main()
