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
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

BOT_TOKEN = "8825351774:AAFI7D9WaBz3fcMV5fClnWCrOmWuLJqn0ug"
ADMIN_ID = 7803078084  # Sizning Telegram ID raqamingiz

DB_NAME = "bot_database.db"

# Database yaratish va ulash
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            referrer_id INTEGER,
            balance INTEGER DEFAULT 0,
            total_referrals INTEGER DEFAULT 0,
            today_referrals INTEGER DEFAULT 0,
            last_ref_date TEXT
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
    
    is_new = False
    if not user:
        is_new = True
        cursor.execute(
            "INSERT INTO users (user_id, full_name, referrer_id, balance, total_referrals, today_referrals, last_ref_date) VALUES (?, ?, ?, 0, 0, 0, ?)",
            (user_id, full_name, referrer_id, today_str)
        )
        conn.commit()
        
        # Taklif qilgan odamga bonus va hisobot qo'shish
        if referrer_id and referrer_id != user_id:
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
                conn.commit()
    conn.close()
    return is_new

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

def get_top_referrers():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, total_referrals FROM users ORDER BY total_referrals DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return rows

# Holatlar (FSM)
class MurojaatState(StatesGroup):
    waiting_for_text = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Asosiy menyu tugmalari
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Olmos ishlash 💎")],
        [KeyboardButton(text="Murojaat ☎️")]
    ],
    resize_keyboard=True
)

# /start buyrug'i
@dp.message(CommandStart())
async def start_cmd(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    
    referrer_id = None
    if command.args and command.args.isdigit():
        referrer_id = int(command.args)
        
    is_new = get_or_create_user(user_id, full_name, referrer_id)
    
    if is_new and referrer_id and referrer_id != user_id:
        try:
            await bot.send_message(
                referrer_id,
                f"🎉 <b>Sizning havolangiz orqali {full_name} botga kirdi!</b>\n"
                f"Sizga <b>+10 💎</b> bonus berildi!",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await message.answer("Assalomu alaykum! Kerakli bo'limni tanlang:", reply_markup=main_menu)

# "Olmos ishlash 💎" tugmasi
@dp.message(F.text.in_(["Olmos ishlash 💎", "Olmos ishlash"]))
async def olmos_handler(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    get_or_create_user(user_id, full_name)
    
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

# /top buyrug'i
@dp.message(Command("top"))
async def top_handler(message: types.Message):
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

# "Murojaat ☎️" tugmasi
@dp.message(F.text == "Murojaat ☎️")
async def murojaat_button(message: types.Message, state: FSMContext):
    await state.set_state(MurojaatState.waiting_for_text)
    await message.answer("Murojaatingizni yozib yuboring ❗")

# Murojaat matnini qabul qilish
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

# Admin Reply orqali javob yozganda
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
            await message.reply(f"❌ Xabarni yuborib bo'lmadi: {e}")

# Render porti uchun veb-server
async def handle(request):
    return web.Response(text="Bot 24/7 rejimida ishlayapti!")

async def main():
    init_db()  # Bazani tayyorlash
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
                       
