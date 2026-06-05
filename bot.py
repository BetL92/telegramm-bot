#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import sqlite3
import threading
import time
import json
import requests
import subprocess
import base64
import random
import string
import hashlib
import urllib.parse
import shutil
import psutil
import platform
import socket
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# ====================================================================================================
# НАСТРОЙКИ
# ====================================================================================================
BOT_TOKEN = "твой тоген телеграмм бота"
MISTRAL_API_KEY = "твой api ключ"
OWNER_ID = твой айди телеграмма

WEB_HOST = "0.0.0.0"
WEB_PORT = 5000

MAC_BASE_DIR = os.path.expanduser("~/Desktop/СуперБот")
MAC_DB_PATH = os.path.join(MAC_BASE_DIR, "superbot.db")
os.makedirs(MAC_BASE_DIR, exist_ok=True)

# ====================================================================================================
# MISTRAL AI
# ====================================================================================================
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

last_request_time = 0
MIN_REQUEST_INTERVAL = 2

def wait_for_rate_limit():
    global last_request_time
    now = time.time()
    elapsed = now - last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    last_request_time = time.time()

def ask_mistral(prompt):
    wait_for_rate_limit()
    try:
        headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "mistral-small-latest",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 800
        }
        r = requests.post(MISTRAL_URL, headers=headers, json=data, timeout=60)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        elif r.status_code == 429:
            return "⏳ Слишком много запросов. Подожди немного."
        return f"❌ Ошибка: {r.status_code}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def analyze_image_vision(image_bytes, prompt="Опиши подробно это изображение на русском языке"):
    wait_for_rate_limit()
    try:
        image_b64 = base64.b64encode(image_bytes).decode()
        headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "pixtral-12b-2409",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_b64}"}
                ]
            }],
            "max_tokens": 600,
            "temperature": 0.5
        }
        r = requests.post(MISTRAL_URL, headers=headers, json=data, timeout=90)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        elif r.status_code == 429:
            return "⏳ Слишком много запросов. Подожди немного."
        return f"❌ Ошибка Vision: {r.status_code}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def split_long_message(text, max_length=4000):
    if len(text) <= max_length:
        return [text]
    parts = []
    while len(text) > max_length:
        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = text.rfind(' ', 0, max_length)
        if split_pos == -1:
            split_pos = max_length
        parts.append(text[:split_pos])
        text = text[split_pos:]
    if text:
        parts.append(text)
    return parts

# ====================================================================================================
# БАЗА ДАННЫХ
# ====================================================================================================
def init_db():
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, name TEXT, joined TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS commands (id INTEGER PRIMARY KEY, user_id TEXT, command TEXT, result TEXT, time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, user_id TEXT, title TEXT, content TEXT, time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, user_id TEXT, task TEXT, priority TEXT, done INTEGER, time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bookmarks (id INTEGER PRIMARY KEY, user_id TEXT, title TEXT, url TEXT, time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS passwords (id INTEGER PRIMARY KEY, user_id TEXT, service TEXT, username TEXT, password TEXT, time TEXT)''')
    conn.commit()
    conn.close()

init_db()

def save_user(user_id, name):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (user_id, name, joined) VALUES (?,?,?)", (str(user_id), name, datetime.now().isoformat()))
    except:
        pass
    conn.commit()
    conn.close()

def save_command(user_id, cmd, result):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO commands (user_id, command, result, time) VALUES (?,?,?,?)",
              (str(user_id), cmd, result[:500], datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_stats(user_id=None):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    if user_id:
        c.execute("SELECT COUNT(*) FROM commands WHERE user_id = ?", (str(user_id),))
        return c.fetchone()[0]
    else:
        c.execute("SELECT COUNT(*) FROM users")
        users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM commands")
        cmds = c.fetchone()[0]
        return users, cmds

def get_chart_data():
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    daily = {}
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        count = c.execute("SELECT COUNT(*) FROM commands WHERE date(time) = ?", (date,)).fetchone()[0]
        daily[date] = count
    top = c.execute("SELECT command, COUNT(*) as cnt FROM commands GROUP BY command ORDER BY cnt DESC LIMIT 10").fetchall()
    conn.close()
    return {"daily": daily, "top_commands": [{"name": row[0], "count": row[1]} for row in top]}

def get_recent_commands(limit=30):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    rows = c.execute("SELECT command, result, time FROM commands ORDER BY time DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [{"command": row[0], "result": row[1][:100], "time": row[2]} for row in rows]

# ====================================================================================================
# УПРАВЛЕНИЕ КОМПЬЮТЕРОМ (ТОЛЬКО РАБОЧИЕ ФУНКЦИИ)
# ====================================================================================================
def run_apple(script):
    subprocess.run(['osascript', '-e', script], capture_output=True)

def volume_up():
    run_apple('set volume output volume (output volume of (get volume settings) + 10)')
    return "🔊 +10%"

def volume_down():
    run_apple('set volume output volume (output volume of (get volume settings) - 10)')
    return "🔉 -10%"

def mute():
    run_apple('set volume output muted true')
    return "🔇 Mute"

def unmute():
    run_apple('set volume output muted false')
    return "🔊 Unmute"

def screenshot():
    path = "/tmp/screen.png"
    subprocess.run(['screencapture', path])
    with open(path, 'rb') as f:
        return f.read()

def screenshot_area():
    path = "/tmp/area.png"
    subprocess.run(['screencapture', '-i', path])
    try:
        with open(path, 'rb') as f:
            return f.read()
    except:
        return None

def lock_screen():
    run_apple('keystroke "q" using {command down, control down}')
    return "🔒 Блокировка"

def sleep_mode():
    subprocess.run(['pmset', 'sleepnow'])
    return "💤 Сон"

def show_desktop():
    run_apple('key code 53 using command down')
    return "🖥️ Рабочий стол"

def execute_pc_action(action):
    actions = {
        "volume_up": volume_up, "volume_down": volume_down, "mute": mute, "unmute": unmute,
        "screenshot": screenshot, "screenshot_area": screenshot_area,
        "lock": lock_screen, "sleep": sleep_mode, "show_desktop": show_desktop
    }
    if action in actions:
        return actions[action]()
    return f"❌ Неизвестное действие: {action}"

# ====================================================================================================
# ПОЛЕЗНЫЕ ФУНКЦИИ (ИНФОРМАЦИЯ О СИСТЕМЕ)
# ====================================================================================================
def get_cpu_info():
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        cpu_freq = psutil.cpu_freq()
        cpu_cores = psutil.cpu_count()
        cpu_stats = psutil.cpu_stats()
        load_avg = psutil.getloadavg()
        return {
            "percent": cpu_percent,
            "freq_current": cpu_freq.current if cpu_freq else 0,
            "freq_max": cpu_freq.max if cpu_freq else 0,
            "cores": cpu_cores,
            "ctx_switches": cpu_stats.ctx_switches,
            "interrupts": cpu_stats.interrupts,
            "load_avg_1min": load_avg[0],
            "load_avg_5min": load_avg[1],
            "load_avg_15min": load_avg[2]
        }
    except:
        return {"percent": 0, "freq_current": 0, "freq_max": 0, "cores": 0, "ctx_switches": 0, "interrupts": 0, "load_avg_1min": 0, "load_avg_5min": 0, "load_avg_15min": 0}

def get_memory_info():
    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total": mem.total,
            "available": mem.available,
            "percent": mem.percent,
            "used": mem.used,
            "free": mem.free,
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_percent": swap.percent
        }
    except:
        return {"total": 0, "available": 0, "percent": 0, "used": 0, "free": 0}

def get_disk_info():
    try:
        disk = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()
        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
            "read_bytes": disk_io.read_bytes if disk_io else 0,
            "write_bytes": disk_io.write_bytes if disk_io else 0,
            "read_count": disk_io.read_count if disk_io else 0,
            "write_count": disk_io.write_count if disk_io else 0
        }
    except:
        return {"total": 0, "used": 0, "free": 0, "percent": 0}

def get_network_info():
    try:
        net = psutil.net_io_counters()
        addresses = []
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    addresses.append({"interface": iface, "ip": addr.address})
        return {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
            "errin": net.errin,
            "errout": net.errout,
            "dropin": net.dropin,
            "dropout": net.dropout,
            "addresses": addresses
        }
    except:
        return {"bytes_sent": 0, "bytes_recv": 0, "packets_sent": 0, "packets_recv": 0, "addresses": []}

def get_battery_info():
    try:
        battery = psutil.sensors_battery()
        if battery:
            return {
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
                "seconds_left": battery.secsleft
            }
        return {"percent": 0, "power_plugged": False, "seconds_left": -1}
    except:
        return {"percent": 0, "power_plugged": False, "seconds_left": -1}

def get_processes_info():
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'memory_rss']):
            try:
                info = proc.info
                info['memory_mb'] = info.get('memory_rss', 0) / (1024 * 1024)
                processes.append(info)
            except:
                pass
        processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        return processes[:25]
    except:
        return []

def get_system_info_full():
    try:
        return {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "version": platform.version(),
            "processor": platform.processor(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
            "uptime": str(timedelta(seconds=int(time.time() - psutil.boot_time())))
        }
    except:
        return {"hostname": "unknown", "os": "unknown", "version": "unknown", "processor": "unknown", "uptime": "unknown"}

def get_temperature_info():
    try:
        temps = psutil.sensors_temperatures()
        result = {}
        for name, entries in temps.items():
            result[name] = [{"current": entry.current, "high": entry.high, "critical": entry.critical} for entry in entries]
        return result
    except:
        return {}

def get_connections_info():
    try:
        conns = psutil.net_connections(kind='inet')
        result = []
        for conn in conns[:50]:
            result.append({
                "fd": conn.fd,
                "family": str(conn.family),
                "type": str(conn.type),
                "laddr": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                "raddr": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                "status": conn.status,
                "pid": conn.pid
            })
        return result
    except:
        return []

# ====================================================================================================
# TELEGRAM БОТ
# ====================================================================================================
MAIN_MENU = ReplyKeyboardMarkup([
    ["🖥️ УПРАВЛЕНИЕ ПК", "🧠 ИИ ЧАТ", "📷 АНАЛИЗ ФОТО"],
    ["📝 ЗАМЕТКИ", "📋 ЗАДАЧИ", "⭐ ЗАКЛАДКИ"],
    ["🔐 ПАРОЛИ", "💻 СИСТЕМА", "🌐 ВЕБ ПАНЕЛЬ"],
    ["📊 СТАТИСТИКА", "❓ ПОМОЩЬ"]
], resize_keyboard=True)

PC_MENU = ReplyKeyboardMarkup([
    ["🔊 ГРОМЧЕ", "🔉 ТИШЕ", "🔇 МУТ", "🔊 ВКЛ"],
    ["📸 СКРИНШОТ", "✂️ ОБЛАСТЬ", "🔒 БЛОК", "💤 СОН"],
    ["🖥️ ДЕСКТОП", "◀️ НАЗАД"]
], resize_keyboard=True)

def is_owner(user_id):
    return user_id == OWNER_ID

def add_note(user_id, title, content):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO notes (user_id, title, content, time) VALUES (?,?,?,?)",
              (str(user_id), title, content, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return f"✅ Заметка '{title}' сохранена"

def get_notes(user_id):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, time FROM notes WHERE user_id = ? ORDER BY time DESC", (str(user_id),))
    return c.fetchall()

def delete_note(note_id):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()
    return f"🗑️ Заметка удалена"

def add_task(user_id, task, priority="medium"):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (user_id, task, priority, time) VALUES (?,?,?,?)",
              (str(user_id), task, priority, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return f"✅ Задача добавлена"

def get_tasks(user_id, show_done=False):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    if show_done:
        c.execute("SELECT id, task, priority, done FROM tasks WHERE user_id = ? ORDER BY time DESC", (str(user_id),))
    else:
        c.execute("SELECT id, task, priority, done FROM tasks WHERE user_id = ? AND done = 0 ORDER BY priority DESC", (str(user_id),))
    return c.fetchall()

def complete_task(task_id):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return f"✅ Задача выполнена"

def delete_task(task_id):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return f"🗑️ Задача удалена"

def add_bookmark(user_id, title, url):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO bookmarks (user_id, title, url, time) VALUES (?,?,?,?)",
              (str(user_id), title, url, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return f"⭐ Закладка '{title}' сохранена"

def get_bookmarks(user_id):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, url FROM bookmarks WHERE user_id = ? ORDER BY time DESC", (str(user_id),))
    return c.fetchall()

def delete_bookmark(bm_id):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM bookmarks WHERE id = ?", (bm_id,))
    conn.commit()
    conn.close()
    return f"🗑️ Закладка удалена"

def encrypt_password(password):
    salt = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
    return base64.b64encode(f"{salt}:{password}".encode()).decode()

def decrypt_password(encrypted):
    return base64.b64decode(encrypted).decode().split(":", 1)[1]

def save_password(user_id, service, username, password):
    encrypted = encrypt_password(password)
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO passwords (user_id, service, username, password, time) VALUES (?,?,?,?,?)",
              (str(user_id), service, username, encrypted, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return f"🔐 Пароль для '{service}' сохранён"

def get_passwords(user_id):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, service, username FROM passwords WHERE user_id = ? ORDER BY service", (str(user_id),))
    return c.fetchall()

def get_password(user_id, service):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, password FROM passwords WHERE user_id = ? AND service = ?", (str(user_id), service))
    result = c.fetchone()
    conn.close()
    if result:
        decrypted = decrypt_password(result[1])
        return f"🔐 {service}\n👤 Логин: {result[0]}\n🔑 Пароль: {decrypted}"
    return "❌ Пароль не найден"

def delete_password(pass_id):
    conn = sqlite3.connect(MAC_DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM passwords WHERE id = ?", (pass_id,))
    conn.commit()
    conn.close()
    return f"🗑️ Пароль удалён"

def get_system_info_text():
    cpu = get_cpu_info()
    mem = get_memory_info()
    disk = get_disk_info()
    net = get_network_info()
    battery = get_battery_info()
    sys_info = get_system_info_full()
    
    text = f"""
💻 *СИСТЕМНАЯ ИНФОРМАЦИЯ*
━━━━━━━━━━━━━━━━━━━━━━

🖥️ *ОС:* {sys_info['os']}
💻 *Хост:* {sys_info['hostname']}
🔄 *Аптайм:* {sys_info['uptime']}
⚡ *Python:* {sys_info['python_version']}

━━━━━━━━━━━━━━━━━━━━━━

*CPU:*
📊 Загрузка: {cpu['percent']}%
🔢 Ядра: {cpu['cores']}
📈 Частота: {cpu['freq_current']:.0f}/{cpu['freq_max']:.0f} МГц
📉 Нагрузка: {cpu['load_avg_1min']:.2f}, {cpu['load_avg_5min']:.2f}, {cpu['load_avg_15min']:.2f}

*ПАМЯТЬ:*
💾 RAM: {mem['percent']}% ({mem['used']//(1024**3)}/{mem['total']//(1024**3)} GB)
🔄 Swap: {mem['swap_percent']}%

*ДИСК:*
💽 Занято: {disk['percent']}% ({disk['used']//(1024**3)}/{disk['total']//(1024**3)} GB)

*СЕТЬ:*
📡 Отправлено: {net['bytes_sent']//(1024**2)} MB
📥 Получено: {net['bytes_recv']//(1024**2)} MB

*БАТАРЕЯ:*
🔋 Заряд: {battery['percent']}%
{'🔌 На зарядке' if battery['power_plugged'] else '🔋 От батареи'}
"""
    return text

# ====================================================================================================
# ТЕЛЕГРАМ ОБРАБОТЧИКИ
# ====================================================================================================
async def start(update, context):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    save_user(user.id, user.first_name)
    await update.message.reply_text(
        f"🤖 *СУПЕР БОТ v37* — TELEGRAM + WEB\n\n"
        f"🔥 Привет, {user.first_name}!\n\n"
        f"*ВОЗМОЖНОСТИ:*\n"
        f"• 🧠 ИИ чат (Mistral)\n"
        f"• 📷 Анализ фото (Pixtral)\n"
        f"• 🖥️ Управление Mac\n"
        f"• 📝 Заметки\n"
        f"• 📋 Задачи\n"
        f"• ⭐ Закладки\n"
        f"• 🔐 Пароли\n"
        f"• 💻 Мониторинг системы\n"
        f"• 🌐 Веб-панель: http://localhost:5000\n\n"
        f"👇 *ИСПОЛЬЗУЙ КНОПКИ!*",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )

async def handle_text(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    
    text = update.message.text

    if text == "🖥️ УПРАВЛЕНИЕ ПК":
        await update.message.reply_text("🖥️ *Управление компьютером*", parse_mode="Markdown", reply_markup=PC_MENU)
    elif text == "🧠 ИИ ЧАТ":
        await update.message.reply_text("🧠 *Напиши свой вопрос*", parse_mode="Markdown")
        context.user_data['mode'] = 'ai'
    elif text == "📷 АНАЛИЗ ФОТО":
        await update.message.reply_text("📷 *Отправь фото*", parse_mode="Markdown")
    elif text == "📝 ЗАМЕТКИ":
        await update.message.reply_text("📝 /addnote Заголовок | Текст\n📋 /mynotes\n🗑️ /delnote ID", parse_mode="Markdown")
    elif text == "📋 ЗАДАЧИ":
        await update.message.reply_text("📋 /addtask задача | приоритет\n📋 /mytasks\n✅ /done ID\n🗑️ /deltask ID", parse_mode="Markdown")
    elif text == "⭐ ЗАКЛАДКИ":
        await update.message.reply_text("⭐ /addbookmark Название | URL\n📋 /mybookmarks\n🗑️ /delbookmark ID", parse_mode="Markdown")
    elif text == "🔐 ПАРОЛИ":
        await update.message.reply_text("🔐 /savepass сервис | логин | пароль\n📋 /mypass\n🔍 /getpass сервис\n🗑️ /delpass ID", parse_mode="Markdown")
    elif text == "💻 СИСТЕМА":
        info = get_system_info_text()
        await update.message.reply_text(info, parse_mode="Markdown")
    elif text == "🌐 ВЕБ ПАНЕЛЬ":
        await update.message.reply_text("🌐 *Веб-панель*\nhttp://localhost:5000\n\nОткрой в браузере на этом же компьютере.", parse_mode="Markdown")
        await update.message.reply_text("🌐 *Веб-панель*\nhttp://localhost:5000", parse_mode="Markdown", reply_markup=keyboard)
    elif text == "📊 СТАТИСТИКА":
        users, cmds = get_stats()
        user_cmds = get_stats(user_id)
        await update.message.reply_text(f"📊 *Статистика*\n👥 {users} пользователей\n📝 {cmds} команд\n👤 Твоих: {user_cmds}", parse_mode="Markdown")
    elif text == "❓ ПОМОЩЬ":
        await update.message.reply_text("❓ *Помощь*\n\n🧠 ИИ ЧАТ — задай вопрос\n📷 АНАЛИЗ ФОТО — отправь картинку\n🖥️ УПРАВЛЕНИЕ ПК — клавиши, скриншоты\n📝 ЗАМЕТКИ — сохраняй важное\n📋 ЗАДАЧИ — список дел\n⭐ ЗАКЛАДКИ — сохраняй ссылки\n🔐 ПАРОЛИ — храни пароли\n💻 СИСТЕМА — мониторинг Mac\n🌐 ВЕБ ПАНЕЛЬ — http://localhost:5000", parse_mode="Markdown")
    elif text == "◀️ НАЗАД":
        await update.message.reply_text("◀️ Главное меню", reply_markup=MAIN_MENU)
        context.user_data['mode'] = None
    elif text in ["🔊 ГРОМЧЕ", "🔉 ТИШЕ", "🔇 МУТ", "🔊 ВКЛ", "📸 СКРИНШОТ", "✂️ ОБЛАСТЬ", "🔒 БЛОК", "💤 СОН", "🖥️ ДЕСКТОП"]:
        action_map = {
            "🔊 ГРОМЧЕ": "volume_up", "🔉 ТИШЕ": "volume_down", "🔇 МУТ": "mute", "🔊 ВКЛ": "unmute",
            "📸 СКРИНШОТ": "screenshot", "✂️ ОБЛАСТЬ": "screenshot_area",
            "🔒 БЛОК": "lock", "💤 СОН": "sleep", "🖥️ ДЕСКТОП": "show_desktop"
        }
        if text in action_map:
            if text in ["📸 СКРИНШОТ", "✂️ ОБЛАСТЬ"]:
                img = execute_pc_action(action_map[text])
                if img:
                    await update.message.reply_photo(img, caption="📸 Скриншот")
                else:
                    await update.message.reply_text("❌ Отменено")
            else:
                result = execute_pc_action(action_map[text])
                save_command(user_id, text, result)
                await update.message.reply_text(result)
    elif context.user_data.get('mode') == 'ai':
        await update.message.reply_text("🤔 *Думаю через Mistral...*", parse_mode="Markdown")
        answer = ask_mistral(text)
        save_command(user_id, "ai", answer[:200])
        for part in split_long_message(answer):
            await update.message.reply_text(f"🧠 *Mistral:*\n\n{part}", parse_mode="Markdown")
        context.user_data['mode'] = None
    else:
        await update.message.reply_text("Используй кнопки 👇", reply_markup=MAIN_MENU)

async def handle_photo(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    await update.message.reply_text("👁️ *Анализирую изображение...*", parse_mode="Markdown")
    photo = await update.message.photo[-1].get_file()
    img_bytes = await photo.download_as_bytearray()
    result = analyze_image_vision(img_bytes)
    save_command(user_id, "vision", result[:200])
    for part in split_long_message(result):
        await update.message.reply_text(f"🖼️ *Pixtral:*\n\n{part}", parse_mode="Markdown")

async def handle_callback(update, context):
    await update.callback_query.answer()

async def cmd_addnote(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    if not context.args:
        await update.message.reply_text("❌ /addnote Заголовок | Текст")
        return
    text = ' '.join(context.args)
    if '|' in text:
        title, content = text.split('|', 1)
        await update.message.reply_text(add_note(user_id, title.strip(), content.strip()))
    else:
        await update.message.reply_text("❌ Используй |")

async def cmd_mynotes(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    notes = get_notes(user_id)
    if notes:
        result = "\n".join([f"📄 ID:{n[0]} {n[1]} ({n[2][:16]})" for n in notes[:10]])
        await update.message.reply_text(f"📝 *Заметки:*\n{result}\n\n🗑️ /delnote ID", parse_mode="Markdown")
    else:
        await update.message.reply_text("📝 Нет заметок")

async def cmd_delnote(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    if not context.args:
        await update.message.reply_text("❌ /delnote ID")
        return
    try:
        await update.message.reply_text(delete_note(int(context.args[0])))
    except:
        await update.message.reply_text("❌ Введи ID")

async def cmd_addtask(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    if not context.args:
        await update.message.reply_text("❌ /addtask задача | приоритет")
        return
    text = ' '.join(context.args)
    if '|' in text:
        task, priority = text.split('|', 1)
        await update.message.reply_text(add_task(user_id, task.strip(), priority.strip()))
    else:
        await update.message.reply_text(add_task(user_id, text))

async def cmd_mytasks(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    tasks = get_tasks(user_id)
    if tasks:
        priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        result = "\n".join([f"{priority_emoji.get(t[2], '⚪')} ID:{t[0]} {t[1]}" for t in tasks[:10]])
        await update.message.reply_text(f"📋 *Задачи:*\n{result}\n\n✅ /done ID\n🗑️ /deltask ID", parse_mode="Markdown")
    else:
        await update.message.reply_text("📋 Нет задач")

async def cmd_done(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    if not context.args:
        await update.message.reply_text("❌ /done ID")
        return
    try:
        await update.message.reply_text(complete_task(int(context.args[0])))
    except:
        await update.message.reply_text("❌ Введи ID")

async def cmd_deltask(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    if not context.args:
        await update.message.reply_text("❌ /deltask ID")
        return
    try:
        await update.message.reply_text(delete_task(int(context.args[0])))
    except:
        await update.message.reply_text("❌ Введи ID")

async def cmd_addbookmark(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    if not context.args:
        await update.message.reply_text("❌ /addbookmark Название | URL")
        return
    text = ' '.join(context.args)
    if '|' in text:
        title, url = text.split('|', 1)
        await update.message.reply_text(add_bookmark(user_id, title.strip(), url.strip()))
    else:
        await update.message.reply_text("❌ Формат: Название | URL")

async def cmd_mybookmarks(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    bookmarks = get_bookmarks(user_id)
    if bookmarks:
        result = "\n".join([f"⭐ ID:{b[0]} {b[1]} → {b[2]}" for b in bookmarks[:10]])
        await update.message.reply_text(f"📑 *Закладки:*\n{result}\n\n🗑️ /delbookmark ID", parse_mode="Markdown")
    else:
        await update.message.reply_text("⭐ Нет закладок")

async def cmd_delbookmark(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    if not context.args:
        await update.message.reply_text("❌ /delbookmark ID")
        return
    try:
        await update.message.reply_text(delete_bookmark(int(context.args[0])))
    except:
        await update.message.reply_text("❌ Введи ID")

async def cmd_savepass(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    if len(context.args) < 3:
        await update.message.reply_text("❌ /savepass сервис | логин | пароль")
        return
    text = ' '.join(context.args)
    parts = text.split('|')
    service = parts[0].strip()
    username = parts[1].strip() if len(parts) > 1 else ""
    password = parts[2].strip() if len(parts) > 2 else ""
    await update.message.reply_text(save_password(user_id, service, username, password))

async def cmd_mypass(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    passwords = get_passwords(user_id)
    if passwords:
        result = "\n".join([f"🔐 ID:{p[0]} {p[1]} ({p[2]})" for p in passwords[:10]])
        await update.message.reply_text(f"📋 *Пароли:*\n{result}\n\n🔍 /getpass сервис\n🗑️ /delpass ID", parse_mode="Markdown")
    else:
        await update.message.reply_text("🔐 Нет паролей")

async def cmd_getpass(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    if not context.args:
        await update.message.reply_text("❌ /getpass сервис")
        return
    service = ' '.join(context.args)
    await update.message.reply_text(get_password(user_id, service))

async def cmd_delpass(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return
    if not context.args:
        await update.message.reply_text("❌ /delpass ID")
        return
    try:
        await update.message.reply_text(delete_password(int(context.args[0])))
    except:
        await update.message.reply_text("❌ Введи ID")

# ====================================================================================================
# ВЕБ-СЕРВЕР (КРАСИВЫЙ ОГРОМНЫЙ HTML)
# ====================================================================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-2026'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>SUPER BOT v37 | Ultimate Control Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,100;14..32,200;14..32,300;14..32,400;14..32,500;14..32,600;14..32,700;14..32,800;14..32,900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0a0a1a 0%, #1a0b2e 50%, #0f0f1a 100%);
            min-height: 100vh;
            overflow-x: hidden;
            color: #fff;
        }
        /* Анимированный фон */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 50%, rgba(168,85,247,0.15) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(236,72,153,0.1) 0%, transparent 50%),
                repeating-linear-gradient(45deg, rgba(255,255,255,0.02) 0px, rgba(255,255,255,0.02) 2px, transparent 2px, transparent 8px);
            pointer-events: none;
            z-index: 0;
        }
        /* Частицы */
        .particles {
            position: fixed;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
        }
        .particle {
            position: absolute;
            background: linear-gradient(135deg, #a855f7, #ec4899);
            border-radius: 50%;
            opacity: 0.2;
            animation: floatParticle 20s infinite;
        }
        @keyframes floatParticle {
            0%,100% { transform: translateY(0) translateX(0); }
            25% { transform: translateY(-80px) translateX(40px); }
            50% { transform: translateY(0) translateX(80px); }
            75% { transform: translateY(80px) translateX(40px); }
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 25px;
            position: relative;
            z-index: 1;
        }
        /* Хедер */
        .header {
            text-align: center;
            margin-bottom: 40px;
            animation: fadeInDown 0.8s cubic-bezier(0.68,-0.55,0.265,1.55);
        }
        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-60px) rotateX(-30deg); }
            to { opacity: 1; transform: translateY(0) rotateX(0); }
        }
        .logo {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
            margin-bottom: 20px;
        }
        .logo-icon {
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #a855f7, #ec4899);
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: pulse 2s ease-in-out infinite;
        }
        @keyframes pulse {
            0%,100% { box-shadow: 0 0 0 0 rgba(168,85,247,0.7); }
            50% { box-shadow: 0 0 0 20px rgba(168,85,247,0); }
        }
        .logo-icon i { font-size: 2em; color: white; }
        h1 {
            font-size: 2.8em;
            font-weight: 800;
            background: linear-gradient(135deg, #fff, #a855f7, #ec4899, #fff);
            background-size: 200% auto;
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            animation: shimmer 3s linear infinite;
        }
        @keyframes shimmer {
            0% { background-position: 0% center; }
            100% { background-position: 200% center; }
        }
        .subtitle { color: #a0a0b0; margin-top: 10px; }
        .badge-container {
            display: flex;
            justify-content: center;
            gap: 15px;
            flex-wrap: wrap;
            margin-top: 20px;
        }
        .badge {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            padding: 6px 16px;
            border-radius: 30px;
            font-size: 0.8em;
            border: 1px solid rgba(168,85,247,0.3);
            transition: 0.3s;
        }
        .badge:hover { border-color: #a855f7; transform: translateY(-2px); }
        /* Статистика */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 25px;
            margin-bottom: 35px;
        }
        .stat-card {
            background: rgba(20,15,40,0.6);
            backdrop-filter: blur(15px);
            border: 1px solid rgba(168,85,247,0.3);
            border-radius: 24px;
            padding: 25px;
            text-align: center;
            transition: 0.3s;
            position: relative;
            overflow: hidden;
        }
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
            transition: left 0.5s;
        }
        .stat-card:hover::before { left: 100%; }
        .stat-card:hover { transform: translateY(-5px); border-color: #a855f7; box-shadow: 0 20px 40px rgba(0,0,0,0.3); }
        .stat-icon { font-size: 2.2em; margin-bottom: 15px; }
        .stat-value { font-size: 2.2em; font-weight: 800; background: linear-gradient(135deg, #a855f7, #ec4899); -webkit-background-clip: text; background-clip: text; color: transparent; margin-bottom: 8px; }
        .stat-label { font-size: 0.85em; color: #a0a0b0; text-transform: uppercase; letter-spacing: 1px; }
        /* Основная сетка */
        .main-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 25px;
            margin-bottom: 25px;
        }
        @media (max-width: 1100px) { .main-grid { grid-template-columns: 1fr; } }
        /* Карточки */
        .card {
            background: rgba(15,15,35,0.6);
            backdrop-filter: blur(15px);
            border: 1px solid rgba(168,85,247,0.2);
            border-radius: 28px;
            overflow: hidden;
            transition: 0.4s;
        }
        .card:hover { border-color: #a855f7; transform: translateY(-3px); box-shadow: 0 25px 50px rgba(0,0,0,0.3); }
        .card-header {
            background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(15,10,35,0.9));
            padding: 20px 25px;
            display: flex;
            align-items: center;
            gap: 15px;
            border-bottom: 1px solid rgba(168,85,247,0.2);
        }
        .card-header i { font-size: 1.6em; color: #a855f7; }
        .card-header h2 { font-size: 1.2em; font-weight: 600; flex: 1; }
        .card-header .badge-count {
            background: linear-gradient(135deg, #a855f7, #ec4899);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.7em;
            font-weight: 600;
        }
        .card-content { padding: 25px; }
        /* Кнопки управления */
        .control-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
            gap: 12px;
        }
        .action-btn {
            background: linear-gradient(135deg, rgba(139,92,246,0.2), rgba(15,10,35,0.8));
            border: 1px solid rgba(168,85,247,0.3);
            padding: 12px;
            border-radius: 16px;
            cursor: pointer;
            font-weight: 500;
            font-size: 0.85em;
            transition: 0.2s;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .action-btn:hover {
            background: linear-gradient(135deg, #a855f7, #ec4899);
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(139,92,246,0.3);
        }
        /* Системная информация */
        .system-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        .system-item {
            background: rgba(10,5,25,0.6);
            border-radius: 16px;
            padding: 15px;
            text-align: center;
        }
        .system-value { font-size: 1.5em; font-weight: 700; color: #a855f7; }
        .system-label { font-size: 0.75em; color: #a0a0b0; margin-top: 5px; }
        .progress-bar {
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            height: 8px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-fill {
            background: linear-gradient(90deg, #a855f7, #ec4899);
            height: 100%;
            border-radius: 10px;
            transition: width 0.3s;
        }
        /* Таблица команд */
        .commands-table {
            width: 100%;
            border-collapse: collapse;
        }
        .commands-table th {
            text-align: left;
            padding: 12px;
            color: #a855f7;
            border-bottom: 1px solid rgba(168,85,247,0.2);
            font-weight: 600;
        }
        .commands-table td { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .commands-table tr:hover { background: rgba(139,92,246,0.1); }
        .chart-container { height: 300px; position: relative; }
        .commands-list {
            max-height: 400px;
            overflow-y: auto;
        }
        .commands-list::-webkit-scrollbar { width: 6px; }
        .commands-list::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); border-radius: 10px; }
        .commands-list::-webkit-scrollbar-thumb { background: #a855f7; border-radius: 10px; }
        .command-item {
            background: rgba(30,20,55,0.5);
            padding: 12px 15px;
            border-radius: 12px;
            margin-bottom: 8px;
            border-left: 3px solid #a855f7;
            transition: 0.2s;
        }
        .command-item:hover { background: rgba(50,35,80,0.6); transform: translateX(5px); }
        .command-name { font-weight: 600; color: #a855f7; font-size: 0.85em; margin-bottom: 5px; }
        .command-result { font-size: 0.8em; color: #a0a0b0; word-break: break-word; }
        .command-time { font-size: 0.7em; color: #6a6a8a; margin-top: 5px; }
        /* Уведомления */
        .notification {
            position: fixed;
            bottom: 25px;
            right: 25px;
            background: linear-gradient(135deg, #a855f7, #ec4899);
            padding: 14px 22px;
            border-radius: 18px;
            display: flex;
            align-items: center;
            gap: 12px;
            z-index: 1000;
            animation: slideInRight 0.3s cubic-bezier(0.68,-0.55,0.265,1.55);
            font-weight: 500;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        @keyframes slideInRight {
            from { opacity: 0; transform: translateX(100px); }
            to { opacity: 1; transform: translateX(0); }
        }
        @media (max-width: 768px) {
            .container { padding: 15px; }
            h1 { font-size: 1.8em; }
            .stats-grid { grid-template-columns: repeat(2,1fr); }
            .system-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 500px) { .stats-grid { grid-template-columns: 1fr; } }
        .loader {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #a855f7;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .empty-state {
            text-align: center;
            padding: 50px;
            color: #a0a0b0;
        }
        .empty-state i { font-size: 3em; margin-bottom: 15px; opacity: 0.5; }
    </style>
</head>
<body>
    <div class="particles" id="particles"></div>
    <div class="container">
        <div class="header">
            <div class="logo">
                <div class="logo-icon"><i class="fas fa-crown"></i></div>
                <h1>SUPER BOT v37</h1>
            </div>
            <div class="subtitle">МОЩНЫЙ ИИ-АССИСТЕНТ НА MISTRAL AI</div>
            <div class="badge-container">
                <div class="badge"><i class="fas fa-check-circle" style="color:#10b981;"></i> Система активна</div>
                <div class="badge"><i class="fas fa-brain"></i> Mistral AI</div>
                <div class="badge"><i class="fas fa-chart-line"></i> Real-time</div>
                <div class="badge"><i class="fas fa-shield-alt"></i> Secure</div>
            </div>
        </div>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-icon"><i class="fas fa-users"></i></div><div class="stat-value" id="users">0</div><div class="stat-label">Пользователей</div></div>
            <div class="stat-card"><div class="stat-icon"><i class="fas fa-terminal"></i></div><div class="stat-value" id="commands">0</div><div class="stat-label">Всего команд</div></div>
            <div class="stat-card"><div class="stat-icon"><i class="fas fa-calendar-day"></i></div><div class="stat-value" id="today">0</div><div class="stat-label">Сегодня</div></div>
            <div class="stat-card"><div class="stat-icon"><i class="fas fa-microchip"></i></div><div class="stat-value" id="cpu">0%</div><div class="stat-label">CPU</div></div>
        </div>
        <div class="main-grid">
            <div class="card">
                <div class="card-header"><i class="fas fa-gamepad"></i><h2>Управление компьютером</h2><div class="badge-count">9 действий</div></div>
                <div class="card-content"><div class="control-grid" id="controls"></div></div>
            </div>
            <div class="card">
                <div class="card-header"><i class="fas fa-desktop"></i><h2>Мониторинг системы</h2><div class="badge-count">живые данные</div></div>
                <div class="card-content">
                    <div class="system-grid">
                        <div class="system-item"><div class="system-value" id="cpu-val">0%</div><div class="system-label">CPU</div><div class="progress-bar"><div class="progress-fill" id="cpu-fill" style="width:0%"></div></div></div>
                        <div class="system-item"><div class="system-value" id="mem-val">0%</div><div class="system-label">RAM</div><div class="progress-bar"><div class="progress-fill" id="mem-fill" style="width:0%"></div></div></div>
                        <div class="system-item"><div class="system-value" id="disk-val">0%</div><div class="system-label">Диск</div><div class="progress-bar"><div class="progress-fill" id="disk-fill" style="width:0%"></div></div></div>
                        <div class="system-item"><div class="system-value" id="battery-val">0%</div><div class="system-label">Батарея</div><div class="progress-bar"><div class="progress-fill" id="battery-fill" style="width:0%"></div></div></div>
                    </div>
                    <div class="system-item" style="margin-top:10px;"><div class="system-value" id="ip-val">0.0.0.0</div><div class="system-label">IP адрес</div></div>
                </div>
            </div>
            <div class="card">
                <div class="card-header"><i class="fas fa-chart-line"></i><h2>Активность за 7 дней</h2><div class="badge-count">динамика</div></div>
                <div class="card-content"><canvas id="activity-chart" class="chart-container"></canvas></div>
            </div>
            <div class="card">
                <div class="card-header"><i class="fas fa-chart-bar"></i><h2>Топ команд</h2><div class="badge-count">по популярности</div></div>
                <div class="card-content"><canvas id="top-chart" class="chart-container"></canvas></div></div>
            <div class="card" style="grid-column:1/-1;">
                <div class="card-header"><i class="fas fa-history"></i><h2>История команд</h2><i class="fas fa-sync-alt" id="refresh-btn" style="cursor:pointer;opacity:0.7;"></i></div>
                <div class="card-content"><div id="commands-list" class="commands-list"></div></div>
            </div>
        </div>
    </div>
    <script>
        const actions = ['volume_up', 'volume_down', 'mute', 'unmute', 'screenshot', 'screenshot_area', 'lock', 'sleep', 'show_desktop'];
        const container = document.getElementById('controls');
        const icons = {volume_up:'fa-volume-up',volume_down:'fa-volume-down',mute:'fa-volume-mute',unmute:'fa-volume-off',screenshot:'fa-camera',screenshot_area:'fa-crop',lock:'fa-lock',sleep:'fa-moon',show_desktop:'fa-desktop'};
        actions.forEach(a=>{let btn=document.createElement('button');btn.className='action-btn';btn.innerHTML=`<i class="fas ${icons[a]}"></i> ${a.replace('_',' ')}`;btn.onclick=()=>executeAction(a);container.appendChild(btn);});
        function executeAction(a){showNotification(`Выполняется: ${a}`);fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a})}).then(r=>r.json()).then(d=>{if(d.success)showNotification(d.message);else showNotification('Ошибка');loadData();});}
        function showNotification(msg,type='info'){let n=document.createElement('div');n.className='notification';n.innerHTML=`<i class="fas ${type==='success'?'fa-check-circle':'fa-info-circle'}"></i> ${msg}`;document.body.appendChild(n);setTimeout(()=>n.remove(),3000);}
        let activityChart,topChart;
        function loadData(){
            fetch('/api/stats').then(r=>r.json()).then(d=>{document.getElementById('users').innerText=d.users;document.getElementById('commands').innerText=d.commands;document.getElementById('today').innerText=d.today||0;});
            fetch('/api/system').then(r=>r.json()).then(d=>{
                document.getElementById('cpu-val').innerText=d.cpu+'%';document.getElementById('cpu-fill').style.width=d.cpu+'%';
                document.getElementById('mem-val').innerText=d.memory+'%';document.getElementById('mem-fill').style.width=d.memory+'%';
                document.getElementById('disk-val').innerText=d.disk+'%';document.getElementById('disk-fill').style.width=d.disk+'%';
                document.getElementById('battery-val').innerText=d.battery+'%';document.getElementById('battery-fill').style.width=d.battery+'%';
                document.getElementById('ip-val').innerText=d.ip;
            });
            fetch('/api/commands').then(r=>r.json()).then(data=>{
                const div=document.getElementById('commands-list');
                if(data.length===0){div.innerHTML='<div class="empty-state"><i class="fas fa-inbox"></i><br>Нет команд</div>';return;}
                div.innerHTML=data.map(c=>`<div class="command-item"><div class="command-name"><i class="fas fa-terminal"></i> ${c.command}</div><div class="command-result">${c.result.substring(0,100)}${c.result.length>100?'...':''}</div><div class="command-time"><i class="far fa-clock"></i> ${new Date(c.time).toLocaleString()}</div></div>`).join('');
            });
            fetch('/api/charts').then(r=>r.json()).then(data=>{
                const dates=Object.keys(data.daily||{}).sort().reverse().slice(0,7).reverse(),counts=dates.map(d=>data.daily[d]||0);
                if(activityChart)activityChart.destroy();
                activityChart=new Chart(document.getElementById('activity-chart'),{type:'line',data:{labels:dates,datasets:[{label:'Команды',data:counts,borderColor:'#a855f7',backgroundColor:'rgba(168,85,247,0.1)',fill:true,tension:0.4,pointBackgroundColor:'#ec4899',pointBorderColor:'#fff'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#e8e8ff'}}},scales:{y:{grid:{color:'rgba(255,255,255,0.1)'},ticks:{color:'#a0a0b0'}},x:{grid:{color:'rgba(255,255,255,0.1)'},ticks:{color:'#a0a0b0'}}}}});
                if(topChart)topChart.destroy();
                const topData=data.top_commands||[];
                topChart=new Chart(document.getElementById('top-chart'),{type:'bar',data:{labels:topData.map(t=>t.name),datasets:[{label:'Количество',data:topData.map(t=>t.count),backgroundColor:'rgba(168,85,247,0.7)',borderRadius:8}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#e8e8ff'}}},scales:{y:{grid:{color:'rgba(255,255,255,0.1)'},ticks:{color:'#a0a0b0'}},x:{ticks:{color:'#a0a0b0',maxRotation:45,minRotation:45}}}}});
            });
        }
        function createParticles(){for(let i=0;i<60;i++){let p=document.createElement('div');p.className='particle';let s=Math.random()*6+2;p.style.width=s+'px';p.style.height=s+'px';p.style.left=Math.random()*100+'%';p.style.top=Math.random()*100+'%';p.style.animationDelay=Math.random()*20+'s';p.style.animationDuration=(Math.random()*15+10)+'s';document.getElementById('particles').appendChild(p);}}
        document.getElementById('refresh-btn').addEventListener('click',loadData);
        setInterval(loadData,5000);
        createParticles();
        loadData();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
def api_stats():
    users, cmds = get_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(MAC_DB_PATH)
    today_cmds = conn.execute("SELECT COUNT(*) FROM commands WHERE date(time) = ?", (today,)).fetchone()[0]
    conn.close()
    return jsonify({"users": users, "commands": cmds, "today": today_cmds})

@app.route('/api/charts')
def api_charts():
    return jsonify(get_chart_data())

@app.route('/api/commands')
def api_commands():
    return jsonify(get_recent_commands(30))

@app.route('/api/system')
def api_system():
    cpu = get_cpu_info()
    mem = get_memory_info()
    disk = get_disk_info()
    battery = get_battery_info()
    net = get_network_info()
    return jsonify({
        "cpu": cpu['percent'],
        "memory": mem['percent'],
        "disk": disk['percent'],
        "battery": battery['percent'],
        "ip": net['addresses'][0]['ip'] if net['addresses'] else 'unknown'
    })

@app.route('/api/action', methods=['POST'])
def api_action():
    data = request.json
    action = data.get('action')
    result = execute_pc_action(action)
    socketio.emit('action', {'action': action, 'result': str(result)})
    if action in ['screenshot', 'screenshot_area']:
        if result:
            import base64
            return jsonify({"success": True, "message": "Скриншот сделан", "image": base64.b64encode(result).decode()})
        return jsonify({"success": False, "message": "Ошибка"})
    return jsonify({"success": True, "message": result})

# ====================================================================================================
# ЗАПУСК
# ====================================================================================================
def main():
    print("=" * 80)
    print("🚀 СУПЕР БОТ v37 — ЗАПУЩЕН")
    print(f"📱 Telegram бот активен")
    print(f"🌐 Веб-панель: http://localhost:{WEB_PORT}")
    print(f"👤 Владелец: {OWNER_ID}")
    print("=" * 80)

    web_thread = threading.Thread(target=lambda: socketio.run(app, host=WEB_HOST, port=WEB_PORT, debug=False, allow_unsafe_werkzeug=True))
    web_thread.daemon = True
    web_thread.start()
    time.sleep(2)

    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("addnote", cmd_addnote))
    tg_app.add_handler(CommandHandler("mynotes", cmd_mynotes))
    tg_app.add_handler(CommandHandler("delnote", cmd_delnote))
    tg_app.add_handler(CommandHandler("addtask", cmd_addtask))
    tg_app.add_handler(CommandHandler("mytasks", cmd_mytasks))
    tg_app.add_handler(CommandHandler("done", cmd_done))
    tg_app.add_handler(CommandHandler("deltask", cmd_deltask))
    tg_app.add_handler(CommandHandler("addbookmark", cmd_addbookmark))
    tg_app.add_handler(CommandHandler("mybookmarks", cmd_mybookmarks))
    tg_app.add_handler(CommandHandler("delbookmark", cmd_delbookmark))
    tg_app.add_handler(CommandHandler("savepass", cmd_savepass))
    tg_app.add_handler(CommandHandler("mypass", cmd_mypass))
    tg_app.add_handler(CommandHandler("getpass", cmd_getpass))
    tg_app.add_handler(CommandHandler("delpass", cmd_delpass))
    tg_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    tg_app.add_handler(CallbackQueryHandler(handle_callback))

    print("✅ БОТ ЗАПУЩЕН!")
    tg_app.run_polling()

if __name__ == "__main__":
    main()
