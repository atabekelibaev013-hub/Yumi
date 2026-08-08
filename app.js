const tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) { tg.ready(); tg.expand(); }

const API = ''; // bir xil serverdan xizmat qilinadi, shuning uchun bo'sh (relative)

const urlParams = new URLSearchParams(window.location.search);
const refCode = urlParams.get('ref');

const tgUser = tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user : null;
const USER_ID = tgUser ? String(tgUser.id) : 'demo_' + (localStorage.getItem('demoId') || (() => {
  const id = Math.floor(Math.random() * 1000000);
  localStorage.setItem('demoId', id);
  return id;
})());
const USERNAME = tgUser ? (tgUser.username || tgUser.first_name) : 'Mehmon';

let state = { user: null, characters: [], tasks: [], auctions: [] };
let charactersById = {};

// ---------- Yordamchi funksiyalar ----------
async function apiGet(url) {
  const res = await fetch(url);
  return res.json();
}
async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  return { ok: res.ok, data: await res.json() };
}
function fmt(n) {
  n = Math.floor(n);
  if (n >= 1000) return (n / 1000).toFixed(1).replace('.0', '') + 'K';
  return String(n);
}

// ---------- Navigatsiya ----------
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => switchScreen(btn.dataset.screen));
});
document.getElementById('gotoBoost').addEventListener('click', () => switchScreen('screen-boost'));
document.getElementById('gotoShop').addEventListener('click', () => switchScreen('screen-boost'));

function switchScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  document.querySelector(`.nav-btn[data-screen="${id}"]`).classList.add('active');
  if (id === 'screen-boost') loadShop();
  if (id === 'screen-tasks') loadTasks();
  if (id === 'screen-auction') loadAuctions('active');
  if (id === 'screen-profile') loadProfile();
}

// ---------- Init ----------
async function init() {
  await apiPost(`/api/user/${USER_ID}/register`, { username: USERNAME, refCode });
  await refreshUser();
  await loadShop();
  document.getElementById('refCode').textContent = state.user.referralCode;
}

async function refreshUser() {
  state.user = await apiGet(`/api/user/${USER_ID}`);
  renderTopbar();
  renderTapScreen();
}

function renderTopbar() {
  document.getElementById('diamondCount').textContent = fmt(state.user.diamonds);
  document.getElementById('coinCount').textContent = fmt(state.user.balance);
}

function renderTapScreen() {
  document.getElementById('tapBalance').textContent = fmt(state.user.balance);
  document.getElementById('energyCur').textContent = Math.floor(state.user.energy);
  document.getElementById('energyMax').textContent = state.user.maxEnergy;
  document.getElementById('hozirVal').textContent = `${Math.floor(state.user.energy)}/${state.user.maxEnergy}`;
  const pct = (state.user.energy / state.user.maxEnergy) * 100;
  document.getElementById('energyFill').style.width = pct + '%';
  const char = charactersById[state.user.activeCharacter];
  document.getElementById('tapMultiplier').textContent = `Tap x${char ? char.clickPower : 1}`;
}

// ---------- Tap (bosish) ----------
const coinBtn = document.getElementById('coinBtn');
let pendingTaps = 0;
let tapTimer = null;

coinBtn.addEventListener('click', (e) => {
  if (state.user.energy <= 0) return;
  spawnFloatingText(e);
  state.user.energy -= 1;
  const char = charactersById[state.user.activeCharacter];
  state.user.balance += char ? char.clickPower : 1;
  renderTopbar();
  renderTapScreen();
  pendingTaps += 1;
  if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');

  clearTimeout(tapTimer);
  tapTimer = setTimeout(flushTaps, 400);
});

async function flushTaps() {
  if (pendingTaps <= 0) return;
  const taps = pendingTaps;
  pendingTaps = 0;
  const { data } = await apiPost('/api/tap', { userId: USER_ID, taps });
  if (data.balance !== undefined) {
    state.user.balance = data.balance;
    state.user.energy = data.energy;
    renderTopbar();
    renderTapScreen();
  }
}

function spawnFloatingText(e) {
  const char = charactersById[state.user.activeCharacter];
  const power = char ? char.clickPower : 1;
  const el = document.createElement('div');
  el.textContent = '+' + power;
  el.style.cssText = `position:fixed; left:${e.clientX}px; top:${e.clientY}px; color:#ffd35c; font-weight:800; font-size:20px; pointer-events:none; z-index:999; animation:floatUp 0.8s ease forwards;`;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 800);
}
const styleTag = document.createElement('style');
styleTag.textContent = `@keyframes floatUp { to { transform: translateY(-50px); opacity: 0; } }`;
document.head.appendChild(styleTag);

// Energiyani asta-sekin qayta tiklash (frontendda vizual, backend haqiqiy hisoblaydi)
setInterval(() => {
  if (state.user && state.user.energy < state.user.maxEnergy) {
    refreshUser();
  }
}, 5000);

// ---------- Do'kon (BOOST) ----------
async function loadShop() {
  state.characters = await apiGet('/api/shop');
  charactersById = Object.fromEntries(state.characters.map(c => [c.id, c]));
  renderShop();
  renderTapScreen();
}

function renderShop() {
  const grid = document.getElementById('charGrid');
  grid.innerHTML = '';
  state.characters.forEach(c => {
    const owned = state.user.ownedCharacters.includes(c.id);
    const selected = state.user.activeCharacter === c.id;
    const canBuy = state.user.diamonds >= c.priceDiamonds;

    const card = document.createElement('div');
    card.className = 'char-card';
    card.innerHTML = `
      <div class="char-img">🪙<span class="char-price">${c.priceDiamonds} 💎</span></div>
      <div class="char-name">${c.name}</div>
      <div class="char-meta">x${c.clickPower} click • ${c.cap} cap/day</div>
      <button class="char-btn ${selected ? 'owned' : owned ? 'buy' : canBuy ? 'buy' : 'locked'}">
        ${selected ? 'TANLANGAN' : owned ? 'TANLASH' : canBuy ? 'SOTIB OLISH' : 'YOPIQ'}
      </button>
    `;
    const btn = card.querySelector('.char-btn');
    btn.addEventListener('click', () => handleCharAction(c, owned, selected));
    grid.appendChild(card);
  });
}

async function handleCharAction(c, owned, selected) {
  if (selected) return;
  if (owned) {
    const { ok, data } = await apiPost('/api/shop/select', { userId: USER_ID, characterId: c.id });
    if (ok) { state.user = data; renderShop(); renderTapScreen(); }
  } else {
    const { ok, data } = await apiPost('/api/shop/buy', { userId: USER_ID, characterId: c.id });
    if (ok) { state.user = data; renderShop(); renderTopbar(); }
    else alert(data.error);
  }
}

document.getElementById('refillBtn').addEventListener('click', () => {
  alert('Bu funksiya uchun olmos kerak bo\'ladi (demo rejimida ishlamaydi).');
});
document.getElementById('addDiamondBtn').addEventListener('click', () => {
  alert('Olmos sotib olish bo\'limi hali ulanmagan — bu yerga to\'lov tizimini ulashingiz mumkin.');
});

// ---------- Vazifalar ----------
async function loadTasks() {
  state.tasks = await apiGet(`/api/tasks/${USER_ID}`);
  document.getElementById('taskCount').textContent = state.tasks.filter(t => !t.completed).length;
  renderTasks();

  document.getElementById('dailyCode').textContent = state.user.referralCode;
  const canClaim = !state.user.lastDailyClaim || (Date.now() - state.user.lastDailyClaim > 24 * 60 * 60 * 1000);
  document.getElementById('dailyStatus').textContent = canClaim ? 'Tayyor' : 'Kutilmoqda';
}

function renderTasks() {
  const list = document.getElementById('taskList');
  list.innerHTML = '';
  state.tasks.forEach(t => {
    const item = document.createElement('div');
    item.className = 'task-item';
    item.innerHTML = `
      <div class="task-info">
        <div class="task-icon">${t.type === 'referral' ? '👥' : '📣'}</div>
        <div>
          <div class="task-title">${t.title}</div>
          <div class="task-reward">+${t.reward} tanga</div>
        </div>
      </div>
      <button class="task-btn ${t.completed ? 'done' : ''}">${t.completed ? '✓ BAJARILDI' : 'O\'TISH'}</button>
    `;
    const btn = item.querySelector('.task-btn');
    btn.addEventListener('click', () => handleTask(t));
    list.appendChild(item);
  });
}

async function handleTask(t) {
  if (t.completed) return;
  if (t.link) window.open(t.link, '_blank');
  const { ok, data } = await apiPost('/api/tasks/claim', { userId: USER_ID, taskId: t.id });
  if (ok) {
    state.user = data;
    renderTopbar();
    await loadTasks();
  } else {
    alert(data.error);
  }
}

document.getElementById('dailyClaimBtn').addEventListener('click', async () => {
  const { ok, data } = await apiPost('/api/daily/claim', { userId: USER_ID });
  if (ok) {
    state.user = data;
    renderTopbar();
    await loadTasks();
  } else {
    alert(data.error || 'Hozircha mavjud emas');
  }
});

// ---------- Auksion ----------
document.querySelectorAll('.tab2-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab2-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    loadAuctions(btn.dataset.status);
  });
});

async function loadAuctions(status) {
  state.auctions = await apiGet(`/api/auctions?status=${status}`);
  renderAuctions(status);
}

function renderAuctions(status) {
  const list = document.getElementById('auctionList');
  list.innerHTML = '';
  state.auctions.forEach(a => {
    const remainSec = Math.max(0, Math.floor((a.endTime - Date.now()) / 1000));
    const mm = String(Math.floor(remainSec / 60)).padStart(2, '0');
    const ss = String(remainSec % 60).padStart(2, '0');
    const item = document.createElement('div');
    item.className = 'auction-item';
    item.innerHTML = `
      <div class="auction-info">
        <div class="auction-img">🎁</div>
        <div>
          <div class="auction-title">${a.title}</div>
          <div class="auction-sub">${a.subtitle}</div>
          <div class="auction-price">${a.currentBid} 🪙 • ${a.bidCount} taklif</div>
          ${status === 'active' ? `<div class="auction-timer">${mm}:${ss}</div>` : `<div class="auction-timer" style="color:#c98a2c;">Yakunlangan</div>`}
        </div>
      </div>
      ${status === 'active' ? `<button class="auction-btn">+</button>` : ''}
    `;
    if (status === 'active') {
      item.querySelector('.auction-btn').addEventListener('click', () => handleBid(a));
    }
    list.appendChild(item);
  });
}

async function handleBid(a) {
  const step = Math.max(50, Math.round(a.currentBid * 0.05));
  const amount = a.currentBid + step;
  const { ok, data } = await apiPost('/api/auctions/bid', { userId: USER_ID, auctionId: a.id, amount });
  if (ok) {
    loadAuctions('active');
  } else {
    alert(data.error);
  }
}

// ---------- Profil ----------
function loadProfile() {
  document.getElementById('profileName').textContent = state.user.username || 'Foydalanuvchi';
  document.getElementById('profBalance').textContent = fmt(state.user.balance);
  document.getElementById('profDiamonds').textContent = fmt(state.user.diamonds);
  document.getElementById('refCode').textContent = state.user.referralCode;
}

document.getElementById('copyRefBtn').addEventListener('click', () => {
  navigator.clipboard.writeText(state.user.referralCode);
  alert('Nusxalandi!');
});

init();
