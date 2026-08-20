import asyncio
import json
import os
import re
import sqlite3
from datetime import date
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiohttp import web

# --- ASOSIY SOZLAMALAR ---
BOT_TOKEN = "8503188728:AAH5ktMt7AIOQIRfJvDFrMLPDnIvjufUH-A"
ADMIN_ID = 7803078084
ADMIN_USERNAME = "@next_biznes"
DB_NAME = "bot_database.db"
CHANNELS = ["@Minecoine_kanal"]

CARD_NUMBER = "5440810311919004"
CARD_HOLDER = "N/S"

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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            pay_type TEXT,
            diamonds INTEGER,
            price TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Boshlang'ich sozlamalar va paket narxlari
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ref_bonus', '10')")
    
    default_pul_packages = json.dumps({
        "500": 5000,
        "1000": 10000,
        "2000": 20000,
        "5000": 50000,
        "10000": 100000,
        "20000": 200000
    })
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('pul_packages', ?)", (default_pul_packages,))
    
    default_stars_packages = json.dumps({
        "15": 260,
        "25": 420,
        "50": 840,
        "100": 1680
    })
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('stars_packages', ?)", (default_stars_packages,))
    
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
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

def get_top_balance_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, balance FROM users WHERE is_banned = 0 ORDER BY balance DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return rows

def create_purchase(user_id: int, pay_type: str, diamonds: int, price: str) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO purchases (user_id, pay_type, diamonds, price) VALUES (?, ?, ?, ?)", (user_id, pay_type, diamonds, price))
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return req_id

def get_purchase(req_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, pay_type, diamonds, price, status FROM purchases WHERE id = ?", (req_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_purchase_status(req_id: int, status: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE purchases SET status = ? WHERE id = ?", (status, req_id))
    conn.commit()
    conn.close()
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
    waiting_for_ref_bonus = State()
    waiting_for_broadcast = State()

class GameState(StatesGroup):
    waiting_for_bet = State()

class BuyState(StatesGroup):
    waiting_for_proof = State()

class AdminMiqdorState(StatesGroup):
    waiting_for_type = State()
    waiting_for_pul_diamonds = State()
    waiting_for_pul_price = State()
    waiting_for_stars_count = State()
    waiting_for_stars_diamonds = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- KLAVIATURALAR ---
def get_main_menu(user_id: int):
    keyboard = [
        [
            KeyboardButton(text="Olmos ishlash 💎"),
            KeyboardButton(text="Profil 👤"),
            KeyboardButton(text="Olmos yechish 💎")
        ],
        [
            KeyboardButton(text="Olmos sotib olish 🛒"),
            KeyboardButton(text="Oʻyin 🎮"),
            KeyboardButton(text="Murojaat ☎️")
        ]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton(text="👨‍💻 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Hisob"), KeyboardButton(text="Ref bonus🔗")],
        [KeyboardButton(text="Miqdor"), KeyboardButton(text="Reklama")],
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

def get_buy_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Pulga 💸", callback_data="buy_type:pul"),
            InlineKeyboardButton(text="Starsga ⭐", callback_data="buy_type:stars")
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_buy")]
    ])

def get_pul_packages_keyboard():
    packages_json = get_setting("pul_packages", "{}")
    try:
        packages = json.loads(packages_json)
    except Exception:
        packages = {"500": 5000, "1000": 10000, "2000": 20000, "5000": 50000, "10000": 100000, "20000": 200000}

    buttons = []
    for dia, price in packages.items():
        price_formatted = f"{int(price):,}".replace(",", " ")
        buttons.append([InlineKeyboardButton(text=f"💎 {dia} Almaz — {price_formatted} so'm", callback_data=f"select_pul:{dia}:{price}")])

    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_buy")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_stars_packages_keyboard():
    packages_json = get_setting("stars_packages", "{}")
    try:
        packages = json.loads(packages_json)
    except Exception:
        packages = {"15": 260, "25": 420, "50": 840, "100": 1680}

    buttons = []
    for stars, dia in packages.items():
        buttons.append([InlineKeyboardButton(text=f"⭐ {stars} Stars — {dia} 💎", callback_data=f"select_stars:{stars}:{dia}")])

    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_buy")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_pul_pay_keyboard(dia: int, price: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Karta raqamini nusxalash", copy_text=types.CopyTextButton(text=CARD_NUMBER))],
        [InlineKeyboardButton(text="✅ To'lov qildim", callback_data=f"confirm_pul_pay:{dia}:{price}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_buy")]
    ])

def get_stars_pay_keyboard(stars: int, dia: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Giftni berdim✅", callback_data=f"confirm_stars_pay:{stars}:{dia}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_buy")]
    ])

def get_admin_purchase_keyboard(req_id: int, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Tasdiqlash ✅", callback_data=f"app_buy:{req_id}"),
            InlineKeyboardButton(text="Rad etish ❌", callback_data=f"rej_buy:{req_id}")
        ],
        [InlineKeyboardButton(text="Ban berish 🚫", callback_data=f"ban_usr:{user_id}")]
    ])

def get_admin_withdraw_keyboard(req_id: int, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"wd_app:{req_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"wd_rej:{req_id}")
        ],
        [InlineKeyboardButton(text="🚫 Ban berish", callback_data=f"ban_usr:{user_id}")]
    ])

def get_games_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎰 Slot", callback_data="game_select:slots"),
            InlineKeyboardButton(text="🎳 Bouling", callback_data="game_select:bowling")
        ],
        [
            InlineKeyboardButton(text="⚽️ Futbol", callback_data="game_select:football"),
            InlineKeyboardButton(text="🎲 Zardob", callback_data="game_select:dice")
        ],
        [
            InlineKeyboardButton(text="🎯 Darts", callback_data="game_select:darts"),
            InlineKeyboardButton(text="🏀 Basketbol", callback_data="game_select:basketball")
        ]
    ])

def get_play_inline_keyboard(game_type: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="O'ynash 🎮", callback_data=f"play_game:{game_type}")]
    ])
# --- FOYDALANUVCHI TEKSHIRUVI VA START ---

async def ensure_access(message: types.Message, state: FSMContext) -> bool:
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username
    
    get_or_create_user(user_id, full_name, username)

    if is_user_banned(user_id):
        await message.answer("Siz botdan foydalanishdan bloklangansiz ❌")
        return False

    if not await check_subscription(bot, user_id):
        await message.answer("Botdan foydalanishdan oldin majburiy kanalga obuna boʻling ❗", reply_markup=get_sub_keyboard())
        return False
    
    if not has_phone(user_id):
        await state.set_state(PhoneState.waiting_for_phone)
        await message.answer("📱 Botdan foydalanish uchun telefon raqamingizni yuboring:", reply_markup=phone_menu)
        return False
        
    return True

@dp.message(CommandStart())
async def start_cmd(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    referrer_id = int(command.args) if command.args and command.args.isdigit() and int(command.args) != user_id else None
    
    get_or_create_user(user_id, message.from_user.full_name, message.from_user.username, referrer_id)

    if not await ensure_access(message, state):
        return

    await message.answer("Siz asosiy menyudasiz🖥️", reply_markup=get_main_menu(user_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        await call.answer("Siz bloklangansiz ❌", show_alert=True)
        return

    if await check_subscription(bot, user_id):
        await call.message.delete()
        if not has_phone(user_id):
            await state.set_state(PhoneState.waiting_for_phone)
            await call.message.answer("📱 Botdan foydalanish uchun telefon raqamingizni yuboring:", reply_markup=phone_menu)
        else:
            await call.message.answer("Siz asosiy menyudasiz🖥️", reply_markup=get_main_menu(user_id))
    else:
        await call.answer("❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)

@dp.message(PhoneState.waiting_for_phone, F.contact)
async def receive_phone(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    
    save_phone(user_id, phone, message.from_user.full_name, message.from_user.username)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT referrer_id, bonus_given FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    ref_bonus = int(get_setting("ref_bonus", "10"))

    if row and row[0] and not row[1]:
        referrer_id = row[0]
        today_str = str(date.today())
        
        cursor.execute("SELECT today_referrals, last_ref_date FROM users WHERE user_id = ?", (referrer_id,))
        ref_user = cursor.fetchone()
        
        if ref_user:
            ref_today, ref_date = ref_user[0], ref_user[1]
            if ref_date != today_str:
                ref_today = 0
            ref_today += 1
            
            cursor.execute('''
                UPDATE users 
                SET balance = balance + ?,
                    total_referrals = total_referrals + 1,
                    today_referrals = ?,
                    last_ref_date = ?
                WHERE user_id = ?
            ''', (ref_bonus, ref_today, today_str, referrer_id))
            
            cursor.execute("UPDATE users SET bonus_given = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 Siz taklif qilgan foydalanuvchi ({message.from_user.full_name}) telefon raqamini tasdiqladi!\nSizga <b>+{ref_bonus} 💎</b> berildi!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    else:
        conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer("Siz asosiy menyudasiz🖥️", reply_markup=get_main_menu(user_id))

# --- PROFIL VA REYTING ---

@dp.message(F.text.in_(["Profil 👤", "Profil", "Balans 💎"]))
async def profile_handler(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
    balance, total_refs, _ = get_user_stats(user_id)

    text = (
        f"Foydalanuvchi:{username}\n"
        f"ID: <code>{user_id}</code>\n"
        f"Balans:{balance}💎\n"
        f"Referallar soni:{total_refs}👥\n\n"
        f"Eng koʻp olmos reytingini koʻrmoqchi boʻlsangiz /reyting buyriığını yuboring 💎"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("reyting"))
async def reyting_handler(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    top_users = get_top_balance_users()
    if not top_users:
        await message.answer("🏆 Hali hech kimda olmos mavjud emas.")
        return

    text = "💎 <b>Eng ko'p olmosi bor Top 10 foydalanuvchi:</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]

    for idx, (name, balance) in enumerate(top_users, start=1):
        prefix = medals[idx-1] if idx <= 3 else f"{idx}."
        safe_name = name.replace("<", "&lt;").replace(">", "&gt;") if name else "Foydalanuvchi"
        text += f"{prefix} <b>{safe_name}</b> — {balance} 💎\n"

    await message.answer(text, parse_mode="HTML")

# --- OLMOS SOTIB OLISH 🛒 ---

@dp.message(F.text == "Olmos sotib olish 🛒")
async def buy_diamonds_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    await message.answer("Nima bilan xarid qilmoqchisiz❓", reply_markup=get_buy_type_keyboard())

@dp.callback_query(F.data == "cancel_buy")
async def cancel_buy_callback(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Xarid bekor qilindi ❌")

@dp.callback_query(F.data.startswith("buy_type:"))
async def select_buy_type(call: types.CallbackQuery):
    pay_type = call.data.split(":")[1]

    if pay_type == "pul":
        await call.message.edit_text("💎 <b>Almaz sotib olish</b>\n\nQuyidagi paketlardan birini tanlang:", reply_markup=get_pul_packages_keyboard(), parse_mode="HTML")
    elif pay_type == "stars":
        await call.message.edit_text("Quyidagi paketlardan birini tanlang:", reply_markup=get_stars_packages_keyboard())

# PULGA XARID QILISH
@dp.callback_query(F.data.startswith("select_pul:"))
async def select_pul_package(call: types.CallbackQuery):
    _, dia, price = call.data.split(":")
    dia_int = int(dia)
    price_int = int(price)
    price_formatted = f"{price_int:,}".replace(",", " ")

    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Almaz sotib olish</b>\n\n"
        f"📦 <b>Paket:</b> {dia_int} Almaz\n"
        f"💰 <b>Narxi:</b> {price_formatted} so'm\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 <b>To'lov kartasi</b>\n\n"
        f"👤 <b>Karta egasi:</b> {CARD_HOLDER}\n"
        f"💳 <b>Karta raqami:</b> <code>{CARD_NUMBER}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>Eslatma</b>\n"
        f'To\'lovni amalga oshirgandan so\'ng "✅ To\'lov qildim" tugmasini bosing va chek (screenshot) ni yuboring.\n'
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await call.message.edit_text(text, reply_markup=get_pul_pay_keyboard(dia_int, price_int), parse_mode="HTML")

@dp.callback_query(F.data.startswith("confirm_pul_pay:"))
async def confirm_pul_payment(call: types.CallbackQuery, state: FSMContext):
    _, dia, price = call.data.split(":")
    await state.update_data(buy_type="pul", buy_dia=int(dia), buy_price=f"{price} so'm")
    await state.set_state(BuyState.waiting_for_proof)
    await call.message.answer("📷 To'lov chekini (screenshot yoki rasm) yuboring.")
    await call.answer()

# STARSGA XARID QILISH
@dp.callback_query(F.data.startswith("select_stars:"))
async def select_stars_package(call: types.CallbackQuery):
    _, stars, dia = call.data.split(":")
    stars_int = int(stars)
    dia_int = int(dia)

    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Almaz sotib olish</b>\n\n"
        f"📦 <b>Paket:</b> {dia_int} 💎\n"
        f"💰 <b>Narxi:</b> {stars_int} ⭐\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 <b>To'lov uchun foydalanuvchi👇</b>\n"
        f"👤 {ADMIN_USERNAME}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>Eslatma</b>\n"
        f"Giftni bergandan soʻng ❗\n"
        f"Giftni berdim✅ tugmasini bosing va keyin (screen) rasm yuboring❗\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await call.message.edit_text(text, reply_markup=get_stars_pay_keyboard(stars_int, dia_int), parse_mode="HTML")

@dp.callback_query(F.data.startswith("confirm_stars_pay:"))
async def confirm_stars_payment(call: types.CallbackQuery, state: FSMContext):
    _, stars, dia = call.data.split(":")
    await state.update_data(buy_type="stars", buy_dia=int(dia), buy_price=f"{stars} ⭐")
    await state.set_state(BuyState.waiting_for_proof)
    await call.message.answer("📷 To'lov chekini (screenshot yoki rasm) yuboring.")
    await call.answer()

# CHEK RASMINI QABUL QILISH
@dp.message(BuyState.waiting_for_proof, F.photo)
async def process_buy_proof(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        await state.clear()
        return

    data = await state.get_data()
    pay_type = data.get("buy_type")
    dia = data.get("buy_dia")
    price = data.get("buy_price")
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"

    req_id = create_purchase(user_id, pay_type, dia, price)
    await state.clear()

    await message.answer("Toʻlov chekingiz tez orada tekshiriladi⏳")

    admin_msg = (
        f"📥 <b>Yangi to'lov arizasi!</b>\n\n"
        f"👤 Foydalanuvchi: {username}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💎 Paket: {dia} olmos\n"
        f"💰 Narxi/To'lov: {price}\n"
        f"💳 Turi: {'Pul orqali' if pay_type == 'pul' else 'Stars Gift orqali'}"
    )

    await message.copy_to(
        chat_id=ADMIN_ID,
        caption=admin_msg,
        reply_markup=get_admin_purchase_keyboard(req_id, user_id),
        parse_mode="HTML"
)
            
