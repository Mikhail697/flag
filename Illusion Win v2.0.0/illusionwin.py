import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
import time
import sqlite3
from datetime import datetime
import random

TOKEN = "8158402995:AAElflm2ymC1JBen6z7ABHyZqiP2eWCs0-U" #Токен бота
CRYPTO_BOT_TOKEN = "323794:AANOP8noXtnVKNazN5cDkxgEako6uldXmSU" # api CryptoBot
API_URL = "https://pay.crypt.bot/api/"
ADMIN_IDS = [7943900933] #id Админов, перечислять через запятую
LOG_CHANNEL_ID = -1002262162343 # айди канала куда постятся логи по депах и выводах
PAYMENTS_CHANNEL_ID = -1002283537111 # айди канала куда постятся выплаты
CHANNEL_ID = -1002479355645 #id игрового канала 
CHANNEL_LINK = "https://t.me/LzU0WYeDYH02OTXr" #URL - игровой канал 

bot = telebot.TeleBot(TOKEN)

def init_db():
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0.0,
        vip_progress INTEGER DEFAULT 0,
        oborot REAL DEFAULT 0.0,
        games_played INTEGER DEFAULT 0,
        account_age INTEGER DEFAULT 0,
        registration_date TEXT DEFAULT CURRENT_TIMESTAMP,
        is_admin INTEGER DEFAULT 0,
        referrer_id INTEGER DEFAULT NULL
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount REAL,
        date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pending_invoices (
        invoice_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mines_games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        mines_count INTEGER,
        bet_amount REAL,
        board_state TEXT,
        current_multiplier REAL DEFAULT 1.0,
        move_count INTEGER DEFAULT 0
    )
    ''')
    conn.commit()
    conn.close()

init_db()

class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.balance = 0.0
        self.vip_progress = 0
        self.oborot = 0.0
        self.games_played = 0
        self.account_age = 0
        self.is_admin = False
        self.referrer_id = None
        self.load_from_db()

    def load_from_db(self):
        conn = sqlite3.connect('bd.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (self.user_id,))
        user_data = cursor.fetchone()
        if user_data:
            self.balance = user_data[1]
            self.vip_progress = user_data[2]
            self.oborot = user_data[3]
            self.games_played = user_data[4]
            self.account_age = (datetime.now() - datetime.strptime(user_data[6], '%Y-%m-%d %H:%M:%S')).days if user_data[6] else 0
            self.is_admin = bool(user_data[7])
            self.referrer_id = user_data[8]
        conn.close()

    def save_to_db(self):
        conn = sqlite3.connect('bd.db')
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, balance, vip_progress, oborot, games_played, account_age, is_admin, referrer_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.user_id, self.balance, self.vip_progress, self.oborot, 
            self.games_played, self.account_age, int(self.is_admin), self.referrer_id
        ))
        conn.commit()
        conn.close()
    
    def add_transaction(self, tx_type, amount):
        conn = sqlite3.connect('bd.db')
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO transactions (user_id, type, amount, date)
        VALUES (?, ?, ?, ?)
        ''', (
            self.user_id, tx_type, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        conn.close()

def get_user(user_id):
    user = User(user_id)
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone()
    conn.close()
    if not exists:
        user.save_to_db()
    return user

def create_invoice(amount, user_id):
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Пополнение баланса для пользователя {user_id}",
        "hidden_message": "Спасибо за деп",
        "paid_btn_name": "viewItem",
        "paid_btn_url": "https://t.me/your_bot",
        "payload": str(user_id)
    }
    response = requests.post(f"{API_URL}createInvoice", headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            conn = sqlite3.connect('bd.db')
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO pending_invoices (invoice_id, user_id, amount, date)
            VALUES (?, ?, ?, ?)
            ''', (
                result['result']['invoice_id'], user_id, amount, 
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            conn.commit()
            conn.close()
        return result
    return None

def check_invoice(invoice_id):
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN
    }
    response = requests.get(f"{API_URL}getInvoices?invoice_ids={invoice_id}", headers=headers)
    return response.json() if response.status_code == 200 else None

def create_check(amount, user_id):
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "pin_to_user_id": user_id
    }
    try:
        response = requests.post(f"{API_URL}createCheck", headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error creating check: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Exception in create_check: {str(e)}")
        return None

def log_deposit(user_id, amount):
    log_message = f"""🔔 Новый депозит!

💸 Сумма депа: {amount:.2f} USDT
🆔 Айди игрока: {user_id}"""
    bot.send_message(LOG_CHANNEL_ID, log_message, parse_mode='HTML')

def log_withdrawal(user_id, amount, check_url):
    log_message = f"""<blockquote>🔔 Новый вывод!</blockquote>

<blockquote>💸 Сумма вывода: {amount:.2f} USDT
🆔 Айди игрока: {user_id}</blockquote>

<blockquote>🔗 Ссылка на чек: {check_url}</blockquote>"""
    bot.send_message(PAYMENTS_CHANNEL_ID, log_message, parse_mode='HTML')

def calculate_referral_bonus(referrer_id, deposit_amount):
    bonus_percentage = 0.1  
    bonus_amount = deposit_amount * bonus_percentage
    
    referrer = get_user(referrer_id)
    referrer.balance += bonus_amount
    referrer.save_to_db()
    referrer.add_transaction('referral_bonus', bonus_amount)

    try:
        bot.send_message(referrer_id, f"<blockquote>🎉 Ваш реферал пополнил баланс, и вы получили бонус: {bonus_amount:.2f} USDT</blockquote>\n<blockquote>Ваш баланс: {referrer.balance:.2f} USDT</blockquote>", parse_mode='HTML')
    except:
        pass
    
    return bonus_amount

def get_referral_link(user_id):
    return f"https://t.me/illusionwin_bot?start=ref_{user_id}"

def get_referral_count(user_id):
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE referrer_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False

@bot.callback_query_handler(func=lambda call: call.data == 'check_subscription')
def check_subscription_callback(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Вы не подписаны на канал!", show_alert=True)

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user = get_user(message.from_user.id)
    if not user.is_admin and message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ Доступ запрещен")
        return
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("💰 Выдать баланс", callback_data='admin_add_balance'),
        InlineKeyboardButton("💸 Снять баланс", callback_data='admin_remove_balance')
    )
    keyboard.row(
        InlineKeyboardButton("👤 Инфо о пользователе", callback_data='admin_user_info'),
        InlineKeyboardButton("📊 Статистика бота", callback_data='admin_bot_stats')
    )
    
    admin_text = """
<blockquote>👑 <b>Админ-панель</b></blockquote>

<blockquote>Выберите действие:
💰 Выдать баланс - добавить средства пользователю
💸 Снять баланс - удалить средства у пользователя
👤 Инфо о пользователе - просмотр информации
📊 Статистика бота - общая статистика</blockquote>
    """
    
    bot.send_message(message.chat.id, admin_text, reply_markup=keyboard, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    user = get_user(call.from_user.id)
    if not user.is_admin and call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ Доступ запрещен", show_alert=True)
        return
    
    if call.data == 'admin_add_balance':
        msg = bot.send_message(call.message.chat.id, 
                              "<b>Введите ID пользователя и сумму через пробел:</b>\nПример: <code>123456789 10.5</code>", 
                              parse_mode='HTML')
        bot.register_next_step_handler(msg, process_admin_add_balance)
    
    elif call.data == 'admin_remove_balance':
        msg = bot.send_message(call.message.chat.id, 
                              "<b>Введите ID пользователя и сумму через пробел:</b>\nПример: <code>123456789 10.5</code>", 
                              parse_mode='HTML')
        bot.register_next_step_handler(msg, process_admin_remove_balance)
    
    elif call.data == 'admin_user_info':
        msg = bot.send_message(call.message.chat.id, 
                              "<b>Введите ID пользователя:</b>", 
                              parse_mode='HTML')
        bot.register_next_step_handler(msg, process_admin_user_info)
    
    elif call.data == 'admin_bot_stats':
        show_bot_stats(call.message)

def process_admin_add_balance(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError
        
        user_id = int(parts[0])
        amount = float(parts[1])
        
        if amount <= 0:
            bot.send_message(message.chat.id, "<blockquote>❌ Сумма должна быть положительной</blockquote>")
            return
        
        user = get_user(user_id)
        user.balance += amount
        user.oborot += amount
        user.add_transaction('admin_add', amount)
        user.save_to_db()
        
        bot.send_message(message.chat.id, f"<blockquote>🥷 Пользователь {user_id}\n💸 Успешно получил {amount:.2f}$\n🎁 Новый баланс: {user.balance:.2f}$</blockquote>")
        
        try:
            bot.send_message(user_id, f"<blockquote>🎉 Администратор выдал вам {amount:.2f}$</blockquote>\n<blockquote>Ваш баланс: {user.balance:.2f} USDT</blockquote>")
        except:
            pass
    
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ Неверный формат ввода. Используйте: <code>ID_пользователя Сумма</code>", parse_mode='HTML')

def process_admin_remove_balance(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError
        
        user_id = int(parts[0])
        amount = float(parts[1])
        
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Сумма должна быть больше 0!")
            return
        
        user = get_user(user_id)
        
        if user.balance < amount:
            bot.send_message(message.chat.id, f"❌ У пользователя недостаточно средств! Текущий баланс: {user.balance:.2f} USDT")
            return
        
        user.balance -= amount
        user.add_transaction('admin_remove', amount)
        user.save_to_db()
        
        bot.send_message(message.chat.id, f"<blockquote>✅ У пользователя {user_id} успешно снято {amount:.2f} USDT\nНовый баланс: {user.balance:.2f} USDT</blockquote>")
        
        try:
            bot.send_message(user_id, f"<blockquote>⚠️ Администратор снял с вас {amount:.2f} USDT\nВаш баланс: {user.balance:.2f} USDT</blockquote>")
        except:
            pass
    
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ Неверный формат ввода. Используйте: <code>ID_пользователя Сумма</code>", parse_mode='HTML')

def process_admin_user_info(message):
    try:
        user_id = int(message.text)
        user = get_user(user_id)
        
        conn = sqlite3.connect('bd.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = ?', (user_id,))
        tx_count = cursor.fetchone()[0]
        cursor.execute('SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = "deposit"', (user_id,))
        total_deposits = cursor.fetchone()[0] or 0
        cursor.execute('SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = "withdraw"', (user_id,))
        total_withdrawals = cursor.fetchone()[0] or 0
        conn.close()
        
        info_text = f"""
<blockquote>👤 <b>Информация о пользователе</b> #{user_id}</blockquote>

💰 Баланс: {user.balance:.2f} USDT
⭐ Ваш рубеж: {user.vip_progress}%
📊 Оборот: {user.oborot:.2f} USDT
🎮 Сыграно ставок: {user.games_played}
⏳ Аккаунту: {user.account_age} дней

💳 Всего депозитов: {total_deposits:.2f} USDT
💸 Всего выводов: {total_withdrawals:.2f} USDT
📝 Всего транзакций: {tx_count}

🆔 ID: <code>{user_id}</code>
        """
        
        bot.send_message(message.chat.id, info_text, parse_mode='HTML')
    
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный ID пользователя!")

def show_bot_stats(message):
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT user_id) FROM transactions')
    active_users = cursor.fetchone()[0]
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE type = "deposit"')
    total_deposits = cursor.fetchone()[0] or 0
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE type = "withdraw"')
    total_withdrawals = cursor.fetchone()[0] or 0
    conn.close()
    
    stats_text = f"""
<blockquote>📊 <b>Статистика бота</b></blockquote>

<blockquote>👥 Всего пользователей: {total_users}
👤 Активных пользователей: {active_users}</blockquote>

<blockquote>💰 Общий оборот: {total_deposits:.2f} USDT
⬆️ Всего депозитов: {total_deposits:.2f} USDT
⬇️ Всего выводов: {total_withdrawals:.2f} USDT</blockquote>
    """
    
    bot.send_message(message.chat.id, stats_text, parse_mode='HTML')

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("📢 Подписаться", url=CHANNEL_LINK),
            InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')
        )
        bot.send_message(
            message.chat.id,
            "<b>Для использования бота необходимо подписаться на наш канал:</b>",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return

    user = get_user(message.from_user.id)
    referrer_id = None
    
    if message.text and len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1].split('_')[1])
        except ValueError:
            pass
    
    if referrer_id and user.user_id != referrer_id:
        referrer = get_user(referrer_id)
        if user.referrer_id is None:
            user.referrer_id = referrer_id
            user.save_to_db()

    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("🚀 Начать играть", callback_data='mini_games'),
        InlineKeyboardButton("💬 Наши каналы", callback_data='game_chats')
    )
    keyboard.row(
        InlineKeyboardButton("👤 Профиль", callback_data='show_profile'),
        InlineKeyboardButton("👥 Реф. программа", callback_data='referral')
    )
    keyboard.row(
        InlineKeyboardButton("🆘 Помощь", url=f't.me/Adrean_support')
    )
    
    welcome_text = """
<blockquote>🤝 Добро пожаловать в <b>Illusion Win</b></blockquote>
    """
    
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, "👋")
    try:
        photo = open('img/illusion.jpg', 'rb')
        bot.send_photo(message.chat.id, photo, caption=welcome_text, reply_markup=keyboard, parse_mode='HTML')
    except FileNotFoundError:
        bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'show_profile')
def show_profile_callback(call):
    user = get_user(call.from_user.id)
    
    profile_text = f"""
<blockquote>👤 <b>Профиль игрока</b> #{user.user_id}</blockquote>

<blockquote>💰 <b>Баланс:</b> {user.balance:.2f} USDT
⭐ <b>VIP прогресс:</b> {user.vip_progress}%
📊 <b>Оборот:</b> {user.oborot:.2f} USDT
🎮 <b>Сыграно ставок:</b> {user.games_played}
⏳ <b>Аккаунту:</b> {user.account_age} дней</blockquote>
    """
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("💰 Пополнить", callback_data='deposit'),
        InlineKeyboardButton("💸 Вывести", callback_data='withdraw')
    )
    keyboard.row(
        InlineKeyboardButton("📊 Статистика", callback_data='statistics'),
        InlineKeyboardButton("📝 Транзакции", callback_data='transactions')
    )
    keyboard.row(
        InlineKeyboardButton("⬅️ Назад", callback_data='back')
    )

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, profile_text, parse_mode='HTML', reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'profile')
def profile_callback(call):
    user = get_user(call.from_user.id)
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("💰 Пополнить", callback_data='deposit'),
        InlineKeyboardButton("💸 Вывести", callback_data='withdraw')
    )
    keyboard.row(
        InlineKeyboardButton("📊 Статистика", callback_data='statistics'),
        InlineKeyboardButton("📝 Транзакции", callback_data='transactions')
    )
    keyboard.row(
        InlineKeyboardButton("⬅️ Назад", callback_data='back')
    )
    
    profile_text = f"""
<blockquote>👤 <b>Профиль игрока</b> #{user.user_id}</blockquote>

<blockquote>💰 <b>Баланс:</b> {user.balance:.2f} USDT
⭐ <b>VIP прогресс:</b> {user.vip_progress}%
📊 <b>Оборот:</b> {user.oborot:.2f} USDT
🎮 <b>Сыграно ставок:</b> {user.games_played}
⏳ <b>Аккаунту:</b> {user.account_age} дней</blockquote>
    """
    
    try:
        bot.edit_message_text(profile_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, profile_text, reply_markup=keyboard, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'mini_games')
def mini_games_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("🚀 Мины", callback_data='mines'),
        InlineKeyboardButton("🎲 Кости", callback_data='dice'),
    )
    keyboard.row(
        InlineKeyboardButton("🛠🏀 Баскетбол🛠", callback_data='button1'),
        InlineKeyboardButton("🛠⚽ Футбол🛠", callback_data='button2'),
    )
    keyboard.row(
        InlineKeyboardButton("🛠🎰 Слоты🛠", callback_data='button3'),
        InlineKeyboardButton("🛠🎯 Дартс🛠", callback_data='button4'),
    )
    keyboard.row(
        InlineKeyboardButton("🛠🎳 Боулинг🛠", callback_data='button5'),
        InlineKeyboardButton("🛠🪨✂️🗒 КНБ🛠", callback_data='button6'),
    )
    keyboard.row(
        InlineKeyboardButton("🛠🎡 Колесо🛠", callback_data='button7'),
        InlineKeyboardButton("🛠🔫 Русская рулетка🛠", callback_data='button8'),
    )
        
    keyboard.row(
        InlineKeyboardButton("⬅️ Назад", callback_data='back')
    )

    play_text = """
<blockquote>🎮 <b>Мини-игры</b></blockquote>

<blockquote>⚡ Выберите игру:</blockquote>
    """
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(play_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, play_text, reply_markup=keyboard, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'button1')
def cdk_message(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "🛠 Игра 🏀 Боулинг, находится в стадии разработки‼", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'button2')
def cdk_message(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "🛠 Игра ⚽ Футбол, находится в стадии разработки‼", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'button3')
def cdk_message(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "🛠 Игра 🎰 Слоты, находится в стадии разработки‼", show_alert=True)
        
@bot.callback_query_handler(func=lambda call: call.data == 'button4')
def cdk_message(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "🛠 Игра 🎯 Дартс, находится в стадии разработки‼", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'button5')
def cdk_message(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "🛠 Игра 🎳 Боулинг, находится в стадии разработки‼", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'button6')
def cdk_message(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "🛠 Игра 🪨✂️🗒 КНБ, находится в стадии разработки‼", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'button7')
def cdk_message(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "🛠 Игра 🎡 Колесо, находится в стадии разработки‼", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'button8')
def cdk_message(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "🛠 Игра 🔫 Русская рулетка, находится в стадии разработки‼", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'deposit')
def deposit_callback(call):
    msg = bot.send_message(call.message.chat.id, "<b>Введите сумму для пополнения (минимум 0.1 USDT):</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_deposit_amount, call.from_user.id)

def process_deposit_amount(message, user_id):
    try:
        amount = float(message.text)
        if amount < 0.1:
            bot.send_message(message.chat.id, "<b>Минимальная сумма пополнения - 0.1 USDT!</b>", parse_mode='HTML')
            return
            
        user = get_user(user_id)
        invoice = create_invoice(amount, user_id)
        
        if invoice and invoice.get('ok'):
            invoice_data = invoice['result']
            
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("💳 Оплатить", url=invoice_data['pay_url']),
                InlineKeyboardButton("🔄 Проверить оплату", callback_data=f'check_invoice_{invoice_data["invoice_id"]}')
            )
            keyboard.row(
                InlineKeyboardButton("⬅️ Назад", callback_data='profile')
            )
            
            invoice_text = f"""
<blockquote>💳 <b>Пополнение баланса</b></blockquote>

<blockquote><b>Сумма:</b> {amount:.2f} USDT
<b>Адрес:</b> <code>{invoice_data['pay_url']}</code></blockquote>

<blockquote>После оплаты нажмите "Проверить оплату"</blockquote>
            """
            
            bot.send_message(message.chat.id, invoice_text, reply_markup=keyboard, parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, "<b>Ошибка при создании счета</b>", parse_mode='HTML')
    except ValueError:
        bot.send_message(message.chat.id, "<b>Пожалуйста, введите корректную сумму!</b>", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_invoice_'))
def check_invoice_callback(call):
    invoice_id = call.data.split('_')[-1]
    
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM pending_invoices WHERE invoice_id = ?', (invoice_id,))
    invoice_data = cursor.fetchone()
    conn.close()
    
    if not invoice_data or invoice_data[0] != call.from_user.id:
        bot.answer_callback_query(call.id, "Этот счет не оплачен", show_alert=True)
        return
    
    user = get_user(call.from_user.id)
    invoice_status = check_invoice(invoice_id)
    
    if invoice_status and invoice_status.get('ok'):
        invoice_data = invoice_status['result']['items'][0]
        
        if invoice_data['status'] == 'paid':
            amount = float(invoice_data['amount'])
            user.balance += amount
            user.oborot += amount
            user.add_transaction('deposit', amount)
            user.save_to_db()

            conn = sqlite3.connect('bd.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM pending_invoices WHERE invoice_id = ?', (invoice_id,))
            conn.commit()
            conn.close()
            
            log_deposit(user.user_id, amount)

            if user.referrer_id:
                referral_bonus = calculate_referral_bonus(user.referrer_id, amount)
                bot.send_message(call.message.chat.id, f"🎉 Спасибо за пополнение! Вам начислено {referral_bonus:.2f} USDT бонуса от реферала!", parse_mode='HTML')
            
            success_text = f"""
<blockquote>✅ <b>Пополнение успешно!</b></blockquote>

<blockquote><b>Зачислено:</b> {amount:.2f} USDT
<b>Новый баланс:</b> {user.balance:.2f} USDT</blockquote>
            """
            
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("👤 В профиль", callback_data='profile')
            )
            
            bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id, 
                                 reply_markup=keyboard, parse_mode='HTML')
        else:
            bot.answer_callback_query(call.id, "❌ Счет не оплачен", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'withdraw')
def withdraw_callback(call):
    user = get_user(call.from_user.id)
    
    if user.balance < 0.5:
        bot.answer_callback_query(call.id, f"❌ Минимальная сумма вывода - 0.5 USDT\n💰 Ваш баланс: {user.balance:.2f} USDT", show_alert=True)
        return
        
    msg = bot.send_message(call.message.chat.id, f"<b><blockquote>Введите сумму для вывода</blockquote></b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_withdraw_amount, call.from_user.id)

def process_withdraw_amount(message, user_id):
    try:
        amount = float(message.text)
        user = get_user(user_id)
        
        if amount < 0.5:
            bot.send_message(message.chat.id, "<b>Минимальная сумма вывода - 5 USDT!</b>", parse_mode='HTML')
            return
        if amount > user.balance:
            bot.send_message(message.chat.id, "<b>Недостаточно средств на балансе!</b>", parse_mode='HTML')
            return
            
        check = create_check(amount, user_id)
        
        if check and check.get('ok'):
            check_data = check['result']
            pay_url = check_data.get('bot_check_url')
            
            if not pay_url:
                error_msg = "<b>Ошибка: не получен URL для выплаты. Попробуйте позже.</b>"
                error_msg += f"\n\nДетали ответа API:\n<code>{json.dumps(check_data, indent=2)}</code>"
                bot.send_message(message.chat.id, error_msg, parse_mode='HTML')
                return
            
            user.balance -= amount
            user.add_transaction('withdraw', amount)
            user.save_to_db()
            
            log_withdrawal(user.user_id, amount, pay_url)

            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🎁 Получить", url=pay_url)
            )
            keyboard.row(
                InlineKeyboardButton("👤 В профиль", callback_data='profile')
            )
            
            withdraw_text = f"""
<blockquote>🎁 <b>Ваша выплата!</b></blockquote>

<blockquote><b>Сумма:</b> {amount:.2f} USDT
<b>Статус:</b> Ожидает получения</blockquote>

<blockquote>🔔 Заберите чек по кнопке ниже</blockquote>
            """
            
            bot.send_message(message.chat.id, withdraw_text, reply_markup=keyboard, parse_mode='HTML')
        else:
            error_msg = "Ошибка при создании чека. Попробуйте позже."
            if check and not check.get('ok'):
                error_msg += f"\nКод ошибки: {check.get('error', {}).get('code', 'неизвестно')}"
                if check.get('error', {}).get('name') == 'insufficient_balance':
                    error_msg = "Ошибка: на балансе бота недостаточно средств для выплаты. Обратитесь к администратору."
            bot.send_message(message.chat.id, error_msg, parse_mode='HTML')
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректную сумму!", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'statistics')
def statistics_callback(call):
    user = get_user(call.from_user.id)
    
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = "deposit"', (user.user_id,))
    total_deposits = cursor.fetchone()[0] or 0
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = "withdraw"', (user.user_id,))
    total_withdrawals = cursor.fetchone()[0] or 0
    conn.close()
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("⬅️ Назад", callback_data='profile')
    )
    
    stats_text = f"""
<blockquote>📊 <b>Статистика игрока</b></blockquote>

<blockquote>💰 <b>Общий оборот:</b> {user.oborot:.2f} USDT
⬆️ <b>Пополнено:</b> {total_deposits:.2f} USDT
⬇️ <b>Выведено:</b> {total_withdrawals:.2f} USDT
🎮 <b>Сыграно игр:</b> {user.games_played}
⭐ <b>VIP уровень:</b> {user.vip_progress}%</blockquote>
    """
    
    try:
        bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id, 
                             reply_markup=keyboard, parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, stats_text, reply_markup=keyboard, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'transactions')
def transactions_callback(call):
    user = get_user(call.from_user.id)
    
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('SELECT type, amount, date FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT 10', (user.user_id,))
    transactions = cursor.fetchall()
    conn.close()
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("⬅️ Назад", callback_data='profile')
    )
    
    if not transactions:
        transactions_text = "<blockquote>📝 <b>История транзакций</b></blockquote>\n\nУ вас еще нет транзакций."
    else:
        transactions_text = "<blockquote>📝 <b>Последние транзакции</b></blockquote>\n\n"
        for tx in transactions:
            icon = "⬇️" if tx[0] == 'withdraw' else "⬆️"
            transactions_text += f"{icon} {tx[0]} {tx[1]:.2f} USDT\n<code>{tx[2]}</code>\n\n"
    
    try:
        bot.edit_message_text(transactions_text, call.message.chat.id, call.message.message_id, 
                             reply_markup=keyboard, parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, transactions_text, reply_markup=keyboard, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'dice')
def dice_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("🎲 Четное (x1.8)", callback_data='dice_even'),
        InlineKeyboardButton("🎲 Нечетное (x1.8)", callback_data='dice_odd')
    )
    keyboard.row(
        InlineKeyboardButton("🎲 Больше 3 (x1.8)", callback_data='dice_more'),
        InlineKeyboardButton("🎲 Меньше 4 (x1.8)", callback_data='dice_less')
    )
    keyboard.row(
        InlineKeyboardButton("⬅️ Назад", callback_data='mini_games')
    )

    dice_text = """
<blockquote>🎲 <b>Выберите ставку</b></blockquote>
    """

    try:
        bot.edit_message_text(dice_text, call.message.chat.id, call.message.message_id,
                             reply_markup=keyboard, parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, dice_text, reply_markup=keyboard, parse_mode='HTML')

def process_dice_bet(message, user_id, bet_type):
    try:
        amount = float(message.text)
        user = get_user(user_id)
        
        if amount <= 0:
            bot.send_message(message.chat.id, "<b>Сумма ставки должна быть больше 0!</b>", parse_mode='HTML')
            return
        if amount > user.balance:
            bot.send_message(message.chat.id, "<b>Недостаточно средств на балансе!</b>", parse_mode='HTML')
            return
        
        user.balance -= amount
        user.save_to_db()

        sent_msg = bot.send_dice(message.chat.id)
        time.sleep(3)
        dice_result = sent_msg.dice.value

        if bet_type == 'even':
            if dice_result % 2 == 0:
                win_amount = amount * 2
                multiplier = 1.8
                win = True
            else:
                win_amount = 0
                multiplier = 0
                win = False
        elif bet_type == 'odd':
            if dice_result % 2 != 0:
                win_amount = amount * 2
                multiplier = 1.8
                win = True
            else:
                win_amount = 0
                multiplier = 0
                win = False
        elif bet_type == 'more':
            if dice_result > 3:
                win_amount = amount * 1.5
                multiplier = 1.8
                win = True
            else:
                win_amount = 0
                multiplier = 0
                win = False
        elif bet_type == 'less':
            if dice_result < 4:
                win_amount = amount * 1.5
                multiplier = 1.8
                win = True
            else:
                win_amount = 0
                multiplier = 0
                win = False

        if win:
            user.balance += win_amount
            user.oborot += win_amount
            user.add_transaction('dice_win', win_amount)
            user.save_to_db()
            bot.send_message(message.chat.id, f"<blockquote>🎉 Поздравляем!</blockquote>\n<blockquote>🎲 Выпало {dice_result}</blockquote>\n<blockquote>💸 Вы выиграли {win_amount:.2f}$</blockquote>\n<blockquote>🍀 Коэффициент победы: (x{multiplier})</blockquote>", parse_mode='HTML')
        else:
            user.add_transaction('dice_lose', -amount)
            user.save_to_db()
            bot.send_message(message.chat.id, f"<b>Выпало {dice_result}! Вы проиграли {amount:.2f} USDT!</b>", parse_mode='HTML')
    except ValueError:
        bot.send_message(message.chat.id, "<b>Пожалуйста, введите корректную сумму!</b>", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('dice_'))
def dice_bet_callback(call):
    bet_type = call.data.split('_')[1]
    msg = bot.send_message(call.message.chat.id, "<b>Введите сумму ставки:</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_dice_bet, call.from_user.id, bet_type)

@bot.callback_query_handler(func=lambda call: call.data == 'mines')
def mines_callback(call):
    user = get_user(call.from_user.id)
    keyboard = InlineKeyboardMarkup()
    row1 = [InlineKeyboardButton(str(i), callback_data=f'mines_set_mines_{i}') for i in range(2, 7)]
    keyboard.add(*row1)
    keyboard.row(InlineKeyboardButton("⬅️ Назад", callback_data='mini_games'))
    mines_text = f"""
<blockquote>💣 <b>Мины</b></blockquote>

<blockquote>Выберите количество мин:</blockquote>
    """
    try:
        bot.edit_message_text(mines_text, call.message.chat.id, call.message.message_id,
                             reply_markup=keyboard, parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, mines_text, reply_markup=keyboard, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('mines_set_mines_'))
def mines_set_mines_callback(call):
    mines_count = int(call.data.split('_')[-1])
    user_id = call.from_user.id
    msg = bot.send_message(call.message.chat.id, "<b>Введите сумму ставки:</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_mines_bet_amount, user_id, mines_count, call.message.message_id)

def process_mines_bet_amount(message, user_id, mines_count, prev_message_id):
    try:
        bet_amount = float(message.text)
        user = get_user(user_id)

        if bet_amount <= 0:
            bot.send_message(message.chat.id, "<b>😡 Сумма ставки должна быть положительной</b>", parse_mode='HTML')
            return
        if bet_amount > user.balance:
            bot.send_message(message.chat.id, "<b>😔 Недостаточно средств на балансе..</b>", parse_mode='HTML')
            return

        user.balance -= bet_amount
        user.save_to_db()
        user.add_transaction('mines_bet', -bet_amount)

        game_id = create_mines_game(user_id, mines_count, bet_amount)
        show_mines_game(prev_message_id, message.chat.id, user_id, game_id, mines_count, bet_amount)

    except ValueError:
        bot.send_message(message.chat.id, "<b>😡 Пожалуйста, введите корректную сумму!</b>", parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        print(f"Error in process_mines_bet_amount: {e}")

def create_mines_game(user_id, mines_count, bet_amount):
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    board_state = generate_mines_board(mines_count)
    cursor.execute('''
    INSERT INTO mines_games (user_id, mines_count, bet_amount, board_state)
    VALUES (?, ?, ?, ?)
    ''', (user_id, mines_count, bet_amount, json.dumps(board_state)))
    game_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return game_id

def generate_mines_board(mines_count):
    board = [[0 for _ in range(5)] for _ in range(5)]
    mines_placed = 0
    
    while mines_placed < mines_count:
        row = random.randint(0, 4)
        col = random.randint(0, 4)
        if board[row][col] == 0:
            board[row][col] = 1
            mines_placed += 1
    return board

def show_mines_game(prev_message_id, chat_id, user_id, game_id, mines_count, bet_amount):
    board_state, current_multiplier, move_count = get_mines_game_state(game_id)
    
    lose_probability = 0
    if move_count == 1:
        lose_probability = 0.10
    elif move_count == 2:
        lose_probability = 0.20
    elif move_count == 3:
        lose_probability = 0.30
    elif move_count == 4:
        lose_probability = 0.40
    elif move_count >= 5:
        lose_probability = 1.0

    keyboard = InlineKeyboardMarkup(row_width=5)
    for row in range(5):
        row_buttons = []
        for col in range(5):
            button_text = " "
            callback_data = f'mines_click_{row}_{col}_{game_id}'
            
            if board_state[row][col] == -1:
                is_mine = check_if_mine(board_state, row, col)
                button_text = "💣" if is_mine else "💎"
            
            elif board_state[row][col] == 2:
                 button_text = "🎁"
                 callback_data = 'noop'
                 
            row_buttons.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        keyboard.row(*row_buttons)
    
    keyboard.row(
        InlineKeyboardButton("💰 Забрать деньги", callback_data=f'mines_take_{game_id}'),
        InlineKeyboardButton("⬅️ Назад", callback_data='mini_games')
    )
    
    balance = get_user(user_id).balance
    
    multiplier_per_move = 1.0
    if mines_count == 2:
        multiplier_per_move = 1.04
    elif mines_count == 3:
        multiplier_per_move = 1.05
    elif mines_count == 4:
        multiplier_per_move = 1.055
    elif mines_count == 5:
        multiplier_per_move = 1.0625
    elif mines_count == 6:
        multiplier_per_move = 1.075
    
    game_text = f"""
<blockquote>💣 <b>Мины</b></blockquote>

<blockquote>💰 Баланс: {balance:.2f} USDT
💸 Ставка: {bet_amount:.2f} USDT
⭐ Множитель: x{current_multiplier:.2f}</blockquote>
    """
    try:
        bot.edit_message_text(game_text, chat_id, prev_message_id, reply_markup=keyboard, parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(chat_id, game_text, reply_markup=keyboard, parse_mode='HTML')

def get_mines_game_state(game_id):
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('SELECT board_state, current_multiplier, move_count FROM mines_games WHERE id = ?', (game_id,))
    game_data = cursor.fetchone()
    conn.close()
    if not game_data:
        return None, 1.0, 0
    board_state = json.loads(game_data[0])
    current_multiplier = game_data[1]
    move_count = game_data[2]
    return board_state, current_multiplier, move_count

def update_mines_game_state(game_id, board_state, current_multiplier, move_count):
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE mines_games
    SET board_state = ?, current_multiplier = ?, move_count = ?
    WHERE id = ?
    ''', (json.dumps(board_state), current_multiplier, move_count, game_id))
    conn.commit()
    conn.close()

def check_if_mine(board_state, row, col):
    return board_state[row][col] == 1

@bot.callback_query_handler(func=lambda call: call.data.startswith('mines_click_'))
def mines_click_callback(call):
    row, col, game_id = map(int, call.data.split('_')[2:])
    user_id = call.from_user.id
    
    board_state, current_multiplier, move_count = get_mines_game_state(game_id)
    
    if board_state is None:
        bot.answer_callback_query(call.id, "Игра не найдена!", show_alert=True)
        return
    
    if board_state[row][col] == -1 or board_state[row][col] == 2:
        bot.answer_callback_query(call.id, "🤝 Клетка уже активирована!", show_alert=True)
        return
        
    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('SELECT mines_count, bet_amount FROM mines_games WHERE id = ?', (game_id,))
    mines_count, bet_amount = cursor.fetchone()
    conn.close()

    lose_probability = 0
    if move_count + 1 == 1:
        lose_probability = 0.10
    elif move_count + 1 == 2:
        lose_probability = 0.20
    elif move_count + 1 == 3:
        lose_probability = 0.30
    elif move_count + 1 == 4:
        lose_probability = 0.40
    elif move_count + 1 >= 5:
        lose_probability = 1.0

    if random.random() < lose_probability:
        for r in range(5):
            for c in range(5):
                if board_state[r][c] == 1:
                    row, col = r, c
                    break
            else:
                continue
            break

    if check_if_mine(board_state, row, col):
        board_state[row][col] = -1
        update_mines_game_state(game_id, board_state, 1, move_count + 1)
        
        user = get_user(user_id)
        user.add_transaction('mines_lose', -bet_amount)
        user.save_to_db()
        
        bot.answer_callback_query(call.id, "Вы проиграли!", show_alert=True)
        
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("Рестарт", callback_data="mines"))
        try:
            bot.edit_message_text("Вы проиграли", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(call.message.chat.id, "Вы проиграли", reply_markup=kb)

    else:
        board_state[row][col] = 2

        multiplier_per_move = 1.0
        if mines_count == 2:
            multiplier_per_move = 1.04
        elif mines_count == 3:
            multiplier_per_move = 1.05
        elif mines_count == 4:
            multiplier_per_move = 1.055
        elif mines_count == 5:
            multiplier_per_move = 1.0625
        elif mines_count == 6:
            multiplier_per_move = 1.075

        current_multiplier *= multiplier_per_move
        update_mines_game_state(game_id, board_state, current_multiplier, move_count + 1)

        show_mines_game(call.message.message_id, call.message.chat.id, user_id, game_id, mines_count, bet_amount)

@bot.callback_query_handler(func=lambda call: call.data.startswith('mines_take_'))
def mines_take_callback(call):
    game_id = int(call.data.split('_')[-1])
    user_id = call.from_user.id

    conn = sqlite3.connect('bd.db')
    cursor = conn.cursor()
    cursor.execute('SELECT bet_amount, current_multiplier, user_id FROM mines_games WHERE id = ?', (game_id,))
    bet_amount, current_multiplier, user_id_from_db = cursor.fetchone()
    conn.close()

    if user_id != user_id_from_db:
        return

    win_amount = bet_amount * current_multiplier
    user = get_user(user_id)
    user.balance += win_amount
    user.save_to_db()
    user.add_transaction('mines_win', win_amount)

    bot.answer_callback_query(call.id, f"Вы выиграли {win_amount:.2f} USDT!", show_alert=True)
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("Мины", callback_data="mines"))
    try:
        bot.edit_message_text(f"Вы выиграли {win_amount:.2f} USDT", call.message.chat.id, call.message.message_id,reply_markup=kb)
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, f"Вы выиграли {win_amount:.2f} USDT", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == 'game_chats')
def game_chats_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("💬 Наш чат", url='https://t.me/Hgy3pro7QdmMjNi')
    )
    keyboard.row(
        InlineKeyboardButton("💎 Наш канал", url='https://t.me/newsXr45')
    )
    keyboard.row(
        InlineKeyboardButton("⬅️ Назад", callback_data='back')
    )
    
    chats_text = """
<blockquote>🔔 <b>Наш чат и канал</b></blockquote>

<blockquote>💬 Основной чат - общение и поддержка
💎 Наш канал - выкладываем новости, обновления</blockquote>
    """
    
    try:
        bot.edit_message_text(chats_text, call.message.chat.id, call.message.message_id,
                             reply_markup=keyboard, parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, chats_text, reply_markup=keyboard, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'referral')
def referral_callback(call):
    user = get_user(call.from_user.id)
    ref_link = get_referral_link(user.user_id)
    referral_count = get_referral_count(user.user_id)
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("📢 Пригласить друзей", url=f"https://t.me/share/url?url={ref_link}")
    )
    keyboard.row(
        InlineKeyboardButton("⬅️ Назад", callback_data='back')
    )
    
    ref_text = f"""
<blockquote>👥 <b>Реферальная программа</b></blockquote>

<blockquote>Приглашайте друзей и получайте бонусы!</blockquote>
<blockquote>🔗 Ваша ссылка: <code>{ref_link}</code></blockquote>

<blockquote>💰 Вы заработали: 0.00 USDT
👥 Приглашено: {referral_count} </blockquote>
    """

    try:
        bot.edit_message_text(ref_text, call.message.chat.id, call.message.message_id,
                             reply_markup=keyboard, parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, ref_text, reply_markup=keyboard, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'help')
def help_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("💳 Финансы", callback_data='help_finance'),
        InlineKeyboardButton("🎮 Игры", callback_data='help_games')
    )
    keyboard.row(
        InlineKeyboardButton("👥 Рефералы", callback_data='help_referral'),
        InlineKeyboardButton("📊 Статистика", callback_data='help_stats')
    )
    keyboard.row(
        InlineKeyboardButton("⬅️ Назад", callback_data='back')
    )
    
    help_text = """
🆘 Центр помощи

Выберите категорию для получения помощи:
💳 Финансы - вопросы по депозитам и выводам
🎮 Игры - как играть и правила игр
👥 Рефералы - о реферальной программе
📊 Статистика - как работает статистика
    """

    try:
        bot.edit_message_text(help_text, call.message.chat.id, call.message.message_id,
                             reply_markup=keyboard, parse_mode='HTML')
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, help_text, reply_markup=keyboard, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'back')
def back_callback(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    start(call.message)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True,
                                  error_message="Произошла ошибка при обработке платежа. Пожалуйста, попробуйте позже.")

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    user_id = message.from_user.id
    amount = float(message.successful_payment.total_amount) / 100
    user = get_user(user_id)
    user.balance += amount
    user.oborot += amount
    user.add_transaction('deposit', amount)
    user.save_to_db()
    bot.send_message(message.chat.id, f"<b>Спасибо за пополнение баланса на {amount:.2f} USDT!</b>", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'noop')
def noop_callback(call):
    bot.answer_callback_query(call.id, "🤝 Клетка уже активирована!", show_alert=True)

if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
    
