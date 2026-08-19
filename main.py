import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)

BOT_TOKEN = 8961743918:AAFYT7ALFuDCN7sqqRrSKcvNgpLbLFVISBc
ADMIN_ID = 7803078084

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# 1. Pastda turadigan oddiy tugma (Reply Keyboard)
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✍️ Murojaat yuborish")]
    ],
    resize_keyboard=True
)

# 2. Xabar ostida chiqadigan inline tugma
inline_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💬 Adminga bog'lanish", url="https://t.me/telegram_username")]
    ]
)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "Assalomu alaykum! Tugmani bosing:",
        reply_markup=main_menu
    )

@dp.message(F.text == "✍️ Murojaat yuborish")
async def murojaat_handler(message: types.Message):
    await message.answer(
        "Murojaatingizni yozib yuboring, men uni adminga yetkazaman:",
        reply_markup=inline_menu
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
