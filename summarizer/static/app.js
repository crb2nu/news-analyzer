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
const sectionChips = $('#sectionChips');
const eventsPanel = $('#eventsPanel');
const eventsList = $('#eventsList');
const feedTab = $('#feedTab');
const eventsTab = $('#eventsTab');
const themeToggle = $('#themeToggle');

const PREF_KEY = 'news-analyzer-feed-v2';
const feedCache = new Map();
const eventsCache = { data: null, lastFetched: null };
let prefs = loadPrefs();
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

function switchView(view) {
  if (view === activeView) return;
  activeView = view;
  savePrefs({ view });
  if (view === 'feed') {
    feedEl.hidden = false;
    eventsPanel.hidden = true;
    feedTab.classList.add('active');
    feedTab.setAttribute('aria-selected', 'true');
    eventsTab.classList.remove('active');
    eventsTab.setAttribute('aria-selected', 'false');
    setStatus('Showing article feed');
  } else {
    feedEl.hidden = true;
    eventsPanel.hidden = false;
    feedTab.classList.remove('active');
    feedTab.setAttribute('aria-selected', 'false');
    eventsTab.classList.add('active');
    eventsTab.setAttribute('aria-selected', 'true');
    loadEvents().catch((err) => setStatus(`Error loading events: ${err.message}`));
  }
}

async function loadEvents(forceRefresh = false) {
  if (!forceRefresh && eventsCache.data) {
    renderEvents(eventsCache.data);
    return;
  }
  setStatus('Loading events…');
  const data = await fetchJSON('/events');
  eventsCache.data = data.events || {};
  eventsCache.lastFetched = Date.now();
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

  for (const item of items) {
    const card = document.createElement('article');
    card.className = 'card';
    card.dataset.articleId = item.id;

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

    const evs = (item.events || []).filter((e) => e && e.start_time);
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
      summary.appendChild(inline);
    }

    card.append(h2, meta, summary);
    feedEl.appendChild(card);
  }
}

function filterItems(items, { section, query, eventsOnly }) {
  return items.filter((item) => {
    const itemSection = normalizeSection(item.section);
    const matchesSection = !section || normalizeSection(section) === itemSection;
    if (!matchesSection) return false;
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
      setStatus(query || section ? 'No articles match the current filters.' : 'No articles available yet.');
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

if (feedTab) feedTab.addEventListener('click', () => switchView('feed'));
if (eventsTab) eventsTab.addEventListener('click', () => switchView('events'));
if (eventsOnlyToggle) eventsOnlyToggle.addEventListener('change', () => loadFeed({ forceRefresh: false }));
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
  if (view && view !== 'feed') p.set('view', view);
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

    // Theme: apply saved or system
    applyTheme(prefs.theme || 'system');

    await loadFeed();
    switchView(activeView);
  } catch (e) {
    setStatus(`Error: ${e.message}`);
    setLastUpdated(null);
  }
})();
