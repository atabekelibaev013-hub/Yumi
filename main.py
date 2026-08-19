import asyncio
import os
import re
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

BOT_TOKEN = "8825351774:AAFI7D9WaBz3fcMV5fClnWCrOmWuLJqn0ug"
ADMIN_ID = 7803078084 # <-- Shu yerga Telegram ID raqamingizni kiriting!

# Holatlarni saqlash (FSM)
class MurojaatState(StatesGroup):
    waiting_for_text = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Bosh menyu tugmasi
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Murojaat ☎️")]
    ],
    resize_keyboard=True
)

# /start komandasi
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Assalomu alaykum! Murojaat qoldirish uchun tugmani bosing:", reply_markup=main_menu)

# "Murojaat ☎️" tugmasi bosilganda
@dp.message(F.text == "Murojaat ☎️")
async def murojaat_button(message: types.Message, state: FSMContext):
    await state.set_state(MurojaatState.waiting_for_text)
    await message.answer("Murojaatingizni yozib yuboring ❗")

# Foydalanuvchi murojaat matnini yuborganda
@dp.message(MurojaatState.waiting_for_text)
async def receive_murojaat(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Murojaatingizni tez orada ko'rib chiqamiz ⏳")
    
    # Adminga yuboriladigan ma'lumot
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

# Admin kelgan xabarga Reply (Javob) qilganda foydalanuvchiga yetkazish
@dp.message(F.chat.id == ADMIN_ID, F.reply_to_message)
async def admin_reply(message: types.Message):
    reply_text = message.reply_to_message.text or message.reply_to_message.caption
    if not reply_text:
        return

    # Kelgan xabardan foydalanuvchi ID sini ajratib olish
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
            await message.reply(f"❌ Xabarni yuborib bo'lmadi. Xatolik: {e}")
    else:
        await message.reply("⚠️ Ushbu xabar orqali foydalanuvchi ID si topilmadi.")

# Render serveri uchun veb-port
async def handle(request):
    return web.Response(text="Bot 24/7 rejimida ishlayapti!")

async def main():
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
