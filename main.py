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
            phone TEXT,
            referrer_id INTEGER,
            balance INTEGER DEFAULT 0,
            total_referrals INTEGER DEFAULT 0,
            today_referrals INTEGER DEFAULT 0,
            last_ref_date TEXT,
            bonus_given INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_or_create_user(user_id: int, full_name: str, referrer_id: int = None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_str = str(date.today())
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, full_name, referrer_id, balance, total_referrals, today_referrals, last_ref_date, bonus_given) VALUES (?, ?, ?, 0, 0, 0, ?, 0)",
            (user_id, full_name, referrer_id, today_str)
        )
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

def deduct_balance(user_id: int, amount: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def get_top_referrers():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, total_referrals FROM users ORDER BY total_referrals DESC LIMIT 10")
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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Menyu va tugmalar
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Olmos ishlash 💎"),
            KeyboardButton(text="Balans 💎"),
            KeyboardButton(text="Olmos yechish 💎")
        ],
        [KeyboardButton(text="🔴 Murojaat ☎️")]
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
    
    referrer_id = None
    if command.args and command.args.isdigit():
        referrer_id = int(command.args)
        
    get_or_create_user(user_id, full_name, referrer_id)

    if not await check_subscription(bot, user_id):
        await message.answer(
            "Botdan foydalanishdan oldin majburiy kanalga obuna boʻling ❗",
            reply_markup=get_sub_keyboard()
        )
        return

    # Telefon raqami yuborilganligini tekshirish
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        await state.set_state(PhoneState.waiting_for_phone)
        await message.answer(
            "📱 Botdan foydalanish uchun telefon raqamingizni yuboring:",
            reply_markup=phone_menu
        )
        return

    await message.answer("Siz asosiy menyudasiz🖥️", reply_markup=main_menu)
    # Foydalanuvchi kirish huquqini tekshirish uchun yordamchi funksiya
async def ensure_access(message: types.Message, state: FSMContext) -> bool:
    user_id = message.from_user.id
    if not await check_subscription(bot, user_id):
        await message.answer("Botdan foydalanishdan oldin majburiy kanalga obuna boʻling ❗", reply_markup=get_sub_keyboard())
        return False
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not row[0]:
        await state.set_state(PhoneState.waiting_for_phone)
        await message.answer("📱 Botdan foydalanish uchun telefon raqamingizni yuboring:", reply_markup=phone_menu)
        return False
    return True

# "Tekshirish" tugmasi bosilganda
@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if await check_subscription(bot, user_id):
        await call.message.delete()
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT phone FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            await state.set_state(PhoneState.waiting_for_phone)
            await call.message.answer(
                "📱 Botdan foydalanish uchun telefon raqamingizni yuboring:",
                reply_markup=phone_menu
            )
        else:
            await call.message.answer("Siz asosiy menyudasiz🖥️", reply_markup=main_menu)
    else:
        await call.answer("❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)

# Telefon raqamni qabul qilish va referal bonus berish
@dp.message(PhoneState.waiting_for_phone, F.contact)
async def receive_phone(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id))
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
    await message.answer("Siz asosiy menyudasiz🖥️", reply_markup=main_menu)

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

# Yumicoin kodini qabul qilish va avtomatik yuborish
@dp.message(WithdrawState.waiting_for_code)
async def process_withdraw_code(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        await state.clear()
        return

    user_data = await state.get_data()
    amount = user_data.get("withdraw_amount")
    yumi_code = message.text.strip()
    user_id = message.from_user.id

    msg = await message.answer("⏳ Darko API orqali olmos yuborilmoqda, kuting...")

    success, api_msg = await send_darko_diamonds(yumi_code, amount)

    if success:
        deduct_balance(user_id, amount)
        await state.clear()
        await msg.edit_text(f"✅ Yumicoin hisobingizga {amount} olmos avtomatik tashlab berildi!")

        admin_msg = (
            f"⚡️ <b>Avto-yechish muvaffaqiyatli bajarildi!</b>\n\n"
            f"👤 <b>Foydalanuvchi:</b> {message.from_user.full_name} (@{message.from_user.username})\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"💎 <b>Miqdori:</b> {amount} olmos\n"
            f"🔑 <b>YumiCoin kodi:</b> <code>{yumi_code}</code>"
        )
        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
    else:
        await state.clear()
        await msg.edit_text(f"❌ Olmos o'tkazishda xatolik yuz berdi: {api_msg}\nBalansizdan olmos ayrilmadi.")

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
        safe_name = name.replace("<", "&lt;").replace(">", "&gt;")
        text += f"{prefix} <b>{safe_name}</b> — {count} ta referal\n"
        
    await message.answer(text, parse_mode="HTML")

# "🔴 Murojaat ☎️"
@dp.message(F.text.in_(["🔴 Murojaat ☎️", "Murojaat ☎️"]))
async def murojaat_button(message: types.Message, state: FSMContext):
    if not await ensure_access(message, state):
        return

    await state.set_state(MurojaatState.waiting_for_text)
    await message.answer("Murojaatingizni yozib yuboring ❗")

@dp.message(MurojaatState.waiting_for_text)
async def receive_murojaat(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Murojaatingizni tez orada ko'rib chiqamiz ⏳")
    
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

# Admin Reply orqali javob berishi
@dp.message(F.chat.id == ADMIN_ID, F.reply_to_message)
async def admin_reply(message: types.Message):
    reply_text = message.reply_to_message.text or message.reply_to_message.caption
    if not reply_text:
        return

    match = re.search(r"🆔 ID:\s*(\d+)", reply_text)
    if match:
        target_user_id = int(match.group(1))
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=f"👨‍💻 <b>Admindan javob:</b>\n\n{message.text}",
                parse_mode="HTML"
            )
            await message.reply("✅ Javobingiz foydalanuvchiga yuborildi!")
        except Exception as e:
            await message.reply(f"❌ Xabarni yuborib bo'mladi: {e}")

# Render serveri uchun veb-server
async def handle(request):
    return web.Response(text="Bot 24/7 rejimida ishlayapti!")

async def main():
    init_db()
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
