require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');

const TOKEN = process.env.BOT_TOKEN;
const WEBAPP_URL = process.env.WEBAPP_URL;

if (!TOKEN) {
  console.error('XATOLIK: .env faylida BOT_TOKEN ko\'rsatilmagan!');
  process.exit(1);
}
if (!WEBAPP_URL) {
  console.error('XATOLIK: .env faylida WEBAPP_URL ko\'rsatilmagan!');
  process.exit(1);
}

const bot = new TelegramBot(TOKEN, { polling: true });

bot.onText(/\/start(?:\s+(.+))?/, (msg, match) => {
  const chatId = msg.chat.id;
  const refCode = match && match[1] ? match[1] : null;
  const appUrl = refCode ? `${WEBAPP_URL}?ref=${encodeURIComponent(refCode)}` : WEBAPP_URL;

  bot.sendMessage(chatId,
    `Assalomu alaykum, ${msg.from.first_name || 'do\'stim'}! 👋\n\n` +
    `*Yopish* o'yiniga xush kelibsiz — tanga yig'ing, xarakterlar sotib oling va auksionda sovg'a yuting! 🪙`,
    {
      parse_mode: 'Markdown',
      reply_markup: {
        inline_keyboard: [[
          { text: '🎮 O\'yinni boshlash', web_app: { url: appUrl } }
        ]]
      }
    }
  );
});

bot.onText(/\/help/, (msg) => {
  bot.sendMessage(msg.chat.id,
    'Buyruqlar:\n/start - o\'yinni ochish\n/help - yordam'
  );
});

console.log('Bot ishga tushdi (polling rejimida)...');
