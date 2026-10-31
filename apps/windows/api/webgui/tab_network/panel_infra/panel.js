/**
 * Панели диагностики сетевой инфраструктуры: panel-network-overview/adapters/switches/
 * ip-config/nat/wsl/diagnostics/history. Данные — API /api/network/infra/*.
 * Файл: apps/windows/api/webgui/tab_network/panel_infra/panel.js
 * Updated: 2026-10-28 16:30:00
 */

import { esc, fmtTime, infraRequest, severityBadge, statusBadge } from './api.js';
import { mountTable, rawDetails, renderStatusBanner } from './render.js';

const inFlight = new Map();

/** @returns {HTMLElement|null} Тело панели по короткому имени. */
function body(name) {
  return document.querySelector(`[data-infra-body="${name}"]`);
}

/**
 * Показывает состояние загрузки / ошибки в теле панели.
 * @param {string} name - Имя панели.
 * @param {string} html - HTML состояния.
 */
function setState(name, html) {
  const el = body(name);
  if (el) el.innerHTML = html;
}

const loading = '<div class="text-center py-4 text-muted"><div class="spinner-border spinner-border-sm text-info me-2"></div>Сбор данных (может занять до 10-30 сек)...</div>';
const failure = (e) => `<div class="alert alert-danger py-2 small mb-0">Ошибка загрузки: ${esc(e.message)}</div>`;
const list = (v) => (v && v.length ? v.map(esc).join('<br>') : '<span class="text-muted">--</span>');
const stamp = (name, iso) => { const t = document.querySelector(`[data-infra-updated="${name}"]`); if (t) t.textContent = `Обновлено: ${fmtTime(iso)}`; };

/** Рендер панели «Обзор». */
async function loadOverview(force) {
  const d = await infraRequest('/summary', { params: force ? { refresh: 'true' } : undefined });
  const s = d.summary;
  const n = (v) => (v === null || v === undefined ? '<span class="text-muted">н/д</span>' : v);
  const card = (title, value, extra = '') => `<div class="col-6 col-md-3"><div class="net-card p-2 h-100"><div class="small text-muted">${title}</div><div class="fs-4 fw-bold">${value}</div><div class="small">${extra}</div></div></div>`;
  const src = (k) => statusBadge(d.sources[k]?.status || 'unknown');
  const sev = Object.entries(s.findings_by_severity || {}).map(([k, v]) => `${severityBadge(k)} ${v}`).join(' ') || 'нет';
  setState('overview', `<div class="d-flex flex-wrap gap-2 mb-2 small">${statusBadge(d.status)}<span class="text-muted">Последний сбор: ${fmtTime(d.collected_at)} (${d.duration_ms} мс)</span></div>
    <div class="row g-2 mb-3">
      ${card('Сетевые адаптеры', n(s.adapters_total), `активных: ${n(s.adapters_up)}, отключённых: ${n(s.adapters_down)}`)}
      ${card('Виртуальные коммутаторы', n(s.switches_count), `Hyper-V: ${src('hyperv')}`)}
      ${card('NAT-конфигурации', n(s.nat_count), `Get-NetNat: ${src('nat')}`)}
      ${card('WSL', s.wsl_status === 'ok' ? `${n(s.wsl_distros)} дистр.` : '--', `${src('wsl')} режим: ${esc(s.wsl_networking_mode || 'н/д')}`)}
      ${card('Маршруты', n(s.routes_count), src('routes'))}
      ${card('Диагностика', s.findings_total, sev)}
    </div>
    <h6 class="small fw-bold">Основные интерфейсы</h6>
    ${(s.main_interfaces || []).length ? `<ul class="small">${s.main_interfaces.map((i) => `<li>${esc(i.name)} — ${esc(i.status)}</li>`).join('')}</ul>` : '<div class="small text-muted mb-2">Физические интерфейсы не определены.</div>'}
    <h6 class="small fw-bold">Состояние источников</h6>
    <div class="d-flex flex-wrap gap-2 small">${Object.entries(d.sources).map(([k, v]) => `<span>${esc(k)}: ${statusBadge(v.status)}</span>`).join('')}</div>`);
  stamp('overview', d.collected_at);
}

/** Рендер панели «Сетевые адаптеры». */
async function loadAdapters(force) {
  const d = await infraRequest('/adapters', { params: force ? { refresh: 'true' } : undefined });
  const el = body('adapters');
  el.innerHTML = `${renderStatusBanner(d)}<div data-role="tbl"></div>`;
  const cls = { physical: 'Физический', hyperv_virtual: 'Hyper-V', wsl: 'WSL2', virtual_other: 'Виртуальный (др.)', unknown: 'Не определён' };
  mountTable(el.querySelector('[data-role="tbl"]'), {
    status: d.status, rows: d.items, emptyText: 'Адаптеры не обнаружены.',
    search: (r) => `${r.props.name} ${r.props.description} ${r.props.mac} ${(r.props.ip.ipv4 || []).map((a) => a.address)}`,
    columns: [
      { label: 'Имя', value: (r) => `<b>${esc(r.props.name)}</b><div class="small text-muted">${esc(r.props.description)}</div>`, sort: (r) => r.props.name },
      { label: 'Index / GUID', value: (r) => `${esc(r.props.interface_index)}<div class="small text-muted">${esc(r.props.interface_guid)}</div>`, sort: (r) => r.props.interface_index },
      { label: 'MAC', value: (r) => esc(r.props.mac) },
      { label: 'Тип', value: (r) => `${cls[r.props.adapter_class] || '?'}<div class="small text-muted">уверенность: ${esc(r.props.confidence)}</div>`, sort: (r) => r.props.adapter_class },
      { label: 'Состояние', value: (r) => `${esc(r.props.status)}<div class="small text-muted">${esc(r.props.link_speed)}</div>`, sort: (r) => r.props.status },
      { label: 'IPv4', value: (r) => list((r.props.ip.ipv4 || []).map((a) => `${a.address}/${a.prefix_length}`)) },
      { label: 'IPv6', value: (r) => list((r.props.ip.ipv6 || []).map((a) => a.address)) },
      { label: 'DNS', value: (r) => list(r.props.ip.dns) },
      { label: 'Шлюзы', value: (r) => list(r.props.ip.gateways) },
    ],
    detail: (r) => `<div class="mb-1"><b>Признаки классификации:</b> ${list(r.props.signals)}</div>${rawDetails(r.raw, (r.sources || []).join(', '))}`,
  });
  stamp('adapters', d.collected_at);
}

/** Рендер панели «Виртуальные коммутаторы». */
async function loadSwitches(force) {
  const d = await infraRequest('/switches', { params: force ? { refresh: 'true' } : undefined });
  const el = body('switches');
  el.innerHTML = `${renderStatusBanner(d)}<div data-role="tbl"></div>`;
  mountTable(el.querySelector('[data-role="tbl"]'), {
    status: d.status, rows: d.items, emptyText: 'Hyper-V доступен, виртуальные коммутаторы не созданы.',
    search: (r) => `${r.props.name} ${r.props.switch_type} ${r.props.bound_adapter_description}`,
    columns: [
      { label: 'Имя', value: (r) => `<b>${esc(r.props.name)}</b><div class="small text-muted">${esc(r.props.id)}</div>`, sort: (r) => r.props.name },
      { label: 'Тип', value: (r) => esc(r.props.switch_type), sort: (r) => r.props.switch_type },
      { label: 'Физический адаптер', value: (r) => esc(r.props.bound_adapter_description) || '<span class="text-muted">--</span>' },
      { label: 'Адаптеры хоста / VLAN', value: (r) => list(r.props.host_adapters.map((h) => `${h.name}${h.vlan_mode ? ` [VLAN ${h.vlan_mode} ${h.vlan_access_id ?? ''}]` : ''}`)) },
      { label: 'Параметры', value: (r) => `AllowManagementOS: ${esc(r.props.allow_management_os)}<br>IOV: ${esc(r.props.iov_enabled)}` },
    ],
    detail: (r) => rawDetails(r.raw, 'Get-VMSwitch'),
  });
  stamp('switches', d.collected_at);
}

/** Рендер панели «IP-конфигурация и маршруты». */
async function loadIpConfig(force) {
  const params = force ? { refresh: 'true' } : undefined;
  const [ip, rt] = await Promise.all([infraRequest('/ip-config', { params }), infraRequest('/routes', { params })]);
  const el = body('ip-config');
  el.innerHTML = `<h6 class="small fw-bold">Интерфейсы</h6>${renderStatusBanner(ip)}<div data-role="ip"></div>
    <h6 class="small fw-bold mt-3">Таблица маршрутизации</h6>${renderStatusBanner(rt)}
    <div class="btn-group btn-group-sm mb-2" data-role="fam"><button class="btn btn-outline-primary active" data-f="">Все</button><button class="btn btn-outline-primary" data-f="IPv4">IPv4</button><button class="btn btn-outline-primary" data-f="IPv6">IPv6</button></div>
    <div data-role="rt"></div>`;
  mountTable(el.querySelector('[data-role="ip"]'), {
    status: ip.status, rows: ip.items, emptyText: 'Интерфейсы не обнаружены.',
    search: (r) => JSON.stringify(r.props),
    columns: [
      { label: 'Интерфейс', value: (r) => `<b>${esc(r.props.alias)}</b>`, sort: (r) => r.props.alias },
      { label: 'IPv4 / маска', value: (r) => list(r.props.ipv4.map((a) => `${a.address} / ${a.mask || a.prefix_length}`)) },
      { label: 'IPv6 / префикс', value: (r) => list(r.props.ipv6.map((a) => `${a.address}/${a.prefix_length}`)) },
      { label: 'Шлюзы', value: (r) => list(r.props.gateways) },
      { label: 'DNS', value: (r) => list(r.props.dns) },
      { label: 'Метрика v4/v6', value: (r) => `${esc(r.props.metric_v4 ?? '--')} / ${esc(r.props.metric_v6 ?? '--')}`, sort: (r) => r.props.metric_v4 ?? 0 },
    ],
    detail: (r) => rawDetails(r.raw, 'Get-NetIPAddress'),
  });
  const drawRoutes = (fam) => mountTable(el.querySelector('[data-role="rt"]'), {
    status: rt.status, rows: rt.items.filter((r) => !fam || r.props.family === fam), emptyText: 'Маршруты не найдены.',
    search: (r) => `${r.props.destination_prefix} ${r.props.next_hop} ${r.props.interface_alias}`,
    columns: [
      { label: 'Префикс', value: (r) => `${esc(r.props.destination_prefix)} ${r.props.is_default ? '<span class="badge bg-primary">default</span>' : ''}`, sort: (r) => r.props.destination_prefix },
      { label: 'Next hop', value: (r) => esc(r.props.next_hop) },
      { label: 'Интерфейс', value: (r) => esc(r.props.interface_alias), sort: (r) => r.props.interface_alias },
      { label: 'Метрика (маршрут+интерфейс)', value: (r) => `${esc(r.props.effective_metric)} <span class="small text-muted">(${esc(r.props.route_metric)}+${esc(r.props.interface_metric)})</span>`, sort: (r) => r.props.effective_metric },
      { label: 'Протокол', value: (r) => esc(r.props.protocol) },
    ],
    detail: (r) => rawDetails(r.raw, 'Get-NetRoute'),
  });
  drawRoutes('');
  el.querySelectorAll('[data-role="fam"] button').forEach((b) => {
    b.onclick = () => { el.querySelectorAll('[data-role="fam"] button').forEach((x) => x.classList.remove('active')); b.classList.add('active'); drawRoutes(b.dataset.f); };
  });
  stamp('ip-config', ip.collected_at);
}

/** Рендер панели «NAT». */
async function loadNat(force) {
  const d = await infraRequest('/nat', { params: force ? { refresh: 'true' } : undefined });
  const el = body('nat');
  el.innerHTML = `${renderStatusBanner(d)}<div data-role="tbl"></div>`;
  mountTable(el.querySelector('[data-role="tbl"]'), {
    status: d.status, rows: d.items, emptyText: 'Get-NetNat не вернул конфигураций (ICS/HNS-NAT этим источником не отображается).',
    columns: [
      { label: 'Имя', value: (r) => `<b>${esc(r.props.name)}</b>`, sort: (r) => r.props.name },
      { label: 'Внутренний префикс', value: (r) => esc(r.props.internal_prefix) },
      { label: 'Связанные коммутаторы / интерфейсы', value: (r) => list([...r.props.related_switches, ...r.props.related_interfaces]) },
      { label: 'Состояние', value: (r) => `Active: ${esc(r.props.active)}<br>Store: ${esc(r.props.store)}` },
      { label: 'Статические маппинги', value: (r) => esc(r.props.static_mappings.length) },
    ],
    detail: (r) => rawDetails({ timeouts: r.props.timeouts, static_mappings: r.props.static_mappings }, 'Get-NetNat'),
  });
  stamp('nat', d.collected_at);
}

/** Рендер панели «WSL2». */
async function loadWsl(force) {
  const d = await infraRequest('/wsl', { params: force ? { refresh: 'true' } : undefined });
  const el = body('wsl');
  const env = d.items.find((i) => i.kind === 'wsl_environment');
  const distros = d.items.filter((i) => i.kind === 'wsl_distro');
  let html = renderStatusBanner(d);
  if (env) {
    const p = env.props;
    html += `<div class="row g-2 small mb-2"><div class="col-md-4"><b>Версия WSL:</b> ${esc(p.wsl_version || 'н/д')}</div>
      <div class="col-md-4"><b>Дистрибутив по умолчанию:</b> ${esc(p.default_distro || 'н/д')} (v${esc(p.default_wsl_version || '?')})</div>
      <div class="col-md-4"><b>Режим сети:</b> ${esc(p.networking_mode)} <span class="text-muted">(${esc(p.mode_source)})</span></div>
      <div class="col-md-4"><b>Коммутаторы:</b> ${list(p.switches)}</div><div class="col-md-4"><b>NAT:</b> ${list(p.nat)}</div></div>
      <h6 class="small fw-bold">Интерфейсы Windows, связанные с WSL</h6>
      ${p.interfaces.length ? `<ul class="small">${p.interfaces.map((i) => `<li>${esc(i.name)} (${esc(i.status)}) — ${esc([...i.ipv4, ...i.ipv6].join(', ') || 'нет IP')}</li>`).join('')}</ul>` : '<div class="small text-muted mb-2">Интерфейсы WSL не обнаружены.</div>'}
      <h6 class="small fw-bold">Дистрибутивы</h6><div data-role="tbl"></div>`;
  }
  el.innerHTML = html;
  const tbl = el.querySelector('[data-role="tbl"]');
  if (tbl) {
    mountTable(tbl, { status: d.status, rows: distros, emptyText: 'Дистрибутивы не зарегистрированы.',
      columns: [{ label: 'Имя', value: (r) => `${r.props.is_default ? '★ ' : ''}${esc(r.props.name)}`, sort: (r) => r.props.name },
        { label: 'Состояние', value: (r) => esc(r.props.state) }, { label: 'Версия', value: (r) => esc(r.props.version) }] });
  }
  stamp('wsl', d.collected_at);
}

/** Рендер панели «Диагностика». */
async function loadDiagnostics(force) {
  const d = force ? await infraRequest('/diagnostics/run', { method: 'POST' }) : await infraRequest('/diagnostics');
  const el = body('diagnostics');
  el.innerHTML = `<div class="d-flex flex-wrap gap-2 mb-2 small">${statusBadge(d.status)}<span class="text-muted">Проверено: ${fmtTime(d.checked_at)}</span><span>Результатов: ${d.findings.length}</span></div><div data-role="tbl"></div>`;
  mountTable(el.querySelector('[data-role="tbl"]'), {
    status: d.status === 'error' ? 'error' : 'ok', rows: d.findings, emptyText: 'Нарушений не обнаружено по доступным данным.',
    search: (f) => `${f.rule_code} ${f.title} ${f.affected.join(' ')}`,
    columns: [
      { label: 'Важность', value: (f) => severityBadge(f.severity), sort: (f) => f.severity },
      { label: 'Код', value: (f) => esc(f.rule_code), sort: (f) => f.rule_code },
      { label: 'Проблема', value: (f) => `<b>${esc(f.title)}</b><div class="small text-muted">${esc(f.description)}</div>` },
      { label: 'Объекты', value: (f) => list(f.affected) },
      { label: 'Источник', value: (f) => esc(f.source) },
    ],
    detail: (f) => `<div><b>Факты:</b></div><pre class="small">${esc(JSON.stringify(f.facts, null, 2))}</pre><div><b>Рекомендации:</b> ${list(f.recommendations)}</div><div class="text-muted">Время проверки: ${fmtTime(f.checked_at)}</div>`,
  });
  stamp('diagnostics', d.checked_at);
}

/** Рендер панели «История изменений». */
async function loadHistory() {
  const [snaps, fh] = await Promise.all([infraRequest('/snapshots', { params: { limit: 50 } }), infraRequest('/history/findings', { params: { limit: 100 } })]);
  const el = body('history');
  const opts = snaps.items.map((s) => `<option value="${esc(s.id)}">${fmtTime(s.finished_at)} — ${esc(s.status)}</option>`).join('');
  el.innerHTML = `<div class="d-flex flex-wrap gap-2 align-items-center mb-2">
      <button class="btn btn-sm btn-primary rounded-pill" data-act="snap">Создать снимок</button>
      <button class="btn btn-sm btn-outline-secondary rounded-pill" data-act="prune">Очистить старую историю</button>
      <select class="form-select form-select-sm w-auto" data-role="base">${opts}</select><span>→</span>
      <select class="form-select form-select-sm w-auto" data-role="target">${opts}</select>
      <button class="btn btn-sm btn-outline-info rounded-pill" data-act="cmp" ${snaps.items.length < 2 ? 'disabled' : ''}>Сравнить</button></div>
    <div data-role="diff" class="mb-3"></div>
    <h6 class="small fw-bold">Снимки</h6><div data-role="snaps"></div>
    <h6 class="small fw-bold mt-3">История диагностических предупреждений</h6><div data-role="fh"></div>`;
  const tsel = el.querySelector('[data-role="target"]');
  const bsel = el.querySelector('[data-role="base"]');
  if (snaps.items.length > 1) bsel.selectedIndex = 1;  // базовый — предыдущий, цель — самый новый
  tsel.selectedIndex = 0;
  mountTable(el.querySelector('[data-role="snaps"]'), {
    status: 'ok', rows: snaps.items, emptyText: 'Снимков пока нет.',
    columns: [{ label: 'Время', value: (s) => fmtTime(s.finished_at), sort: (s) => s.finished_at }, { label: 'Статус', value: (s) => statusBadge(s.status === 'ok' ? 'ok' : s.status === 'partial' ? 'partial' : 'error') },
      { label: 'Объектов', value: (s) => s.objects_count }, { label: 'Диагностик', value: (s) => s.findings_count },
      { label: 'Источники', value: (s) => Object.entries(s.sources).map(([k, v]) => `${esc(k)}: ${esc(v)}`).join(', ') }],
    detail: (s) => `<div data-snap="${esc(s.id)}">Загрузка исходных данных...</div>`,
  });
  el.querySelector('[data-role="snaps"]').addEventListener('click', async (e) => {
    const tr = e.target.closest('tr[data-row]');
    if (!tr) return;
    const sid = snaps.items[Number(tr.dataset.row)].id;
    const holder = el.querySelector(`[data-snap="${sid}"]`);
    if (holder && holder.dataset.done !== '1') {
      try { const full = await infraRequest(`/snapshots/${sid}`); holder.dataset.done = '1'; holder.innerHTML = rawDetails(full.data, `снимок ${sid}`); } catch (err) { holder.innerHTML = failure(err); }
    }
  });
  mountTable(el.querySelector('[data-role="fh"]'), {
    status: 'ok', rows: fh.items, emptyText: 'Предупреждений в сохранённых снимках нет.',
    columns: [{ label: 'Время', value: (f) => fmtTime(f.checked_at), sort: (f) => f.checked_at }, { label: 'Важность', value: (f) => severityBadge(f.severity) },
      { label: 'Код', value: (f) => esc(f.rule_code) }, { label: 'Проблема', value: (f) => esc(f.title) }, { label: 'Объекты', value: (f) => list(f.affected) }],
  });
  el.onclick = async (e) => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (!act) return;
    try {
      if (act === 'snap') { await infraRequest('/snapshots', { method: 'POST' }); await loadHistory(); }
      if (act === 'prune') { const r = await infraRequest('/history/prune', { method: 'POST' }); await loadHistory(); alert(`Удалено снимков: ${r.removed}`); }
      if (act === 'cmp') renderDiff(el.querySelector('[data-role="diff"]'), await infraRequest('/snapshots/compare', { params: { base: bsel.value, target: tsel.value } }));
    } catch (err) { el.querySelector('[data-role="diff"]').innerHTML = failure(err); }
  };
  stamp('history', new Date().toISOString());
}

/**
 * Рендерит результат сравнения снимков.
 * @param {HTMLElement} box - Контейнер.
 * @param {Object} diff - Ответ /snapshots/compare.
 */
function renderDiff(box, diff) {
  const skipped = Object.entries(diff.skipped || {});
  box.innerHTML = `${skipped.length ? `<div class="alert alert-warning py-1 px-2 small">Неполные данные — added/removed не вычислялись:<ul class="mb-0">${skipped.map(([k, v]) => `<li>${esc(k)}: ${esc(v)}</li>`).join('')}</ul></div>` : ''}
    <div class="small mb-1">${Object.entries(diff.summary).map(([k, v]) => `<span class="badge bg-body-secondary border text-body me-1">${esc(k)}: ${v}</span>`).join('') || 'Изменений нет.'}</div><div data-role="chg"></div>
    <div class="small">Новых предупреждений: ${diff.findings.new.length}, устранённых: ${diff.findings.resolved.length}</div>`;
  if (diff.changes.length) {
    mountTable(box.querySelector('[data-role="chg"]'), { status: 'ok', rows: diff.changes, emptyText: '',
      columns: [{ label: 'Тип', value: (c) => esc(c.change_type), sort: (c) => c.change_type }, { label: 'Объект', value: (c) => esc(c.kind), sort: (c) => c.kind },
        { label: 'Имя', value: (c) => esc(c.name) }, { label: 'Детали', value: (c) => `<code class="small">${esc(JSON.stringify(c.details))}</code>` }] });
  }
}

const LOADERS = { overview: loadOverview, adapters: loadAdapters, switches: loadSwitches, 'ip-config': loadIpConfig, nat: loadNat, wsl: loadWsl, diagnostics: loadDiagnostics, history: loadHistory };

/**
 * Загружает панель; повторный запрос к уже выполняющейся панели игнорируется.
 * @param {string} name - Короткое имя панели (overview, adapters, ...).
 * @param {boolean} [force=false] - Запустить новый сбор вместо кэша.
 */
export async function loadInfraPanel(name, force = false) {
  const loader = LOADERS[name];
  if (!loader || inFlight.has(name)) return;
  inFlight.set(name, true);
  if (force || !body(name)?.dataset.loaded) setState(name, loading);
  try {
    await loader(force);
    body(name).dataset.loaded = '1';
  } catch (e) {
    console.error('[NetworkInfra] panel', name, e);
    setState(name, failure(e));
  } finally {
    inFlight.delete(name);
  }
}

/**
 * Подключает кнопки «Обновить» панелей (однократно).
 */
export function initInfraPanels() {
  document.querySelectorAll('[data-infra-refresh]').forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', () => loadInfraPanel(btn.dataset.infraRefresh, true));
  });
}
