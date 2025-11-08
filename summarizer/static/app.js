const $ = (sel) => document.querySelector(sel);
const feedEl = $('#feed');
const statusEl = $('#status');
const lastUpdatedEl = $('#lastUpdated');
const dateSelect = $('#dateSelect');
const sectionSelect = $('#sectionSelect');
const searchInput = $('#search');
const clearSearchBtn = $('#clearSearchBtn');
const refreshBtn = $('#refreshBtn');
const eventsOnlyToggle = $('#eventsOnlyToggle');
const hideReadToggle = $('#hideReadToggle');
const markAllReadBtn = $('#markAllReadBtn');
const sectionChips = $('#sectionChips');
const feedControls = $('#feedControls');
const eventsPanel = $('#eventsPanel');
const eventsList = $('#eventsList');
// Discover view elements
const discoverTab = $('#discoverTab');
const discoverPanel = $('#discoverPanel');
const discoverSearch = $('#discoverSearch');
const discoverSearchBtn = $('#discoverSearchBtn');
const discoverResults = $('#discoverResults');
const discoverTrending = $('#discoverTrending');
const similarResults = $('#similarResults');
const feedTab = $('#feedTab');
const eventsTab = $('#eventsTab');
const themeToggle = $('#themeToggle');

const PREF_KEY = 'news-analyzer-feed-v2';
const feedCache = new Map();
const eventsCache = { data: null, lastFetched: null };
let prefs = loadPrefs();
const READ_KEY = 'news-analyzer-read-v1';
let readSet = new Set();
try { readSet = new Set(JSON.parse(localStorage.getItem(READ_KEY) || '[]')); } catch {}
let suppressSectionChange = false;
let activeView = 'feed';
let theme = 'system';

// Section normalization (improves categorization UX)
const SECTION_ALIASES = new Map([
  ['obituary', 'Obituaries'],
  ['obituaries', 'Obituaries'],
  ['obits', 'Obituaries'],
  ['sports', 'Sports'],
  ['news', 'News'],
  ['local', 'Local'],
  ['business', 'Business'],
  ['opinion', 'Opinion'],
  ['editorial', 'Opinion'],
  ['police', 'Public Safety'],
  ['police and courts', 'Public Safety'],
  ['crime', 'Public Safety'],
  ['classifieds', 'Classifieds'],
]);

function normalizeSection(s) {
  if (!s) return 'General';
  const key = String(s).trim().toLowerCase();
  return SECTION_ALIASES.get(key) || s.replace(/\s+/g, ' ').trim();
}

function loadPrefs() {
  try {
    const raw = localStorage.getItem(PREF_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (_) {
    return {};
  }
}

function savePrefs(next) {
  prefs = { ...prefs, ...next };
  try {
    localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
  } catch (_) {
    /* ignore storage quota errors */
  }
}

function persistReadSet() {
  try { localStorage.setItem(READ_KEY, JSON.stringify([...readSet])); } catch {}
}

function applyTheme(mode) {
  const root = document.documentElement;
  if (mode === 'light') {
    root.setAttribute('data-theme', 'light');
  } else if (mode === 'dark') {
    root.setAttribute('data-theme', 'dark');
  } else {
    root.removeAttribute('data-theme');
  }
  theme = mode;
  if (themeToggle) themeToggle.textContent = mode === 'dark' ? '🌞' : '🌗';
}

function setStatus(msg = '') {
  statusEl.textContent = msg;
}

function setLastUpdated(ts = null) {
  if (!lastUpdatedEl) return;
  if (!ts) {
    lastUpdatedEl.textContent = '';
    return;
  }
  const dt = new Date(ts);
  lastUpdatedEl.textContent = `Updated ${dt.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`;
}

// --- Tab Controller (robust, ARIA-compliant) ---
const tabs = [feedTab, eventsTab, discoverTab].filter(Boolean);
const panels = new Map([
  ['feed', feedEl],
  ['events', eventsPanel],
  ['discover', discoverPanel],
]);

function setActiveTab(view) {
  if (!panels.has(view)) view = 'feed';
  // Hide/show panels
  panels.forEach((panel, name) => {
    const isActive = name === view;
    panel.hidden = !isActive;
  });
  // Show/hide feed-only controls and chips when switching views
  const isFeed = view === 'feed';
  if (feedControls) feedControls.hidden = !isFeed;
  if (sectionChips) sectionChips.style.display = isFeed ? '' : 'none';
  // Update tab button states
  tabs.forEach((btn) => {
    const target = btn.dataset.target;
    const isActive = target === view;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    btn.tabIndex = isActive ? 0 : -1;
  });
  // Lazy loads per view
  if (view === 'events') {
    loadEvents().catch((err) => setStatus(`Error loading events: ${err.message}`));
  } else if (view === 'discover') {
    if (!discoverTrending.dataset.loaded) {
      loadTrending().catch(() => {});
    }
  }
  // Persist + URL
  activeView = view;
  savePrefs({ view });
  const urlState = readURL();
  updateURL({ ...urlState, view });
}

// Backward-compatible alias
function switchView(view) { setActiveTab(view); }

async function loadEvents(forceRefresh = false) {
  if (!forceRefresh && eventsCache.data) {
    renderEvents(eventsCache.data);
    return;
  }
  setStatus('Loading events…');
  const data = await fetchJSON('/events');
  eventsCache.data = data.events || {};
  eventsCache.lastFetched = Date.now();
  try {
    const total = Object.values(eventsCache.data).reduce((n, arr) => n + (Array.isArray(arr) ? arr.length : 0), 0);
    const badge = document.querySelector('#eventsBadge');
    if (badge) {
      badge.textContent = String(total);
      badge.classList.toggle('hidden', total === 0);
    }
  } catch (_) {}
  renderEvents(eventsCache.data);
  setStatus('Events updated');
}

function renderEvents(eventsByDate) {
  eventsList.innerHTML = '';
  const dates = Object.keys(eventsByDate);
  if (!dates.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'No events detected yet. Check back soon!';
    eventsList.appendChild(empty);
    return;
  }

  dates.sort();
  dates.forEach((dateKey) => {
    const group = document.createElement('section');
    group.className = 'events-group';
    const heading = document.createElement('h3');
    heading.textContent = dateKey === 'unscheduled' ? 'Date to be announced' : fmtDate(dateKey);
    group.appendChild(heading);

    const list = document.createElement('div');
    list.className = 'events-columns';

    eventsByDate[dateKey].forEach((event) => {
      const item = document.createElement('div');
      item.className = 'event-item';

      const title = document.createElement('strong');
      title.textContent = event.title;
      item.appendChild(title);

      const meta = document.createElement('div');
      meta.className = 'event-meta';
      if (event.start_time) meta.appendChild(document.createTextNode(new Date(event.start_time).toLocaleString()));
      if (event.location_name) meta.appendChild(document.createTextNode(event.location_name));
      item.appendChild(meta);

      if (event.description) {
        const desc = document.createElement('p');
        desc.className = 'event-description';
        desc.textContent = event.description;
        item.appendChild(desc);
      }

      if (event.article_id) {
        const link = document.createElement('a');
        link.href = `/articles/${event.article_id}/source`;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = 'View source ↗';
        item.appendChild(link);
      }

      list.appendChild(item);
    });

    group.appendChild(list);
    eventsList.appendChild(group);
  });
}

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// -------- Discover (global search + trending) --------
async function loadTrending(kind = 'section') {
  try {
    const data = await fetchJSON(`/analytics/trending?kind=${encodeURIComponent(kind)}&limit=20`);
    discoverTrending.innerHTML = '';
    if (!Array.isArray(data) || !data.length) {
      discoverTrending.innerHTML = '<div class="muted">No trending items yet.</div>';
    } else {
      data.forEach((row) => {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = `<strong>${row.key}</strong> <span class="muted">score: ${Number(row.score||0).toFixed(2)} z: ${row.zscore==null?'–':Number(row.zscore).toFixed(2)}</span>`;
        div.addEventListener('click', async () => {
          // Quick timeline fetch when clicking a trending item
          try {
            const tl = await fetchJSON(`/analytics/timeline?kind=${encodeURIComponent(kind)}&key=${encodeURIComponent(row.key)}&days=30`);
            // Render a minimal sparkline below
            const values = tl.map(p => Number(p.count||0));
            const svg = sparkline(values, 120, 24);
            div.appendChild(svg);
          } catch {}
        });
        discoverTrending.appendChild(div);
      });
    }
    discoverTrending.dataset.loaded = '1';
  } catch (e) {
    discoverTrending.innerHTML = `<div class="muted">Failed to load trending: ${e.message}</div>`;
  }
}

function sparkline(values, w=120, h=24){
  if (!values.length) return document.createElement('span');
  const max = Math.max(...values); const min = Math.min(...values);
  const dx = w/(values.length-1||1); const rng = (max-min)||1;
  const pts = values.map((v,i)=>`${i*dx},${h - ((v-min)/rng)*h}`).join(' ');
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('width', w); svg.setAttribute('height', h); svg.style.display='block'; svg.style.marginTop='6px';
  const poly = document.createElementNS('http://www.w3.org/2000/svg','polyline');
  poly.setAttribute('fill','none'); poly.setAttribute('stroke','var(--accent)'); poly.setAttribute('stroke-width','2');
  poly.setAttribute('points', pts); svg.appendChild(poly); return svg;
}

async function doGlobalSearch(q){
  if (!q) { discoverResults.innerHTML = '<div class="muted">Enter a query to search all dates.</div>'; return; }
  setStatus('Searching…');
  try{
    const data = await fetchJSON(`/search?q=${encodeURIComponent(q)}&limit=30`);
    renderDiscoverResults(data||[], q);
    setStatus('');
  }catch(e){
    discoverResults.innerHTML = `<div class="muted">Search failed: ${e.message}</div>`;
    setStatus('');
  }
}

function renderDiscoverResults(items, q){
  discoverResults.innerHTML = '';
  if (!items.length){
    discoverResults.innerHTML = `<div class="muted">No results for “${q}”.</div>`; return;
  }
  items.forEach(it => {
    const div = document.createElement('div'); div.className='item';
    const h = document.createElement('div'); h.innerHTML = `<strong>${it.title||'(untitled)'}</strong> <span class="muted">${it.section||''}</span>`; div.appendChild(h);
    if (it.summary){ const p=document.createElement('div'); p.textContent = it.summary.slice(0,220); div.appendChild(p); }
    const row = document.createElement('div'); row.className='meta';
    const open = document.createElement('a'); open.href = it.article_id ? `/articles/${it.article_id}/source` : '#'; open.textContent='Open source'; open.target='_blank'; open.rel='noopener'; row.appendChild(open);
    const sim = document.createElement('button'); sim.textContent='Similar'; sim.className='ghost'; sim.addEventListener('click',()=>showSimilar(it.article_id)); row.appendChild(sim);
    div.appendChild(row);
    discoverResults.appendChild(div);
  });
}

async function showSimilar(id){
  if (!id) return;
  similarResults.innerHTML = '<div class="muted">Loading similar…</div>';
  try{
    const data = await fetchJSON(`/similar?id=${id}&limit=10`);
    similarResults.innerHTML = '';
    data.forEach(it => {
      const div = document.createElement('div'); div.className='item';
      div.innerHTML = `<strong>${it.title||'(untitled)'}</strong> <span class="muted">${it.section||''}</span><div>${(it.summary||'').slice(0,200)}</div>`;
      similarResults.appendChild(div);
    });
  }catch(e){
    similarResults.innerHTML = `<div class="muted">Similar failed: ${e.message}</div>`;
  }
}

function fmtDate(d) {
  const dt = new Date(d);
  return dt.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

function fmtDateTime(d) {
  if (!d) return null;
  const dt = new Date(d);
  return dt.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  });
}

async function loadDates() {
  setStatus('Loading dates…');
  const data = await fetchJSON('/feed/dates');
  dateSelect.innerHTML = '';
  let firstDate = null;
  data.dates.forEach((d, i) => {
    const opt = document.createElement('option');
    opt.value = d.date;
    const summarized = typeof d.summarized === 'number' ? d.summarized : d.total;
    opt.textContent = `${fmtDate(d.date)} (${summarized}/${d.total})`;
    if (i === 0) firstDate = d.date;
    dateSelect.appendChild(opt);
  });

  const initialDate = prefs.date && Array.from(dateSelect.options).some((opt) => opt.value === prefs.date)
    ? prefs.date
    : firstDate;
  if (initialDate) {
    dateSelect.value = initialDate;
    savePrefs({ date: initialDate });
  }
  setStatus('');
}

function render(items, context, query) {
  feedEl.innerHTML = '';

  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = query
      ? `No articles matched “${query}” for ${fmtDate(context.date)}.`
      : `No articles available for ${fmtDate(context.date)} yet.`;
    feedEl.appendChild(empty);
    return;
  }

  const header = document.createElement('div');
  header.className = 'meta feed-meta';
  const plural = items.length === 1 ? '' : 's';
  header.textContent = `${items.length} article${plural} • ${fmtDate(context.date)}`;
  feedEl.appendChild(header);

  // Update Events badge with count from this date
  try {
    const all = items.flatMap((it) => (it.events || []));
    const ids = new Set();
    let count = 0;
    for (const ev of all) {
      if (!ev) continue;
      const key = ev.id || `t:${ev.title || ''}`;
      if (!ids.has(key)) { ids.add(key); count++; }
    }
    const badge = document.querySelector('#eventsBadge');
    if (badge) {
      badge.textContent = String(count);
      badge.classList.toggle('hidden', count === 0);
    }
  } catch (_) {}

  for (const item of items) {
    const card = document.createElement('article');
    card.className = 'card';
    card.tabIndex = 0;
    card.dataset.articleId = item.id;
    if (item.id && readSet.has(item.id)) card.classList.add('read');

    const h2 = document.createElement('h2');
    h2.textContent = item.title;

    const meta = document.createElement('div');
    meta.className = 'meta';
    const metaParts = [];
    if (item.section && item.section !== 'General') metaParts.push(item.section);
    if (item.location_name) metaParts.push(item.location_name);
    if (item.page_number) {
      metaParts.push(`Page ${item.page_number}`);
    } else if (item.source_path) {
      const slug = item.source_path.split('/').pop();
      if (slug) metaParts.push(slug.replace(/_/g, ' '));
    }
    const published = fmtDateTime(item.date_published);
    if (published) metaParts.push(`Published ${published}`);
    if (item.word_count) metaParts.push(`${item.word_count} words`);
    if ((item.events || []).length) metaParts.push(`Events ×${item.events.length}`);
    meta.textContent = metaParts.join(' • ');

    const summary = document.createElement('div');
    summary.className = 'summary';
    if (item.summary) {
      item.summary
        .split(/\n{2,}/)
        .map((p) => p.trim())
        .filter(Boolean)
        .forEach((paragraph) => {
          const p = document.createElement('p');
          p.textContent = paragraph;
          summary.appendChild(p);
        });
    } else {
      const p = document.createElement('p');
      p.className = 'muted';
      p.textContent = 'Summary pending.';
      summary.appendChild(p);
    }

    {
      const kp = document.createElement('a');
      kp.className = 'kp';
      const sourceHref = item.id ? `/articles/${item.id}/source` : (item.url || '#');
      kp.href = sourceHref;
      kp.target = '_blank';
      kp.rel = 'noopener';
      kp.textContent = 'Read full article ↗';
      summary.appendChild(kp);
    }

    // Inline actions
    const actions = document.createElement('div');
    actions.className = 'actions';
    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.className = 'ghost';
    copyBtn.textContent = 'Copy link';
    copyBtn.addEventListener('click', async () => {
      const href = item.id ? `${location.origin}/articles/${item.id}/source` : (item.url || '');
      try { await navigator.clipboard.writeText(href); setStatus('Link copied'); } catch { setStatus('Copy failed'); }
    });
    const markBtn = document.createElement('button');
    markBtn.type = 'button';
    markBtn.className = 'ghost';
    const updateMark = () => markBtn.textContent = (item.id && readSet.has(item.id)) ? 'Mark unread' : 'Mark read';
    updateMark();
    markBtn.addEventListener('click', () => {
      if (!item.id) return;
      if (readSet.has(item.id)) readSet.delete(item.id); else readSet.add(item.id);
      persistReadSet();
      card.classList.toggle('read');
      updateMark();
    });
    actions.append(copyBtn, markBtn);
    summary.appendChild(actions);

    const evs = (item.events || []).filter((e) => e && (e.start_time || e.title));
    if (evs.length) {
      const inline = document.createElement('div');
      inline.className = 'event-inline';
      const label = document.createElement('strong');
      label.textContent = 'Events';
      inline.appendChild(label);
      const list = document.createElement('ul');
      evs.slice(0, 3).forEach((ev) => {
        const li = document.createElement('li');
        const parts = [];
        if (ev.start_time) parts.push(new Date(ev.start_time).toLocaleString());
        if (ev.location_name) parts.push(ev.location_name);
        li.textContent = parts.length ? parts.join(' • ') : ev.title;
        list.appendChild(li);
      });
      inline.appendChild(list);
      const jump = document.createElement('a');
      jump.href = '#eventsPanel';
      jump.className = 'kp';
      jump.textContent = 'Jump to Events ↴';
      jump.addEventListener('click', (e) => {
        e.preventDefault();
        switchView('events');
        document.getElementById('eventsPanel')?.scrollIntoView({ behavior: 'smooth' });
      });
      inline.appendChild(jump);
      summary.appendChild(inline);
    }

    card.append(h2, meta, summary);
    feedEl.appendChild(card);
  }
}

function filterItems(items, { section, query, eventsOnly }) {
  const hideRead = !!(hideReadToggle && hideReadToggle.checked);
  return items.filter((item) => {
    const itemSection = normalizeSection(item.section);
    const matchesSection = !section || normalizeSection(section) === itemSection;
    if (!matchesSection) return false;
    if (hideRead && item.id && readSet.has(item.id)) return false;
    if (eventsOnly) {
      const evs = (item.events || []).filter((e) => e && (e.start_time || e.title));
      if (!evs.length) return false;
    }
    if (!query) return true;
    const haystack = `${item.title}\n${item.summary}\n${item.location_name || ''}`.toLowerCase();
    return haystack.includes(query.toLowerCase());
  });
}

function updateSectionOptions(items) {
  const counts = new Map();
  items.forEach((item) => {
    const key = normalizeSection(item.section || 'General');
    counts.set(key, (counts.get(key) || 0) + 1);
  });

  const preferred = prefs.section || sectionSelect.value;
  suppressSectionChange = true;
  sectionSelect.innerHTML = '';

  const allOpt = document.createElement('option');
  allOpt.value = '';
  allOpt.textContent = `All sections (${items.length})`;
  sectionSelect.appendChild(allOpt);

  const sorted = [...counts.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
  sorted.forEach(([name, count]) => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = `${name} (${count})`;
      sectionSelect.appendChild(opt);
    });

  if (preferred && counts.has(preferred)) {
    sectionSelect.value = preferred;
  } else {
    sectionSelect.value = '';
  }
  suppressSectionChange = false;
  savePrefs({ section: sectionSelect.value });

  // Render section chips as quick filters (top 8 by count)
  if (sectionChips) {
    sectionChips.innerHTML = '';
    const top = sorted.sort((a, b) => b[1] - a[1]).slice(0, 8);
    top.forEach(([name, count]) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip' + (sectionSelect.value === name ? ' active' : '');
      chip.textContent = `${name} (${count})`;
      chip.setAttribute('data-section', name);
      chip.addEventListener('click', () => {
        sectionSelect.value = name;
        savePrefs({ section: name });
        loadFeed({ forceRefresh: false });
      });
      sectionChips.appendChild(chip);
    });
  }
}

async function fetchDateFeed(date, { forceRefresh = false } = {}) {
  if (!forceRefresh && feedCache.has(date)) {
    return feedCache.get(date);
  }
  const params = new URLSearchParams({ date_str: date, limit: '200' });
  const data = await fetchJSON(`/feed?${params.toString()}`);
  feedCache.set(date, data);
  return data;
}

async function loadFeed({ forceRefresh = false } = {}) {
  const date = dateSelect.value || prefs.date;
  if (!date) return;

  const query = searchInput.value.trim();
  const section = sectionSelect.value;
  const eventsOnly = !!(eventsOnlyToggle && eventsOnlyToggle.checked);
  const isCached = !forceRefresh && feedCache.has(date);
  setStatus(isCached ? 'Applying filters…' : 'Loading feed…');
  try {
    const data = await fetchDateFeed(date, { forceRefresh });
    updateSectionOptions(data.items ?? []);

    const filtered = filterItems(data.items ?? [], { section, query, eventsOnly });
    render(filtered, { date: data.date || date }, query);

    const totalCount = data.items ? data.items.length : 0;
    if (!filtered.length) {
      if (eventsOnly) {
        setStatus('No articles with events. Showing Events panel…');
        switchView('events');
        await loadEvents();
      } else {
        setStatus(query || section ? 'No articles match the current filters.' : 'No articles available yet.');
      }
    } else {
      const base = `Showing ${filtered.length}${filtered.length !== totalCount ? ` of ${totalCount}` : ''} articles`;
      setStatus(base);
    }
    setLastUpdated(Date.now());
    savePrefs({ date, section, search: query, eventsOnly });
    updateURL({ date, section, q: query, view: activeView, eventsOnly });
  } catch (e) {
    setStatus(`Error loading feed: ${e.message}`);
    setLastUpdated(null);
  }
}

refreshBtn.addEventListener('click', () => loadFeed({ forceRefresh: true }));
dateSelect.addEventListener('change', () => {
  savePrefs({ date: dateSelect.value });
  loadFeed({ forceRefresh: true });
});
sectionSelect.addEventListener('change', () => {
  if (suppressSectionChange) return;
  savePrefs({ section: sectionSelect.value });
  loadFeed({ forceRefresh: false });
});
searchInput.addEventListener('input', () => {
  savePrefs({ search: searchInput.value.trim() });
  loadFeed({ forceRefresh: false });
});
searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    loadFeed({ forceRefresh: false });
  }
});
clearSearchBtn.addEventListener('click', () => {
  if (!searchInput.value) return;
  searchInput.value = '';
  savePrefs({ search: '' });
  loadFeed({ forceRefresh: false });
  searchInput.focus();
});

// Delegate clicks to the tablist for resilience
const tablist = document.querySelector('.view-toggle[role="tablist"]');
if (tablist) {
  tablist.addEventListener('click', (e) => {
    const btn = e.target.closest('button[role="tab"]');
    if (!btn) return;
    const target = btn.dataset.target;
    setActiveTab(target);
  });
  // Keyboard navigation (ArrowLeft/ArrowRight/Home/End)
  tablist.addEventListener('keydown', (e) => {
    const idx = tabs.indexOf(document.activeElement);
    if (idx === -1) return;
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      const next = tabs[(idx + 1) % tabs.length];
      next.focus(); setActiveTab(next.dataset.target);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      const prev = tabs[(idx - 1 + tabs.length) % tabs.length];
      prev.focus(); setActiveTab(prev.dataset.target);
    } else if (e.key === 'Home') {
      e.preventDefault(); tabs[0].focus(); setActiveTab(tabs[0].dataset.target);
    } else if (e.key === 'End') {
      e.preventDefault(); const last = tabs[tabs.length-1]; last.focus(); setActiveTab(last.dataset.target);
    }
  });
}
if (eventsOnlyToggle) eventsOnlyToggle.addEventListener('change', () => loadFeed({ forceRefresh: false }));
if (eventsOnlyToggle) eventsOnlyToggle.addEventListener('change', () => {
  savePrefs({ eventsOnly: !!eventsOnlyToggle.checked });
  const urlState = readURL();
  updateURL({ ...urlState, eventsOnly: eventsOnlyToggle.checked });
  loadFeed({ forceRefresh: false });
});
if (hideReadToggle) hideReadToggle.addEventListener('change', () => {
  savePrefs({ hideRead: !!hideReadToggle.checked });
  loadFeed({ forceRefresh: false });
});
if (markAllReadBtn) markAllReadBtn.addEventListener('click', () => {
  const date = dateSelect.value || prefs.date;
  const items = (feedCache.get(date) || {}).items || [];
  items.forEach((it) => { if (it.id) readSet.add(it.id); });
  persistReadSet();
  loadFeed({ forceRefresh: false });
});
if (themeToggle) themeToggle.addEventListener('click', () => {
  const next = theme === 'dark' ? 'light' : theme === 'light' ? 'system' : 'dark';
  applyTheme(next);
  savePrefs({ theme: next });
});

// URL state helpers for shareable filters
function readURL() {
  const p = new URLSearchParams(location.search);
  return {
    date: p.get('date') || undefined,
    section: p.get('section') || undefined,
    q: p.get('q') || undefined,
    view: p.get('view') || undefined,
    eventsOnly: p.get('eventsOnly') === '1' ? true : undefined,
  };
}

function updateURL({ date, section, q, view, eventsOnly }) {
  const p = new URLSearchParams();
  if (date) p.set('date', date);
  if (section) p.set('section', section);
  if (q) p.set('q', q);
  if (view) p.set('view', view);
  if (eventsOnly) p.set('eventsOnly', '1');
  const qs = p.toString();
  const next = qs ? `?${qs}` : location.pathname;
  history.replaceState(null, '', next);
}

(async () => {
  try {
    const urlState = readURL();
    await loadDates();

    // Initialize from URL, then prefs
    const initDate = urlState.date || prefs.date;
    if (initDate) dateSelect.value = initDate;

    const initSection = urlState.section || prefs.section;
    if (initSection) sectionSelect.value = initSection;

    const initSearch = urlState.q || prefs.search;
    if (initSearch) searchInput.value = initSearch;

    const initView = urlState.view || prefs.view;
    if (initView) activeView = initView;

  const initEventsOnly = urlState.eventsOnly ?? prefs.eventsOnly;
  if (eventsOnlyToggle && typeof initEventsOnly === 'boolean') {
    eventsOnlyToggle.checked = initEventsOnly;
  }
  if (hideReadToggle && typeof prefs.hideRead === 'boolean') {
    hideReadToggle.checked = !!prefs.hideRead;
  }

    // Theme: apply saved or system
    applyTheme(prefs.theme || 'system');

    // Ensure tabs start in a consistent state before data (also hides feed-only controls for other views)
    setActiveTab(activeView || 'feed');
    await loadFeed();
    // Discover listeners
    if (discoverSearchBtn) discoverSearchBtn.addEventListener('click', ()=> doGlobalSearch(discoverSearch.value.trim()));
    if (discoverSearch) discoverSearch.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); doGlobalSearch(discoverSearch.value.trim()); }});
  } catch (e) {
    setStatus(`Error: ${e.message}`);
    setLastUpdated(null);
  }
})();

// Keyboard navigation: j/k to move, Enter to open article
document.addEventListener('keydown', (e) => {
  const cards = Array.from(document.querySelectorAll('.feed .card'));
  if (!cards.length) return;
  const active = document.activeElement?.closest?.('.card');
  const idx = active ? cards.indexOf(active) : -1;
  if (e.key === 'j') {
    e.preventDefault();
    const next = cards[Math.min(idx + 1, cards.length - 1)];
    next?.focus({ preventScroll: false });
    next?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } else if (e.key === 'k') {
    e.preventDefault();
    const prev = cards[Math.max(idx - 1, 0)];
    prev?.focus({ preventScroll: false });
    prev?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } else if (e.key === 'Enter' && active) {
    const link = active.querySelector('.summary .kp[href]');
    if (link) window.open(link.href, '_blank', 'noopener');
  }
});
