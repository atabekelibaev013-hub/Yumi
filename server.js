require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const { readDB, writeDB, getUser, regenEnergy } = require('./db');

const app = express();
app.use(cors());
app.use(express.json());
app.use('/webapp', express.static(path.join(__dirname, 'webapp')));

const PORT = process.env.PORT || 3000;

// ---------- Foydalanuvchi ma'lumotlari ----------
app.get('/api/user/:id', (req, res) => {
  const db = readDB();
  const user = getUser(db, req.params.id);
  regenEnergy(user);
  writeDB(db);
  res.json(publicUser(user));
});

app.post('/api/user/:id/register', (req, res) => {
  const db = readDB();
  const user = getUser(db, req.params.id);
  const { username, refCode } = req.body;
  if (username) user.username = username;

  // Referal kodi orqali kirgan bo'lsa
  if (refCode && !user.referredBy && String(req.params.id) !== '') {
    const referrer = Object.values(db.users).find(u => u.referralCode === refCode);
    if (referrer && referrer.id !== user.id) {
      user.referredBy = referrer.id;
      referrer.balance += 3000; // Do'stlar vazifasi mukofoti
    }
  }
  writeDB(db);
  res.json(publicUser(user));
});

// ---------- Bosish (tap) ----------
app.post('/api/tap', (req, res) => {
  const { userId, taps } = req.body;
  const db = readDB();
  const user = getUser(db, userId);
  regenEnergy(user);

  const character = db.characters.find(c => c.id === user.activeCharacter) || db.characters[0];
  const requestedTaps = Math.max(1, Math.min(50, taps || 1)); // suiiste'moldan himoya
  const actualTaps = Math.min(requestedTaps, user.energy);

  user.balance += actualTaps * character.clickPower;
  user.energy -= actualTaps;
  user.lastEnergyUpdate = Date.now();

  writeDB(db);
  res.json({ balance: user.balance, energy: user.energy, maxEnergy: user.maxEnergy, clickPower: character.clickPower });
});

// ---------- Do'kon ----------
app.get('/api/shop', (req, res) => {
  const db = readDB();
  res.json(db.characters);
});

app.post('/api/shop/buy', (req, res) => {
  const { userId, characterId } = req.body;
  const db = readDB();
  const user = getUser(db, userId);
  const character = db.characters.find(c => c.id === characterId);

  if (!character) return res.status(404).json({ error: 'Xarakter topilmadi' });
  if (user.ownedCharacters.includes(characterId)) return res.status(400).json({ error: 'Allaqachon sotib olingan' });
  if (user.diamonds < character.priceDiamonds) return res.status(400).json({ error: 'Olmos yetarli emas' });

  user.diamonds -= character.priceDiamonds;
  user.ownedCharacters.push(characterId);
  writeDB(db);
  res.json(publicUser(user));
});

app.post('/api/shop/select', (req, res) => {
  const { userId, characterId } = req.body;
  const db = readDB();
  const user = getUser(db, userId);
  if (!user.ownedCharacters.includes(characterId)) return res.status(400).json({ error: 'Bu xarakter sizda yo\'q' });
  user.activeCharacter = characterId;
  writeDB(db);
  res.json(publicUser(user));
});

// ---------- Vazifalar ----------
app.get('/api/tasks/:userId', (req, res) => {
  const db = readDB();
  const user = getUser(db, req.params.userId);
  const tasks = db.tasks.map(t => ({ ...t, completed: user.completedTasks.includes(t.id) }));
  res.json(tasks);
});

app.post('/api/tasks/claim', (req, res) => {
  const { userId, taskId } = req.body;
  const db = readDB();
  const user = getUser(db, userId);
  const task = db.tasks.find(t => t.id === taskId);
  if (!task) return res.status(404).json({ error: 'Vazifa topilmadi' });
  if (user.completedTasks.includes(taskId)) return res.status(400).json({ error: 'Vazifa allaqachon bajarilgan' });

  user.completedTasks.push(taskId);
  user.balance += task.reward;
  writeDB(db);
  res.json(publicUser(user));
});

// ---------- Kunlik bonus kod ----------
app.post('/api/daily/claim', (req, res) => {
  const { userId } = req.body;
  const db = readDB();
  const user = getUser(db, userId);
  const now = Date.now();
  const DAY_MS = 24 * 60 * 60 * 1000;

  if (user.lastDailyClaim && now - user.lastDailyClaim < DAY_MS) {
    const remainMs = DAY_MS - (now - user.lastDailyClaim);
    return res.status(400).json({ error: 'Hali vaqt kelmadi', remainMs });
  }

  user.balance += 100;
  user.lastDailyClaim = now;
  writeDB(db);
  res.json(publicUser(user));
});

// ---------- Auksion ----------
app.get('/api/auctions', (req, res) => {
  const db = readDB();
  const status = req.query.status || 'active';
  ensureAuctionTimers(db);
  writeDB(db);
  res.json(db.auctions.filter(a => a.status === status));
});

app.post('/api/auctions/bid', (req, res) => {
  const { userId, auctionId, amount } = req.body;
  const db = readDB();
  const user = getUser(db, userId);
  ensureAuctionTimers(db);
  const auction = db.auctions.find(a => a.id === auctionId);

  if (!auction) return res.status(404).json({ error: 'Auksion topilmadi' });
  if (auction.status !== 'active') return res.status(400).json({ error: 'Auksion tugagan' });
  if (amount <= auction.currentBid) return res.status(400).json({ error: 'Taklif joriy narxdan yuqori bo\'lishi kerak' });
  if (user.balance < amount) return res.status(400).json({ error: 'Tanga yetarli emas' });

  auction.currentBid = amount;
  auction.bidCount += 1;
  auction.highestBidder = userId;
  writeDB(db);
  res.json(auction);
});

function ensureAuctionTimers(db) {
  const now = Date.now();
  db.auctions.forEach(a => {
    if (!a.endTime) a.endTime = now + a.durationSeconds * 1000;
    if (a.status === 'active' && now >= a.endTime) {
      a.status = 'ended';
      if (a.highestBidder && db.users[a.highestBidder]) {
        db.users[a.highestBidder].balance -= a.currentBid;
      }
    }
  });
}

function publicUser(user) {
  const { id, username, balance, diamonds, energy, maxEnergy, ownedCharacters, activeCharacter, completedTasks, lastDailyClaim, referralCode } = user;
  return { id, username, balance, diamonds, energy, maxEnergy, ownedCharacters, activeCharacter, completedTasks, lastDailyClaim, referralCode };
}

app.listen(PORT, () => {
  console.log(`Yopish-clone server ${PORT}-portda ishga tushdi`);
});

// Bot tokeni mavjud bo'lsa, botni ham shu jarayon ichida ishga tushiramiz
// (Railway kabi hostinglarda bitta xizmat sifatida joylash uchun qulay)
if (process.env.BOT_TOKEN) {
  require('./bot');
}
