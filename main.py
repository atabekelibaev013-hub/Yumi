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
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiohttp import web

BOT_TOKEN = "8825351774:AAFI7D9WaBz3fcMV5fClnWCrOmWuLJqn0ug"
ADMIN_ID = 7803078084
DARKO_API_KEY = "yc_live_5286afa187f7b3d0a172d0e6c3e0e829cc65a48faf7b2748"

DB_NAME = "bot_database.db"
CHANNELS = ["@Minecoine_kanal"]

# Database yaratish va yangilash
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

def save_phone(user_id: int, phone: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
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

def ban_user_db(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

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

# Admin uchun foydalanuvchini topish va hisobini o'zgartirish funksiyalari
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

# Majburiy kanal obunasini tekshirish
async def check_subscription(bot: Bot, user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

# Obuna klaviaturasi
def get_sub_keyboard():
    buttons = []
    for ch in CHANNELS:
        ch_url = ch.replace("@", "https://t.me/")
        buttons.append([InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=ch_url)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Admin uchun yechib olish tugmalari
def get_admin_withdraw_keyboard(req_id: int, user_id: int):
    buttons = [
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"wd_app:{req_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"wd_rej:{req_id}")
        ],
        [InlineKeyboardButton(text="🚫 Ban berish", callback_data=f"ban_usr:{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Darko API orqali olmos yuborish
async def send_darko_diamonds(yumi_code: str, amount: int):
    url = "https://api.darko.uz/v1/withdraw"
    payload = {"api_key": DARKO_API_KEY, "code": yumi_code, "amount": amount}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("status") == "success", data.get("message", "Muvaffaqiyatli")
                return False, f"Server xatosi: {resp.status}"
    except Exception as e:
        return False, str(e)

# FSM Holatlari
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

# Dinamik menyu (Adminga "Admin Panel" tugmasi chiqadi)
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

@dp.message(CommandStart())
async def start_cmd(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username
    
    if is_user_banned(user_id):
        await message.answer("Siz botdan foydalanishdan bloklangansiz ❌")
        return

    referrer_id = None
    if command.args and command.args.isdigit():
        referrer_id = int(command.args)
        
    get_or_create_user(user_id, full_name, username, referrer_id)

    if not await check_subscription(bot, user_id):
        await message.answer(
            "Botdan foydalanishdan oldin majburiy kanalga obuna boʻling ❗",
            reply_markup=get_sub_keyboard()
        )
        return

    if not has_phone(user_id):
        await state.set_state(PhoneState.waiting_for_phone)
        await message.answer(
            "📱 Botdan foydalanish uchun telefon raqamingizni yuboring:",
            reply_markup=phone_menu
        )
        return

    await message.answer("Siz asosiy menyudasiz🖥️", reply_markup=get_main_menu(user_id))
    # --- ADMIN PANEL HANDLERLARI ---

@dp.message(F.text == "👨‍💻 Admin Panel")
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Admin panelga xush kelibsiz!", reply_markup=admin_menu)

@dp.message(F.text == "⬅️ Bosh menyu")
async def back_to_main(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu(message.from_user.id))

@dp.message(F.text == "💰 Hisob")
async def ask_for_user(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await state.set_state(AdminPanelState.waiting_for_identifier)
        await message.answer("Foydalanuvchi ID raqami yoki @username ni yuboring:")

@dp.message(AdminPanelState.waiting_for_identifier)
async def process_user_search(message: types.Message, state: FSMContext):
    identifier = message.text.strip()
    user_info = get_user_by_id_or_username(identifier)
    
    if not user_info:
        await message.answer("Foydalanuvchi topilmadi. Qaytadan urinib ko'ring yoki /start yozing.")
        return

    user_id, full_name, username, phone, balance = user_info
    
    text = (
        f"👤 Foydalanuvchi topildi:\n\n"
        f"🆔 ID: {user_id}\n"
        f"📛 Ism: {full_name}\n"
        f"📱 Username: @{username if username else 'Mavjud emas'}\n"
        f"📞 Telefon: {phone if phone else 'Mavjud emas'}\n"
        f"💎 Olmos: {balance}"
    )
    
    # Hisobni o'zgartirish tugmasi
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Hisobni o'zgartirish", callback_data=f"edit_bal:{user_id}")]
    ])
    
    await message.answer(text, reply_markup=keyboard)
    await state.clear()

# --- CALLBACKLAR ---

@dp.callback_query(F.data.startswith("edit_bal:"))
async def edit_balance_prompt(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.data.split(":")[1]
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminPanelState.waiting_for_new_balance)
    await callback.message.answer("Foydalanuvchining yangi hisobini (sonini) kiriting:")
    await callback.answer()

# --- ASOSIY MENYU VA QOLGAN HANDLERLAR ---

@dp.message(F.text == "Balans 💎")
async def show_balance(message: types.Message):
    balance, total_refs, today_refs = get_user_stats(message.from_user.id)
    await message.answer(f"Sizning hisobingiz: {balance} ta olmos 💎")

@dp.message(F.text == "🔴 Murojaat ☎️")
async def ask_murojaat(message: types.Message, state: FSMContext):
    await state.set_state(MurojaatState.waiting_for_text)
    await message.answer("Murojaatingizni yuboring:")

@dp.message(MurojaatState.waiting_for_text)
async def process_murojaat(message: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"Yangi murojaat:\nFoydalanuvchi: @{message.from_user.username}\nID: {message.from_user.id}\nXabar: {message.text}")
    await message.answer("Murojaatingiz adminga yetkazildi.")
    await state.clear()
# --- ADMIN PANEL: HISOBNI YANGILASH LOGIKASI ---

@dp.message(AdminPanelState.waiting_for_new_balance)
async def process_new_balance(message: types.Message, state: FSMContext):
    # Kiritilgan qiymat son ekanligini tekshirish
    if not message.text.isdigit():
        await message.answer("Iltimos, hisob uchun faqat butun son kiriting!")
        return
    
    new_balance = int(message.text)
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    
    # Bazada hisobni yangilash
    set_user_balance(int(target_user_id), new_balance)
    
    await message.answer(f"✅ Foydalanuvchining hisobi {new_balance} olmosga o'zgartirildi!")
    
    # Foydalanuvchiga xabar yuborish
    try:
        await bot.send_message(
            target_user_id, 
            f"Admin tomonidan hisobingiz o'zgartirildi. Hozirgi balans: {new_balance} 💎"
        )
    except:
        pass
    
    await state.clear()

# --- QOLGAN KERAKLI HANDLERLAR (Withdraw va Top uchun) ---

@dp.message(F.text.in_(["Olmos yechish 💎", "Olmos yechish"]))
async def withdraw_start(message: types.Message, state: FSMContext):
    # Bu qism oldingi qismlarda bo'lgan, agar mavjud bo'lmasa shu yerdan qo'shasiz
    user_id = message.from_user.id
    balance, _, _ = get_user_stats(user_id)
    if balance < 10:
        await message.answer("Hisobingizda yetarli olmos yo'q (min 10)!")
        return
    await state.set_state(WithdrawState.waiting_for_amount)
    await message.answer("Qancha olmos yechmoqchisiz?")

# --- BOTNI ISHGA TUSHIRISH ---

async def main():
    # Bazani ishga tushirish
    init_db()
    
    # Botni polling rejimida ishga tushirish
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
