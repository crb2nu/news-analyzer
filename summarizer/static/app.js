const $ = (sel) => document.querySelector(sel);
const feedEl = $('#feed');
const statusEl = $('#status');
const dateSelect = $('#dateSelect');
const sectionSelect = $('#sectionSelect');
const searchInput = $('#search');
const refreshBtn = $('#refreshBtn');

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function fmtDate(d) {
  const dt = new Date(d);
  return dt.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

async function loadDates() {
  statusEl.textContent = 'Loading dates…';
  const data = await fetchJSON('/feed/dates');
  dateSelect.innerHTML = '';
  data.dates.forEach((d, i) => {
    const opt = document.createElement('option');
    opt.value = d.date;
    opt.textContent = `${fmtDate(d.date)} (${d.summarized ?? d.total})`;
    if (i === 0) opt.selected = true;
    dateSelect.appendChild(opt);
  });
  statusEl.textContent = '';
}

function render(items, context) {
  feedEl.innerHTML = '';
  const header = document.createElement('div');
  header.className = 'meta';
  header.textContent = `${items.length} articles • ${fmtDate(context.date)}`;
  feedEl.appendChild(header);

  for (const item of items) {
    const card = document.createElement('article');
    card.className = 'card';
    const h2 = document.createElement('h2');
    h2.textContent = item.title;
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = [item.section, item.date_published?.slice(0, 10)].filter(Boolean).join(' • ');
    const summary = document.createElement('div');
    summary.className = 'summary';
    summary.textContent = item.summary || '(No summary yet)';
    if (item.url) {
      const kp = document.createElement('a');
      kp.className = 'kp';
      kp.href = item.url;
      kp.target = '_blank';
      kp.rel = 'noopener';
      kp.textContent = 'Read full article ↗';
      summary.appendChild(kp);
    }
    card.append(h2, meta, summary);
    feedEl.appendChild(card);
  }
}

async function loadFeed() {
  const date = dateSelect.value;
  const section = sectionSelect.value;
  const q = searchInput.value.trim();
  const params = new URLSearchParams({ date_str: date });
  if (section) params.set('section', section);
  if (q) params.set('q', q);
  statusEl.textContent = 'Loading feed…';
  try {
    const data = await fetchJSON(`/feed?${params.toString()}`);
    render(data.items, { date: data.date });
    statusEl.textContent = '';
  } catch (e) {
    statusEl.textContent = `Error loading feed: ${e.message}`;
  }
}

refreshBtn.addEventListener('click', loadFeed);
dateSelect.addEventListener('change', loadFeed);
sectionSelect.addEventListener('change', loadFeed);
searchInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') loadFeed(); });

(async () => {
  try {
    await loadDates();
    await loadFeed();
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
})();

