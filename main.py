import asyncio
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # Boshlang'ich referal bonus miqdori (default: 10)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ref_bonus', '10')")
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

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]
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

# --- KANAL OBUNASI TEKSHIRUVI ---
async def check_subscription(bot: Bot, user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

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
        [
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
        [KeyboardButton(text="Reklama"), KeyboardButton(text="⬅️ Bosh menyu")]
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

def get_admin_withdraw_keyboard(req_id: int, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"wd_app:{req_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"wd_rej:{req_id}")
        ],
        [InlineKeyboardButton(text="🚫 Ban berish", callback_data=f"ban_usr:{user_id}")]
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

# --- MENYU TUGMALARI HANDLERLARI ---

# Olmos ishlash 💎
@dp.message(F.text.in_(["Olmos ishlash 💎", "Olmos ishlash"]))
async def olmos_handler(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    user_id = message.from_user.id
    balance, total_refs, today_refs = get_user_stats(user_id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    ref_bonus = get_setting("ref_bonus", "10")
    
    text = (
        f"👥 Referal tizimi\n\n"
        f"🔗 Sizning referal havolangiz:\n"
        f"<code>{ref_link}</code>\n\n"
        f"👤 Referallar soni: {total_refs}\n"
        f"📅 Bugungi referallar: {today_refs}\n"
        f"💎 Jami bonus: {balance}\n\n"
        f"Har bir referal uchun {ref_bonus} olmos beriladi!\n\n"
        f"🏆 Top referallar ro'yxatini ko'rish uchun /top buyrug'ini yuboring."
    )
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

# /top buyrug'i
@dp.message(Command("top"))
async def top_handler(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    top_users = get_top_referrers()
    if not top_users:
        await message.answer("🏆 Hali hech kim referal taklif qilmagan.")
        return
        
    text = "🏆 <b>Eng ko'p referal taklif qilgan Top 10 foydalanuvchi:</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for idx, (name, count) in enumerate(top_users, start=1):
        prefix = medals[idx-1] if idx <= 3 else f"{idx}."
        safe_name = name.replace("<", "&lt;").replace(">", "&gt;") if name else "Foydalanuvchi"
        text += f"{prefix} <b>{safe_name}</b> — {count} ta referal\n"
        
    await message.answer(text, parse_mode="HTML")

# Balans 💎
@dp.message(F.text.in_(["Balans 💎", "Balans"]))
async def balance_handler(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    user_id = message.from_user.id
    balance, _, _ = get_user_stats(user_id)
    await message.answer(f"Sizning hisobingizda {balance} olmos bor❗")

# Olmos yechish 💎 (Minimal 200 olmos)
@dp.message(F.text.in_(["Olmos yechish 💎", "Olmos yechish"]))
async def start_withdraw(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    user_id = message.from_user.id
    balance, _, _ = get_user_stats(user_id)

    if balance < 200:
        await message.answer("Hisobingizda olmos yetarli emas❌(min 200💎)")
        return

    await state.set_state(WithdrawState.waiting_for_amount)
    await message.answer("Qancha olmos yechmoqchisiz miqdorini yozib yuboring ❗")

@dp.message(WithdrawState.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        await state.clear()
        return

    if not message.text.isdigit():
        await message.answer("Iltimos miqdorini raqamda yozib yuboring ❗")
        return

    amount = int(message.text)
    user_id = message.from_user.id
    balance, _, _ = get_user_stats(user_id)

    if amount < 200:
        await message.answer("Minimal yechish miqdori 200 olmos! Qaytadan miqdor kiriting:")
        return

    if amount > balance:
        await message.answer("Hisobingizda olmos yetarli emas ❌")
        return

    await state.update_data(withdraw_amount=amount)
    await state.set_state(WithdrawState.waiting_for_code)
    await message.answer("Yumicoin kodingizni yuboring ❗")

@dp.message(WithdrawState.waiting_for_code)
async def process_withdraw_code(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        await state.clear()
        return

    user_data = await state.get_data()
    amount = user_data.get("withdraw_amount")
    yumi_code = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    phone = row[0] if row else "Mavjud emas"

    deduct_balance(user_id, amount)
    req_id = create_withdrawal(user_id, amount, yumi_code)
    
    await state.clear()
    await message.answer("Olmos yechish arizangiz adminga yuborildi tasdiqlashini kuting⏳")

    uname_str = f"@{username}" if username else "Mavjud emas"
    admin_msg = (
        f"Foydalanuvchi: {uname_str}\n"
        f"Id raqami :{user_id}\n"
        f"Tel nomer: {phone}\n"
        f"Olmos yechmoqchi: {amount}\n"
        f"Yumicoin kodi:{yumi_code}"
    )

    await bot.send_message(
        ADMIN_ID,
        admin_msg,
        reply_markup=get_admin_withdraw_keyboard(req_id, user_id)
    )

# --- O'YINLAR BO'LIMI (🎰, 🎳, ⚽️, 🎲, 🎯, 🏀) ---

@dp.message(F.text == "Oʻyin 🎮")
async def game_main_menu(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    await message.answer("Birini tanlang:", reply_markup=get_games_inline_keyboard())

@dp.callback_query(F.data.startswith("game_select:"))
async def select_game_callback(call: types.CallbackQuery):
    game_type = call.data.split(":")[1]
    
    game_descriptions = {
        "slots": "Agar siz 777ni tushirsangiz sizga 10x olmos beriladi",
        "bowling": "Agar barchasini yiqitsangiz sizga 2x olmos beriladi",
        "football": "Goal ursa 1.5x olmos beriladi",
        "dice": "6 ni tushursa 3x 💎 beriladi",
        "darts": "Markazga ursa 2x 💎 beriladi",
        "basketball": "Savatga tushursa 1.5x 💎 beriladi"
    }

    text = game_descriptions.get(game_type, "O'yin sharti mavjud emas.")
    await call.message.edit_text(text, reply_markup=get_play_inline_keyboard(game_type))

@dp.callback_query(F.data.startswith("play_game:"))
async def play_game_callback(call: types.CallbackQuery, state: FSMContext):
    game_type = call.data.split(":")[1]
    await state.update_data(selected_game=game_type)
    await state.set_state(GameState.waiting_for_bet)
    await call.message.answer("Qancha olmos tikmoqchisiz miqdorini yozib yuboring ❗(min 10💎)")
    await call.answer()

@dp.message(GameState.waiting_for_bet)
async def process_game_bet(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        await state.clear()
        return

    if not message.text.isdigit():
        await message.answer("Iltimos miqdorini raqamda yozib yuboring ❗")
        return

    bet = int(message.text)
    user_id = message.from_user.id
    balance, _, _ = get_user_stats(user_id)

    if bet < 10:
        await message.answer("Minimal garov 10 💎! Qaytadan kiriting:")
        return

    if bet > balance:
        await message.answer("Hisobingizda olmos yetarli emas ❌")
        await state.clear()
        return

    data = await state.get_data()
    game_type = data.get("selected_game")
    await state.clear()

    # Balansdan tikilgan olmosni ayiramiz
    deduct_balance(user_id, bet)

    emoji_map = {
        "slots": "🎰",
        "bowling": "🎳",
        "football": "⚽",
        "dice": "🎲",
        "darts": "🎯",
        "basketball": "🏀"
    }

    emoji = emoji_map.get(game_type, "🎲")
    dice_msg = await bot.send_dice(chat_id=message.chat.id, emoji=emoji)
    
    # Animatsiya tugashini kusamiz
    await asyncio.sleep(3.5)

    value = dice_msg.dice.value
    win = False
    win_amount = 0

    if game_type == "slots":
        # Slotda 64 qymati "777" hisoblanadi
        if value == 64:
            win = True
            win_amount = int(bet * 10)
    elif game_type == "bowling":
        # 6 hamma keglini yiqitish (Strike)
        if value == 6:
            win = True
            win_amount = int(bet * 2)
    elif game_type == "football":
        # 3, 4, 5 qiymatlar gol hisoblanadi
        if value in [3, 4, 5]:
            win = True
            win_amount = int(bet * 1.5)
    elif game_type == "dice":
        # 6 tushishi
        if value == 6:
            win = True
            win_amount = int(bet * 3)
    elif game_type == "darts":
        # 6 qiymat markazga urish (Bullseye)
        if value == 6:
            win = True
            win_amount = int(bet * 2)
    elif game_type == "basketball":
        # 4, 5 qiymatlar savatga tushish
        if value in [4, 5]:
            win = True
            win_amount = int(bet * 1.5)

    if win:
        add_balance(user_id, win_amount)
        await message.answer(f"🎉 Tabriklaymiz! Siz yutdingiz va <b>+{win_amount} 💎</b> hisobingizga qo'shildi!", parse_mode="HTML")
    else:
        await message.answer(f"❌ Afsuski yutqazdingiz! {bet} olmos yechib olindi.")

# --- MUROJAAT ☎️ ---

@dp.message(F.text.in_(["Murojaat ☎️", "🔴 Murojaat ☎️"]))
async def murojaat_button(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    await state.set_state(MurojaatState.waiting_for_text)
    await message.answer("Murojaatingizni yozib yuboring ❗")

@dp.message(MurojaatState.waiting_for_text)
async def receive_murojaat(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Murojaatingizni admin ko'rib chiqadi ⏳")
    
    user_info = f"👤 Kimdan: {message.from_user.full_name}\n"
    if message.from_user.username:
        user_info += f"🔗 Username: @{message.from_user.username}\n"
    user_info += f"🆔 ID: <code>{message.from_user.id}</code>"

    admin_msg = (
        f"📩 <b>Yangi murojaat keldi!</b>\n\n"
        f"{user_info}\n\n"
        f"💬 <b>Xabar:</b>\n{message.text}\n\n"
        f"<i>👇 Javob berish uchun ushbu xabarga Reply (Javob bering) qiling.</i>"
    )
    await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
    
