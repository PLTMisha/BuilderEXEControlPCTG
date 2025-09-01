import os
import sys
import time
import io
import threading
import logging
import subprocess
import platform
import socket
import json
import shutil
import tempfile
from datetime import datetime
from functools import wraps
import pyautogui
import asyncio
import cv2
import numpy as np
import json
from aiortc import RTCPeerConnection, VideoStreamTrack
from aiortc.contrib.media import MediaStreamTrack
from flask_socketio import SocketIO, emit
import mss
import requests
from pyngrok import ngrok
from telegram import KeyboardButton, ReplyKeyboardMarkup, InputFile, Update, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from flask import Flask, Response, request, render_template_string, abort
from PIL import Image
import psutil
import sounddevice as sd
import scipy.io.wavfile as wavfile
import pyperclip
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import win32gui
import win32con


try:
    import speedtest
except Exception:
    speedtest = None


TOKEN = "PLACEHOLDER_TOKEN"   
OWNER_CHAT_ID = 0  
WEB_PASSWORD = "controlpcTG"        
STREAM_PORT = 5000                
STREAM_FPS = 24          
SCREENSHOT_Q = 75      
LOGFILE = "controlPCLog.log"
NGROK_TOKEN = "31nhzoymJ4sJ8Jf2NtggDJjlkFi_77zToVJpj8LhCAE33vAPS"  
NGROK_PATH = "ngrok"
NGROK_AUTH = ""
PYNGROK_AVAILABLE = True
try:
    from pyngrok import ngrok, conf as ngrok_conf
except Exception:
    PYNGROK_AVAILABLE = False
    ngrok = None
    ngrok_conf = None
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
_stream_running = False
_stream_lock = threading.Lock()
_ngrok_tunnel = None
_ngrok_lock = threading.Lock()

pcs = set()  
screen_track = None

STREAM_MONITOR_INDEX = 0


PROGRAMS_FILE = "user_programs.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOGFILE), logging.StreamHandler(sys.stdout)]
)

cpu_ram_data = {
    "times": [],
    "cpu": [],
    "ram": []
}
cpu_ram_lock = threading.Lock()  
data_collection_running = False

SELECTED_CAMERA_INDEX = 0

_ngrok_lock = threading.Lock()

awaiting = {}


def main_menu_keyboard():
    kb = [
        [KeyboardButton("🖥 Система"), KeyboardButton("🔊 Звук")],
        [KeyboardButton("📂 Файлы"), KeyboardButton("📡 Сеть")],
        [KeyboardButton("📸 Медиа"), KeyboardButton("⌨ Ввод")],
        [KeyboardButton("⚙ Мониторинг"), KeyboardButton("🖥 Программы и Игры")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def system_menu_keyboard():
    kb = [
        [KeyboardButton("🔄 Перезагрузить"), KeyboardButton("⏹ Выключить")],
        [KeyboardButton("🔁 Reboot to BIOS"), KeyboardButton("🔒 Блокировать")],
        [KeyboardButton("🖼 Сменить обои"), KeyboardButton("💡 Яркость")],
        [KeyboardButton("🖥 Экран Вкл/Выкл"), KeyboardButton("➖ Свернуть все окна")],
        [KeyboardButton("🚫 Закрыть все окна"), KeyboardButton("🗑 Очистить корзину")],  
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def files_menu_keyboard():
    kb = [
        [KeyboardButton("📋 Листинг"), KeyboardButton("⬆ Загрузить файл на ПК"), ],
        [KeyboardButton("🗑 Удалить"), KeyboardButton("🔎 Поиск")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def network_menu_keyboard():
    kb = [
        [KeyboardButton("🔍 Сканер LAN"), KeyboardButton("📶 Ping")],
        [KeyboardButton("⚡ Speedtest"), KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def media_menu_keyboard():
    kb = [
        [KeyboardButton("📷 Скриншот"), KeyboardButton("📹 Запись Экрана")],
        [KeyboardButton("📸 Вебкам фото"), KeyboardButton("🎥 Вебкам видео")],
        [KeyboardButton("⏱ Авто-скрины"), KeyboardButton("🖥 Live Control")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def input_menu_keyboard():
    kb = [
        [KeyboardButton("⌨ Ввести текст"), KeyboardButton("🖥 Виртуальная клавиатура")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def monitor_menu_keyboard():
    kb = [
        [KeyboardButton("ℹ️ Sysinfo"), KeyboardButton("📈 График CPU/RAM (день)")],
        [KeyboardButton("📝 Лог окон"),KeyboardButton("🌡️Температуры")],
        [KeyboardButton("🔙 Назад")]
        ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def sound_menu_keyboard():
    kb = [
        [KeyboardButton("🔊 Громкость"), KeyboardButton("⏯ Пауза/Воспроизведение")],
        [KeyboardButton("⏭ Следующий трек"), KeyboardButton("⏮ Предыдущий трек")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def owner_only(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        try:
            user = update.effective_chat.id
        except Exception:
            return
        if user != OWNER_CHAT_ID:
            logging.warning("Unauthorized access by %s", user)
            try:
                update.message.reply_text("Доступ запрещён.")
            except:
                pass
            return
        return func(update, context, *args, **kwargs)
    return wrapper 



@owner_only
def start_handler(update: Update, context: CallbackContext):
    update.message.reply_text("Привет! Выбери категорию:", reply_markup=main_menu_keyboard())

@owner_only
def help_cmd(update: Update, context: CallbackContext):
    update.message.reply_text("Нажми /start чтобы открыть главное меню с кнопками.")

@owner_only
def message_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    
    if text == "🖥 Система":
        update.message.reply_text("🖥 Управление системой:", reply_markup=system_menu_keyboard())
        return
    elif text == "📂 Файлы":
        update.message.reply_text("📂 Файлы:", reply_markup=files_menu_keyboard())
        return
    elif text == "📡 Сеть":
        update.message.reply_text("📡 Сеть:", reply_markup=network_menu_keyboard())
        return
    elif text == "📸 Медиа":
        update.message.reply_text("📸 Медиа:", reply_markup=media_menu_keyboard())
        return
    elif text == "⌨ Ввод":
        update.message.reply_text("⌨ Ввод:", reply_markup=input_menu_keyboard())
        return
    elif text == "⚙ Мониторинг":
        update.message.reply_text("⚙ Мониторинг:", reply_markup=monitor_menu_keyboard())
        return
    elif text == "🔊 Звук":
        update.message.reply_text("🔊 Управление звуком:", reply_markup=sound_menu_keyboard())
        return
    elif text == "🖥 Программы и Игры":
        update.message.reply_text("🚀 Выбери программу:", reply_markup=programs_menu_keyboard())
        return True
    elif text == "🔙 Назад":
        update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())
        return
    if text.startswith("📱 "):
        program_name = text[2:].lower().replace(' ', '_')
        
        if program_name in PROGRAMS:
            try:
                subprocess.Popen(PROGRAMS[program_name])
                update.message.reply_text(f"✅ Запустил {text[2:]}.", reply_markup=programs_menu_keyboard())
            except Exception as e:
                update.message.reply_text(f"❌ Ошибка запуска: {e}", reply_markup=programs_menu_keyboard())
        else:
            update.message.reply_text("❌ Программа не найдена", reply_markup=programs_menu_keyboard())
        return True
    
    
    if text == "➕ Добавить программу":
        awaiting[chat_id] = {"action": "add_program_name"}
        update.message.reply_text(
            "📝 Напиши название программы (одним словом, без пробелов):\n"
            "Пример: notepad, photoshop, chrome",
            reply_markup=ReplyKeyboardRemove()
        )
        return True
    
    
    elif text == "➖ Удалить программу":
        if not PROGRAMS:
            update.message.reply_text(
                "❌ Нет программ для удаления",
                reply_markup=programs_menu_keyboard()
            )
            return True
        
        awaiting[chat_id] = {"action": "remove_program_name"}
        kb = []
        for name in PROGRAMS.keys():
            display_name = name.replace('_', ' ').title()
            kb.append([KeyboardButton(f"🗑 {display_name}")])
        kb.append([KeyboardButton("🔙 Отменить")])
        
        update.message.reply_text(
            "🗑 Выбери программу для удаления:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return True
    
    
    elif text == "📋 Список программ":
        list_programs_cmd(update, context)
        return True
    


    
    if text == "🔄 Перезагрузить":
        update.message.reply_text("Перезагружаю систему...")
        threading.Thread(target=do_restart_action, daemon=True).start()
        update.message.reply_text("Команда отправлена.", reply_markup=system_menu_keyboard())
        return
    elif text == "⏹ Выключить":
        update.message.reply_text("Выключаю систему...")
        threading.Thread(target=do_shutdown_action, daemon=True).start()
        update.message.reply_text("Команда отправлена.", reply_markup=system_menu_keyboard())
        return
    elif text == "🔁 Reboot to BIOS":
        update.message.reply_text("Перезагрузка в BIOS (если поддерживается)...")
        threading.Thread(target=do_reboot_to_bios, daemon=True).start()
        update.message.reply_text("Команда отправлена.", reply_markup=system_menu_keyboard())
        return
    elif text == "🔒 Блокировать":
        update.message.reply_text("Блокировка...")
        do_lock_action()
        update.message.reply_text("Система заблокирована.", reply_markup=system_menu_keyboard())
        return
    elif text == "🖼 Сменить обои":
        awaiting[chat_id] = {"action": "sys_wallpaper"}
        update.message.reply_text("Отправь файл изображения в чат, чтобы изменить обои.", reply_markup=ReplyKeyboardRemove())
        return
    elif text == "🔊 Громкость":
        awaiting[chat_id] = {"action": "sys_volume"}
        update.message.reply_text("Отправь число (0-100) для установки громкости.", reply_markup=ReplyKeyboardRemove())
        return
    elif text == "💡 Яркость":
        awaiting[chat_id] = {"action": "sys_brightness"}
        update.message.reply_text("Отправь число (0-100) для установки яркости.", reply_markup=ReplyKeyboardRemove())
        return
    elif text == "🖥 Экран Вкл/Выкл":
        kb = [
            [KeyboardButton("Выключить экран"), KeyboardButton("Включить экран")],
            [KeyboardButton("🔙 Назад")]
        ]
        update.message.reply_text("Экран:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return
    elif text == "Выключить экран":
        set_display_power(off=True)
        update.message.reply_text("Экран выключен (если поддерживается).", reply_markup=system_menu_keyboard())
        return
    elif text == "Включить экран":
        set_display_power(off=False)
        update.message.reply_text("Попытка включить экран.", reply_markup=system_menu_keyboard())
        return
    elif text == "➖ Свернуть все окна":
        minimize_all_windows()
        update.message.reply_text("Все окна свернуты.", reply_markup=system_menu_keyboard())
        return
    elif text == "🚫 Закрыть все окна":
        awaiting[chat_id] = {"action": "sys_close_all_confirm"}
        kb = [
            [KeyboardButton("✅ Подтвердить"), KeyboardButton("❌ Отменить")]
        ]
        update.message.reply_text("Вы уверены, что хотите закрыть все окна?", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return
    elif text == "✅ Подтвердить" and chat_id in awaiting and awaiting[chat_id].get("action") == "sys_close_all_confirm":
        awaiting.pop(chat_id)
        update.message.reply_text("Закрываю все окна...")
        close_all_windows()
        update.message.reply_text("Готово.", reply_markup=system_menu_keyboard())
        return
    elif text == "❌ Отменить" and chat_id in awaiting and awaiting[chat_id].get("action") == "sys_close_all_confirm":
        awaiting.pop(chat_id)
        update.message.reply_text("Действие отменено.", reply_markup=system_menu_keyboard())
        return

    if text == "🔊 Громкость":
        awaiting[chat_id] = {"action": "sys_volume"}
        update.message.reply_text("Отправь число (0-100) для установки громкости.", reply_markup=ReplyKeyboardRemove())
        return
    elif text == "⏯ Пауза/Воспроизведение":
        pause_play()
        update.message.reply_text("Команда паузы/воспроизведения отправлена.", reply_markup=sound_menu_keyboard())
        return
    elif text == "⏭ Следующий трек":
        next_track()
        update.message.reply_text("Команда следующего трека отправлена.", reply_markup=sound_menu_keyboard())
        return
    elif text == "⏮ Предыдущий трек":
        prev_track()
        update.message.reply_text("Команда предыдущего трека отправлена.", reply_markup=sound_menu_keyboard())
        return


    if text == "📋 Листинг":
        awaiting[chat_id] = {"action": "files_list"}
        update.message.reply_text("Напиши путь до папки для листинга (или . для текущей).", reply_markup=ReplyKeyboardRemove())
        return
    elif text == "⬆ Загрузить файл на ПК":
        awaiting[chat_id] = {"action": "files_upload"}
        update.message.reply_text("Отправь файл в чат — он будет загружен в домашнюю папку на ПК.", reply_markup=ReplyKeyboardRemove())
        return
    elif text == "🗑 Удалить":
        awaiting[chat_id] = {"action": "files_delete"}
        update.message.reply_text("Напиши путь к файлу/папке для удаления.", reply_markup=ReplyKeyboardRemove())
        return
    elif text == "🔎 Поиск":
        awaiting[chat_id] = {"action": "files_search"}
        update.message.reply_text("Напиши путь и шаблон через | (пример: C:\\Users\\User|*.txt) или /home/user|report", reply_markup=ReplyKeyboardRemove())
        return


    elif text == "🔍 Сканер LAN":
        update.message.reply_text("Запускаю LAN сканер, подождите...")
        
        def lan_scan_run():
            out = lan_scan()
            for chunk in chunk_text(out, 3000):
                context.bot.send_message(chat_id=chat_id, text=chunk)
            context.bot.send_message(chat_id=chat_id, text="✅ LAN сканирование завершено!")
        
        threading.Thread(target=lan_scan_run, daemon=True).start()
        return
    elif text == "📶 Ping":
        awaiting[chat_id] = {"action": "net_ping"}
        update.message.reply_text("Напиши адрес для ping (пример: 8.8.8.8 или example.com).", reply_markup=ReplyKeyboardRemove())
        return
    elif text == "⚡ Speedtest":
        update.message.reply_text("Запускаю speedtest, пожалуйста подождите (30-40 секунд)")
        
        def st_run():
            res = do_speedtest()
            context.bot.send_message(chat_id=chat_id, text=res)
            context.bot.send_message(chat_id=chat_id, text="✅ Speedtest завершен!")
        
        threading.Thread(target=st_run, daemon=True).start()
    

    if text == "📷 Скриншот":
        mons = count_physical_monitors()
        if mons >= 2:
            awaiting[chat_id] = {"action": "choose_monitor_for_screenshot"}
            kb = [
                [KeyboardButton("Оба монитора")],
                [KeyboardButton("📺Первый монитор")],
                [KeyboardButton("📺Второй монитор")],
                [KeyboardButton("🔙 Назад")]
            ]
            update.message.reply_text("Выбери что скринить:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
            return
        else:
            update.message.reply_text("Делаю скриншот...")
            path = f"screenshot_{int(time.time())}.jpg"
            if take_screenshot_save(path, monitor_index=1):
                context.bot.send_photo(chat_id=chat_id, photo=open(path, "rb"))
                os.remove(path)
                update.message.reply_text("Скриншот отправлен.", reply_markup=media_menu_keyboard())
            else:
                update.message.reply_text("Ошибка создания скриншота.", reply_markup=media_menu_keyboard())
            return

    elif text == "📹 Запись Экрана":
        mons = count_physical_monitors()
        if mons >= 2:
            awaiting[chat_id] = {"action": "choose_monitor_for_screenrec"}
            kb = [
                [KeyboardButton("Оба монитора")],
                [KeyboardButton("📺Первый монитор")],
                [KeyboardButton("📺Второй монитор")],
                [KeyboardButton("🔙 Назад")]
            ]
            update.message.reply_text("Выбери монитор для записи экрана:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
            return
        else:
            awaiting[chat_id] = {"action": "media_screenrec"}
            update.message.reply_text("Напиши длительность записи в секундах (пример: 10).", reply_markup=ReplyKeyboardRemove())
            return
        
    elif text == "🗑 Очистить корзину":
        update.message.reply_text("Очищаю корзину...")
        success = empty_recycle_bin()
        if success:
            update.message.reply_text("Корзина очищена.", reply_markup=system_menu_keyboard())
        else:
            update.message.reply_text("Ошибка при очистке корзины.", reply_markup=system_menu_keyboard())
        return
    elif text == "📸 Вебкам фото":
        
        if is_windows():
            cameras = get_camera_names_windows()
        else:
            cameras = get_available_cameras()
        
        if not cameras:
            update.message.reply_text("Камеры не найдены.", reply_markup=media_menu_keyboard())
            return
        elif len(cameras) == 1:
            
            update.message.reply_text("Делаю фото с веб-камеры...")
            path = f"webcam_{int(time.time())}.jpg"
            if webcam_photo_improved(path, cameras[0]['index']):
                context.bot.send_photo(chat_id=chat_id, photo=open(path, "rb"))
                try: os.remove(path)
                except: pass
                update.message.reply_text("Фото отправлено.", reply_markup=media_menu_keyboard())
            else:
                update.message.reply_text("Камера недоступна.", reply_markup=media_menu_keyboard())
            return
        else:
            
            awaiting[chat_id] = {
                "action": "choose_camera_for_photo", 
                "cameras": cameras
            }
            
            
            kb = []
            for camera in cameras:
                kb.append([KeyboardButton(f"{camera['name']}")])
            kb.append([KeyboardButton("🔙 Назад")])
            
            update.message.reply_text("Выбери камеру для фото:", 
                                    reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
            return
    elif text == "🎥 Вебкам видео":
        update.message.reply_text("Ищу доступные камеры...")
        handle_webcam_video_selection(update, context, chat_id)
        
        
        if not cameras:
            update.message.reply_text("Камеры не найдены.", reply_markup=media_menu_keyboard())
            return
        elif len(cameras) == 1:
            
            awaiting[chat_id] = {
                "action": "media_webcam_video", 
                "camera_index": cameras[0]['index']
            }
            update.message.reply_text("Напиши длительность записи в секундах (пример: 10).", 
                                    reply_markup=ReplyKeyboardRemove())
            return
        else:
            
            awaiting[chat_id] = {
                "action": "choose_camera_for_video", 
                "cameras": cameras
            }
            
            
            kb = []
            for camera in cameras:
                kb.append([KeyboardButton(f"{camera['name']}")])
            kb.append([KeyboardButton("🔙 Назад")])
            
            update.message.reply_text("Выбери камеру для видео:", 
                                    reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
            return
    elif text == "⏱ Авто-скрины":
        awaiting[chat_id] = {"action": "media_autoscreens"}
        update.message.reply_text("Напиши интервал в минутах для автоматических скриншотов (0 для остановки).", reply_markup=ReplyKeyboardRemove())
        return

    elif text == "🖥 Live Control":

        mons = count_physical_monitors()
        debug_monitors()
        if mons >= 2:
            awaiting[chat_id] = {"action": "choose_monitor_for_live"}
            kb = [
                [KeyboardButton("Оба монитора")],
                [KeyboardButton("📺Первый монитор")],
                [KeyboardButton("📺Второй монитор")],
                [KeyboardButton("🔙 Назад")]
            ]
            update.message.reply_text("Выбери монитор для Live Control:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
            return

        update.message.reply_text("Запускаю live-панель...")
        start_flask_thread()
        ip = get_local_ip()
        local_url = f"http://{ip}:{STREAM_PORT}/?pw={WEB_PASSWORD}"
        msg = f"Live панель запущена локально:\n{local_url}\n\n"
        
        
        logging.info(f"PYNGROK_AVAILABLE: {PYNGROK_AVAILABLE}")
        logging.info(f"NGROK_TOKEN set: {bool(NGROK_TOKEN)}")
        
        if PYNGROK_AVAILABLE and NGROK_TOKEN:
            url = start_ngrok_tunnel()
            if url:
                msg += f"Доступ через ngrok: {url}/?pw={WEB_PASSWORD}\nПароль: {WEB_PASSWORD}\nНажми /stop_realtime чтобы остановить."
            else:
                msg += "Не удалось запустить ngrok. Проверь логи для деталей."
        else:
            reasons = []
            if not PYNGROK_AVAILABLE:
                reasons.append("pyngrok не установлен")
            if not NGROK_TOKEN:
                reasons.append("NGROK_TOKEN пуст")
            msg += f"ngrok недоступен: {', '.join(reasons)}"
        
        update.message.reply_text(msg, reply_markup=media_menu_keyboard())
        return


    if text == "⌨ Ввести текст":
        awaiting[chat_id] = {"action": "type_text"}
        update.message.reply_text("Напиши текст, который нужно ввести в активное окно.", reply_markup=ReplyKeyboardRemove())
        return
    elif text == "🖥 Виртуальная клавиатура":
        keyboard = virtual_keyboard_layout()
        update.message.reply_text("Виртуальная клавиатура ПК:", reply_markup=keyboard)
        return
    elif text in ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "A", "S", "D", "F", "G", "H", "J", "K", "L", "Z", "X", "C", "V", "B", "N", "M", "Пробел", "Enter", "Backspace", ".", '?', "!"]:
        logging.info(f"Virtual keyboard: Processing key '{text}'")  
        try:
            if text == "Пробел":
                pyautogui.press('space')
                logging.info("Pressed: space")
            elif text == "Enter":
                pyautogui.press('enter')
                logging.info("Pressed: enter")
            elif text == "Backspace":
                pyautogui.press('backspace')
                logging.info("Pressed: backspace")
            elif text == ".":
                pyautogui.press('.')
                logging.info("Pressed: .")
            elif text == "?":
                pyautogui.press("?")
                logging.info("Pressed: ?")           
            elif text == "!":
                pyautogui.press("!")
                logging.info("Pressed: !")               
            else:
                pyautogui.press(text.lower())
                logging.info(f"Pressed: {text.lower()}")
            
            
            keyboard = virtual_keyboard_layout()
            update.message.reply_text(f"✅ Нажата клавиша: {text}", reply_markup=keyboard)
        except Exception as e:
            logging.exception("virtual keyboard press failed")
            keyboard = virtual_keyboard_layout()
            update.message.reply_text(f"❌ Ошибка нажатия клавиши: {e}", reply_markup=keyboard)
        return
    elif text == "⏺ Записать макрос":
        awaiting[chat_id] = {"action": "macro_record"}
        update.message.reply_text("Функция записи макроса (заглушка) — напиши имя макроса и выполненные действия позже.", reply_markup=ReplyKeyboardRemove())
        return
    elif text == "▶ Воспроизвести макрос":
        awaiting[chat_id] = {"action": "macro_play"}
        update.message.reply_text("Напиши имя макроса для воспроизведения.", reply_markup=ReplyKeyboardRemove())
        return

    if text == "ℹ️ Sysinfo":
        update.message.reply_text("Получаю информацию о системе...")
        txt = get_sysinfo_text()
        context.bot.send_message(chat_id=chat_id, text=txt)
        update.message.reply_text("Готово.", reply_markup=monitor_menu_keyboard())
        return

    elif text == "📝 Лог окон":
        update.message.reply_text("Получаю лог окон...")
        try:
            if platform.system().lower() == "windows":
                try:
                    import win32gui
                    hwnd = win32gui.GetForegroundWindow()
                    window_title = win32gui.GetWindowText(hwnd) or "Без названия"
                    out = f"Текущее окно: {window_title}\n"
                    context.bot.send_message(chat_id=chat_id, text=out)
                except ImportError:
                    context.bot.send_message(chat_id=chat_id, text="Требуется pywin32. Установите: pip install pywin32")
                except Exception as e:
                    context.bot.send_message(chat_id=chat_id, text=f"Ошибка: {str(e)}")
            else:
                if shutil.which("wmctrl"):
                    try:
                        out = subprocess.check_output(["wmctrl", "-l"], universal_newlines=True, stderr=subprocess.DEVNULL)
                        context.bot.send_message(chat_id=chat_id, text=f"Список окон:\n{out}")
                    except Exception:
                        context.bot.send_message(chat_id=chat_id, text="Ошибка получения списка окон.")
                else:
                    context.bot.send_message(chat_id=chat_id, text="wmctrl не установлен. Установите: sudo apt install wmctrl")
        except Exception:
            logging.exception("window log failed")
            context.bot.send_message(chat_id=chat_id, text="Ошибка при получении лога окон.")
        update.message.reply_text("Готово.", reply_markup=monitor_menu_keyboard())
        return

    elif text == "🌡️Температуры":
        handle_temperature_request(update, context, chat_id)
        return

    elif text == "📈 График CPU/RAM (день)":
        update.message.reply_text("Создаю график CPU/RAM...")
        try:
            import matplotlib.pyplot as plt
            with cpu_ram_lock:
                if not cpu_ram_data["times"]:
                    context.bot.send_message(chat_id=chat_id, text="Нет данных для графика. Подождите, пока данные соберутся.")
                    update.message.reply_text("Готово.", reply_markup=monitor_menu_keyboard())
                    return
                times = [t - cpu_ram_data["times"][0] for t in cpu_ram_data["times"]]
                cpu_data = cpu_ram_data["cpu"]
                ram_data = cpu_ram_data["ram"]
            plt.figure(figsize=(10, 5))
            plt.plot(times, cpu_data, label="CPU (%)", color="blue")
            plt.plot(times, ram_data, label="RAM (%)", color="orange")
            plt.xlabel("Время (сек)")
            plt.ylabel("Загрузка (%)")
            plt.title("Загрузка CPU и RAM")
            plt.legend()
            plt.grid(True)
            graph_path = f"graph_{int(time.time())}.png"
            plt.savefig(graph_path)
            plt.close()
            context.bot.send_photo(chat_id=chat_id, photo=open(graph_path, "rb"))
            try:
                os.remove(graph_path)
            except:
                pass
            update.message.reply_text("График отправлен.", reply_markup=monitor_menu_keyboard())
        except ImportError:
            context.bot.send_message(chat_id=chat_id, text="Требуется matplotlib. Установите: pip install matplotlib")
        except Exception:
            logging.exception("graph failed")
            context.bot.send_message(chat_id=chat_id, text="Ошибка при создании графика.")
        return


    if chat_id in awaiting:
        info = awaiting.pop(chat_id)
        action = info.get("action")
        logging.info("Awaited action %s with text: %s", action, text)
        if action == "sys_wallpaper":
            if update.message.photo or update.message.document:
                try:
                    if update.message.photo:
                        file = update.message.photo[-1].get_file()
                        ext = ".jpg"
                    else:
                        file = update.message.document.get_file()
                        ext = os.path.splitext(update.message.document.file_name)[1] or ".dat"
                    dest = os.path.join(os.path.expanduser("~"), "wallpaper" + ext)
                    file.download(custom_path=dest)
                    ok = set_wallpaper(dest)
                    if ok:
                        update.message.reply_text("Обои изменены.", reply_markup=main_menu_keyboard())
                    else:
                        update.message.reply_text("Не удалось сменить обои автоматически. Попробуй вручную.", reply_markup=main_menu_keyboard())
                except Exception:
                    logging.exception("setting wallpaper from tg failed")
                    update.message.reply_text("Ошибка при получении файла.", reply_markup=main_menu_keyboard())
            else:
                update.message.reply_text("Ожидается файл изображения.", reply_markup=main_menu_keyboard())
            return

        if action == "choose_monitor_for_screenshot":
            mapping = {"Оба монитора": 0, "📺Первый монитор": 1, "📺Второй монитор": 2}
            idx = mapping.get(text.strip())
            if idx is None:
                update.message.reply_text("Неверный выбор. Попробуй еще раз через '📷 Скриншот'.", reply_markup=media_menu_keyboard())
                return
            path = f"screenshot_{int(time.time())}.jpg"
            if take_screenshot_save(path, monitor_index=idx):
                context.bot.send_photo(chat_id=chat_id, photo=open(path, "rb"))
                os.remove(path)
                update.message.reply_text("Скриншот отправлен.", reply_markup=media_menu_keyboard())
            else:
                update.message.reply_text("Ошибка создания скриншота.", reply_markup=media_menu_keyboard())
            return
        
        if action == "choose_monitor_for_screenrec":
            mapping = {"Оба монитора": 0, "📺Первый монитор": 1, "📺Второй монитор": 2}
            idx = mapping.get(text.strip())
            if idx is None:
                if text == "🔙 Назад":
                    update.message.reply_text("Действие отменено.", reply_markup=media_menu_keyboard())
                else:
                    update.message.reply_text("Неверный выбор. Попробуй еще раз через '📹 Запись Экрана'.", reply_markup=media_menu_keyboard())
                return
            
            awaiting[chat_id] = {"action": "media_screenrec", "monitor_index": idx}
            update.message.reply_text(f"Выбран монитор: {text}. Напиши длительность записи в секундах (пример: 10).", reply_markup=ReplyKeyboardRemove())
            return
        

        if action == "choose_monitor_for_live":
                    global STREAM_MONITOR_INDEX  
                    mapping = {"Оба монитора": 0, "📺Первый монитор": 1, "📺Второй монитор": 2}
                    idx = mapping.get(text.strip())
                    if idx is None:
                        update.message.reply_text("Неверный выбор. Попробуй снова нажать '🖥 Live Control'.", reply_markup=media_menu_keyboard())
                        return
                    STREAM_MONITOR_INDEX = idx  
                    update.message.reply_text(f"Выбран монитор: {text}. Запускаю live-панель...")
                    restart_stream_with_monitor(idx)
                    ip = get_local_ip()
                    local_url = f"http://{ip}:{STREAM_PORT}/?pw={WEB_PASSWORD}"
                    msg = f"Live панель запущена локально:\n{local_url}\n\n"
                    
                    
                    logging.info(f"PYNGROK_AVAILABLE: {PYNGROK_AVAILABLE}")
                    logging.info(f"NGROK_TOKEN set: {bool(NGROK_TOKEN)}")
                    logging.info(f"Selected monitor index: {STREAM_MONITOR_INDEX}")  
                    
                    if PYNGROK_AVAILABLE and NGROK_TOKEN:
                        url = start_ngrok_tunnel()
                        if url:
                            msg += f"Доступ через ngrok: {url}/?pw={WEB_PASSWORD}\nПароль: {WEB_PASSWORD}\nНажми /stop_realtime чтобы остановить."
                        else:
                            msg += "Не удалось запустить ngrok. Проверь логи для деталей."
                    else:
                        reasons = []
                        if not PYNGROK_AVAILABLE:
                            reasons.append("pyngrok не установлен")
                        if not NGROK_TOKEN:
                            reasons.append("NGROK_TOKEN пуст")
                        msg += f"ngrok недоступен: {', '.join(reasons)}"
                    
                    update.message.reply_text(msg, reply_markup=media_menu_keyboard())
                    return
        
        if action == "add_program_name":
                    name = text.strip().lower()
                    if not name or ' ' in name:
                        update.message.reply_text(
                            "❌ Название должно быть одним словом без пробелов. Попробуй еще раз:",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        awaiting[chat_id] = {"action": "add_program_name"}  
                        return True
                    
                    awaiting[chat_id] = {"action": "add_program_path", "name": name}
                    update.message.reply_text(
                        f"📂 Теперь напиши полный путь к исполняемому файлу программы '{name}':\n"
                        "Пример: C:\\Program Files\\Notepad++\\notepad++.exe",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return True
                    
        elif action == "add_program_path":
            
            if "name" not in info:
                update.message.reply_text(
                    "❌ Ошибка: имя программы не найдено. Попробуй снова через меню.",
                    reply_markup=programs_menu_keyboard()
                )
                return True
                
            name = info["name"]  
            path = text.strip()
            
            if not os.path.exists(path):
                update.message.reply_text(
                    f"❌ Файл не найден: {path}\n"
                    "Проверь путь и попробуй еще раз:",
                    reply_markup=ReplyKeyboardRemove()
                )
                
                awaiting[chat_id] = {"action": "add_program_path", "name": name}
                return True
            
            PROGRAMS[name] = path
            if save_user_programs():
                update.message.reply_text(
                    f"✅ Программа '{name}' успешно добавлена!\n"
                    f"Путь: {path}\n\n"
                    "Теперь она доступна в меню 'Программы и Игры'",
                    reply_markup=programs_menu_keyboard()
                )
            else:
                update.message.reply_text(
                    "❌ Ошибка сохранения программы",
                    reply_markup=programs_menu_keyboard()
                )
            return True
        
        elif action == "remove_program_name":
                    if text == "🔙 Отменить":
                        update.message.reply_text("❌ Удаление отменено", reply_markup=programs_menu_keyboard())
                        return True
                    
                    if text.startswith("🗑 "):
                        program_name = text[2:].lower().replace(' ', '_')
                        
                        if program_name not in PROGRAMS:
                            update.message.reply_text(
                                f"❌ Программа '{program_name}' не найдена",
                                reply_markup=programs_menu_keyboard()
                            )
                            return True
                        
                        
                        program_path = PROGRAMS[program_name]
                        
                        del PROGRAMS[program_name]
                        if save_user_programs():
                            display_name = text[2:]  
                            update.message.reply_text(
                                f"✅ Программа '{display_name}' удалена!\n"
                                f"Путь был: {program_path}",
                                reply_markup=programs_menu_keyboard()
                            )
                        else:
                            
                            PROGRAMS[program_name] = program_path
                            update.message.reply_text(
                                "❌ Ошибка сохранения изменений",
                                reply_markup=programs_menu_keyboard()
                            )
                        return True
                    else:
                        update.message.reply_text(
                            "❌ Неверный формат. Выбери программу из списка.",
                            reply_markup=programs_menu_keyboard()
                        )
                        return True
        


        if action == "choose_camera_for_video":
            cameras = info.get("cameras", [])
            selected_camera = None
            
            
            camera_name = text.replace("📷 ", "").strip()
            for camera in cameras:
                if camera['name'] == camera_name:
                    selected_camera = camera
                    break
            
            if selected_camera is None:
                if text == "🔙 Назад":  
                    update.message.reply_text("Действие отменено.", reply_markup=media_menu_keyboard())
                else:
                    update.message.reply_text("Неверный выбор камеры. Попробуй еще раз через '🎥 Вебкам видео'.", reply_markup=media_menu_keyboard())
                return
            
            
            awaiting[chat_id] = {
                "action": "media_webcam_video", 
                "camera_index": selected_camera['index']
            }
            update.message.reply_text(f"Выбрана камера: {selected_camera['name']}. Напиши длительность записи в секундах (пример: 10).", 
                                    reply_markup=ReplyKeyboardRemove())
            return

    

        if action == "media_webcam_video":
            try:
                secs = int(text.strip())
            except:
                if text == "🔙 Назад":
                    update.message.reply_text("Действие отменено.", reply_markup=media_menu_keyboard())
                    return
                else:
                    update.message.reply_text("Нужно число секунд.", reply_markup=media_menu_keyboard())
                    return
            
            camera_index = info.get("camera_index", 0)
            
            update.message.reply_text(f"Начинаю запись с камеры {camera_index} на {secs} секунд...")
            
            def cam_run():
                out = f"webcamrec_{int(time.time())}.avi"
                ok = webcam_video_selected(out, secs, camera_index=camera_index, fps=10)
                if ok:
                    context.bot.send_video(chat_id=chat_id, video=open(out, "rb"))
                    try: 
                        os.remove(out)
                    except: 
                        pass
                    context.bot.send_message(chat_id=chat_id, text="✅ Видео записано и отправлено!")
                else:
                    context.bot.send_message(chat_id=chat_id, text="❌ Ошибка записи с вебкамеры.")
            
            threading.Thread(target=cam_run, daemon=True).start()
            return
                
        if action == "choose_camera_for_photo":
            cameras = info.get("cameras", [])
            selected_camera = None
            
            
            for camera in cameras:
                if camera['name'] == text.strip():
                    selected_camera = camera
                    break
            
            if selected_camera is None:
                update.message.reply_text("Неверный выбор. Попробуй еще раз через '📸 Вебкам фото'.", 
                                        reply_markup=media_menu_keyboard())
                return
            
            update.message.reply_text(f"Делаю фото с {selected_camera['name']}...")
            path = f"webcam_{selected_camera['index']}_{int(time.time())}.jpg"
            
            if webcam_photo_improved(path, selected_camera['index']):
                context.bot.send_photo(chat_id=chat_id, photo=open(path, "rb"))
                try: os.remove(path)
                except: pass
                update.message.reply_text("Фото отправлено.", reply_markup=media_menu_keyboard())
            else:
                update.message.reply_text("Ошибка при съемке с выбранной камеры.", 
                                        reply_markup=media_menu_keyboard())
            return
        if action == "sys_volume":
            try:
                level = int(text)
                if 0 <= level <= 100:
                    ok = get_set_volume_windows(level)
                    if ok:
                        update.message.reply_text("Громкость установлена.", reply_markup=system_menu_keyboard())
                    else:
                        update.message.reply_text("Попытка установить громкость выполнена (может требоваться nircmd/pycaw).", reply_markup=system_menu_keyboard())
                else:
                    update.message.reply_text("Укажи число 0-100.", reply_markup=system_menu_keyboard())
            except:
                update.message.reply_text("Нужно число.", reply_markup=system_menu_keyboard())
            return
        if action == "sys_brightness":
            try:
                level = int(text)
                if 0 <= level <= 100:
                    success, error_msg = set_brightness(level)
                    if success:
                        update.message.reply_text("Яркость установлена.", reply_markup=system_menu_keyboard())
                    else:
                        update.message.reply_text(f"Не удалось установить яркость: {error_msg}", reply_markup=system_menu_keyboard())
                else:
                    update.message.reply_text("Укажи число 0-100.", reply_markup=system_menu_keyboard())
            except ValueError:
                update.message.reply_text("Нужно число.", reply_markup=system_menu_keyboard())
            return
        if action == "files_list":
            path = text or "."
            items, err = list_folder(path)
            if err:
                update.message.reply_text(err, reply_markup=files_menu_keyboard())
            else:
                if not items:
                    update.message.reply_text("(пусто)", reply_markup=files_menu_keyboard())
                else:
                    out = "\n".join(items)
                    for chunk in chunk_text(out, 3000):
                        update.message.reply_text(chunk, reply_markup=files_menu_keyboard())
            return
        if action == "files_archive":
            path = text.strip()
            update.message.reply_text("Создаю архив и отправляю...")
            threading.Thread(target=make_archive_and_send, args=(chat_id, path, context.bot), daemon=True).start()
            update.message.reply_text("Готово.", reply_markup=files_menu_keyboard())
            return
        if action == "files_upload":
            if update.message.document or update.message.photo:
                try:
                    upldir = os.path.join(os.path.expanduser("~"), "telegram_Uploads")
                    os.makedirs(upldir, exist_ok=True)
                    if update.message.photo:
                        file = update.message.photo[-1].get_file()
                        fname = f"photo_{int(time.time())}.jpg"
                    else:
                        file = update.message.document.get_file()
                        fname = update.message.document.file_name or f"file_{int(time.time())}"
                    dest = os.path.join(upldir, fname)
                    file.download(custom_path=dest)
                    update.message.reply_text(f"Файл сохранён на ПК: {dest}", reply_markup=files_menu_keyboard())
                except Exception:
                    logging.exception("file save failed")
                    update.message.reply_text("Ошибка сохранения файла.", reply_markup=files_menu_keyboard())
            else:
                update.message.reply_text("Отправь файл (как документ/фото).", reply_markup=files_menu_keyboard())
            return
        if action == "files_delete":
            path = text.strip()
            threading.Thread(target=delete_path, args=(chat_id, path, context.bot), daemon=True).start()
            update.message.reply_text("Готово.", reply_markup=files_menu_keyboard())
            return
        if action == "files_search":
            try:
                if "|" in text:
                    root, pattern = text.split("|", 1)
                else:
                    update.message.reply_text("Неверный формат. Пример: C:\\Users\\User|*.txt", reply_markup=files_menu_keyboard())
                    return
                res = search_files(root.strip() or ".", pattern.strip())
                if not res:
                    update.message.reply_text("Ничего не найдено.", reply_markup=files_menu_keyboard())
                else:
                    for chunk in chunk_text("\n".join(res), 3000):
                        update.message.reply_text(chunk, reply_markup=files_menu_keyboard())
            except Exception:
                logging.exception("files_search failed")
                update.message.reply_text("Ошибка поиска.", reply_markup=files_menu_keyboard())
            return
        if action == "net_ping":
            host = text.strip()
            out = ping_host(host)
            for chunk in chunk_text(out, 3000):
                update.message.reply_text(chunk, reply_markup=network_menu_keyboard())
            return
        if action == "media_screenrec":
            try:
                secs = int(text.strip())
            except:
                update.message.reply_text("Нужно число секунд.", reply_markup=media_menu_keyboard())
                return
            
            
            monitor_index = info.get("monitor_index", 1)
            
            update.message.reply_text(f"Начинаю запись экрана на {secs} секунд (монитор: {monitor_index})...")
            
            def rec_run():
                out = f"screenrec_{int(time.time())}.avi"
                ok = record_screen_secs(out, secs, fps=10, monitor_index=monitor_index)
                if ok:
                    context.bot.send_video(chat_id=chat_id, video=open(out, "rb"))
                    try: 
                        os.remove(out)
                    except: 
                        pass
                    context.bot.send_message(chat_id=chat_id, text="✅ Запись экрана завершена и отправлена!")
                else:
                    context.bot.send_message(chat_id=chat_id, text="❌ Ошибка записи экрана.")
            
            threading.Thread(target=rec_run, daemon=True).start()
            return
        if action == "media_autoscreens":
            try:
                mins = int(text.strip())
            except:
                update.message.reply_text("Нужно число минут (0 для остановки).", reply_markup=media_menu_keyboard())
                return
            
            def auto_screens_run(interval_min, bot, chat_id):
                stop_flag_name = f"autoscreens_{chat_id}"
                setattr(auto_screens_run, stop_flag_name, True)
                
                if interval_min <= 0:
                    bot.send_message(chat_id=chat_id, text="✅ Автоскрины остановлены.")
                    return
                
                bot.send_message(chat_id=chat_id, text=f"✅ Автоскрины запущены с интервалом {interval_min} минут.")
                
                while getattr(auto_screens_run, stop_flag_name, True):
                    p = f"autoscreen_{int(time.time())}.jpg"
                    if take_screenshot_save(p):
                        bot.send_photo(chat_id=chat_id, photo=open(p, "rb"))
                        try: 
                            os.remove(p)
                        except: 
                            pass
                    time.sleep(interval_min * 60)
            
            if mins <= 0:
                name = f"autoscreens_{chat_id}"
                setattr(auto_screens_run, name, False)
                update.message.reply_text("Останавливаю автоскрины...", reply_markup=media_menu_keyboard())
            else:
                name = f"autoscreens_{chat_id}"
                setattr(auto_screens_run, name, True)
                
            t = threading.Thread(target=auto_screens_run, args=(mins, context.bot, chat_id), daemon=True)
            t.start()
            return
        if action == "type_text":
            txt = text
            try:
                pyautogui.typewrite(txt)
                update.message.reply_text("Текст введён.", reply_markup=input_menu_keyboard())
            except Exception:
                logging.exception("type_text failed")
                update.message.reply_text("Ошибка ввода текста.", reply_markup=input_menu_keyboard())
            return

        if update.message.document or update.message.photo:
            try:
                upldir = os.path.join(os.path.expanduser("~"), "telegram_Uploads")
                os.makedirs(upldir, exist_ok=True)
                if update.message.photo:
                    file = update.message.photo[-1].get_file()
                    fname = f"photo_{int(time.time())}.jpg"
                else:
                    file = update.message.document.get_file()
                    fname = update.message.document.file_name or f"file_{int(time.time())}"
                dest = os.path.join(upldir, fname)
                file.download(custom_path=dest)
                update.message.reply_text(f"Файл сохранён на ПК: {dest}", reply_markup=main_menu_keyboard())
            except Exception:
                logging.exception("file save failed")
                update.message.reply_text("Ошибка сохранения файла.", reply_markup=main_menu_keyboard())
            return
        elif text == "/stop_realtime":
            stop_flask()
            stop_ngrok_tunnel()
            update.message.reply_text("Live-панель остановлена (возможно, потребуется завершить процесс вручную).", reply_markup=main_menu_keyboard())
            return

        
        update.message.reply_text("Не понимаю. Нажми /start для меню.", reply_markup=main_menu_keyboard())

def is_windows():
    return platform.system().lower().startswith("win")

def get_local_ip():
    ip = "127.0.0.1"
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip.startswith("127."):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            finally:
                s.close()
    except Exception:
        pass
    return ip

def check_web_password(req):
    pw = req.values.get("pw") or req.headers.get("X-PW")
    return pw == WEB_PASSWORD




def start_flask_thread(host="0.0.0.0", port=STREAM_PORT):
    global _stream_running
    with _stream_lock:
        if _stream_running:
            logging.info("Flask already running")
            return
        _stream_running = True
    def run():
        logging.info("Starting Flask live server with SocketIO")
        socketio.run(app, host=host, port=port, debug=False, use_reloader=False)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t

def stop_flask():
    global _stream_running
    with _stream_lock:
        _stream_running = False
    logging.info("Requested Flask stop (may need manual kill)")


        
def stop_ngrok_tunnel():
    global _ngrok_proc, _ngrok_tunnel_url
    with _ngrok_lock:
        if _ngrok_proc:
            try:
                _ngrok_proc.terminate()
            except Exception:
                pass
            _ngrok_proc = None
            _ngrok_tunnel_url = None
            logging.info("ngrok stopped")


def handle_webcam_video_selection(update, context, chat_id):
    """Обработчик выбора камеры для видео"""
    
    cameras = get_camera_names_windows()
    
    if not cameras:
        update.message.reply_text("Камеры не найдены.", reply_markup=media_menu_keyboard())
        return
    elif len(cameras) == 1:
        
        awaiting[chat_id] = {
            "action": "media_webcam_video", 
            "camera_index": cameras[0]['index']
        }
        update.message.reply_text("Напиши длительность записи в секундах (пример: 10).", 
                                reply_markup=ReplyKeyboardRemove())
        return
    else:
        
        awaiting[chat_id] = {
            "action": "choose_camera_for_video", 
            "cameras": cameras
        }
        
        
        kb = []
        for i, camera in enumerate(cameras[:5]):  
            kb.append([KeyboardButton(f"📷 {camera['name']}")])
        kb.append([KeyboardButton("🔙 Назад")])
        
        update.message.reply_text("Выбери камеру для видео:", 
                                reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return


def do_shutdown_action():
    try:
        if is_windows():
            os.system("shutdown /s /t 1")
        else:
            os.system("shutdown -h now")
    except Exception:
        logging.exception("shutdown failed")

def do_restart_action():
    try:
        if is_windows():
            os.system("shutdown /r /t 1")
        else:
            os.system("reboot")
    except Exception:
        logging.exception("restart failed")

def do_reboot_to_bios():
    try:
        if is_windows():
            os.system("shutdown /r /fw /t 0")
        else:
            os.system("systemctl reboot --firmware-setup")
    except Exception:
        logging.exception("reboot to bios failed")

def do_lock_action():
    try:
        if is_windows():
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        else:
            os.system("loginctl lock-session || gnome-screensaver-command -l")
    except Exception:
        logging.exception("lock failed")


def set_wallpaper(path):
    try:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        if is_windows():
            import ctypes
            SPI_SETDESKWALLPAPER = 20
            ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, path, 3)
        else:
            try:
                subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{path}"], check=False)
            except Exception:
                logging.warning("gsettings failed; may need DE-specific command")
        return True
    except Exception:
        logging.exception("set_wallpaper failed")
        return False


def get_set_volume_windows(level=None):
    try:
        if is_windows():
            nircmd = shutil.which("nircmd")
            if nircmd:
                if level is None:
                    return None
                else:
                    subprocess.run([nircmd, "setsysvolume", str(int(level * 65535 / 100))])
                    return True
            else:
                return None
        else:
            if shutil.which("amixer"):
                if level is None:
                    return None
                subprocess.run(["amixer", "sset", "Master", f"{int(level)}%"])
                return True
    except Exception:
        logging.exception("volume control failed")
    return False


def set_brightness(level):
    try:
        level = max(0, min(100, int(level)))
        if platform.system().lower() == "windows":
            try:
                from monitorcontrol import get_monitors
                for monitor in get_monitors():
                    with monitor:
                        monitor.set_luminance(level)
                        return True, None
                return False, "Не удалось найти мониторы с поддержкой DDC/CI."
            except ImportError:
                logging.error("monitorcontrol library not installed. Install with 'pip install monitorcontrol'.")
                return False, "Библиотека monitorcontrol не установлена. Установите: pip install monitorcontrol"
            except Exception as e:
                logging.warning("monitorcontrol failed: %s. Falling back to WMI.", str(e))
                try:
                    import wmi
                    wmi_instance = wmi.WMI(namespace="wmi")
                    methods = wmi_instance.WmiMonitorBrightnessMethods()[0]
                    methods.WmiSetBrightness(Brightness=level, Timeout=0)
                    return True, None
                except ImportError:
                    logging.error("WMI library not installed. Install with 'pip install wmi'.")
                    return False, "Библиотека WMI не установлена. Установите: pip install wmi"
                except Exception as e:
                    logging.exception("WMI brightness set failed")
                    return False, f"Ошибка WMI: {str(e)}"
        else:
            if shutil.which("xrandr"):
                out = subprocess.check_output(["xrandr", "--verbose"], universal_newlines=True, stderr=subprocess.DEVNULL)
                output = None
                for line in out.splitlines():
                    if " connected " in line:
                        output = line.split()[0]
                        break
                if output:
                    bri = max(0.1, level / 100.0)
                    subprocess.run(["xrandr", "--output", output, "--brightness", str(bri)], check=True)
                    return True, None
                else:
                    return False, "Подключенный дисплей не найден."
            else:
                return False, "xrandr не установлен. Установите: sudo apt install x11-xserver-utils"
    except Exception as e:
        logging.exception("set_brightness failed")
        return False, f"Ошибка: {str(e)}"


def set_display_power(off=True):
    try:
        if is_windows():
            nircmd = shutil.which("nircmd")
            if nircmd:
                if off:
                    subprocess.run([nircmd, "monitor", "off"])
                else:
                    pyautogui.moveRel(1, 0, duration=0.1); pyautogui.moveRel(-1, 0, duration=0.1)
                return True
        else:
            if off:
                subprocess.run(["xset", "dpms", "force", "off"])
            else:
                subprocess.run(["xset", "dpms", "force", "on"])
            return True
    except Exception:
        logging.exception("set_display_power failed")
    return False
def minimize_all_windows():
    try:
        if is_windows():
            import ctypes
            
            user32 = ctypes.windll.user32
            user32.keybd_event(0x5B, 0, 0, 0)  
            user32.keybd_event(0x44, 0, 0, 0)  
            user32.keybd_event(0x44, 0, 2, 0)  
            user32.keybd_event(0x5B, 0, 2, 0)  
    except Exception:
        logging.exception("minimize_all_windows failed")
def close_all_windows():
    try:
        if is_windows():
            def callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            win32gui.EnumWindows(callback, None)
        else:
            if shutil.which("wmctrl"):
                subprocess.run(["wmctrl", "-c", ":ACTIVE:"])
            else:
                logging.warning("wmctrl not installed for closing windows")
    except Exception as e:
        logging.exception(f"close_all_windows failed: {e}")
        try:
            logging.info("Falling back to Alt+F4")
            for _ in range(10):
                pyautogui.hotkey("alt", "f4")
                time.sleep(0.1)
        except Exception as e:
            logging.exception(f"Fallback Alt+F4 failed: {e}")

def list_folder(path):
    try:
        if not os.path.exists(path):
            return None, "Путь не найден."
        if os.path.isfile(path):
            return None, "Это файл. Используй /download."
        items = os.listdir(path)
        return items, None
    except Exception:
        logging.exception("list_folder failed")
        return None, "Ошибка."

def restart_stream_with_monitor(monitor_index):
    global _stream_running, STREAM_MONITOR_INDEX
    stop_flask()
    time.sleep(1)
    STREAM_MONITOR_INDEX = monitor_index
    logging.info(f"Restarting stream with monitor index: {STREAM_MONITOR_INDEX}")
    start_flask_thread()

def make_archive_and_send(chat_id, folder_path, bot):
    try:
        if not os.path.exists(folder_path):
            bot.send_message(chat_id=chat_id, text="Путь не найден.")
            return
        base = os.path.basename(os.path.normpath(folder_path))
        tmp_dir = tempfile.mkdtemp()
        out = os.path.join(tmp_dir, base)
        archive = shutil.make_archive(out, "zip", folder_path)
        bot.send_document(chat_id=chat_id, document=open(archive, "rb"))
    except Exception:
        logging.exception("archive failed")
        bot.send_message(chat_id=chat_id, text="Ошибка архивации.")
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except:
            pass

def load_user_programs():
    """Загружает пользовательские программы из файла"""
    global PROGRAMS
    try:
        
        PROGRAMS = {}
        
        if os.path.exists(PROGRAMS_FILE):
            with open(PROGRAMS_FILE, 'r', encoding='utf-8') as f:
                user_programs = json.load(f)
                PROGRAMS.update(user_programs)
                logging.info(f"Загружено {len(user_programs)} пользовательских программ")
        else:
            logging.info("Файл пользовательских программ не найден, начинаем с пустого списка")
    except Exception as e:
        logging.error(f"Ошибка загрузки пользовательских программ: {e}")
        PROGRAMS = {}

def save_user_programs():
    """Сохраняет пользовательские программы в файл"""
    try:
        
        with open(PROGRAMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(PROGRAMS, f, ensure_ascii=False, indent=2)
        logging.info(f"Сохранено {len(PROGRAMS)} пользовательских программ")
        return True
    except Exception as e:
        logging.error(f"Ошибка сохранения пользовательских программ: {e}")
        return False

def programs_menu_keyboard():
    """Создает клавиатуру с программами"""
    kb = []
    
    
    user_programs = []
    
    for key in PROGRAMS.keys():
        
        display_name = key.replace('_', ' ').title()
        user_programs.append(KeyboardButton(f"📱 {display_name}"))
    
    
    for i in range(0, len(user_programs), 2):
        row = user_programs[i:i+2]
        kb.append(row)
    
    
    if not user_programs:
        kb.append([KeyboardButton("📝 Список программ пуст")])
    
    
    kb.extend([
        [KeyboardButton("➕ Добавить программу"), KeyboardButton("➖ Удалить программу")],
        [KeyboardButton("📋 Список программ"), KeyboardButton("🔙 Назад")]
    ])
    
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

@owner_only
def add_program_cmd(update: Update, context: CallbackContext):
    """Команда для добавления программы через /add_program"""
    args = context.args
    if len(args) < 2:
        update.message.reply_text(
            "Использование: /add_program <название> <путь>\n"
            "Пример: /add_program notepad C:\\Windows\\System32\\notepad.exe",
            reply_markup=main_menu_keyboard()
        )
        return
    
    name = args[0].lower()
    path = " ".join(args[1:])
    
    if not os.path.exists(path):
        update.message.reply_text(
            f"❌ Файл не найден: {path}",
            reply_markup=main_menu_keyboard()
        )
        return
    
    PROGRAMS[name] = path
    if save_user_programs():
        update.message.reply_text(
            f"✅ Программа '{name}' добавлена!\nПуть: {path}",
            reply_markup=main_menu_keyboard()
        )
    else:
        update.message.reply_text(
            "❌ Ошибка сохранения программы",
            reply_markup=main_menu_keyboard()
        )

@owner_only  
def remove_program_cmd(update: Update, context: CallbackContext):
    """Команда для удаления программы через /remove_program"""
    args = context.args
    if len(args) != 1:
        update.message.reply_text(
            "Использование: /remove_program <название>\n"
            "Пример: /remove_program notepad",
            reply_markup=main_menu_keyboard()
        )
        return
    
    name = args[0].lower()
    base_programs = {"brave", "cs2", "majestic", "telegram", "discord"}
    
    if name in base_programs:
        update.message.reply_text(
            "❌ Нельзя удалить базовую программу",
            reply_markup=main_menu_keyboard()
        )
        return
    
    if name not in PROGRAMS:
        update.message.reply_text(
            f"❌ Программа '{name}' не найдена",
            reply_markup=main_menu_keyboard()
        )
        return
    
    del PROGRAMS[name]
    if save_user_programs():
        update.message.reply_text(
            f"✅ Программа '{name}' удалена!",
            reply_markup=main_menu_keyboard()
        )
    else:
        update.message.reply_text(
            "❌ Ошибка сохранения изменений",
            reply_markup=main_menu_keyboard()
        )

@owner_only
def list_programs_cmd(update: Update, context: CallbackContext):
    """Команда для просмотра всех программ через /list_programs"""
    if not PROGRAMS:
        update.message.reply_text(
            "📋 Список программ пуст\n\n"
            "Добавьте программы командой /add_program или через меню кнопкой '➕ Добавить программу'",
            reply_markup=main_menu_keyboard()
        )
        return
    
    msg = "📋 **Список программ:**\n\n"
    
    for key, path in PROGRAMS.items():
        msg += f"• **{key}**: `{path}`\n"
    
    
    for chunk in chunk_text(msg, 3000):
        update.message.reply_text(chunk, parse_mode='Markdown', reply_markup=main_menu_keyboard())

from aiortc.contrib.media import MediaStreamTrack
from av import VideoFrame

class ScreenCaptureTrack(MediaStreamTrack):
    kind = "video"
    
    def __init__(self):
        super().__init__()
        self.sct = mss.mss()
        logging.info(f"Available monitors: {self.sct.monitors}")
        self.monitor = get_monitor_by_index(self.sct, STREAM_MONITOR_INDEX)
        self.last_frame_time = 0
        self.frame_interval = 0.033
    
    async def recv(self):
        try:
            current_time = time.time()
            if current_time - self.last_frame_time < self.frame_interval:
                await asyncio.sleep(self.frame_interval - (current_time - self.last_frame_time))
            sct_img = self.sct.grab(self.monitor)
            frame = np.array(Image.frombytes("RGB", sct_img.size, sct_img.rgb))
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = cv2.resize(frame, (1280, 720))
            video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
            video_frame.pts = int(time.time() * 1000)
            video_frame.time_base = (1, 1000)
            self.last_frame_time = current_time
            return video_frame
        except Exception as e:
            logging.error(f"Screen capture failed: {str(e)}")
            return None

def delete_path(chat_id, path, bot):
    try:
        if not os.path.exists(path):
            bot.send_message(chat_id=chat_id, text="Путь не найден.")
            return
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        bot.send_message(chat_id=chat_id, text="Удалено.")
    except Exception:
        logging.exception("delete failed")
        bot.send_message(chat_id=chat_id, text="Ошибка удаления.")

def search_files(root, pattern):
    res = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            if pattern.startswith("*."):
                if fname.lower().endswith(pattern[1:].lower()):
                    res.append(os.path.join(dirpath, fname))
            else:
                if pattern.lower() in fname.lower():
                    res.append(os.path.join(dirpath, fname))
    return res
def empty_recycle_bin():
    """Очищает корзину"""
    try:
        if is_windows():
            
            import ctypes
            from ctypes import wintypes
            
            
            shell32 = ctypes.windll.shell32
            SHEmptyRecycleBin = shell32.SHEmptyRecycleBinW
            SHEmptyRecycleBin.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.DWORD]
            SHEmptyRecycleBin.restype = wintypes.LONG
            
            
            SHERB_NOCONFIRMATION = 0x00000001
            SHERB_NOPROGRESSUI = 0x00000002
            
            result = SHEmptyRecycleBin(None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI)
            return result == 0  
        else:
            
            trash_dirs = [
                os.path.expanduser("~/.local/share/Trash/files"),
                os.path.expanduser("~/.Trash")
            ]
            
            for trash_dir in trash_dirs:
                if os.path.exists(trash_dir):
                    shutil.rmtree(trash_dir)
                    os.makedirs(trash_dir, exist_ok=True)
            
            
            info_dir = os.path.expanduser("~/.local/share/Trash/info")
            if os.path.exists(info_dir):
                shutil.rmtree(info_dir)
                os.makedirs(info_dir, exist_ok=True)
            
            return True
            
    except Exception as e:
        logging.exception("empty_recycle_bin failed")
        return False

@socketio.on('connect')
def handle_connect():
    logging.info(f"WebSocket client connected from {request.remote_addr}")
    emit('connected', {'message': 'WebSocket connected'})

class ScreenCaptureTrackSelected(MediaStreamTrack):
    kind = "video"

    def __init__(self, monitor_index=0):
        super().__init__()
        self.sct = mss.mss()
        self.monitor_index = monitor_index
        self.last_frame_time = 0
        self.frame_interval = 0.033  

    async def recv(self):
        current_time = time.time()
        if current_time - self.last_frame_time < self.frame_interval:
            await asyncio.sleep(self.frame_interval - (current_time - self.last_frame_time))

        monitor = get_monitor_by_index(self.sct, self.monitor_index)
        sct_img = self.sct.grab(monitor)
        frame = np.array(Image.frombytes("RGB", sct_img.size, sct_img.rgb))
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        frame = cv2.resize(frame, (1280, 720))

        from av import VideoFrame
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = int(time.time() * 1000)
        video_frame.time_base = (1, 1000)
        self.last_frame_time = current_time
        return video_frame


@socketio.on('offer')
async def handle_offer(data):
    global screen_track, pcs
    logging.info(f"Received WebRTC offer: {data}")
    try:
        pc = RTCPeerConnection()
        pcs.add(pc)
        
        screen_track = ScreenCaptureTrackSelected(monitor_index=STREAM_MONITOR_INDEX)

        pc.addTrack(screen_track)
        
        @pc.on("icecandidate")
        def on_icecandidate(candidate):
            if candidate:
                logging.info(f"Sending ICE candidate: {candidate.sdp}")
                emit('candidate', {
                    'candidate': candidate.sdp,
                    'sdpMid': candidate.sdpMid,
                    'sdpMLineIndex': candidate.sdpMLineIndex
                })

        await pc.setRemoteDescription(data['offer'])
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        logging.info(f"Sending WebRTC answer: {pc.localDescription.sdp}")
        emit('answer', {'sdp': pc.localDescription.sdp, 'type': pc.localDescription.type})

    except Exception as e:
        logging.error(f"WebRTC offer failed: {str(e)}")
        emit('error', {'message': str(e)})
    
@socketio.on('candidate')
def handle_candidate(data):
    logging.info(f"Received ICE candidate: {data}")
    for pc in pcs:
        try:
            pc.addIceCandidate(data)
        except Exception as e:
            logging.error(f"WebRTC candidate failed: {str(e)}")

@socketio.on('disconnect')
def handle_disconnect():
    global pcs, screen_track
    logging.info(f"WebSocket client disconnected from {request.remote_addr}")
    for pc in list(pcs):
        pc.close()
        pcs.remove(pc)
    screen_track = None

def ping_host(host):
    try:
        param = "-n" if is_windows() else "-c"
        cmd = ["ping", param, "4", host]
        out = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.STDOUT, timeout=10)
        return out
    except Exception as e:
        return str(e)
    
def get_temperature_info():
    """Получает информацию о температуре системы различными способами"""
    temp_info = []
    
    if platform.system().lower() == "windows":
        
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        for entry in entries:
                            temp_info.append(f"{name} ({entry.label or 'Unknown'}): {entry.current}°C")
                else:
                    temp_info.append("Датчики температуры недоступны через psutil")
            else:
                temp_info.append("psutil не поддерживает sensors_temperatures на этой системе")
        except Exception as e:
            temp_info.append(f"Ошибка psutil: {e}")
        
        
        try:
            
            cmd = [
                "powershell", 
                "-Command", 
                "Get-WmiObject -Namespace 'root/wmi' -Class 'MSAcpi_ThermalZoneTemperature' | Select-Object CurrentTemperature"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip() and line.strip() != "CurrentTemperature" and line.strip() != "-----------------":
                        try:
                            
                            temp_kelvin = float(line.strip()) / 10.0
                            temp_celsius = temp_kelvin - 273.15
                            temp_info.append(f"Thermal Zone: {temp_celsius:.1f}°C")
                        except ValueError:
                            continue
            else:
                temp_info.append("WMI thermal zones недоступны")
                
        except subprocess.TimeoutExpired:
            temp_info.append("PowerShell команда превысила время ожидания")
        except Exception as e:
            temp_info.append(f"Ошибка PowerShell: {e}")
        
        
        try:
            import winreg
            
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                               r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            processor_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            temp_info.append(f"Процессор: {processor_name}")
        except Exception:
            pass
            
        
        try:
            result = subprocess.run(
                ["wmic", "path", "Win32_PerfRawData_Counters_ThermalZoneInformation", "get", "Temperature"], 
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and "Temperature" in result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  
                    if line.strip() and line.strip().isdigit():
                        temp_kelvin = float(line.strip()) / 10.0
                        temp_celsius = temp_kelvin - 273.15
                        temp_info.append(f"Thermal Zone (wmic): {temp_celsius:.1f}°C")
        except Exception:
            pass
    
    
    if not temp_info:
        temp_info.append("Информация о температуре недоступна на данной системе")
        temp_info.append("Для получения температуры CPU может потребоваться:")
        temp_info.append("- Специализированное ПО (HWiNFO, Core Temp)")
        temp_info.append("- Библиотеки с админ правами")
        temp_info.append("- Современные процессоры с поддержкой датчиков")
    
    return "\n".join(temp_info)

def handle_temperature_request(update, context, chat_id):
    """Обработчик запроса температуры для телеграм бота"""
    update.message.reply_text("Получаю информацию о температуре системы...")
    
    def temp_worker():
        try:
            temp_data = get_temperature_info()
            context.bot.send_message(chat_id=chat_id, text=f"🌡️ Температура системы:\n\n{temp_data}")
        except Exception as e:
            logging.exception("Temperature request failed")
            context.bot.send_message(chat_id=chat_id, text=f"❌ Ошибка получения температуры: {e}")
    
    import threading
    threading.Thread(target=temp_worker, daemon=True).start()

def lan_scan():
    try:
        if is_windows():
            out = subprocess.check_output("arp -a", shell=True, universal_newlines=True)
            return out
        else:
            out = subprocess.check_output(["arp", "-a"], universal_newlines=True)
            return out
    except Exception:
        logging.exception("lan scan failed")
        return "Ошибка запуска сканера (нужны права/утилиты)."

def do_speedtest():
    if speedtest is None:
        return "speedtest-cli не установлен."
    try:
        st = speedtest.Speedtest(secure=True)
        st.get_best_server()
        st.download()
        st.upload()
        res = st.results.dict()
        return f"Download: {res['download']/1e6:.2f} Mbps\nUpload: {res['upload']/1e6:.2f} Mbps\nPing: {res['ping']} ms"
    except Exception:
        logging.exception("speedtest failed")
        return "Ошибка при выполнении speedtest."

def ip_monitor_thread_func(bot):
    global _ip_monitor_running, _last_ip
    _ip_monitor_running = True
    while _ip_monitor_running:
        try:
            ip = get_local_ip()
            if _last_ip is None:
                _last_ip = ip
            elif ip != _last_ip:
                bot.send_message(chat_id=OWNER_CHAT_ID, text=f"IP changed: {_last_ip} -> {ip}")
                _last_ip = ip
        except Exception:
            logging.exception("ip monitor error")
        time.sleep(30)

def get_monitor_by_index(sct, idx):
    try:
        mons = sct.monitors
        if idx == 0 and len(mons) >= 1:
            return mons[0]          
        if 1 <= idx < len(mons):
            return mons[idx]        
        return mons[1] if len(mons) > 1 else mons[0]
    except Exception:
        return sct.monitors[0]

def count_physical_monitors():
    try:
        import mss
        with mss.mss() as sct:
            
            return max(0, len(sct.monitors) - 1)
    except Exception:
        return 1


def take_screenshot_save(path, monitor_index=None):
    try:
        with mss.mss() as sct:
            monitor = get_monitor_by_index(sct, STREAM_MONITOR_INDEX if monitor_index is None else monitor_index)
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            img.save(path, "JPEG", quality=SCREENSHOT_Q)
            return True
    except Exception:
        logging.exception("take_screenshot failed")
        return False

def debug_monitors():
    """Функция для отладки - показывает информацию о мониторах"""
    with mss.mss() as sct:
        for i, monitor in enumerate(sct.monitors):
            logging.info(f"Monitor {i}: {monitor}")
    
    cursor_x, cursor_y = pyautogui.position()
    logging.info(f"Cursor position: {cursor_x}, {cursor_y}")

def record_screen_secs(out_path, secs, fps=10, monitor_index=None):
    try:
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        with mss.mss() as sct:
            
            effective_index = monitor_index if monitor_index is not None else STREAM_MONITOR_INDEX
            monitor = get_monitor_by_index(sct, effective_index)
            w, h = monitor["width"], monitor["height"]
            vw = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
            start = time.time()
            while time.time() - start < secs:
                sct_img = sct.grab(monitor)
                frame = cv2.cvtColor(np.array(Image.frombytes("RGB", sct_img.size, sct_img.rgb)), cv2.COLOR_RGB2BGR)
                vw.write(frame)
                time.sleep(1.0 / fps)
            vw.release()
        return True
    except Exception:
        logging.exception("record_screen failed")
        return False

def webcam_video_selected(path, secs, camera_index=0, fps=10):
    """Записывает видео с указанной камеры"""
    try:
        if is_windows():
            cam = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        else:
            cam = cv2.VideoCapture(camera_index)
        
        if not cam.isOpened():
            logging.error(f"Cannot open camera {camera_index}")
            return False
        
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        ret, frame = cam.read()
        if not ret:
            cam.release()
            return False
            
        h, w = frame.shape[:2]
        vw = cv2.VideoWriter(path, fourcc, fps, (w, h))
        
        start = time.time()
        while time.time() - start < secs:
            ret, frame = cam.read()
            if not ret:
                break
            vw.write(frame)
        
        vw.release()
        cam.release()
        return True
        
    except Exception as e:
        logging.exception(f"webcam video failed for camera {camera_index}")
        return False
    
def test_camera_capture(camera_index):
    """Тестирует конкретную камеру перед использованием"""
    try:
        if is_windows():
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FPS, 30)
        else:
            cap = cv2.VideoCapture(camera_index)
        
        if not cap.isOpened():
            return False, "Не удалось открыть камеру"
        
        
        time.sleep(0.5)
        
        
        for attempt in range(3):
            ret, frame = cap.read()
            if ret and frame is not None:
                cap.release()
                return True, "Камера работает корректно"
            time.sleep(0.2)
        
        cap.release()
        return False, "Камера не возвращает кадры"
        
    except Exception as e:
        return False, f"Ошибка тестирования камеры: {e}"

def webcam_photo_improved(path, camera_index=0):
    """Улучшенная функция для съемки с камеры с детальной обратной связью"""
    try:
        logging.info(f"Attempting to capture photo from camera {camera_index}")
        
        
        is_working, message = test_camera_capture(camera_index)
        if not is_working:
            logging.error(f"Camera {camera_index} test failed: {message}")
            return False
        
        
        if is_windows():
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
        else:
            cap = cv2.VideoCapture(camera_index)
        
        if not cap.isOpened():
            logging.error(f"Cannot open camera {camera_index}")
            return False
        
        logging.info(f"Camera {camera_index} opened successfully, warming up...")
        
        
        for i in range(5):
            ret, frame = cap.read()
            if not ret:
                logging.warning(f"Failed to read frame {i+1}/5 during warmup")
                break
            time.sleep(0.1)
        
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            logging.error(f"Cannot capture final frame from camera {camera_index}")
            return False
        
        
        success = cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if success:
            logging.info(f"Photo successfully saved to {path}")
        else:
            logging.error(f"Failed to save photo to {path}")
        
        return success
        
    except Exception as e:
        logging.exception(f"webcam photo failed for camera {camera_index}: {e}")
        return False
    
def pause_play():
    try:
        pyautogui.press("playpause")
    except Exception:
        logging.exception("pause_play failed")

def next_track():
    try:
        pyautogui.press("nexttrack")
    except Exception:
        logging.exception("next_track failed")

def prev_track():
    try:
        pyautogui.press("prevtrack")
    except Exception:
        logging.exception("prev_track failed")

def check_web_password(req):
    pw = req.values.get("pw") or req.headers.get("X-PW") or req.headers.get('Authorization')
    if not pw:
        return False
    if pw.startswith('Basic '):
        return False
    return pw == WEB_PASSWORD

def virtual_keyboard_layout():
    """Returns the virtual keyboard layout"""
    keyboard = [
        [KeyboardButton("Q"), KeyboardButton("W"), KeyboardButton("E"), KeyboardButton("R"), KeyboardButton("T"), KeyboardButton("Y"), KeyboardButton("U"), KeyboardButton("I"), KeyboardButton("O"), KeyboardButton("P")],
        [KeyboardButton("A"), KeyboardButton("S"), KeyboardButton("D"), KeyboardButton("F"), KeyboardButton("G"), KeyboardButton("H"), KeyboardButton("J"), KeyboardButton("K"), KeyboardButton("L")],
        [KeyboardButton("Z"), KeyboardButton("X"), KeyboardButton("C"), KeyboardButton("V"), KeyboardButton("B"), KeyboardButton("N"), KeyboardButton("M")],
        [KeyboardButton("."), KeyboardButton("?"), KeyboardButton("!"), KeyboardButton("Enter"), KeyboardButton("Backspace")],
        [KeyboardButton("Пробел")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

@app.route('/', methods=['GET'])
def index():
    if not check_web_password(request):
        return "Unauthorized", 401
    try:
        with open("live_control.html", encoding="utf-8") as f:
            return render_template_string(f.read(), client=request.remote_addr, pw=WEB_PASSWORD)
    except Exception as e:
        logging.error(f"Failed to render template: {e}")
        return "Internal Server Error", 500

def jpeg_stream_generator():
    global _stream_running, STREAM_MONITOR_INDEX
    with mss.mss() as sct:
        monitor = get_monitor_by_index(sct, STREAM_MONITOR_INDEX)
        while _stream_running:
            try:
                sct_img = sct.grab(monitor)
                arr = np.asarray(sct_img)
                if arr is None:
                    time.sleep(0.1)
                    continue
                frame = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
                h, w = frame.shape[:2]
                max_w = 1280
                scale = 1.0
                if w > max_w:
                    scale = max_w / w
                    frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
                
                try:
                    
                    cursor_x, cursor_y = pyautogui.position()
                    
                    
                    relative_x = cursor_x - monitor['left']
                    relative_y = cursor_y - monitor['top']
                    
                    
                    if (0 <= relative_x < monitor['width'] and 
                        0 <= relative_y < monitor['height']):
                        
                        
                        cursor_x_scaled = int(relative_x * scale)
                        cursor_y_scaled = int(relative_y * scale)
                        
                        
                        if (0 <= cursor_x_scaled < frame.shape[1] and 
                            0 <= cursor_y_scaled < frame.shape[0]):
                            cv2.line(frame, (cursor_x_scaled - 5, cursor_y_scaled), 
                                   (cursor_x_scaled + 5, cursor_y_scaled), (0, 0, 255), 2)
                            cv2.line(frame, (cursor_x_scaled, cursor_y_scaled - 5), 
                                   (cursor_x_scaled, cursor_y_scaled + 5), (0, 0, 255), 2)
                    
                except Exception as e:
                    logging.error(f"Failed to draw cursor: {e}")
                
                ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), SCREENSHOT_Q])
                if not ret:
                    time.sleep(0.1)
                    continue
                frame_bytes = jpeg.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(1.0 / max(1, 60))
            except Exception as e:
                logging.error(f"Stream generator error: {e}")
                time.sleep(0.1)

@app.route("/stream")
def stream():
    if not check_web_password(request):
        return abort(401)
    return Response(jpeg_stream_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/mouse", methods=["POST"])
def api_mouse():
    if not check_web_password(request):
        return abort(401)
    action = request.form.get("action") or request.data.decode() or request.values.get('action')
    try:
        if action == "left":
            pyautogui.click()
        elif action == "right":
            pyautogui.click(button='right')
        elif action == "double":
            pyautogui.doubleClick()
        elif action == "up":
            pyautogui.moveRel(0, -40)
        elif action == "down":
            pyautogui.moveRel(0, 40)
        elif action == "left_move":
            pyautogui.moveRel(-40, 0)
        elif action == "right_move":
            pyautogui.moveRel(40, 0)
        return "OK"
    except Exception as e:
        logging.exception("Mouse API error")
        return str(e), 500

@app.route("/api/keyboard", methods=["POST"])
def api_keyboard():
    if not check_web_password(request):
        return abort(401)
    action = request.form.get("action") or request.values.get("action")
    text = request.form.get("text") or request.values.get("text") or ""
    try:
        if action == "type":
            pyautogui.typewrite(text)
        elif action == "enter":
            pyautogui.press('enter')
        elif action == "esc":
            pyautogui.press('esc')
        return "OK"
    except Exception as e:
        logging.exception("Keyboard API error")
        return str(e), 500

def start_flask_thread(host="0.0.0.0", port=STREAM_PORT):
    global _stream_running
    with _stream_lock:
        if _stream_running:
            logging.info("Flask already running")
            return
        _stream_running = True
    def run():
        logging.info("Starting Flask live server")
        socketio.run(app, host=host, port=port, debug=False, use_reloader=False)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t

def stop_flask():
    global _stream_running
    with _stream_lock:
        _stream_running = False
    logging.info("Requested Flask stop (may need manual kill)")

def start_ngrok_tunnel(port=STREAM_PORT, auth=NGROK_AUTH, authtoken=NGROK_TOKEN):
    global _ngrok_tunnel
    if not PYNGROK_AVAILABLE:
        logging.warning('pyngrok not available; install with pip install pyngrok')
        return None
    with _ngrok_lock:
        try:
            
            if authtoken and ngrok_conf:
                ngrok_conf.get_default().auth_token = authtoken
            
            options = {'bind_tls': True}
            if auth:
                options['auth'] = auth
            
            _ngrok_tunnel = ngrok.connect(addr=port, proto='http', **options)
            logging.info('ngrok tunnel started: %s', _ngrok_tunnel.public_url)
            return _ngrok_tunnel.public_url
        except Exception as e:
            logging.exception('Failed to start ngrok: %s', str(e))
            return None

def stop_ngrok_tunnel():
    global _ngrok_tunnel
    with _ngrok_lock:
        try:
            if _ngrok_tunnel:
                ngrok.disconnect(_ngrok_tunnel.public_url)
                ngrok.kill()
                logging.info('ngrok tunnel stopped')
        except Exception:
            logging.exception('Stopping ngrok failed')
        finally:
            _ngrok_tunnel = None

def perform_hotkey(hotkey):
    try:
        keys = hotkey.split("+")
        pyautogui.hotkey(*keys)
        return True
    except Exception:
        logging.exception("hotkey failed")
        return False


def get_sysinfo_text():
    try:
        uname = platform.uname()
        ip = get_local_ip()
        vm = psutil.virtual_memory()
        du = psutil.disk_usage("/")
        txt = (
            f"OS: {uname.system} {uname.release}\n"
            f"Node: {uname.node}\nIP: {ip}\n"
            f"CPU %: {psutil.cpu_percent()}%\n"
            f"RAM: {vm.percent}% ({vm.used//1024**2}MB/{vm.total//1024**2}MB)\n"
            f"Disk: {du.percent}% ({du.used//1024**3}GB/{du.total//1024**3}GB)"
        )
        return txt
    except Exception:
        logging.exception("get_sysinfo_text failed")
        return "Ошибка получения информации."

def get_available_cameras():
    """Быстро возвращает список доступных камер с их индексами"""
    cameras = []
    
    
    for i in range(10):
        try:
            if is_windows():
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            else:
                cap = cv2.VideoCapture(i)
            
            
            if cap.isOpened():
                
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                
                if width > 0 and height > 0:
                    
                    cap.set(cv2.CAP_PROP_FPS, 30)  
                    ret, frame = cap.read()
                    
                    if ret and frame is not None:
                        camera_name = f"Camera {i} ({int(width)}x{int(height)})"
                        cameras.append({
                            'index': i,
                            'name': camera_name,
                            'width': int(width),
                            'height': int(height)
                        })
                        logging.info(f"Found working camera {i}: {camera_name}")
                
                cap.release()
            
        except Exception as e:
            logging.debug(f"Camera {i} check failed: {e}")
            continue
    
    return cameras

def get_camera_info_windows():
    """Получает дополнительную информацию о камерах через DirectShow (только для Windows)"""
    try:
        import pygrabber.dshow_graph as dshow
        
        cameras_info = {}
        devices = dshow.FilterGraph().get_input_devices()
        
        for i, device_name in enumerate(devices):
            
            cameras_info[i] = {
                'name': device_name,
                'index': i
            }
            
        return cameras_info
        
    except ImportError:
        logging.info("pygrabber not available for DirectShow info")
        return {}
    except Exception as e:
        logging.error(f"Failed to get DirectShow info: {e}")
        return {}

def get_camera_names_windows():
    """Оптимизированная версия получения названий камер"""
    cameras = []
    
    
    basic_cameras = get_available_cameras()
    
    if is_windows():
        
        try:
            dshow_info = get_camera_info_windows()
            
            for camera in basic_cameras:
                idx = camera['index']
                if idx in dshow_info:
                    camera['name'] = f"{dshow_info[idx]['name']} (Index {idx})"
                cameras.append(camera)
                
        except Exception:
            
            cameras = basic_cameras
    else:
        
        try:
            import glob
            video_devices = glob.glob('/dev/video*')
            
            for camera in basic_cameras:
                idx = camera['index']
                if idx < len(video_devices):
                    try:
                        
                        device_path = video_devices[idx]
                        with open(f'/sys/class/video4linux/video{idx}/name', 'r') as f:
                            device_name = f.read().strip()
                        camera['name'] = f"{device_name} ({device_path})"
                    except Exception:
                        pass
                cameras.append(camera)
                
        except Exception:
            cameras = basic_cameras
    
    return cameras



PROGRAMS = {
}

def collect_cpu_ram_data():
    global data_collection_running
    with cpu_ram_lock:
        if data_collection_running:
            return
        data_collection_running = True
    try:
        while data_collection_running:
            start_time = time.time()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            ram_percent = psutil.virtual_memory().percent
            with cpu_ram_lock:
                cpu_ram_data["times"].append(start_time)
                cpu_ram_data["cpu"].append(cpu_percent)
                cpu_ram_data["ram"].append(ram_percent)
                if len(cpu_ram_data["times"]) > 60:
                    cpu_ram_data["times"] = cpu_ram_data["times"][-60:]
                    cpu_ram_data["cpu"] = cpu_ram_data["cpu"][-60:]
                    cpu_ram_data["ram"] = cpu_ram_data["ram"][-60:]
            time.sleep(10)
    except Exception:
        logging.exception("CPU/RAM data collection failed")
    finally:
        with cpu_ram_lock:
            data_collection_running = False

@owner_only
def download_cmd(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("Использование: /download <путь_к_файлу_или_папке>", reply_markup=main_menu_keyboard())
        return
    path = " ".join(args)
    if not os.path.exists(path):
        update.message.reply_text("Файл/папка не найдены.", reply_markup=main_menu_keyboard())
        return
    try:
        if os.path.isdir(path):
            update.message.reply_text("Это папка — создаю архив...")
            threading.Thread(target=make_archive_and_send, args=(update.effective_chat.id, path, context.bot), daemon=True).start()
            update.message.reply_text("Готово.", reply_markup=main_menu_keyboard())
            return
        else:
            update.message.reply_document(open(path, "rb"))
            update.message.reply_text("Готово.", reply_markup=main_menu_keyboard())
    except Exception:
        logging.exception("download command failed")
        update.message.reply_text("Ошибка отправки файла.", reply_markup=main_menu_keyboard())

@owner_only
def start_realtime_cmd(update: Update, context: CallbackContext):
    start_flask_thread()
    ip = get_local_ip()
    local_url = f"http://{ip}:{STREAM_PORT}/?pw={WEB_PASSWORD}"
    msg = f"Live (view-only) запущен локально:\n{local_url}\n\n"
    if NGROK_TOKEN:
        msg += "Чтобы пробросить в интернет через ngrok, используй команду /start_tunnel"
    else:
        msg += "ngrok не настроен (NGROK_TOKEN пуст)."
    update.message.reply_text(msg, reply_markup=main_menu_keyboard())

@owner_only
def stop_realtime_cmd(update: Update, context: CallbackContext):
    stop_flask()
    update.message.reply_text("Запрошена остановка live панели (возможно потребуется завершить процесс вручную).", reply_markup=main_menu_keyboard())

@owner_only
def start_tunnel_cmd(update: Update, context: CallbackContext):
    if not NGROK_TOKEN:
        update.message.reply_text("NGROK_TOKEN не задан в файле. Установи его и перезапусти бота.", reply_markup=main_menu_keyboard())
        return
    update.message.reply_text("Запускаю ngrok и создаю туннель (view-only)...")
    try:
        start_flask_thread()
        url = start_ngrok_tunnel()
        update.message.reply_text(f"ngrok tunnel создан: {url}\nПароль для веб-панели: {WEB_PASSWORD}\nНе публикуй этот URL публично.", reply_markup=main_menu_keyboard())
    except Exception as e:
        logging.exception("start_tunnel failed")
        update.message.reply_text(f"Ошибка запуска ngrok: {e}", reply_markup=main_menu_keyboard())

@owner_only
def stop_tunnel_cmd(update: Update, context: CallbackContext):
    stop_ngrok_tunnel()
    update.message.reply_text("ngrok туннель остановлен (если он был запущен).", reply_markup=main_menu_keyboard())

def error_handler(update: Update, context: CallbackContext):
    logging.exception("Update caused error: %s", context.error)


def chunk_text(text, n):
    for i in range(0, len(text), n):
        yield text[i:i+n]

def main():
    load_user_programs()
    if TOKEN == "" or TOKEN == "ВАШ_TELEGRAM_BOT_TOKEN":
        print("Поменяй TOKEN в начале файла перед запуском.")
        return
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    threading.Thread(target=collect_cpu_ram_data, daemon=True).start()
    dp.add_handler(CommandHandler("start", start_handler))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(CommandHandler("start_realtime", start_realtime_cmd))
    dp.add_handler(CommandHandler("stop_realtime", stop_realtime_cmd))
    dp.add_handler(CommandHandler("download", download_cmd))
    dp.add_handler(CommandHandler("start_tunnel", start_tunnel_cmd))
    dp.add_handler(CommandHandler("stop_tunnel", stop_tunnel_cmd))
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), message_handler))
    dp.add_handler(MessageHandler(Filters.document | Filters.photo, message_handler))
    dp.add_handler(CommandHandler("add_program", add_program_cmd))
    dp.add_handler(CommandHandler("remove_program", remove_program_cmd)) 
    dp.add_handler(CommandHandler("list_programs", list_programs_cmd))

    dp.add_error_handler(error_handler)
    try:
        logging.info("Starting bot polling...")
        updater.start_polling()
        updater.idle()
    except Exception:
        logging.exception("Bot polling failed")
    finally:
        stop_flask()
        stop_ngrok_tunnel()

if __name__ == "__main__":
    main()
