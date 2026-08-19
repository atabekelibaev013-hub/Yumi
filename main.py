import asyncio
import os
import re
import sqlite3
import aiohttp
from datetime import date
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- ASOSIY SOZLAMALAR ---
BOT_TOKEN = "8503188728:AAH5ktMt7AIOQIRfJvDFrMLPDnIvjufUH-A"
ADMIN_ID = 7803078084
DARKO_API_KEY = "yc_live_f4e9...456bd4"  # Yumicoin API kalitingiz
DARKO_API_URL = "https://api.darko.uz/v1/withdraw"
DB_NAME = "bot_database.db"
CHANNELS = ["@Minecoine_kanal"]

# --- MA'LUMOTLAR BAZASI (SQLITE) ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            phone TEXT,
            referrer_id INTEGER,
            balance INTEGER DEFAULT 0,
            total_referrals INTEGER DEFAULT 0,
            today_referrals INTEGER DEFAULT 0,
            last_ref_date TEXT,
            bonus_given INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            yumi_code TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

def get_or_create_user(user_id: int, full_name: str, username: str = None, referrer_id: int = None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_str = str(date.today())
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, full_name, username, referrer_id, balance, total_referrals, today_referrals, last_ref_date, bonus_given, is_banned) VALUES (?, ?, ?, ?, 0, 0, 0, ?, 0, 0)",
            (user_id, full_name, username, referrer_id, today_str)
        )
    else:
        cursor.execute("UPDATE users SET full_name = ?, username = ? WHERE user_id = ?", (full_name, username, user_id))
    conn.commit()
    conn.close()

def has_phone(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row and row[0] and str(row[0]).strip() != "")

def save_phone(user_id: int, phone: str, full_name: str = "", username: str = ""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        today_str = str(date.today())
        cursor.execute(
            "INSERT INTO users (user_id, full_name, username, phone, balance, total_referrals, today_referrals, last_ref_date, bonus_given, is_banned) VALUES (?, ?, ?, ?, 0, 0, 0, ?, 0, 0)",
            (user_id, full_name, username, str(phone), today_str)
        )
    else:
        cursor.execute("UPDATE users SET phone = ? WHERE user_id = ?", (str(phone), user_id))
    conn.commit()
    conn.close()

def is_user_banned(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row and row[0] == 1)

def get_user_stats(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_str = str(date.today())
    cursor.execute("SELECT balance, total_referrals, today_referrals, last_ref_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        balance, total_refs, today_refs, last_date = row
        if last_date != today_str:
            today_refs = 0
            cursor.execute("UPDATE users SET today_referrals = 0, last_ref_date = ? WHERE user_id = ?", (today_str, user_id))
            conn.commit()
        conn.close()
        return balance, total_refs, today_refs
    conn.close()
    return 0, 0, 0

def add_balance(user_id: int, amount: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def deduct_balance(user_id: int, amount: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
   # --- QOLGAN BAZA FUNKSIYALARI ---
def ban_user_db(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user_by_id_or_username(identifier: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    clean_id = identifier.strip().replace("@", "")
    if clean_id.isdigit():
        cursor.execute("SELECT user_id, full_name, username, phone, balance FROM users WHERE user_id = ?", (int(clean_id),))
    else:
        cursor.execute("SELECT user_id, full_name, username, phone, balance FROM users WHERE LOWER(username) = LOWER(?)", (clean_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def set_user_balance(user_id: int, new_balance: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()

def create_withdrawal(user_id: int, amount: int, yumi_code: str) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO withdrawals (user_id, amount, yumi_code) VALUES (?, ?, ?)", (user_id, amount, yumi_code))
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return req_id

def get_withdrawal(req_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, yumi_code, status FROM withdrawals WHERE id = ?", (req_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_withdrawal_status(req_id: int, status: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE withdrawals SET status = ? WHERE id = ?", (status, req_id))
    conn.commit()
    conn.close()

def get_top_referrers():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, total_referrals FROM users WHERE is_banned = 0 ORDER BY total_referrals DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- KANAL OBUNASI VA DARKO API FUNKSIYASI ---
async def check_subscription(bot: Bot, user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

async def send_darko_diamonds(yumi_code: str, amount: int):
    payload = {"api_key": DARKO_API_KEY, "code": yumi_code, "amount": amount}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DARKO_API_URL, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("status") == "success", data.get("message", "Muvaffaqiyatli")
                return False, f"Server xatosi: {resp.status}"
    except Exception as e:
        return False, str(e)

# --- FSM HOLATLARI ---
class MurojaatState(StatesGroup):
    waiting_for_text = State()

class WithdrawState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_code = State()

class PhoneState(StatesGroup):
    waiting_for_phone = State()

class AdminPanelState(StatesGroup):
    waiting_for_identifier = State()
    waiting_for_new_balance = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- KLAVIATURALAR ---
def get_main_menu(user_id: int):
    keyboard = [
        [
            KeyboardButton(text="Olmos ishlash 💎"),
            KeyboardButton(text="Balans 💎"),
            KeyboardButton(text="Olmos yechish 💎")
        ],
        [KeyboardButton(text="🔴 Murojaat ☎️")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton(text="👨‍💻 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Hisob")],
        [KeyboardButton(text="⬅️ Bosh menyu")]
    ],
    resize_keyboard=True
)

phone_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

def get_sub_keyboard():
    buttons = []
    for ch in CHANNELS:
        ch_url = ch.replace("@", "https://t.me/")
        buttons.append([InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=ch_url)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_withdraw_keyboard(req_id: int, user_id: int):
    buttons = [
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"wd_app:{req_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"wd_rej:{req_id}")
        ],
        [InlineKeyboardButton(text="🚫 Ban berish", callback_data=f"ban_usr:{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

