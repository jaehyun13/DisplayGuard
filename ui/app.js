/* Spectra Display Studio — window UI. Talks to the local app over /api (see server.py). */
(() => {
'use strict';

// ───────────────────────── session / API ─────────────────────────
const m = /[#&]t=([^&]+)/.exec(location.hash);
if (m) { try { sessionStorage.setItem('spectra-token', m[1]); } catch (e) {} history.replaceState(null, '', location.pathname); }
let TOKEN = m ? m[1] : '';
if (!TOKEN) { try { TOKEN = sessionStorage.getItem('spectra-token') || ''; } catch (e) {} }

async function api(path, body) {
  const opt = { headers: { 'X-Spectra-Token': TOKEN } };
  if (body !== undefined) { opt.method = 'POST'; opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
  const res = await fetch('/api/' + path, opt);
  let data = null;
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error((data && data.error) || ('HTTP ' + res.status));
  return data;
}

// ───────────────────────── state ─────────────────────────
let S = null;                 // last server state
let logs = [], logSeq = 0, sig = '';
const ui = {
  page: 'arrange', sel: null, snap: true, draft: null, drag: null, busy: false, renderQueued: false,
  modes: {}, modePick: {}, ddc: {}, hw: null, gpu: [], gpuHist: {}, gpuTimer: null, showLog: false,
  localCountdown: null, view: 'mm',
};
try { ui.view = localStorage.getItem('spectra-view') === 'px' ? 'px' : 'mm'; } catch (e) {}
const lang = () => (S && S.app.language === 'ko') ? 'ko' : 'en';
const L = (ko, en) => lang() === 'ko' ? ko : en;
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ms = (name, cls = '') => `<span class="ms ${cls}">${name}</span>`;
const $ = id => document.getElementById(id);
const mon = name => S.monitors.find(x => x.name === name);
const selMon = () => mon(ui.sel) || S.monitors.find(x => x.primary) || S.monitors[0];
const LAYOUT_KEYS = ['name', 'primary', 'x', 'y', 'w', 'h', 'freq', 'rot'];
const pickLayout = list => list.map(c => { const o = {}; LAYOUT_KEYS.forEach(k => o[k] = c[k]); return o; });
const ROT = () => [L('가로', 'Landscape'), L('세로', 'Portrait'), L('가로 (뒤집힘)', 'Landscape (flipped)'), L('세로 (뒤집힘)', 'Portrait (flipped)')];
const gb = b => (b / 1073741824).toFixed(1);

function toast(text, isErr) {
  const el = $('toast');
  el.textContent = text; el.className = 'toast show' + (isErr ? ' err' : '');
  clearTimeout(toast.t); toast.t = setTimeout(() => el.className = 'toast', isErr ? 5000 : 2200);
}
async function call(path, body, okText) {
  try { const r = await api(path, body); if (r && r.monitors) accept(r); if (okText) toast(okText); return r; }
  catch (e) { toast(e.message, true); return null; }
}

function accept(state) {
  S = state;
  if (state.log && state.log.length) { logs = logs.concat(state.log).slice(-200); logSeq = logs[logs.length - 1].seq; }
  document.documentElement.lang = lang();
  if (!ui.sel || !mon(ui.sel)) ui.sel = (S.monitors.find(x => x.primary) || S.monitors[0] || {}).name || null;
  const layoutSig = JSON.stringify(pickLayout(S.monitors));
  if (accept.layoutSig !== layoutSig) { accept.layoutSig = layoutSig; ui.draft = null; ui.modes = {}; ui.modePick = {}; }
  const g = Object.assign({}, S.guard, { pending: !!S.guard.pending });
  const next = JSON.stringify([S.monitors, S.profiles, g, S.zones, S.settings, S.app.language, logSeq]);
  if (next !== sig) { sig = next; queueRender(); }
  renderModal();
}
function queueRender() { if (ui.busy || ui.drag) { ui.renderQueued = true; return; } render(); }
async function poll() {
  try { accept(await api('state?since=' + logSeq)); } catch (e) { /* app closed or restarting */ }
  setTimeout(poll, S && S.guard.pending ? 700 : 2000);
}

// ───────────────────────── chrome ─────────────────────────
const PAGES = () => [
  ['arrange', 'dashboard', L('디스플레이 배치', 'Arrangement')],
  ['mode', 'speed', L('해상도 및 화면 주사율', 'Resolution & refresh')],
  ['color', 'tonality', L('컬러 및 HDR', 'Colour & HDR')],
  ['zones', 'grid_view', L('가상 작업 공간', 'Window zones')],
  ['hardware', 'memory', L('하드웨어 및 GPU', 'Hardware & GPU')],
  ['settings', 'settings', L('설정', 'Settings')],
];

function renderChrome() {
  const active = S.profiles.find(p => p.active);
  $('topbar').innerHTML = `
    <div class="row gap-md brand">
      ${ms('monitor', 'c-primary')}
      <span class="name">Spectra <span class="thin">Display Studio</span></span>
      <span class="chip caps">v${esc(S.app.version)}</span>
      ${S.app.demo ? `<span class="chip warn caps">DEMO</span>` : ''}
    </div>
    <div class="presetbar">
      <span class="lbl dim" style="padding:0 4px">PRESET</span>
      ${S.profiles.length ? S.profiles.slice(0, 5).map(p => `
        <button class="btn sm ${p.active ? '' : 'ghost'}" data-act="profile-apply" data-name="${esc(p.name)}">
          ${ms('view_quilt', p.active ? 'c-tertiary' : '')}<span class="truncate" style="max-width:130px">${esc(p.name)}</span></button>`).join('')
        : `<span class="lbl dim" style="padding:0 8px">${L('저장된 프로필 없음', 'No saved profiles')}</span>`}
    </div>
    <div class="row">
      <button class="btn" data-act="detect">${ms('sync', 'c-primary')}${L('디스플레이 감지', 'Detect displays')}</button>
      <button class="btn accent" data-act="identify">${ms('tag')}${L('모니터 식별', 'Identify')}</button>
    </div>`;
  const total = S.monitors.reduce((a, x) => a + x.w * x.h, 0);
  const adapters = [...new Set(S.monitors.map(x => x.adapter).filter(Boolean))];
  const g = S.guard;
  $('sidebar').innerHTML = `
    <div class="col gap-xs">
      <div class="lbl dim caps nav-title" style="padding:4px 20px">Workspace Engine</div>
      <nav class="nav">${PAGES().map(([id, icon, text]) => `
        <a class="${ui.page === id ? 'active' : ''}" data-act="nav" data-page="${id}">${ms(icon)}<span class="t">${text}</span></a>`).join('')}</nav>
    </div>
    <div class="side-card" style="padding:0 12px">
      <div class="inset col gap-xs" style="padding:8px">
        <div class="row between lbl muted"><span class="caps">${L('배치 보호', 'Layout guard')}</span>
          <span class="row gap-xs ${g.enabled ? 'c-tertiary' : 'c-error'}"><span class="dot ${g.enabled ? 'ok pulse' : 'err'}" style="width:6px;height:6px"></span>${g.enabled ? L('활성', 'Active') : L('꺼짐', 'Off')}</span></div>
        <div class="lbl-md truncate">${esc(adapters.join(' · ') || '—')}</div>
        <div class="lbl dim truncate">${S.monitors.length} ${L('디스플레이', 'displays')} · ${(total / 1e6).toFixed(1)}M px${active ? ' · ' + esc(active.name) : ''}</div>
      </div>
    </div>`;
}

function render() {
  if (!S) return;
  ui.renderQueued = false;
  renderChrome();
  const pages = { arrange: pageArrange, mode: pageMode, color: pageColor, zones: pageZones, hardware: pageHardware, settings: pageSettings };
  const scroll = window.scrollY;
  $('main').innerHTML = `<div class="page">${S.app.demo ? `<div class="demo-banner body-sm">${L('데모 모드 — 실제 하드웨어가 아닌 가상 모니터로 동작합니다. 여기서 바꾸는 값은 실제 화면에 적용되지 않습니다.', 'Demo mode — running against made-up monitors. Nothing here changes your real displays.')}</div>` : ''}${S.monitors.length ? pages[ui.page]() : `<div class="card">${L('활성 디스플레이를 찾을 수 없습니다.', 'No active displays found.')}</div>`}</div>`;
  window.scrollTo(0, scroll);
  renderActionBar();
  if (ui.page === 'hardware') startGpu(); else stopGpu();
  if (ui.page === 'arrange') layoutStage();
}

const pageHead = (icon, title, sub, right = '') => `
  <div class="card"><div class="card-head">
    <div class="row gap-md"><div class="iconbox">${ms(icon, '')}</div>
      <div class="col" style="gap:2px"><div class="h-sm">${title}</div><div class="lbl dim">${sub}</div></div></div>
    <div class="row wrap">${right}</div></div></div>`;

const monTabs = () => `<div class="grid g3">${S.monitors.map(x => `
  <button class="montab ${x.name === selMon().name ? 'on' : ''}" data-act="select" data-name="${esc(x.name)}">
    <div class="row between top" style="position:relative">
      <div class="row"><span class="num">${x.number}</span>
        <div class="col" style="gap:0"><div class="h-sm truncate">${esc(x.label)}</div><div class="body-sm muted">${esc(x.short)}${x.connector ? ' · ' + esc(x.connector) : ''}</div></div></div>
      ${x.primary ? `<span class="chip pri">${L('주 디스플레이', 'Main')}</span>` : `<span class="chip">${ROT()[x.rot]}</span>`}
    </div>
    <div style="position:relative"><div class="lbl-lg bold ${x.name === selMon().name ? 'c-primary' : ''}">${x.w} × ${x.h}</div>
      <div class="lbl ${x.name === selMon().name ? 'c-tertiary' : 'dim'}">${x.freq > 1 ? x.freq + ' Hz' : ''}${x.hdr && x.hdr.enabled ? ' · HDR' : ''}</div></div>
  </button>`).join('')}</div>`;

const logBox = () => `<div class="log">${logs.length ? logs.slice(-80).map(e => `<div><span>${esc(e.time)}</span>${esc(e.text)}</div>`).join('') : `<span>—</span>`}</div>`;
const sw = (act, on, extra = '', disabled = false) => `<label class="switch"><input type="checkbox" data-in="${act}" ${extra} ${on ? 'checked' : ''} ${disabled ? 'disabled' : ''}><i></i></label>`;

// ───────────────────────── arrangement ─────────────────────────
function draft() { if (!ui.draft) ui.draft = pickLayout(S.monitors); return ui.draft; }
const draftDirty = () => !!ui.draft && JSON.stringify(ui.draft) !== JSON.stringify(pickLayout(S.monitors));
const overlap = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

/* Windows needs displays to touch and never overlap: put `d` at the valid spot nearest to where it is. */
function settle(d, others, snap) {
  if (!others.length) return true;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const snapTo = (v, targets, thr) => { let best = v, bd = thr; targets.forEach(tg => { const dd = Math.abs(v - tg); if (dd <= bd) { bd = dd; best = tg; } }); return best; };
  let best = null;
  for (const o of others) {
    const thrY = snap ? o.h * 0.08 : 0, thrX = snap ? o.w * 0.08 : 0;
    const ySlide = snapTo(clamp(d.y, o.y - d.h + 1, o.y + o.h - 1), [o.y, o.y + o.h - d.h, o.y + (o.h - d.h) / 2], thrY);
    const xSlide = snapTo(clamp(d.x, o.x - d.w + 1, o.x + o.w - 1), [o.x, o.x + o.w - d.w, o.x + (o.w - d.w) / 2], thrX);
    const cands = [{ x: o.x + o.w, y: ySlide }, { x: o.x - d.w, y: ySlide }, { x: xSlide, y: o.y + o.h }, { x: xSlide, y: o.y - d.h }];
    for (const c of cands) {
      const t = { x: Math.round(c.x), y: Math.round(c.y), w: d.w, h: d.h };
      if (others.some(p => overlap(t, p))) continue;
      const dist = (t.x - d.x) ** 2 + (t.y - d.y) ** 2;
      if (!best || dist < best.dist) best = { x: t.x, y: t.y, dist };
    }
  }
  if (!best) return false;
  d.x = best.x; d.y = best.y; return true;
}
/* After a size/orientation change: keep `anchor` put and re-seat everything else around it. */
function repack(list, anchorName) {
  const anchor = list.find(c => c.name === anchorName) || list[0];
  const placed = [anchor];
  list.filter(c => c !== anchor)
    .sort((a, b) => ((a.x - anchor.x) ** 2 + (a.y - anchor.y) ** 2) - ((b.x - anchor.x) ** 2 + (b.y - anchor.y) ** 2))
    .forEach(c => { settle(c, placed, false); placed.push(c); });
  originToPrimary(list);
}
function originToPrimary(list) {
  const p = list.find(c => c.primary) || list[0];
  const ox = p.x, oy = p.y;
  list.forEach(c => { c.x -= ox; c.y -= oy; });
}

/* Real-world rectangles (mm) derived from the pixel layout. Mirrors physical_layout() in core.py. */
function touchSide(a, b) {
  const v = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y), hz = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  if (v > 0) { if (b.x === a.x + a.w) return 'right'; if (b.x + b.w === a.x) return 'left'; }
  if (hz > 0) { if (b.y === a.y + a.h) return 'below'; if (b.y + b.h === a.y) return 'above'; }
  return null;
}
function mmOf(c) {
  const x = mon(c.name), cur = x.mm, turned = (x.w > x.h) !== (c.w > c.h);   // draft may be rotated
  return turned ? [cur[1], cur[0]] : cur;
}
function physLayout(list) {
  const primary = list.find(c => c.primary) || list[0], out = {}, mm = {};
  list.forEach(c => mm[c.name] = mmOf(c));
  out[primary.name] = { x: 0, y: 0, w: mm[primary.name][0], h: mm[primary.name][1] };
  const queue = [primary];
  while (queue.length) {
    const a = queue.shift(), A = out[a.name];
    for (const b of list) {
      if (out[b.name]) continue;
      const side = touchSide(a, b); if (!side) continue;
      const [bw, bh] = mm[b.name]; let x, y;
      if (side === 'right' || side === 'left') { x = side === 'right' ? A.x + A.w : A.x - bw; y = A.y + (b.y + b.h / 2 - a.y) / a.h * A.h - bh / 2; }
      else { y = side === 'below' ? A.y + A.h : A.y - bh; x = A.x + (b.x + b.w / 2 - a.x) / a.w * A.w - bw / 2; }
      out[b.name] = { x, y, w: bw, h: bh }; queue.push(b);
    }
  }
  const k = mm[primary.name][0] / primary.w;
  list.forEach(b => { if (!out[b.name]) out[b.name] = { x: (b.x - primary.x) * k, y: (b.y - primary.y) * k, w: mm[b.name][0], h: mm[b.name][1] }; });
  return out;
}
/* The rectangles the stage draws: pixels, or real-world millimetres. */
function viewRects(list) {
  if (ui.view !== 'mm') return list.map(c => ({ name: c.name, x: c.x, y: c.y, w: c.w, h: c.h }));
  const ph = physLayout(list);
  return list.map(c => Object.assign({ name: c.name }, ph[c.name]));
}
function stageGeometry(rects, el) {
  const minX = Math.min(...rects.map(c => c.x)), minY = Math.min(...rects.map(c => c.y));
  const maxX = Math.max(...rects.map(c => c.x + c.w)), maxY = Math.max(...rects.map(c => c.y + c.h));
  const W = el.clientWidth, H = el.clientHeight;
  const k = Math.min(W * 0.86 / (maxX - minX), H * 0.74 / (maxY - minY));
  return { k, ox: (W - (maxX - minX) * k) / 2 - minX * k, oy: (H - (maxY - minY) * k) / 2 - minY * k - 10 };
}
/* Shared edges = where the pointer can cross from one monitor to the next. */
function crossings(rects) {
  const eps = ui.view === 'mm' ? 1 : 0, out = [];
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
    const a = rects[i], b = rects[j];
    const v0 = Math.max(a.y, b.y), v1 = Math.min(a.y + a.h, b.y + b.h), h0 = Math.max(a.x, b.x), h1 = Math.min(a.x + a.w, b.x + b.w);
    if (v1 - v0 > eps) { if (Math.abs(b.x - (a.x + a.w)) <= eps) out.push({ x: b.x, y: v0, len: v1 - v0, vert: true }); else if (Math.abs(a.x - (b.x + b.w)) <= eps) out.push({ x: a.x, y: v0, len: v1 - v0, vert: true }); }
    if (h1 - h0 > eps) { if (Math.abs(b.y - (a.y + a.h)) <= eps) out.push({ x: h0, y: b.y, len: h1 - h0, vert: false }); else if (Math.abs(a.y - (b.y + b.h)) <= eps) out.push({ x: h0, y: a.y, len: h1 - h0, vert: false }); }
  }
  return out;
}
function layoutStage() {
  const el = $('stage'); if (!el) return;
  const list = draft();
  const rects = ui.drag ? ui.drag.rects : viewRects(list);
  const geo = ui.drag ? ui.drag.geo : stageGeometry(rects, el);
  rects.forEach(r => {
    const c = list.find(x => x.name === r.name), node = el.querySelector(`[data-mon="${CSS.escape(r.name)}"]`); if (!node || !c) return;
    node.style.left = (r.x * geo.k + geo.ox + 2) + 'px'; node.style.top = (r.y * geo.k + geo.oy + 2) + 'px';
    node.style.width = (r.w * geo.k - 4) + 'px'; node.style.height = (r.h * geo.k - 4) + 'px';
    node.classList.toggle('narrow', r.w * geo.k < 150);
    const pos = node.querySelector('[data-pos]'); if (pos) pos.textContent = `X: ${Math.round(c.x)}, Y: ${Math.round(c.y)}`;
  });
  const layer = $('cross');
  if (layer) layer.innerHTML = ui.drag && ui.drag.moved ? '' : crossings(rects).map(s => s.vert
    ? `<i style="left:${s.x * geo.k + geo.ox - 2}px;top:${s.y * geo.k + geo.oy + 6}px;width:4px;height:${Math.max(0, s.len * geo.k - 12)}px"></i>`
    : `<i style="left:${s.x * geo.k + geo.ox + 6}px;top:${s.y * geo.k + geo.oy - 2}px;height:4px;width:${Math.max(0, s.len * geo.k - 12)}px"></i>`).join('');
}

function pageArrange() {
  const list = draft(), g = S.guard, sel = list.find(c => c.name === ui.sel) || list[0], info = mon(sel.name) || {};
  const dirty = draftDirty();
  const guardChip = !g.enabled ? `<span class="chip err">${L('보호 꺼짐', 'Guard off')}</span>`
    : g.match ? `<span class="chip ok"><span class="dot ok" style="width:6px;height:6px"></span>${L('저장된 배치와 일치', 'Matches saved layout')}</span>`
      : `<span class="chip warn">${L('저장된 배치와 다름', 'Differs from saved layout')}</span>`;
  const bw = Math.max(...list.map(c => c.x + c.w)) - Math.min(...list.map(c => c.x));
  const bh = Math.max(...list.map(c => c.y + c.h)) - Math.min(...list.map(c => c.y));
  return `
  ${pageHead('view_quilt', `${L('디스플레이 배치 캔버스', 'Display arrangement')} ${guardChip}`,
    `${list.length}${L('개 디스플레이 연결됨', ' displays connected')} · ${[...new Set(S.monitors.map(x => x.connector).filter(Boolean))].join(', ')}`,
    `<label class="row inset" style="cursor:pointer;padding:6px 8px">${ms('drag_pan', 'c-primary')}<span class="lbl-md muted">${L('자석 스냅 (Edge Snap)', 'Edge snap')}</span>${sw('snap', ui.snap)}</label>`)}
  <div class="split">
    <div class="col">
      <div class="row between" style="padding:0 4px">
        <div class="row gap-xs"><span class="lbl dim caps">Spatial Staging Viewport</span><span class="lbl dim">•</span>
          <span class="lbl muted">${L('가상 데스크톱', 'Virtual desktop')} ${bw} × ${bh}px</span></div>
        <div class="row">
        <div class="seg" style="grid-template-columns:repeat(2,auto);padding:2px">
          <button class="${ui.view === 'mm' ? 'on' : ''}" data-act="view" data-view="mm" style="flex-direction:row;padding:4px 10px">${L('실제 크기 기준', 'Real size')}</button>
          <button class="${ui.view === 'px' ? 'on' : ''}" data-act="view" data-view="px" style="flex-direction:row;padding:4px 10px">${L('해상도 기준', 'By resolution')}</button>
        </div>
        <div class="row gap-xs inset" style="padding:2px">
          ${[['top', 'align_vertical_top', L('상단 맞춤', 'Align top')], ['center', 'align_vertical_center', L('중앙 맞춤', 'Align centre')], ['bottom', 'align_vertical_bottom', L('하단 맞춤', 'Align bottom')]]
            .map(([a, i, tt]) => `<button class="btn sm ghost" title="${tt}" data-act="align" data-how="${a}" ${sel.primary ? 'disabled' : ''}>${ms(i)}</button>`).join('')}
        </div>
        </div>
      </div>
      <div class="stage" id="stage">
        ${list.map(c => { const x = mon(c.name) || {}; return `
          <div class="mon ${c.name === sel.name ? 'sel' : ''}" data-mon="${esc(c.name)}">
            <div class="row between"><span class="row gap-xs">${c.primary ? `<span class="chip pri">${x.number}</span><span class="lbl c-primary bold row gap-xs">${ms('star', '')}${L('주 모니터', 'Main')}</span>` : `<span class="lbl dim">${esc(x.short || '')}</span>`}</span>
              <span class="chip">${ROT()[c.rot]}</span></div>
            <div class="col" style="align-items:center;gap:2px"><span class="big ${c.name === sel.name ? '' : 'muted'}">${x.number || ''}</span>
              ${x.inches ? `<span class="lbl-md ${c.primary ? 'c-primary' : 'muted'}">${x.inches}″</span>` : ''}
              <span class="lbl ${c.primary ? 'c-primary' : 'dim'}" style="white-space:nowrap">${c.w} × ${c.h}</span></div>
            <div class="row between lbl muted"><span class="truncate">${esc(x.label || '')}</span><span class="dim" data-pos></span></div>
          </div>`; }).join('')}
        <div id="cross" class="cross"></div>
        <div class="hint lbl">${ms('drag_pan', 'c-primary')}${L('디스플레이를 드래그하여 책상 위 실제 모니터 위치와 맞게 정렬하세요', 'Drag the displays so they match where your monitors really sit')}</div>
      </div>
      <div class="lbl dim row gap-xs"><i style="display:inline-block;width:18px;height:4px;border-radius:2px;background:var(--tertiary)"></i>
        ${ui.view === 'mm' ? L('초록 선 = 실제 모니터가 맞닿은 구간. "마우스 이동 보정"을 켜면 마우스가 정확히 이 구간으로 넘어갑니다.', 'Green line = where the monitors really touch. With "Cursor mapping" on, the pointer crosses exactly there.')
          : L('초록 선 = Windows가 마우스를 넘겨주는 구간 (픽셀 기준).', 'Green line = where Windows lets the pointer cross (in pixels).')}</div>
      <div class="card">
        <div class="card-head"><div class="row">${ms('drag_pan', 'c-primary')}<span class="h-sm">${L('마우스 이동 보정', 'Cursor mapping')}</span>
          ${S.mouse.enabled ? `<span class="chip ok">${L('사용 중', 'On')}</span>` : ''}</div>${sw('mouse', S.mouse.enabled, '', list.length < 2)}</div>
        <div class="body-sm muted">${L('크기나 해상도가 다른 모니터 사이를 넘어갈 때 마우스가 위아래로 튀거나 벽에 막히는 현상을 없앱니다. "실제 크기 기준" 화면에서 모니터를 책상 위 실제 위치대로 놓으면, 마우스가 그 위치 그대로 옆 모니터로 넘어갑니다.', 'Stops the pointer from jumping up or down — or hitting an invisible wall — when it moves between monitors of different size or resolution. Place the monitors in "Real size" view the way they sit on your desk and the pointer crosses at that same spot.')}</div>
        <div class="lbl dim">${L('게임이 마우스를 화면 안에 가둔 동안에는 동작하지 않습니다. 넘어가는 위치가 어색하면 오른쪽에서 각 모니터의 실제 화면 크기(인치)를 확인하세요.', 'Inactive while a game confines the pointer. If the crossing point feels off, check each monitor’s real screen size (inches) on the right.')}</div>
      </div>
      <div class="card">
        <div class="card-head"><div class="row">${ms('shield', 'c-primary')}<span class="h-sm">${L('배치 보호', 'Layout protection')}</span></div>${sw('guard', g.enabled)}</div>
        <div class="body-sm muted">${L('전체 화면 게임 등으로 Windows가 모니터 배치를 바꾸면, 저장된 기준 배치로 자동 복원합니다. 이 화면에서 "배치 적용 및 저장"을 누르면 새 배치가 기준이 됩니다.', 'When a fullscreen game or Windows itself shuffles your monitors, the saved layout is put back automatically. "Apply & save" on this page makes the new layout the protected one.')}</div>
        <div class="row wrap">
          <button class="btn" data-act="snapshot">${ms('save', 'c-tertiary')}${L('현재 배치를 기준으로 저장', 'Save current layout as reference')}</button>
          <button class="btn" data-act="restore" ${g.has_saved ? '' : 'disabled'}>${ms('restart_alt', 'c-primary')}${L('지금 복원', 'Restore now')}</button>
          <button class="btn ghost" data-act="toggle-log">${ms('expand_more')}${L('활동 로그', 'Activity log')}</button>
        </div>
        ${ui.showLog ? logBox() : (logs.length ? `<div class="lbl dim truncate">${esc(logs[logs.length - 1].time)} ${esc(logs[logs.length - 1].text)}</div>` : '')}
      </div>
    </div>
    <div class="col gap-md">
      <div class="card c2">
        <div class="row between"><div class="row"><span class="num on">${info.number || ''}</span>
          <div class="col" style="gap:0"><span class="lbl dim caps">${L('선택된 타겟', 'Selected')}</span><span class="h-sm truncate">${esc(info.label || '')}</span></div></div>
          <span class="chip soft">${esc(info.short || '')}</span></div>
        <label class="inset row between" style="cursor:pointer"><span class="row">${ms('check_circle', 'c-primary')}<span>${L('이 디스플레이를 주 모니터로 사용', 'Make this the main display')}</span></span>
          <input type="checkbox" class="chk" data-in="primary" ${sel.primary ? 'checked disabled' : ''}></label>
        <div class="col gap-xs"><span class="lbl dim">${L('화면 방향 (Orientation)', 'Orientation')}</span>
          <div class="seg" style="grid-template-columns:repeat(4,1fr)">${ROT().map((r, i) => `<button class="${sel.rot === i ? 'on' : ''}" data-act="rotate" data-rot="${i}">${ms('monitor', '')}<span style="${i % 2 ? '' : ''}">${r}</span></button>`).join('')}</div></div>
        <div class="col gap-xs"><div class="row between"><span class="lbl dim">${L('실제 화면 크기 (대각선, 인치)', 'Real screen size (diagonal, inches)')}</span>
            <span class="chip ${info.mm_source === 'guess' ? 'warn' : info.mm_source === 'user' ? 'soft' : 'ok'}">${info.mm_source === 'user' ? L('직접 입력', 'Entered by you') : info.mm_source === 'edid' ? L('모니터에서 자동 인식', 'Read from monitor') : L('추정값 — 입력 권장', 'Estimate — please enter')}</span></div>
          <div class="row"><input class="txt" type="number" id="size-inches" min="5" max="200" step="0.1" value="${info.inches || ''}" data-in="size-inches">
            <button class="btn" data-act="size-auto" ${info.mm_source === 'user' ? '' : 'disabled'} title="${L('자동 인식 값으로 되돌리기', 'Back to the detected value')}">${ms('restart_alt')}${L('자동', 'Auto')}</button></div>
          <span class="lbl dim">${info.mm ? `${Math.round(info.mm[0])} × ${Math.round(info.mm[1])} mm` : ''}</span></div>
        <div class="col gap-xs mono" style="font-size:11px">
          <div class="kv"><span class="dim">${L('위치', 'Position')}</span><span>(${sel.x}, ${sel.y})</span></div>
          <div class="kv"><span class="dim">${L('해상도', 'Resolution')}</span><span>${sel.w} × ${sel.h}${sel.freq > 1 ? ' @ ' + sel.freq + 'Hz' : ''}</span></div>
          ${info.connector ? `<div class="kv"><span class="dim">${L('연결 인터페이스', 'Connection')}</span><span>${esc(info.connector)}</span></div>` : ''}
          ${info.scale ? `<div class="kv"><span class="dim">${L('배율', 'Scaling')}</span><span class="c-primary">${info.scale}%</span></div>` : ''}
        </div>
      </div>
      <div class="card c2">
        <div class="row between"><span class="h-sm">${L('배치 프로필 관리', 'Layout profiles')}</span><span class="lbl dim">${S.profiles.length}/12</span></div>
        ${S.profiles.length ? `<div class="col gap-xs">${S.profiles.map((p, i) => `
          <div class="row inset" style="padding:6px 8px">
            <button class="col grow" style="gap:0;text-align:left" data-act="profile-apply" data-name="${esc(p.name)}">
              <span class="lbl-md bold ${p.active ? 'c-primary' : ''} truncate">${esc(p.name)}${p.active ? ' ✓' : ''}</span>
              <span class="lbl dim">${p.count} ${L('디스플레이', 'displays')}${i < 3 ? ` · Win+Alt+${i + 1}` : ''}</span></button>
            <button class="btn sm ghost danger" title="${L('삭제', 'Delete')}" data-act="profile-delete" data-name="${esc(p.name)}">${ms('delete')}</button>
          </div>`).join('')}</div>` : `<div class="body-sm dim">${L('현재 배치를 이름 붙여 저장해 두면 한 번에 전환할 수 있습니다.', 'Save the current layout under a name to switch back to it in one click.')}</div>`}
        <div class="row"><input class="txt" id="profile-name" maxlength="40" placeholder="${L('프로필 이름 (예: 게이밍)', 'Profile name (e.g. Gaming)')}">
          <button class="btn" data-act="profile-save">${ms('add', 'c-tertiary')}${L('저장', 'Save')}</button></div>
        <div class="row">
          <button class="btn lg grow" data-act="draft-reset" ${dirty ? '' : 'disabled'}>${L('변경 취소', 'Discard changes')}</button>
          <button class="btn lg primary grow" data-act="draft-apply" ${dirty ? '' : 'disabled'}>${ms('done_all')}${L('배치 적용 및 저장', 'Apply & save')}</button>
        </div>
      </div>
    </div>
  </div>`;
}

function stagePointerDown(ev) {
  const node = ev.target.closest('.mon'); if (!node || !$('stage') || node.classList.contains('static')) return;
  const list = draft(), c = list.find(x => x.name === node.dataset.mon); if (!c) return;
  ui.sel = c.name;
  const rects = viewRects(list), r = rects.find(x => x.name === c.name);
  ui.drag = { c, r, rects, node, sx: ev.clientX, sy: ev.clientY, x0: r.x, y0: r.y, geo: stageGeometry(rects, $('stage')), moved: false };
  node.setPointerCapture(ev.pointerId);
}
function stagePointerMove(ev) {
  const d = ui.drag; if (!d) return;
  const dx = ev.clientX - d.sx, dy = ev.clientY - d.sy;
  if (!d.moved && Math.abs(dx) + Math.abs(dy) < 4) return;
  d.moved = true; d.node.classList.add('drag');
  d.r.x = d.x0 + dx / d.geo.k; d.r.y = d.y0 + dy / d.geo.k;
  layoutStage();
}
/* Real-size view: turn where the monitor was dropped (mm) back into a pixel position. */
function dropPhysical(d, list) {
  const others = d.rects.filter(x => x !== d.r);
  if (!settle(d.r, others, ui.snap)) return false;
  let best = null;
  others.forEach(o => {
    const v = Math.min(o.y + o.h, d.r.y + d.r.h) - Math.max(o.y, d.r.y), hz = Math.min(o.x + o.w, d.r.x + d.r.w) - Math.max(o.x, d.r.x);
    const sides = [['right', Math.abs(d.r.x - (o.x + o.w)), v], ['left', Math.abs(d.r.x + d.r.w - o.x), v], ['below', Math.abs(d.r.y - (o.y + o.h)), hz], ['above', Math.abs(d.r.y + d.r.h - o.y), hz]];
    sides.forEach(([side, gap, ov]) => { if (gap <= 1.5 && ov > 0 && (!best || ov > best.ov)) best = { o, side, ov }; });
  });
  if (!best) return false;
  const o = best.o, oc = list.find(x => x.name === o.name), c = d.c;
  if (best.side === 'right' || best.side === 'left') {
    const f = (d.r.y + d.r.h / 2 - o.y) / o.h;
    c.x = best.side === 'right' ? oc.x + oc.w : oc.x - c.w; c.y = Math.round(oc.y + f * oc.h - c.h / 2);
  } else {
    const f = (d.r.x + d.r.w / 2 - o.x) / o.w;
    c.y = best.side === 'below' ? oc.y + oc.h : oc.y - c.h; c.x = Math.round(oc.x + f * oc.w - c.w / 2);
  }
  return settle(c, list.filter(x => x !== c), false);
}
function stagePointerUp() {
  const d = ui.drag; if (!d) return;
  ui.drag = null;
  if (d.moved) {
    const list = draft(), keep = { x: d.c.x, y: d.c.y };
    let ok;
    if (ui.view === 'mm') ok = dropPhysical(d, list);
    else { d.c.x = Math.round(d.r.x); d.c.y = Math.round(d.r.y); ok = settle(d.c, list.filter(x => x !== d.c), ui.snap); }
    if (!ok) { d.c.x = keep.x; d.c.y = keep.y; }
    originToPrimary(list);
  }
  render();
}

// ───────────────────────── resolution & refresh ─────────────────────────
async function loadModes(name) {
  if (ui.modes[name]) return;
  ui.modes[name] = 'loading';
  try { ui.modes[name] = (await api('modes?name=' + encodeURIComponent(name))).modes; }
  catch (e) { ui.modes[name] = []; }
  if (ui.page === 'mode') queueRender();
}
function pageMode() {
  const x = selMon(), modes = ui.modes[x.name];
  if (!modes) loadModes(x.name);
  const pick = ui.modePick[x.name] || { w: x.w, h: x.h, freq: x.freq };
  let body = `<div class="body-sm dim">${L('지원 모드를 불러오는 중…', 'Loading supported modes…')}</div>`;
  if (Array.isArray(modes)) {
    const sizes = []; modes.forEach(md => { if (!sizes.some(s => s.w === md.w && s.h === md.h)) sizes.push({ w: md.w, h: md.h }); });
    const native = sizes[0] || { w: x.w, h: x.h };
    const freqs = modes.filter(md => md.w === pick.w && md.h === pick.h).map(md => md.freq);
    const ratio = s => { const g = (a, b) => b ? g(b, a % b) : a, d = g(s.w, s.h); const r = `${s.w / d}:${s.h / d}`; return r === '8:5' ? '16:10' : r === '5:8' ? '10:16' : r; };
    body = `
      <div class="grid g3">${sizes.slice(0, 6).map(s => { const on = s.w === pick.w && s.h === pick.h, cur = s.w === x.w && s.h === x.h; return `
        <button class="pick ${on ? 'on' : ''}" data-act="pick-size" data-w="${s.w}" data-h="${s.h}">
          <div class="row between"><span class="h-sm ${on ? 'c-primary' : ''}">${s.w} × ${s.h}</span>
            ${s === native ? `<span class="chip ok">${L('권장 (Native)', 'Native')}</span>` : ''}</div>
          <div class="lbl ${on ? 'muted' : 'dim'}">${ratio(s)} · ${(s.w * s.h / 1e6).toFixed(1)} MP</div>
          <div class="row gap-xs lbl ${on ? 'c-primary' : 'dim'}" style="margin-top:4px">${ms(on ? 'check_circle' : 'monitor', '')}<span>${cur ? L('현재 적용됨', 'Current') : on ? L('선택됨', 'Selected') : L('선택 가능', 'Available')}</span></div>
        </button>`; }).join('')}</div>
      <div class="grid g2">
        <div class="col gap-xs"><label class="lbl muted caps">${L('전체 해상도 목록', 'All resolutions')}</label>
          <select class="sel" data-in="size">${sizes.map(s => `<option value="${s.w}x${s.h}" ${s.w === pick.w && s.h === pick.h ? 'selected' : ''}>${s.w} × ${s.h}</option>`).join('')}</select></div>
        <div class="col gap-xs"><label class="lbl muted caps">${L('활성 주사율 선택', 'Refresh rate')}</label>
          <select class="sel" data-in="freq">${freqs.map(f => `<option value="${f}" ${f === pick.freq ? 'selected' : ''}>${f} Hz${f === Math.max(...freqs) ? L(' (최대)', ' (max)') : ''}</option>`).join('')}</select>
          <span class="lbl dim">${L('이 해상도에서 드라이버가 제공하는 주사율만 표시됩니다.', 'Only rates the driver offers at this resolution are listed.')}</span></div>
      </div>`;
  }
  return `
  ${pageHead('speed', L('해상도 및 화면 주사율', 'Resolution & refresh rate'), 'Display Pipeline Tuning',
    `<span class="chip"><span class="dot ok pulse" style="width:6px;height:6px"></span>${L('활성 디스플레이', 'Active displays')}: ${S.monitors.length}</span>`)}
  <div class="row between"><span class="lbl dim caps">Connected monitors (${S.monitors.length})</span><span class="lbl muted">${L('디스플레이를 선택하여 개별 설정을 구성하세요.', 'Pick a display to configure it.')}</span></div>
  ${monTabs()}
  <div class="split">
    <div class="col gap-lg">
      <div class="card c2">
        <div class="row gap-md">${ms('monitor', 'c-primary')}<div class="col" style="gap:0"><span class="h-sm">${L('해상도 (Desktop Resolution)', 'Desktop resolution')}</span>
          <span class="body-sm muted">${L('적용 후 15초 안에 확인하지 않으면 이전 설정으로 자동 복구됩니다.', 'If you do not confirm within 15 seconds the previous mode comes back automatically.')}</span></div></div>
        ${body}
      </div>
      <div class="card c2">
        <div class="row gap-md">${ms('tune', 'c-primary')}<div class="col" style="gap:0"><span class="h-sm">${L('텍스트 및 앱 크기 배율 (DPI Scaling)', 'Text & app scaling (DPI)')}</span>
          <span class="body-sm muted">${L('배율은 Windows 설정 › 시스템 › 디스플레이에서 변경합니다. Windows가 앱에 변경 기능을 공개하지 않아 여기서는 현재 값만 표시합니다.', 'Change scaling in Windows Settings › System › Display. Windows offers apps no supported way to set it, so only the current value is shown.')}</span></div>
          <span class="chip soft lbl-lg" style="margin-left:auto;padding:4px 12px">${x.scale ? x.scale + '%' : '—'}</span></div>
      </div>
    </div>
    <div class="col gap-md">
      <div class="card c2">
        <div class="row between"><div class="row">${ms('cable', 'c-tertiary')}<span class="h-sm">${L('인터페이스 신호 상태', 'Signal')}</span></div><span class="chip">${esc(x.short)}</span></div>
        <div class="col gap-xs">
          ${[[L('연결 프로토콜', 'Connection'), x.connector], [L('현재 모드', 'Current mode'), `${x.w} × ${x.h}${x.freq > 1 ? ' @ ' + x.freq + ' Hz' : ''}`],
            [L('색상 심도', 'Colour depth'), x.bits_per_channel ? x.bits_per_channel + L('비트 / 채널', ' bits / channel') : null],
            ['HDR', x.hdr ? (x.hdr.supported ? (x.hdr.enabled ? L('켜짐', 'On') : L('꺼짐', 'Off')) : L('미지원', 'Not supported')) : null],
            [L('화면 방향', 'Orientation'), ROT()[x.rot]], ['EDID', x.edid], [L('그래픽 어댑터', 'Adapter'), x.adapter]]
            .filter(r => r[1]).map(r => `<div class="kv"><span class="body-sm muted">${r[0]}</span><span class="lbl-md bold">${esc(r[1])}</span></div>`).join('')}
        </div>
      </div>
    </div>
  </div>`;
}
const modeDirty = () => Object.keys(ui.modePick).some(n => { const x = mon(n), p = ui.modePick[n]; return x && (p.w !== x.w || p.h !== x.h || p.freq !== x.freq); });
function setPick(name, w, h, freq) {
  const modes = Array.isArray(ui.modes[name]) ? ui.modes[name] : [];
  const freqs = modes.filter(md => md.w === w && md.h === h).map(md => md.freq);
  if (!freqs.includes(freq)) freq = freqs.includes(mon(name).freq) ? mon(name).freq : Math.max(...freqs);
  ui.modePick[name] = { w, h, freq };
  render();
}
async function applyModes() {
  const list = pickLayout(S.monitors);
  let anchor = null;
  list.forEach(c => { const p = ui.modePick[c.name]; if (p) { c.w = p.w; c.h = p.h; c.freq = p.freq; } if (c.primary) anchor = c.name; });
  repack(list, anchor);
  const r = await call('layout', { configs: list });
  if (r) ui.modePick = {};
  render();
}

function renderActionBar() {
  const show = ui.page === 'mode' && modeDirty() && !S.guard.pending;
  $('actionbar').innerHTML = show ? `<div class="actionbar">
    <div class="row gap-md"><div class="iconbox" style="width:32px;height:32px;border-radius:50%;background:rgba(173,198,255,.2)">${ms('tune')}</div>
      <div class="col" style="gap:0"><span class="h-sm">${L('디스플레이 파라미터가 수정되었습니다', 'Display mode changed')}</span>
        <span class="body-sm muted">${L('해상도 또는 주사율 변경을 시스템에 적용할까요?', 'Apply the new resolution / refresh rate?')}</span></div></div>
    <div class="row"><button class="btn lg" data-act="mode-discard">${L('되돌리기 (취소)', 'Discard')}</button>
      <button class="btn lg primary" data-act="mode-apply">${ms('check')}${L('변경 사항 적용', 'Apply')}</button></div></div>` : '';
}

function renderModal() {
  const p = S && S.guard.pending;
  if (!p) { $('modal').innerHTML = ''; clearInterval(ui.localCountdown); ui.localCountdown = null; return; }
  if (!$('countdown')) {
    $('modal').innerHTML = `<div class="overlay"><div class="dialog">
      <div class="iconbox" style="margin:0 auto;width:48px;height:48px;border-radius:50%;background:rgba(173,198,255,.2)">${ms('timer', '')}</div>
      <div><div class="h-md">${L('이 디스플레이 설정을 유지하시겠습니까?', 'Keep these display settings?')}</div>
        <p class="muted" style="margin-top:4px">${L('화면이 정상적으로 출력되지 않으면 카운트다운 종료 후 자동으로 이전 설정으로 복구됩니다.', 'If the picture is wrong, just wait — the previous settings return when the countdown ends.')}</p></div>
      <div class="countdown" id="countdown"></div>
      <div class="row"><button class="btn lg grow" data-act="layout-revert">${L('이전으로 복원', 'Revert')}</button>
        <button class="btn lg primary grow" data-act="layout-confirm">${L('설정 유지 (확인)', 'Keep settings')}</button></div></div></div>`;
    renderActionBar();
  }
  ui.pendingLeft = p.seconds_left;
  $('countdown').textContent = ui.pendingLeft + 's';
  if (!ui.localCountdown) ui.localCountdown = setInterval(() => {
    if (ui.pendingLeft > 0) ui.pendingLeft--;
    const el = $('countdown'); if (el) el.textContent = ui.pendingLeft + 's';
  }, 1000);
}

// ───────────────────────── colour & HDR ─────────────────────────
const COLOR_DEFAULT = { r: 100, g: 100, b: 100, gamma: 100, brightness: 0, contrast: 100 };
async function loadDdc(name, force) {
  if (ui.ddc[name] !== undefined && !force) return;
  ui.ddc[name] = 'loading';
  try { ui.ddc[name] = (await api('ddc?name=' + encodeURIComponent(name))).ddc; } catch (e) { ui.ddc[name] = null; }
  if (ui.page === 'color') queueRender();
}
function pageColor() {
  const x = selMon(), c = x.color, ddc = ui.ddc[x.name];
  if (ddc === undefined) loadDdc(x.name);
  const neutral = JSON.stringify(c) === JSON.stringify(COLOR_DEFAULT);
  const slider = (key, label, min, max, cls, fmt) => `
    <div class="tile"><div class="row between lbl"><span class="bold ${cls === 'r' ? 'c-error' : cls === 'g' ? 'c-tertiary' : cls === 'b' ? 'c-primary' : 'muted'}">${label}</span>
      <span class="lbl-md" data-val="${key}">${fmt(c[key])}</span></div>
      <input type="range" class="${cls}" min="${min}" max="${max}" value="${c[key]}" data-in="color" data-key="${key}">
      <div class="row between lbl dim"><span>${fmt(min)}</span><span>${fmt(key === 'brightness' ? 0 : 100)}</span><span>${fmt(max)}</span></div></div>`;
  const pct = v => v + '%', signed = v => (v > 0 ? '+' : '') + v, gam = v => (v / 100).toFixed(2) + '×';
  const hdrOn = x.hdr && x.hdr.enabled;
  const ddcBody = ddc === 'loading' || ddc === undefined ? `<div class="body-sm dim">${L('모니터에 질의하는 중…', 'Asking the monitor…')}</div>`
    : !ddc ? `<div class="body-sm dim">${L('이 모니터는 DDC/CI에 응답하지 않습니다. 모니터 OSD 메뉴에서 DDC/CI를 켜면 여기서 밝기를 조절할 수 있습니다.', 'This monitor does not answer DDC/CI. Enable DDC/CI in the monitor’s own menu to control brightness from here.')}</div>`
      : ['brightness', 'contrast'].filter(k => ddc[k]).map(k => `
        <div class="col gap-xs"><div class="row between lbl"><span class="muted">${k === 'brightness' ? L('하드웨어 밝기 (Luminance)', 'Hardware brightness') : L('하드웨어 명암비 (Contrast)', 'Hardware contrast')}</span>
          <span class="lbl-md c-primary bold" data-val="ddc-${k}">${ddc[k].cur}</span></div>
          <input type="range" min="${ddc[k].min || 0}" max="${ddc[k].max}" value="${ddc[k].cur}" data-in="ddc" data-key="${k}"></div>`).join('');
  return `
  ${pageHead('tonality', L('컬러 보정 및 HDR', 'Colour correction & HDR'), L('소프트웨어 감마 보정 · 모니터 하드웨어 밝기 · HDR 전환', 'Software gamma correction · monitor hardware brightness · HDR switch'),
    `<button class="btn" data-act="color-all" ${S.monitors.length < 2 ? 'disabled' : ''}>${ms('done_all', 'c-tertiary')}${L('이 값을 모든 모니터에 적용', 'Apply these values to all monitors')}</button>`)}
  ${monTabs()}
  <div class="split">
    <div class="col gap-lg">
      <div class="card">
        <div class="row between"><div class="row"><span class="lbl dim caps">Test pattern</span><span class="h-sm">${L('보정 확인용 패턴', 'Check pattern')}</span></div>
          <span class="lbl dim">${L('이 창을 보정할 모니터로 옮겨서 확인하세요', 'Move this window onto the monitor you are adjusting')}</span></div>
        <div class="ramp" style="background:linear-gradient(90deg,#000,#fff)"></div>
        <div class="grid g3" style="gap:6px"><div class="ramp" style="background:linear-gradient(90deg,#000,#f00)"></div><div class="ramp" style="background:linear-gradient(90deg,#000,#0f0)"></div><div class="ramp" style="background:linear-gradient(90deg,#000,#00f)"></div></div>
        <div class="patches">${Array.from({ length: 16 }, (_, i) => { const v = i < 8 ? i * 3 : 255 - (15 - i) * 3; return `<div style="background:rgb(${v},${v},${v})"></div>`; }).join('')}</div>
        <div class="lbl dim">${L('아래 16칸: 왼쪽 8칸(어두운 단계)과 오른쪽 8칸(밝은 단계)이 각각 구분되어 보이면 계조가 뭉개지지 않은 것입니다.', 'Bottom strip: if you can tell the 8 dark steps and the 8 bright steps apart, shadows and highlights are not being crushed.')}</div>
      </div>
      <div class="card">
        <div class="row between"><div class="row"><span class="lbl dim caps">Channel tuning</span><span class="h-sm">${L('RGB 채널별 게인 및 톤', 'RGB gain & tone')}</span>
          ${neutral ? '' : `<span class="chip ok">${L('보정 적용 중', 'Correction active')}</span>`}</div>
          <button class="btn sm ghost" data-act="color-reset" ${neutral ? 'disabled' : ''}>${ms('restart_alt')}${L('기본값 초기화', 'Reset')}</button></div>
        ${hdrOn ? `<div class="demo-banner body-sm">${L('HDR이 켜진 모니터에서는 Windows가 소프트웨어 감마 보정을 무시합니다. HDR을 끄면 아래 값이 적용됩니다.', 'Windows ignores software gamma correction while HDR is on. These values take effect when HDR is off.')}</div>` : ''}
        <div class="grid g3">${slider('r', 'Red', 80, 120, 'r', pct)}${slider('g', 'Green', 80, 120, 'g', pct)}${slider('b', 'Blue', 80, 120, 'b', pct)}</div>
        <div class="grid g3">${slider('gamma', L('감마 (Gamma)', 'Gamma'), 60, 160, '', gam)}${slider('brightness', L('밝기 오프셋', 'Brightness offset'), -20, 20, '', signed)}${slider('contrast', L('명암비 (Contrast)', 'Contrast'), 70, 130, '', pct)}</div>
        <div class="lbl dim">${L('그래픽 카드의 감마 테이블을 조정하는 소프트웨어 보정입니다. 측색기 없이 눈으로 맞추는 용도이며, 값은 저장되어 재시작·배치 복원 후에도 다시 적용됩니다.', 'This adjusts the graphics card’s gamma table (software correction, by eye — no colorimeter involved). Values are saved and re-applied after restarts and layout restores.')}</div>
      </div>
    </div>
    <div class="col gap-lg">
      <div class="card">
        <div class="row between"><div class="row">${ms('hdr_on', 'c-primary')}<span class="h-sm">${L('HDR 제어', 'HDR')}</span></div>
          <span class="chip ${x.hdr && x.hdr.supported ? 'soft' : ''}">${x.hdr ? (x.hdr.supported ? L('지원됨', 'Supported') : L('미지원', 'Not supported')) : L('정보 없음', 'Unknown')}</span></div>
        <div class="tile row between" style="flex-direction:row;align-items:center"><div class="col" style="gap:0"><span class="h-sm">${L('Windows HDR 사용', 'Use HDR')}</span>
          <span class="body-sm muted">${esc(x.label)}${x.bits_per_channel ? ' · ' + x.bits_per_channel + '-bit' : ''}</span></div>
          ${sw('hdr', hdrOn, '', !(x.hdr && x.hdr.supported))}</div>
        <div class="lbl dim">${L('Windows 설정의 "HDR 사용" 스위치와 같은 동작입니다. 전환 시 화면이 잠깐 깜빡일 수 있습니다.', 'Same as the "Use HDR" switch in Windows Settings. The screen may blink while switching.')}</div>
      </div>
      <div class="card">
        <div class="row between"><div class="row">${ms('tune', 'c-primary')}<span class="h-sm">${L('모니터 하드웨어 제어 (DDC/CI)', 'Monitor hardware (DDC/CI)')}</span></div>
          <button class="btn sm" data-act="ddc-reload">${ms('sync', 'c-primary')}${L('다시 읽기', 'Re-read')}</button></div>
        ${ddcBody}
        <div class="lbl dim">${L('모니터 자체의 백라이트 밝기를 케이블을 통해 직접 조절합니다. 노트북 내장 화면은 대부분 지원하지 않습니다.', 'Sets the monitor’s own backlight over the cable. Built-in laptop panels usually do not support this.')}</div>
      </div>
    </div>
  </div>`;
}
const debounced = {};
function debounce(key, fn, wait) { clearTimeout(debounced[key]); debounced[key] = setTimeout(fn, wait); }

// ───────────────────────── zones ─────────────────────────
const PRESET_NAMES = () => ({ full: L('단일 전체 화면', 'Single full screen'), cols2: L('좌우 2열 분할', 'Two columns'), cols3: L('3분할 세로 컬럼', 'Three columns'),
  focus: L('울트라와이드 포커스', 'Centre focus'), main70: L('메인 70% + 사이드 30%', 'Main 70% + side 30%'), quad: L('2x2 쿼드 그리드', '2×2 grid'),
  rows2: L('상하 2분할', 'Two rows'), rows3: L('상중하 3단 분할', 'Three rows') });
function zonesHtml(preset, label) {
  const zs = S.zones.presets[preset] || [], big = zs.reduce((a, z) => Math.max(a, z[2] * z[3]), 0);
  return zs.map((z, i) => `<div class="zone ${zs.length > 1 && z[2] * z[3] === big && zs.filter(q => q[2] * q[3] === big).length === 1 ? 'hero' : ''}" style="left:calc(${z[0] * 100}% + 2px);top:calc(${z[1] * 100}% + 2px);width:calc(${z[2] * 100}% - 4px);height:calc(${z[3] * 100}% - 4px)">${label ? i + 1 : ''}</div>`).join('');
}
function pageZones() {
  const z = S.zones, x = selMon(), names = PRESET_NAMES();
  const minX = Math.min(...S.monitors.map(c => c.x)), minY = Math.min(...S.monitors.map(c => c.y));
  const bw = Math.max(...S.monitors.map(c => c.x + c.w)) - minX, bh = Math.max(...S.monitors.map(c => c.y + c.h)) - minY;
  const failed = new Set(z.hotkeys_failed);
  const hk = (label, keys, ids) => { const bad = ids.some(i => failed.has(i)); return `
    <div class="row between inset" style="padding:6px 8px"><span class="body-sm muted">${label}</span>
      <span class="row gap-xs">${bad ? `<span class="chip err">${L('다른 프로그램이 사용 중', 'In use by another app')}</span>` : ''}${keys.map(k => `<kbd>${k}</kbd>`).join('<span class="dim">+</span>')}</span></div>`; };
  return `
  ${pageHead('grid_view', `${L('가상 작업 공간 및 화면 분할', 'Window zones')} <span class="chip ${z.enabled ? 'ok' : ''} caps">${z.enabled ? L('사용 중', 'On') : L('꺼짐', 'Off')}</span>`,
    L('모니터마다 분할 구역을 정하고, 단축키나 Shift+드래그로 창을 구역에 맞춥니다', 'Define zones per monitor, then snap windows into them with hotkeys or Shift+drag'),
    `${sw('zones-enabled', z.enabled)}<button class="btn primary" data-act="tile" ${z.enabled ? '' : 'disabled'}>${ms('done_all')}${L('열린 창을 구역에 정렬', 'Arrange open windows')}</button>`)}
  <div class="split">
    <div class="col gap-lg">
      <div class="card" style="background:var(--lowest)">
        <div class="row between"><div class="row">${ms('view_quilt', 'c-primary')}<span class="h-sm">${L('라이브 멀티 디스플레이 존 토폴로지', 'Zone map')}</span><span class="lbl dim">${L('모니터를 클릭하여 구역 변경', 'Click a monitor to change its zones')}</span></div></div>
        <div style="position:relative;width:100%;aspect-ratio:${bw}/${bh};max-height:340px;margin:0 auto">
          ${S.monitors.map(c => `<button class="mon static ${c.name === x.name ? 'sel' : ''}" data-act="select" data-name="${esc(c.name)}" style="left:${(c.x - minX) / bw * 100}%;top:${(c.y - minY) / bh * 100}%;width:calc(${c.w / bw * 100}% - 6px);height:calc(${c.h / bh * 100}% - 6px);padding:4px;cursor:pointer">
            <div style="position:relative;flex:1;width:100%;height:100%">${zonesHtml(c.zone_preset, true)}</div>
            <span class="lbl ${c.name === x.name ? 'c-primary' : 'dim'}" style="position:absolute;left:8px;bottom:6px">${c.number} · ${esc(names[c.zone_preset] || '')}</span></button>`).join('')}
        </div>
      </div>
      <div class="col gap-md">
        <div class="row between"><div class="row">${ms('view_quilt', 'c-primary')}<span class="h-sm">${L('모니터', 'Monitor')} ${x.number} (${esc(x.label)}) ${L('스냅 프리셋 선택', '— choose a layout')}</span></div>
          <span class="lbl dim">${x.w} × ${x.h}</span></div>
        <div class="grid g4">${Object.keys(z.presets).map(p => `
          <button class="pick ${x.zone_preset === p ? 'on' : ''}" data-act="zone-preset" data-preset="${p}">
            <div class="row between"><span class="lbl-md bold">${names[p]}</span>${x.zone_preset === p ? `<span class="chip pri">${L('선택됨', 'Selected')}</span>` : ''}</div>
            <div class="preview" style="${x.h > x.w ? 'width:46%;height:110px;margin:0 auto' : ''}">${zonesHtml(p, false)}</div>
          </button>`).join('')}</div>
      </div>
    </div>
    <div class="col gap-md">
      <div class="card">
        <div class="row">${ms('drag_pan', 'c-primary')}<span class="h-sm">${L('창 자석(Snap) 동작', 'Snapping')}</span></div>
        <div class="tile row between" style="flex-direction:row;align-items:center"><div class="col" style="gap:0"><span class="bold">${L('Shift 키 누르고 드래그 시 구역에 스냅', 'Snap when dropping with Shift held')}</span>
          <span class="body-sm muted">${L('창을 옮기다가 Shift를 누른 채 놓으면, 마우스 아래 구역 크기로 맞춰집니다.', 'Drag a window and release it while holding Shift: it takes the size of the zone under the cursor.')}</span></div>${sw('zones-shift', z.shift_snap, '', !z.enabled)}</div>
        <div class="tile"><div class="row between"><span class="bold">${L('창 테두리 간격 (Zone Padding)', 'Gap between zones')}</span><span class="lbl-md c-primary" data-val="padding">${z.padding} px</span></div>
          <input type="range" min="0" max="32" step="2" value="${z.padding}" data-in="zones-padding">
          <div class="row between lbl dim"><span>0px</span><span>16px</span><span>32px</span></div></div>
      </div>
      <div class="card">
        <div class="row">${ms('keyboard', 'c-tertiary')}<span class="h-sm">${L('전역 단축키', 'Global hotkeys')}</span></div>
        <div class="col gap-xs">
          ${hk(L('활성 창을 이전/다음 구역으로 이동', 'Move active window to previous / next zone'), ['Win', 'Alt', '← / →'], ['zone_prev', 'zone_next'])}
          ${hk(L('활성 창을 모니터 전체 구역으로', 'Fill the whole monitor'), ['Win', 'Alt', '↑'], ['zone_fill'])}
          ${hk(L('배치 프로필 1~3 적용', 'Apply layout profile 1–3'), ['Win', 'Alt', '1 ~ 3'], ['profile_1', 'profile_2', 'profile_3'])}
        </div>
        <div class="tile row top" style="flex-direction:row;background:rgba(45,52,73,.5)">${ms('bolt', 'c-tertiary')}<p class="body-sm muted">${L('단축키는 가상 작업 공간이 켜져 있을 때만 등록됩니다. 관리자 권한으로 실행된 프로그램의 창은 Windows 보안 정책상 옮길 수 없습니다.', 'Hotkeys are registered only while window zones are on. Windows of programs running as administrator cannot be moved (Windows security rule).')}</p></div>
      </div>
    </div>
  </div>`;
}

// ───────────────────────── hardware & GPU ─────────────────────────
function startGpu() {
  if (ui.gpuTimer) return;
  const tick = async () => {
    try {
      ui.gpu = (await api('gpu')).gpus; ui.gpuLoaded = true;
      ui.gpu.forEach(g => { const h = ui.gpuHist[g.index] = ui.gpuHist[g.index] || { load: [], temp: [], power: [] };
        [['load', g.load_pct], ['temp', g.temp_c], ['power', g.power_w]].forEach(([k, v]) => { h[k].push(v == null ? null : v); if (h[k].length > 60) h[k].shift(); }); });
    } catch (e) {}
    const el = $('gpu-live'); if (el) el.innerHTML = gpuHtml();
  };
  tick(); ui.gpuTimer = setInterval(tick, 1000);
  if (!ui.hw) loadHardware(false);
}
function stopGpu() { clearInterval(ui.gpuTimer); ui.gpuTimer = null; }
async function loadHardware(withDdc) {
  try { ui.hw = await api('hardware' + (withDdc ? '?ddc=1' : '')); } catch (e) { toast(e.message, true); }
  if (ui.page === 'hardware') queueRender();
}
function spark(values, max, color) {
  const pts = values.map((v, i) => v == null ? null : `${(i / 59 * 200).toFixed(1)},${(40 - Math.min(1, v / max) * 36 - 2).toFixed(1)}`).filter(Boolean);
  return `<svg class="spark" viewBox="0 0 200 40" preserveAspectRatio="none"><line x1="0" x2="200" y1="20" y2="20" stroke="#424754" stroke-dasharray="2,2" stroke-width="1"/>${pts.length > 1 ? `<polyline points="${pts.join(' ')}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>` : ''}</svg>`;
}
function gpuHtml() {
  if (!ui.gpuLoaded) return `<div class="body-sm dim">${L('센서를 읽는 중…', 'Reading sensors…')}</div>`;
  if (!ui.gpu.length) return `<div class="body-sm muted">${L('실시간 센서를 읽을 수 있는 GPU를 찾지 못했습니다. 현재 NVIDIA 그래픽 카드(드라이버에 포함된 NVML)만 지원하며, AMD·Intel은 공개된 동등 라이브러리가 없어 지원하지 않습니다.', 'No GPU with readable live sensors was found. Only NVIDIA cards are supported for now (via NVML, which ships with the driver); AMD and Intel have no equivalent public library.')}</div>`;
  const stat = (label, value, unit, sub, pctv, color, hist, max) => `
    <div class="tile low"><span class="lbl dim caps">${label}</span>
      <div class="row gap-xs" style="align-items:baseline"><span class="bigval" style="color:${color}">${value}</span><span class="lbl bold" style="color:${color}">${unit}</span><span class="lbl dim" style="margin-left:auto">${sub || ''}</span></div>
      ${pctv == null ? '' : `<div class="gauge"><i style="width:${Math.max(0, Math.min(100, pctv))}%;background:${color}"></i></div>`}
      ${hist ? spark(hist, max, color) : ''}</div>`;
  return ui.gpu.map(g => { const h = ui.gpuHist[g.index] || { load: [], temp: [], power: [] }; return `
    <div class="col gap-md">
      <div class="row between"><div class="row"><span class="dot ok pulse"></span><span class="h-sm">${esc(g.name)}</span></div>
        <span class="chip soft"><span class="dot ok pulse" style="width:6px;height:6px"></span>${L('1초 간격 갱신', 'Updated every second')}</span></div>
      <div class="grid g4">
        ${g.load_pct == null ? '' : stat(L('GPU 사용률', 'GPU load'), g.load_pct, '%', '', g.load_pct, '#adc6ff', h.load, 100)}
        ${g.temp_c == null ? '' : stat(L('코어 온도', 'Core temperature'), g.temp_c, '°C', '', g.temp_c, g.temp_c >= 85 ? '#ffb4ab' : '#4edea3', h.temp, 100)}
        ${g.power_w == null ? '' : stat(L('소비 전력', 'Power draw'), g.power_w.toFixed(1), 'W', g.power_limit_w ? '/ ' + g.power_limit_w.toFixed(0) + ' W' : '', g.power_limit_w ? g.power_w / g.power_limit_w * 100 : null, '#c0c1ff', h.power, g.power_limit_w || Math.max(100, ...h.power.filter(v => v != null)))}
        ${g.vram_total ? stat(L('전용 VRAM', 'Dedicated VRAM'), gb(g.vram_used), 'GB', '/ ' + gb(g.vram_total) + ' GB', g.vram_used / g.vram_total * 100, '#adc6ff') : ''}
      </div>
      <div class="row wrap lbl muted" style="gap:16px">
        ${g.fan_pct == null ? '' : `<span>${L('팬', 'Fan')}: <b class="c-tertiary">${g.fan_pct}%</b></span>`}
        ${g.clock_core_mhz == null ? '' : `<span>${L('코어 클럭', 'Core clock')}: <b class="c-primary">${g.clock_core_mhz.toLocaleString()} MHz</b></span>`}
        ${g.clock_mem_mhz == null ? '' : `<span>${L('메모리 클럭', 'Memory clock')}: <b class="c-tertiary">${g.clock_mem_mhz.toLocaleString()} MHz</b></span>`}
      </div>
    </div>`; }).join('<div class="divider"></div>');
}
function pageHardware() {
  const hw = ui.hw, adapters = hw ? hw.adapters : [];
  const mons = hw ? hw.monitors : S.monitors;
  return `
  ${pageHead('memory', L('하드웨어 및 GPU', 'Hardware & GPU'), L('그래픽 어댑터, 디스플레이 연결 정보, 실시간 GPU 센서 (읽기 전용)', 'Graphics adapters, display links and live GPU sensors (read-only)'),
    `<button class="btn" data-act="hw-reload">${ms('restart_alt', 'c-primary')}${L('다시 스캔', 'Rescan')}</button>
     <button class="btn accent" data-act="report">${ms('download')}${L('하드웨어 리포트 내보내기', 'Export hardware report')}</button>`)}
  <div class="card"><div class="card-head divider"><div class="row">${ms('speed', 'c-primary')}<span class="h-sm">${L('GPU 실시간 모니터링', 'Live GPU monitoring')}</span></div>
    <span class="chip">${L('읽기 전용 · 설정을 변경하지 않음', 'Read-only · changes nothing')}</span></div>
    <div id="gpu-live" class="col gap-md">${gpuHtml()}</div></div>
  <div class="grid g2">
    <div class="card"><div class="card-head divider"><div class="row">${ms('memory', 'c-primary')}<span class="h-sm">${L('그래픽 어댑터', 'Graphics adapters')}</span></div><span class="lbl dim">${hw ? esc(hw.os) : ''}</span></div>
      ${hw ? adapters.map(a => `<div class="tile"><span class="h-sm">${esc(a.name)}</span>
        <div class="col gap-xs lbl muted">${a.driver_version ? `<div class="row between"><span>${L('드라이버 버전', 'Driver version')}</span><span class="mono" style="color:var(--on)">${esc(a.driver_version)}${a.driver_date ? ' · ' + esc(a.driver_date) : ''}</span></div>` : ''}
          ${a.vram ? `<div class="row between"><span>${L('전용 메모리', 'Dedicated memory')}</span><span class="mono" style="color:var(--on)">${gb(a.vram)} GB</span></div>` : ''}</div></div>`).join('')
        : `<div class="body-sm dim">${L('불러오는 중…', 'Loading…')}</div>`}
    </div>
    <div class="card"><div class="card-head divider"><div class="row">${ms('tune', 'c-primary')}<span class="h-sm">${L('DDC/CI 통신 진단', 'DDC/CI check')}</span></div>
      <button class="btn sm" data-act="ddc-ping">${ms('sync', 'c-primary')}${L('DDC 버스 핑', 'Ping monitors')}</button></div>
      <div class="grid g3">${mons.map(x => `<div class="tile low"><span class="lbl dim">${x.number}. ${esc(x.label)}</span>
        ${'ddc' in x ? (x.ddc ? `<span class="lbl c-tertiary">${L('응답함', 'Responding')}</span><span class="lbl muted">${Object.keys(x.ddc).map(k => `${k} ${x.ddc[k].cur}/${x.ddc[k].max}`).join(' · ')}</span>` : `<span class="lbl c-amber">${L('응답 없음', 'No response')}</span>`) : `<span class="lbl dim">${L('아직 확인 안 함', 'Not checked yet')}</span>`}</div>`).join('')}</div>
      <div class="lbl dim">${L('각 모니터가 케이블을 통한 제어 명령에 응답하는지 확인합니다. 모니터당 최대 1초 정도 걸릴 수 있습니다.', 'Checks whether each monitor answers control commands over its cable. Can take up to a second per monitor.')}</div>
    </div>
  </div>
  <div class="card"><div class="card-head divider"><div class="row">${ms('cable', 'c-primary')}<span class="h-sm">${L('디스플레이 연결 정보', 'Display links')}</span></div>
    <span class="row gap-md lbl muted"><span class="row gap-xs"><span class="dot ok"></span>${L('활성 링크', 'Active links')} (${mons.length})</span></span></div>
    <div class="col">${mons.map(x => `
      <div class="tile row between wrap" style="flex-direction:row;align-items:center;position:relative;padding-left:16px;overflow:hidden">
        <div style="position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--tertiary)"></div>
        <div class="row gap-md"><span class="num" style="width:40px;height:40px;color:var(--primary)">${x.number}</span>
          <div class="col" style="gap:2px"><div class="row wrap"><span class="h-sm">${esc(x.label)}</span>
            ${x.primary ? `<span class="chip pri">${L('주 디스플레이', 'Main')}</span>` : ''}${x.rot ? `<span class="chip c-secondary">${ROT()[x.rot]}</span>` : ''}
            ${x.hdr && x.hdr.enabled ? `<span class="chip c-tertiary">HDR</span>` : ''}</div>
            <div class="row wrap lbl muted" style="gap:10px"><span>${x.w}×${x.h}${x.freq > 1 ? ' @ ' + x.freq + 'Hz' : ''}</span>${x.bits_per_channel ? `<span>• ${x.bits_per_channel}-bit</span>` : ''}${x.connector ? `<span>• ${esc(x.connector)}</span>` : ''}<span>• (${x.x}, ${x.y})</span></div></div></div>
        <div class="col lbl dim" style="gap:2px;text-align:right"><span>${esc(x.short)}${x.edid ? ' · EDID ' + esc(x.edid) : ''}</span><span>${esc(x.adapter || '')}</span></div>
      </div>`).join('')}</div>
  </div>
  <div class="lbl dim">${L('오버클럭·전압·팬 제어, 스트레스 테스트, 신호 품질(아이 다이어그램·비트 에러율) 측정은 제공하지 않습니다. 앞의 것은 제조사 비공개 인터페이스가 필요하고 하드웨어를 손상시킬 수 있으며, 신호 품질은 계측 장비 없이는 소프트웨어로 측정할 수 없기 때문입니다.', 'Overclocking, voltage or fan control, stress testing and signal-quality measurements (eye diagram, bit error rate) are not offered: the former need private vendor interfaces and can damage hardware, the latter cannot be measured by software without lab equipment.')}</div>`;
}

// ───────────────────────── settings ─────────────────────────
function pageSettings() {
  const g = S.guard;
  return `
  ${pageHead('settings', L('설정', 'Settings'), `${esc(S.app.name)} v${esc(S.app.version)}`)}
  <div class="grid g2">
    <div class="card">
      <div class="h-sm">${L('일반', 'General')}</div>
      <div class="tile row between" style="flex-direction:row;align-items:center"><div class="col" style="gap:0"><span class="bold">${L('Windows 시작 시 자동 실행', 'Start with Windows')}</span>
        <span class="body-sm muted">${L('창을 띄우지 않고 트레이에서 조용히 시작합니다.', 'Starts quietly in the tray, without opening this window.')}</span></div>${sw('autostart', S.settings.autostart)}</div>
      <div class="tile"><span class="bold">${L('언어', 'Language')}</span>
        <select class="sel" data-in="language">${Object.entries(S.app.languages).map(([code, name]) => `<option value="${code}" ${code === S.app.language ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select>
        <span class="lbl dim">${L('이 창은 한국어와 영어로 표시됩니다. 그 외 언어는 트레이 메뉴와 활동 로그에 적용되고 창은 영어로 표시됩니다.', 'This window is available in Korean and English. Other languages apply to the tray menu and activity log; the window then shows English.')}</span></div>
    </div>
    <div class="card">
      <div class="h-sm">${L('배치 보호', 'Layout protection')}</div>
      <div class="tile row between" style="flex-direction:row;align-items:center"><div class="col" style="gap:0"><span class="bold">${L('자동 복원 사용', 'Automatic restore')}</span>
        <span class="body-sm muted">${L('Windows가 배치를 바꾸면 저장된 기준 배치로 되돌립니다.', 'Puts the saved layout back when Windows changes it.')}</span></div>${sw('guard', g.enabled)}</div>
      <div class="tile"><div class="row between"><span class="bold">${L('복원 대기 시간', 'Delay before restoring')}</span><span class="lbl-md c-primary" data-val="delay">${g.delay.toFixed(1)}${L('초', ' s')}</span></div>
        <input type="range" min="0.5" max="10" step="0.5" value="${g.delay}" data-in="delay">
        <span class="lbl dim">${L('게임이 화면 모드 전환을 마칠 때까지 기다리는 시간입니다. 복원이 너무 일찍 일어나 다시 틀어지면 늘려 보세요.', 'How long to wait for a game to finish switching modes. Increase it if the layout gets shuffled again right after a restore.')}</span></div>
    </div>
  </div>
  <div class="card"><div class="h-sm">${L('활동 로그', 'Activity log')}</div>${logBox()}</div>`;
}

// ───────────────────────── actions ─────────────────────────
const actions = {
  nav(el) { ui.page = el.dataset.page; window.scrollTo(0, 0); render(); },
  select(el) { ui.sel = el.dataset.name; render(); },
  async detect() { ui.modes = {}; ui.ddc = {}; ui.hw = null; try { accept(await api('state?since=' + logSeq)); render(); toast(L('디스플레이를 다시 읽었습니다', 'Displays re-read')); } catch (e) { toast(e.message, true); } },
  identify() { call('identify', {}, L('각 모니터에 번호를 표시했습니다', 'Numbers shown on each monitor')); },
  snapshot() { call('snapshot', {}, L('현재 배치를 기준으로 저장했습니다', 'Current layout saved as reference')); },
  restore() { call('restore', {}, L('저장된 배치로 복원했습니다', 'Restored the saved layout')); },
  'toggle-log'() { ui.showLog = !ui.showLog; render(); },
  view(el) { ui.view = el.dataset.view; try { localStorage.setItem('spectra-view', ui.view); } catch (e) {} render(); },
  'size-auto'() { call('size', { name: ui.sel, inches: null }); },
  align(el) {
    const list = draft(), c = list.find(x => x.name === ui.sel), p = list.find(x => x.primary);
    if (!c || !p || c === p) return;
    const how = el.dataset.how;
    if (ui.view === 'mm') {      // align the real edges: move the monitor's physical rect, then convert back
      const rects = viewRects(list), r = rects.find(x => x.name === c.name), pr = rects.find(x => x.name === p.name);
      r.y = how === 'top' ? pr.y : how === 'bottom' ? pr.y + pr.h - r.h : pr.y + (pr.h - r.h) / 2;
      const keep = { x: c.x, y: c.y };
      if (!dropPhysical({ c, r, rects }, list)) { c.x = keep.x; c.y = keep.y; }
    } else {
      c.y = how === 'top' ? p.y : how === 'bottom' ? p.y + p.h - c.h : Math.round(p.y + (p.h - c.h) / 2);
      settle(c, list.filter(x => x !== c), false);
    }
    originToPrimary(list); render();
  },
  rotate(el) {
    const list = draft(), c = list.find(x => x.name === ui.sel), rot = +el.dataset.rot; if (!c || c.rot === rot) return;
    if ((c.rot % 2) !== (rot % 2)) { const w = c.w; c.w = c.h; c.h = w; }
    c.rot = rot; repack(list, (list.find(x => x.primary) || c).name); render();
  },
  'draft-reset'() { ui.draft = null; render(); },
  async 'draft-apply'() { const r = await call('layout', { configs: draft() }); if (r) { ui.draft = null; if (!r.guard.pending) toast(L('배치를 적용하고 저장했습니다', 'Layout applied and saved')); } render(); },
  'profile-save'() { const name = ($('profile-name') || {}).value || ''; call('profiles', { action: 'save', name }, name.trim() ? L('프로필을 저장했습니다', 'Profile saved') : undefined); },
  'profile-apply'(el) { call('profiles', { action: 'apply', name: el.dataset.name }); },
  'profile-delete'(el) { call('profiles', { action: 'delete', name: el.dataset.name }); },
  'pick-size'(el) { setPick(selMon().name, +el.dataset.w, +el.dataset.h, (ui.modePick[selMon().name] || selMon()).freq); },
  'mode-discard'() { ui.modePick = {}; render(); },
  'mode-apply'() { applyModes(); },
  'layout-confirm'() { call('layout/confirm', {}, L('설정을 유지합니다', 'Settings kept')); },
  'layout-revert'() { call('layout/revert', {}, L('이전 설정으로 되돌렸습니다', 'Reverted')); },
  'color-reset'() { call('color', { name: selMon().name, settings: COLOR_DEFAULT }); },
  async 'color-all'() { const s = selMon().color; for (const x of S.monitors) await call('color', { name: x.name, settings: s }); toast(L('모든 모니터에 적용했습니다', 'Applied to all monitors')); },
  'ddc-reload'() { loadDdc(selMon().name, true); },
  'zone-preset'(el) { const layouts = {}; layouts[selMon().name] = el.dataset.preset; call('zones', { layouts }); },
  async tile() { const r = await call('zones/tile', {}); if (r) toast(L(`창 ${r.moved}개를 정렬했습니다`, `Arranged ${r.moved} windows`)); },
  'hw-reload'() { ui.hw = null; loadHardware(false); render(); },
  'ddc-ping'() { toast(L('모니터에 질의하는 중…', 'Asking the monitors…')); loadHardware(true); },
  async report() {
    try {
      const res = await fetch('/api/report', { headers: { 'X-Spectra-Token': TOKEN } });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const a = document.createElement('a'); a.href = URL.createObjectURL(await res.blob()); a.download = 'spectra-hardware-report.txt';
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      toast(L('리포트를 다운로드 폴더에 저장했습니다', 'Report saved to your downloads'));
    } catch (e) { toast(e.message, true); }
  },
};
const inputs = {
  snap(el) { ui.snap = el.checked; },
  mouse(el) { call('mouse', { enabled: el.checked }); },
  'size-inches'(el) { const v = parseFloat(el.value); if (v > 0) call('size', { name: ui.sel, inches: v }); },
  guard(el) { call('guard', { enabled: el.checked }); },
  primary(el) { if (!el.checked) return; const list = draft(); list.forEach(c => c.primary = c.name === ui.sel); originToPrimary(list); render(); },
  size(el) { const [w, h] = el.value.split('x').map(Number); setPick(selMon().name, w, h, (ui.modePick[selMon().name] || selMon()).freq); },
  freq(el) { const x = selMon(), p = ui.modePick[x.name] || { w: x.w, h: x.h }; setPick(x.name, p.w, p.h, +el.value); },
  color(el, live) {
    const x = selMon(), key = el.dataset.key, v = +el.value; x.color[key] = v;
    const out = document.querySelector(`[data-val="${key}"]`);
    if (out) out.textContent = key === 'gamma' ? (v / 100).toFixed(2) + '×' : key === 'brightness' ? (v > 0 ? '+' : '') + v : v + '%';
    debounce('color', () => call('color', { name: x.name, settings: x.color }), live ? 120 : 0);
  },
  ddc(el, live) {
    const x = selMon(), key = el.dataset.key, v = +el.value;
    const out = document.querySelector(`[data-val="ddc-${key}"]`); if (out) out.textContent = v;
    if (ui.ddc[x.name] && ui.ddc[x.name][key]) ui.ddc[x.name][key].cur = v;
    debounce('ddc-' + key, () => call('ddc', { name: x.name, key, value: v }), live ? 250 : 0);
  },
  hdr(el) { call('hdr', { name: selMon().name, enabled: el.checked }).then(() => { setTimeout(() => actions.detect(), 1500); }); },
  'zones-enabled'(el) { call('zones', { enabled: el.checked }); },
  'zones-shift'(el) { call('zones', { shift_snap: el.checked }); },
  'zones-padding'(el, live) { const out = document.querySelector('[data-val="padding"]'); if (out) out.textContent = el.value + ' px'; if (!live) call('zones', { padding: +el.value }); },
  delay(el, live) { const out = document.querySelector('[data-val="delay"]'); if (out) out.textContent = (+el.value).toFixed(1) + L('초', ' s'); if (!live) call('guard', { delay: +el.value }); },
  autostart(el) { call('settings', { autostart: el.checked }); },
  language(el) { call('settings', { language: el.value }); },
};

document.addEventListener('click', ev => {
  const el = ev.target.closest('[data-act]'); if (!el || el.disabled) return;
  const fn = actions[el.dataset.act]; if (fn) fn(el, ev);
});
document.addEventListener('input', ev => { const el = ev.target; if (el.dataset && el.dataset.in && el.type === 'range' && inputs[el.dataset.in]) inputs[el.dataset.in](el, true); });
document.addEventListener('change', ev => { const el = ev.target; if (el.dataset && el.dataset.in && inputs[el.dataset.in]) inputs[el.dataset.in](el, false); });
document.addEventListener('pointerdown', ev => { if (ev.target.type === 'range') ui.busy = true; stagePointerDown(ev); });
document.addEventListener('pointermove', stagePointerMove);
const release = () => { stagePointerUp(); if (ui.busy) { ui.busy = false; setTimeout(() => { if (ui.renderQueued) render(); }, 400); } };
document.addEventListener('pointerup', release);
document.addEventListener('pointercancel', release);
document.addEventListener('keydown', ev => { if (ev.key === 'Enter' && ev.target.id === 'profile-name') actions['profile-save'](); });
window.addEventListener('resize', () => { if (ui.page === 'arrange') layoutStage(); });

// ───────────────────────── boot ─────────────────────────
(async () => {
  if (!TOKEN) { $('main').innerHTML = '<div class="boot">Open Spectra Display Studio from its tray icon.</div>'; return; }
  try { accept(await api('state')); render(); poll(); }
  catch (e) { $('main').innerHTML = `<div class="boot">${esc(e.message)}</div>`; }
})();
})();
