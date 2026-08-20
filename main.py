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
BOT_TOKEN = "8686011931:AAHH-zU66HLMPRXBbIKKhhMY0QB06FQrc1U"
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
# --- TO'LOVLARNI TASDIQLASH / RAD ETISH / BAN BERISH (ADMIN CALLBACKS) ---

@dp.callback_query(F.data.startswith("app_buy:"))
async def approve_purchase(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    req_id = int(call.data.split(":")[1])
    purchase = get_purchase(req_id)

    if not purchase:
        await call.answer("Ariz ma'lumotlari topilmadi ❌", show_alert=True)
        return

    user_id, pay_type, diamonds, price, status = purchase

    if status != 'pending':
        await call.answer("Ushbu ariza ko'rib chiqilgan!", show_alert=True)
        return

    update_purchase_status(req_id, 'approved')
    add_balance(user_id, diamonds)

    await call.message.edit_caption(
        caption=call.message.caption + "\n\n✅ <b>Holat: TASDIQLANDI</b>",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            user_id,
            f"🎉 Tabriklaymiz! Sizning <b>{diamonds} 💎</b> miqdoridagi xaridingiz tasdiqlandi va hisobingizga qo'shildi!",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await call.answer("Xarid tasdiqlandi va olmoslar qo'shildi! ✅")

@dp.callback_query(F.data.startswith("rej_buy:"))
async def reject_purchase(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    req_id = int(call.data.split(":")[1])
    purchase = get_purchase(req_id)

    if not purchase:
        await call.answer("Ariza topilmadi ❌", show_alert=True)
        return

    user_id, pay_type, diamonds, price, status = purchase

    if status != 'pending':
        await call.answer("Ushbu ariza ko'rib chiqilgan!", show_alert=True)
        return

    update_purchase_status(req_id, 'rejected')

    await call.message.edit_caption(
        caption=call.message.caption + "\n\n❌ <b>Holat: RAD ETILDI</b>",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            user_id,
            f"❌ Sizning <b>{diamonds} 💎</b> miqdoridagi to'lov arizangiz rad etildi.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await call.answer("Ariza rad etildi ❌")

@dp.callback_query(F.data.startswith("ban_usr:"))
async def ban_user_callback(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    user_id = int(call.data.split(":")[1])
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    await call.answer(f"Foydalanuvchi ({user_id}) bloklandi! 🚫", show_alert=True)
    try:
        await bot.send_message(user_id, "Siz botdan foydalanishdan bloklandingiz 🚫")
    except Exception:
        pass

# --- OLMOS YECHISH 💎 ---

@dp.message(F.text == "Olmos yechish 💎")
async def withdraw_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    balance, _, _ = get_user_stats(message.from_user.id)
    if balance < 100:
        await message.answer(f"⚠️ Yechib olish uchun minimal summa: 100 💎\nSizning balansingiz: {balance} 💎")
        return

    await state.set_state(WithdrawState.waiting_for_amount)
    await message.answer(f"Balansingiz: {balance} 💎\n\nQancha olmos yechib olmoqchisiz? Miqdorni kiriting:")

@dp.message(WithdrawState.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("Iltimos, faqat raqam kiriting ❗")
        return

    amount = int(message.text)
    balance, _, _ = get_user_stats(message.from_user.id)

    if amount < 100:
        await message.answer("Minimal yechish miqdori 100 💎")
        return

    if amount > balance:
        await message.answer(f"Mablag' yetarli emas! Sizning balansingiz: {balance} 💎")
        return

    await state.update_data(withdraw_amount=amount)
    await state.set_state(WithdrawState.waiting_for_code)
    await message.answer("Olmos o'tkaziladigan Yumi ID kodingizni kiriting:")

@dp.message(WithdrawState.waiting_for_code)
async def process_withdraw_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    amount = data.get("withdraw_amount")
    user_id = message.from_user.id

    deduct_balance(user_id, amount)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO withdrawals (user_id, amount, yumi_code) VALUES (?, ?, ?)", (user_id, amount, code))
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(" Yechib olish arizangiz adminga yuborildi. Tez orada ko'rib chiqiladi! ⏳")

    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
    admin_msg = (
        f"📤 <b>Yangi olmos yechish arizasi!</b>\n\n"
        f"👤 Foydalanuvchi: {username}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💎 Miqdor: {amount} 💎\n"
        f"🔑 Yumi kodi: <code>{code}</code>"
    )

    await bot.send_message(
        ADMIN_ID,
        admin_msg,
        reply_markup=get_admin_withdraw_keyboard(req_id, user_id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("wd_app:"))
async def approve_withdraw(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    req_id = int(call.data.split(":")[1])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, status FROM withdrawals WHERE id = ?", (req_id,))
    row = cursor.fetchone()

    if not row or row[2] != 'pending':
        await call.answer("Ariza allaqachon ko'rib chiqilgan!", show_alert=True)
        conn.close()
        return

    user_id, amount = row[0], row[1]
    cursor.execute("UPDATE withdrawals SET status = 'approved' WHERE id = ?", (req_id,))
    conn.commit()
    conn.close()

    await call.message.edit_text(call.message.text + "\n\n✅ <b>Holat: TASDIQLANDI</b>", parse_mode="HTML")
    try:
        await bot.send_message(user_id, f"🎉 Sizning <b>{amount} 💎</b> yechib olish arizangiz tasdiqlandi va o'tkazib berildi!", parse_mode="HTML")
    except Exception:
        pass
    await call.answer("Tasdiqlandi! ✅")

@dp.callback_query(F.data.startswith("wd_rej:"))
async def reject_withdraw(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    req_id = int(call.data.split(":")[1])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, status FROM withdrawals WHERE id = ?", (req_id,))
    row = cursor.fetchone()

    if not row or row[2] != 'pending':
        await call.answer("Ariza allaqachon ko'rib chiqilgan!", show_alert=True)
        conn.close()
        return

    user_id, amount = row[0], row[1]
    cursor.execute("UPDATE withdrawals SET status = 'rejected' WHERE id = ?", (req_id,))
    add_balance(user_id, amount)
    conn.commit()
    conn.close()

    await call.message.edit_text(call.message.text + "\n\n❌ <b>Holat: RAD ETILDI (Balans qaytarildi)</b>", parse_mode="HTML")
    try:
        await bot.send_message(user_id, f"❌ Sizning <b>{amount} 💎</b> yechish arizangiz rad etildi va balansingizga qaytarildi.", parse_mode="HTML")
    except Exception:
        pass
    await call.answer("Rad etildi! ❌")

# --- OLMOS ISHLASH 💎 ---

@dp.message(F.text == "Olmos ishlash 💎")
async def earn_diamonds_handler(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    ref_bonus = get_setting("ref_bonus", "10")

    text = (
        f"🔗 <b>Sizning taklif havolangiz:</b>\n<code>{ref_link}</code>\n\n"
        f"👥 Har bir taklif qilgan do'stingiz uchun <b>{ref_bonus} 💎</b> beriladi!"
    )
    await message.answer(text, parse_mode="HTML")

# --- MUROJAAT ☎️ ---

@dp.message(F.text == "Murojaat ☎️")
async def contact_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    await state.set_state(MurojaatState.waiting_for_text)
    await message.answer("☎️ Adminlarimizga yubormoqchi bo'lgan xabaringizni yozing:")

@dp.message(MurojaatState.waiting_for_text)
async def process_murojaat(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"

    await message.answer("Xabaringiz adminga yetkazildi ✅")
    await bot.send_message(
        ADMIN_ID,
        f"📩 <b>Yangi Murojaat!</b>\n\n👤 Foydalanuvchi: {username}\n🆔 ID: <code>{user_id}</code>\n\n📝 Xabar: {message.text}",
        parse_mode="HTML"
    )

# --- O'YINLAR 🎮 ---

@dp.message(F.text.in_(["Oʻyin 🎮", "O'yin 🎮"]))
async def games_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    await message.answer("🎮 Kerakli o'yinni tanlang:", reply_markup=get_games_inline_keyboard())
# --- O'YINLAR LOGIKASI ---

@dp.callback_query(F.data.startswith("game_select:"))
async def game_selected(call: types.CallbackQuery, state: FSMContext):
    game_type = call.data.split(":")[1]
    await state.update_data(selected_game=game_type)
    await state.set_state(GameState.waiting_for_bet)
    
    balance, _, _ = get_user_stats(call.from_user.id)
    await call.message.edit_text(
        f"🎮 O'yin tanlandi: <b>{game_type.upper()}</b>\n"
        f"💰 Balansingiz: <b>{balance} 💎</b>\n\n"
        f"Tikmoqchi bo'lgan olmos miqdorini yozing (kamida 5 💎):",
        parse_mode="HTML"
    )

@dp.message(GameState.waiting_for_bet)
async def process_game_bet(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("Iltimos, faqat musbat raqam kiriting ❗")
        return

    bet = int(message.text)
    user_id = message.from_user.id
    balance, _, _ = get_user_stats(user_id)

    if bet < 5:
        await message.answer("Minimal tikish miqdori 5 💎!")
        return

    if bet > balance:
        await message.answer(f"Mablag' yetarli emas! Sizning balansingiz: {balance} 💎")
        return

    data = await state.get_data()
    game_type = data.get("selected_game", "dice")
    await state.clear()

    deduct_balance(user_id, bet)

    dice_emoji_map = {
        "slots": "🎰",
        "bowling": "🎳",
        "football": "⚽",
        "dice": "🎲",
        "darts": "🎯",
        "basketball": "🏀"
    }

    emoji = dice_emoji_map.get(game_type, "🎲")
    msg = await message.answer_dice(emoji=emoji)
    await asyncio.sleep(3)

    value = msg.dice.value
    win = False
    multiplier = 0

    if game_type in ["slots", "dice"]:
        if value in [6, 64]:
            win = True
            multiplier = 2
    elif game_type in ["bowling", "darts", "basketball"]:
        if value >= 5:
            win = True
            multiplier = 1.8
    elif game_type == "football":
        if value in [3, 4, 5]:
            win = True
            multiplier = 1.5

    if win:
        win_amount = int(bet * multiplier)
        add_balance(user_id, win_amount)
        await message.answer(f"🎉 Qoyil! Siz g'olib bo'ldingiz va <b>+{win_amount} 💎</b> yutib oldingiz!", parse_mode="HTML")
    else:
        await message.answer(f"😔 Afsuski, yutqazdingiz. <b>-{bet} 💎</b> yo'qotildi.", parse_mode="HTML")

# --- ADMIN PANEL HODISALARI VA MIQDOR SOZLAMALARI ---

@dp.message(F.text == "👨‍💻 Admin Panel")
async def admin_panel_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("👨‍💻 Admin panelga xush kelibsiz!", reply_markup=admin_menu)

@dp.message(F.text == "⬅️ Bosh menyu")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Siz asosiy menyudasiz🖥️", reply_markup=get_main_menu(message.from_user.id))

@dp.message(F.text == "💰 Hisob")
async def admin_change_balance_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminPanelState.waiting_for_identifier)
    await message.answer("Foydalanuvchi ID raqamini kiriting:")

@dp.message(AdminPanelState.waiting_for_identifier)
async def process_admin_userid(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID raqam faqat sonlardan iborat bo'lishi kerak!")
        return
    await state.update_data(target_user_id=int(message.text))
    await state.set_state(AdminPanelState.waiting_for_new_balance)
    await message.answer("Yangi balans miqdorini kiriting (masalan: 500 yoki -100):")

@dp.message(AdminPanelState.waiting_for_new_balance)
async def process_admin_new_balance(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("target_user_id")
    try:
        amount = int(message.text)
        add_balance(target_id, amount)
        await state.clear()
        await message.answer(f"✅ Foydalanuvchi (<code>{target_id}</code>) balansiga {amount} 💎 qo'shildi/ayirildi!", parse_mode="HTML")
    except ValueError:
        await message.answer("Iltimos, to'g'ri son kiriting!")

@dp.message(F.text == "Ref bonus🔗")
async def admin_ref_bonus_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    curr_bonus = get_setting("ref_bonus", "10")
    await state.set_state(AdminPanelState.waiting_for_ref_bonus)
    await message.answer(f"Hozirgi referal bonusi: {curr_bonus} 💎\nYangi bonus miqdorini kiriting:")

@dp.message(AdminPanelState.waiting_for_ref_bonus)
async def process_admin_ref_bonus(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat musbat raqam kiriting!")
        return
    set_setting("ref_bonus", message.text.strip())
    await state.clear()
    await message.answer(f"✅ Referal bonusi {message.text.strip()} 💎 ga o'zgartirildi!")

@dp.message(F.text == "Reklama")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminPanelState.waiting_for_broadcast)
    await message.answer("Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni (rasm yoki matn) yuboring:")

@dp.message(AdminPanelState.waiting_for_broadcast)
async def process_admin_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("📢 Reklama tarqatish boshlandi...")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = cursor.fetchall()
    conn.close()

    count = 0
    for u in users:
        try:
            await message.copy_to(u[0])
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(f"✅ Reklama {count} ta foydalanuvchiga muvaffaqiyatli yuborildi!")

# --- MIQDOR (PUL VA STARS NARXLARINI O'ZGARTIRISH) ---

@dp.message(F.text == "Miqdor")
async def admin_miqdor_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Pul paketlarini yangilash 💸", callback_data="set_pkg:pul")],
        [InlineKeyboardButton(text="Stars paketlarini yangilash ⭐", callback_data="set_pkg:stars")]
    ])
    await message.answer("⚙️ Qaysi to'lov turi paketlarini o'zgartirmoqchisiz?", reply_markup=kb)

@dp.callback_query(F.data.startswith("set_pkg:"))
async def process_set_pkg_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return

    pkg_type = call.data.split(":")[1]
    await state.update_data(pkg_type=pkg_type)

    if pkg_type == "pul":
        await state.set_state(AdminMiqdorState.waiting_for_pul_diamonds)
        await call.message.edit_text("💸 <b>Pul paketi sozlash:</b>\n\nOlmos miqdorini kiriting (Masalan: 500):", parse_mode="HTML")
    else:
        await state.set_state(AdminMiqdorState.waiting_for_stars_count)
        await call.message.edit_text("⭐ <b>Stars paketi sozlash:</b>\n\nStars miqdorini kiriting (Masalan: 15):", parse_mode="HTML")

# PUL PAKETI UPDATE
@dp.message(AdminMiqdorState.waiting_for_pul_diamonds)
async def process_pul_dia(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting!")
        return
    await state.update_data(new_pul_dia=message.text.strip())
    await state.set_state(AdminMiqdorState.waiting_for_pul_price)
    await message.answer("Ushbu olmos paketi uchun so'mdagi narxni kiriting (Masalan: 5000):")

@dp.message(AdminMiqdorState.waiting_for_pul_price)
async def process_pul_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting!")
        return

    data = await state.get_data()
    dia = data.get("new_pul_dia")
    price = int(message.text.strip())

    curr_json = get_setting("pul_packages", "{}")
    try:
        pkgs = json.loads(curr_json)
    except Exception:
        pkgs = {}

    pkgs[str(dia)] = price
    set_setting("pul_packages", json.dumps(pkgs))

    await state.clear()
    await message.answer(f"✅ Yangi Pul paketi saqlandi:\n<b>{dia} 💎 — {price} so'm</b>", parse_mode="HTML")

# STARS PAKETI UPDATE
@dp.message(AdminMiqdorState.waiting_for_stars_count)
async def process_stars_count(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting!")
        return
    await state.update_data(new_stars_count=message.text.strip())
    await state.set_state(AdminMiqdorState.waiting_for_stars_diamonds)
    await message.answer("Ushbu Stars uchun beriladigan olmos miqdorini kiriting (Masalan: 260):")

@dp.message(AdminMiqdorState.waiting_for_stars_diamonds)
async def process_stars_dia(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting!")
        return

    data = await state.get_data()
    stars = data.get("new_stars_count")
    dia = int(message.text.strip())

    curr_json = get_setting("stars_packages", "{}")
    try:
        pkgs = json.loads(curr_json)
    except Exception:
        pkgs = {}

    pkgs[str(stars)] = dia
    set_setting("stars_packages", json.dumps(pkgs))

    await state.clear()
    await message.answer(f"✅ Yangi Stars paketi saqlandi:\n<b>{stars} ⭐ — {dia} 💎</b>", parse_mode="HTML")

# --- MAJBURITY OBUNANI TEKSHIRISH FUNKSIYASI ---

async def check_subscription(bot_obj: Bot, user_id: int) -> bool:
    for ch in CHANNELS:
        try:
            member = await bot_obj.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            pass
    return True

# --- BOTNI ISHGA TUSHIRISH ---

async def main():
    init_db()
    print("Bot muvaffaqiyatli ishga tushdi! 🚀")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
