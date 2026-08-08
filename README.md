# Yopish-clone — Tap-to-Earn Telegram Mini App

Rasmlardagi "Yopish" ilovasiga o'xshash to'liq loyiha: Telegram bot + Mini App (Web App) + backend server.

## Loyiha tarkibi

```
yopish-clone/
├── bot.js            # Telegram bot (Mini App'ni ochadi)
├── server.js         # Backend API server (Express)
├── db.js             # Ma'lumotlar bazasi bilan ishlash (JSON fayl asosida)
├── data/db.json       # Baza fayli (xarakterlar, vazifalar, auksionlar, userlar)
├── webapp/
│   ├── index.html     # Mini App interfeysi
│   ├── style.css       # Qora-oltin dizayn (rasmlarga mos)
│   └── app.js          # Frontend logika
├── package.json
└── .env.example
```

## Funksiyalar

- 🪙 **Bosish (Tap-to-earn)** — tangani bosib tanga yig'ish, energiya tizimi
- 🏪 **Do'kon** — olmos evaziga xarakterlar sotib olish (click multiplier oshiradi)
- ✅ **Vazifalar** — kanalga obuna, referal, kunlik bonus kod
- ⚖️ **Auksion** — tangaga narx aytish, taymer bilan tugaydigan lotlar
- 👤 **Profil** — balans va referal kod

## O'rnatish (deploy qilish)

### 1. Kerakli dasturlarni o'rnatish
Kompyuteringizda [Node.js](https://nodejs.org) (v18+) o'rnatilgan bo'lishi kerak.

```bash
cd yopish-clone
npm install
```

### 2. Bot token olish
1. Telegram'da [@BotFather](https://t.me/BotFather) ga yozing
2. `/newbot` buyrug'ini yuboring, nom va username bering
3. Sizga beriladigan tokenni saqlab qo'ying

### 3. `.env` faylini sozlash
`.env.example` faylidan nusxa oling va `.env` deb nomlang:

```bash
cp .env.example .env
```

Ichiga tokeningizni kiriting:
```
BOT_TOKEN=sizning_tokeningiz
WEBAPP_URL=https://sizning-domeningiz.com/webapp
PORT=3000
```

### 4. Serverni internetga chiqarish (hosting)
Mini App ishlashi uchun `webapp/` papkasi **HTTPS** orqali ochiq bo'lishi kerak (Telegram HTTP'ni qabul qilmaydi). Bepul variantlar:

- **Railway.app** — GitHub repo'ni ulab, bir necha click bilan deploy qilinadi
- **Render.com** — bepul Node.js hosting
- **VPS + Nginx + Let's Encrypt** — o'zingizning serveringiz bo'lsa

Deploy qilingandan so'ng, sizga berilgan domenni `.env` faylidagi `WEBAPP_URL` ga qo'ying (masalan `https://yopish-clone.up.railway.app/webapp`).

### 5. BotFather orqali Mini App'ni ulash
1. @BotFather'ga qayting → botingizni tanlang → **Bot Settings → Menu Button**
2. URL sifatida `WEBAPP_URL` manzilini kiriting

### 6. Ishga tushirish
Ikkita alohida terminalda (yoki `pm2` bilan):

```bash
npm start      # backend serverni ishga tushiradi (server.js)
npm run bot    # botni ishga tushiradi (bot.js)
```

Botga `/start` yozing — "O'yinni boshlash" tugmasi chiqadi.

## Keyingi qadamlar (kengaytirish)

- **To'lov tizimi**: olmos sotib olish uchun Telegram Payments yoki tashqi to'lov provayderini ulash (`server.js`dagi `/api/shop/buy` yonida)
- **Baza**: hozir oddiy JSON fayl ishlatilgan (kichik loyihalar uchun yetarli). Ko'p foydalanuvchi bo'lsa PostgreSQL/MongoDB'ga o'tish tavsiya etiladi
- **Admin panel**: vazifalar, auksion lotlarini qo'shish/o'chirish uchun alohida boshqaruv sahifasi
- **Xavfsizlik**: hozirgi API'lar ochiq — production uchun Telegram `initData` imzosini tekshirish (HMAC validatsiya) qo'shish tavsiya etiladi

## Muhim eslatma

Bu loyiha demo/boshlang'ich versiya sifatida yozilgan — asosiy mexanika (tap, do'kon, vazifalar, auksion) to'liq ishlaydi, lekin production muhitiga chiqarishdan oldin xavfsizlik va bazani mustahkamlash tavsiya etiladi.
