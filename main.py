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

BOT_TOKEN = "8503188728:AAH5ktMt7AIOQIRfJvDFrMLPDnIvjufUH-A"
ADMIN_ID = 7803078084
DARKO_API_KEY = "yc_live_5286afa187f7b3d0a172d0e6c3e0e829cc65a48faf7b2748"

DB_NAME = "bot_database.db"
CHANNELS = ["@Minecoine_kanal"]

# Baza funksiyalari
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

# Dinamik menyu
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
    # Foydalanuvchi kirish huquqini, ban va telefonni tekshirish
async def ensure_access(message: types.Message, state: FSMContext) -> bool:
    user_id = message.from_user.id
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

# "Tekshirish" tugmasi bosilganda
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
            await call.message.answer(
                "📱 Botdan foydalanish uchun telefon raqamingizni yuboring:",
                reply_markup=phone_menu
            )
        else:
            await call.message.answer("Siz asosiy menyudasiz🖥️", reply_markup=get_main_menu(user_id))
    else:
        await call.answer("❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)

# Telefon raqamni qabul qilish va saqlash
@dp.message(PhoneState.waiting_for_phone, F.contact)
async def receive_phone(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if is_user_banned(user_id):
        await message.answer("Siz bloklangansiz ❌")
        return

    phone = message.contact.phone_number
    save_phone(user_id, phone)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT referrer_id, bonus_given FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
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
                SET balance = balance + 10,
                    total_referrals = total_referrals + 1,
                    today_referrals = ?,
                    last_ref_date = ?
                WHERE user_id = ?
            ''', (ref_today, today_str, referrer_id))
            
            cursor.execute("UPDATE users SET bonus_given = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 Siz taklif qilgan foydalanuvchi ({message.from_user.full_name}) telefon raqamini tasdiqladi!\nSizga <b>+10 💎</b> berildi!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    else:
        conn.commit()
        
    conn.close()
    await state.clear()
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
    if message.from_user.id != ADMIN_ID:
        return

    identifier = message.text.strip()
    user_info = get_user_by_id_or_username(identifier)
    
    if not user_info:
        await message.answer("❌ Foydalanuvchi topilmadi. ID yoki username ni to'g'ri kiriting:")
        return

    user_id, full_name, username, phone, balance = user_info
    
    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"📛 <b>Ism:</b> {full_name}\n"
        f"🔗 <b>Username:</b> @{username if username else 'Mavjud emas'}\n"
        f"📱 <b>Nomer:</b> {phone if phone else 'Mavjud emas'}\n"
        f"💎 <b>Hisobindagi olmos:</b> {balance} ta"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Hisobni o'zgartirish", callback_data=f"edit_bal:{user_id}")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()

# "Olmos ishlash 💎"
@dp.message(F.text.in_(["Olmos ishlash 💎", "Olmos ishlash"]))
async def olmos_handler(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    user_id = message.from_user.id
    balance, total_refs, today_refs = get_user_stats(user_id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    text = (
        f"👥 <b>Referal tizimi</b>\n\n"
        f"🔗 <b>Sizning referal havolangiz:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👤 <b>Referallar soni:</b> {total_refs}\n"
        f"📅 <b>Bugungi referallar:</b> {today_refs}\n"
        f"💎 <b>Jami bonus:</b> {balance}\n\n"
        f"Har bir taklif qilingan do'stingiz uchun 10 💎 olasiz!\n\n"
        f"🏆 Top referallar ro'yxatini ko'rish uchun /top buyrug'ini yuboring."
    )
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

# "Balans 💎"
@dp.message(F.text.in_(["Balans 💎", "Balans"]))
async def balance_handler(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    user_id = message.from_user.id
    balance, _, _ = get_user_stats(user_id)
    await message.answer(f"Sizning hisobingizda {balance} olmos bor❗")

# "Olmos yechish 💎"
@dp.message(F.text.in_(["Olmos yechish 💎", "Olmos yechish"]))
async def start_withdraw(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    user_id = message.from_user.id
    balance, _, _ = get_user_stats(user_id)

    if balance < 10:
        await message.answer("hisobingizda olmos yetarli emas ❌")
        return

    await state.set_state(WithdrawState.waiting_for_amount)
    await message.answer("qancha olmos yechmoqchisiz miqdorini yozib yuboring")

# Miqdorni qabul qilish
@dp.message(WithdrawState.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        await state.clear()
        return

    if not message.text.isdigit():
        await message.answer("iltimos miqdorini yozib yuboring ❗")
        return

    amount = int(message.text)
    user_id = message.from_user.id
    balance, _, _ = get_user_stats(user_id)

    if amount < 10:
        await message.answer("Minimal yechish miqdori 10 olmos! Qaytadan miqdor kiriting:")
        return

    if amount > balance:
        await message.answer("hisobingizda olmos yetarli emas ❌")
        return

    await state.update_data(withdraw_amount=amount)
    await state.set_state(WithdrawState.waiting_for_code)
    await message.answer("yumicoin kodingizni yozib yuboring")

# Yumicoin kodini qabul qilish va Adminga so'rov yuborish
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
    phone = row[0] if row else "Yo'q"

    deduct_balance(user_id, amount)
    req_id = create_withdrawal(user_id, amount, yumi_code)
    
    await state.clear()
    await message.answer("✅ So'rovingiz adminga yuborildi! Tasdiqlanishini kuting ⏳")

    uname_str = f"@{username}" if username else "Mavjud emas"
    admin_msg = (
        f"📥 <b>Yangi olmos yechish so'rovi! (#ID{req_id})</b>\n\n"
        f"👤 {uname_str}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📱 Nomeri: <code>{phone}</code>\n"
        f"💎 Olmos yechmoqchi: <b>{amount}</b>\n"
        f"🔑 Kodi: <code>{yumi_code}</code>"
    )

    await bot.send_message(
        ADMIN_ID,
        admin_msg,
        parse_mode="HTML",
        reply_markup=get_admin_withdraw_keyboard(req_id, user_id)
    )
    
