import asyncio
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

BOT_TOKEN = "8825351774:AAFI7D9WaBz3fcMV5fClnWCrOmWuLJqn0ug"
ADMIN_ID = 7803078084 # <-- Shu yerga o'zingizning Telegram ID raqamingizni yozing

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✍️ Murojaat yuborish")]
    ],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "Assalomu alaykum! Tugmani bosing:",
        reply_markup=main_menu
    )

@dp.message(F.text == "✍️ Murojaat yuborish")
async def murojaat_handler(message: types.Message):
    await message.answer("Murojaatingizni yozib yuboring, men uni adminga yetkazaman:")

# Foydalanuvchi yozgan har qanday xabarni adminga yuborish
@dp.message()
async def forward_to_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        await message.reply("✅ Murojaatingiz adminga yetkazildi!")

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
    
