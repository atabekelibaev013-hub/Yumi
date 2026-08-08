const fs = require('fs');
const path = require('path');

const DB_PATH = path.join(__dirname, 'data', 'db.json');

function readDB() {
  const raw = fs.readFileSync(DB_PATH, 'utf-8');
  return JSON.parse(raw);
}

function writeDB(data) {
  fs.writeFileSync(DB_PATH, JSON.stringify(data, null, 2), 'utf-8');
}

function getUser(db, userId) {
  if (!db.users[userId]) {
    db.users[userId] = {
      id: userId,
      username: null,
      balance: 0,
      diamonds: 0,
      energy: 500,
      maxEnergy: 500,
      lastEnergyUpdate: Date.now(),
      ownedCharacters: ['classic'],
      activeCharacter: 'classic',
      completedTasks: [],
      lastDailyClaim: null,
      referralCode: genCode(userId),
      referredBy: null,
      createdAt: Date.now()
    };
  }
  return db.users[userId];
}

function genCode(seed) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let out = '';
  let s = String(seed) + Date.now();
  for (let i = 0; i < 8; i++) {
    const idx = (s.charCodeAt(i % s.length) * (i + 7)) % chars.length;
    out += chars[idx];
  }
  return out;
}

// Vaqt o'tishi bilan energiyani qayta tiklash: har 3 soniyada +1 energy
function regenEnergy(user) {
  const now = Date.now();
  const elapsedSec = Math.floor((now - user.lastEnergyUpdate) / 1000);
  if (elapsedSec <= 0) return user;
  const regen = Math.floor(elapsedSec / 3);
  if (regen > 0) {
    user.energy = Math.min(user.maxEnergy, user.energy + regen);
    user.lastEnergyUpdate = now;
  }
  return user;
}

module.exports = { readDB, writeDB, getUser, regenEnergy, genCode };
